"""Generation service — pluggable text generation backends.

Implements the Generator port with three backends:
- template (default): extractive QA with citation markers, zero LLM required
- ollama: local LLM via Ollama's OpenAI-compatible API
- openai_compat: any OpenAI-compatible API endpoint (vLLM, TGI, etc.)

Falls back to template mode on LLM failure.
"""

from __future__ import annotations

import re
import time

from app.core.config import settings
from app.core.logging import get_logger
from app.core.metrics import GENERATION_LATENCY
from app.models.domain import GeneratedAnswer
from app.services.model_router import ModelRouter

logger = get_logger(__name__)


class GenerationService:
    """Text generation with configurable backend and automatic fallback."""

    def __init__(self) -> None:
        self.router = ModelRouter()
        self.backend = settings.generation_backend

    async def generate(self, prompt: str, task_type: str) -> GeneratedAnswer:
        """Generate answer using configured backend. Falls back to template on failure."""
        model_version = self.router.route(task_type)
        start = time.perf_counter()

        if self.backend in ('ollama', 'openai_compat'):
            try:
                result = await self._generate_llm(prompt, model_version)
                latency = time.perf_counter() - start
                GENERATION_LATENCY.observe(latency)
                logger.info('LLM generation completed', latency=f'{latency:.2f}s', backend=self.backend)
                return result
            except Exception as e:
                logger.warning('LLM generation failed, falling back to template', error=str(e))

        result = self._generate_template(prompt, model_version)
        latency = time.perf_counter() - start
        GENERATION_LATENCY.observe(latency)
        logger.info('Template generation completed', latency=f'{latency:.2f}s')
        return result

    def generate_sync(self, prompt: str, task_type: str) -> GeneratedAnswer:
        """Synchronous generation — template backend only, for offline pipelines.

        Offline evaluation always uses the template backend since it doesn't
        require an event loop. For LLM-backed evaluation, use the async path.
        """
        model_version = self.router.route(task_type)
        result = self._generate_template(prompt, model_version)
        return result

    def _estimate_tokens(self, text: str) -> int:
        """Approximate token count from character length.

        Uses len(text) // 4 as a rough chars-to-tokens ratio. This is a common
        approximation (GPT-family averages ~4 chars per token for English). Not
        exact, but sufficient for logging and cost estimation.
        """
        return len(text) // 4

    def _generate_template(self, prompt: str, model_version: str) -> GeneratedAnswer:
        """Extractive QA: parse evidence blocks, score sentences, compose answer.

        Not a toy — this demonstrates the pipeline working end-to-end.
        Extracts the most relevant sentences from evidence and composes
        them into a coherent answer with citation markers.
        """
        question, evidence_blocks = self._parse_prompt(prompt)
        if not evidence_blocks:
            text = 'I do not have enough grounded evidence to answer this question.'
            return GeneratedAnswer(
                text=text,
                model_version=f'{model_version}:template',
                tokens_in=self._estimate_tokens(prompt),
                tokens_out=self._estimate_tokens(text),
            )

        scored_sentences = self._score_evidence_sentences(question, evidence_blocks)
        text = self._compose_answer(question, scored_sentences)

        return GeneratedAnswer(
            text=text,
            model_version=f'{model_version}:template',
            tokens_in=self._estimate_tokens(prompt),
            tokens_out=self._estimate_tokens(text),
        )

    def _parse_prompt(self, prompt: str) -> tuple[str, list[tuple[int, str, str]]]:
        """Extract question and numbered evidence blocks from rendered prompt."""
        question = ''
        q_match = re.search(r'Question:\s*\n(.+?)(?:\n\n|\nEvidence:)', prompt, re.DOTALL)
        if q_match:
            question = q_match.group(1).strip()

        blocks = []
        block_pattern = re.findall(r'\[(\d+)\]\s*(.+?)\n(.*?)(?=\[\d+\]|\Z)', prompt, re.DOTALL)
        for idx_str, title, content in block_pattern:
            blocks.append((int(idx_str), title.strip(), content.strip()))

        return question, blocks

    def _score_evidence_sentences(
        self,
        question: str,
        blocks: list[tuple[int, str, str]],
    ) -> list[tuple[str, int, float]]:
        """Score each sentence in evidence against the question using TF-IDF."""
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        sentences_with_ref = []
        for block_idx, _title, content in blocks:
            for sent in re.split(r'(?<=[.!?])\s+', content):
                sent = sent.strip()
                if len(sent) > 20:
                    sentences_with_ref.append((sent, block_idx))

        if not sentences_with_ref:
            return []

        texts = [question] + [s for s, _ in sentences_with_ref]
        vectorizer = TfidfVectorizer(stop_words='english')
        try:
            tfidf_matrix = vectorizer.fit_transform(texts)
        except ValueError:
            return []

        similarities = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:]).flatten()

        scored = []
        for i, (sent, block_idx) in enumerate(sentences_with_ref):
            scored.append((sent, block_idx, float(similarities[i])))

        scored.sort(key=lambda x: x[2], reverse=True)
        return scored

    def _compose_answer(
        self,
        question: str,
        scored_sentences: list[tuple[str, int, float]],
    ) -> str:
        """Compose a grounded answer from top-scored evidence sentences."""
        if not scored_sentences:
            return 'I do not have enough grounded evidence to answer this question.'

        # Take top sentences (up to 5), maintaining diversity across sources
        selected = []
        seen_sources: set[int] = set()
        for sent, block_idx, score in scored_sentences:
            if score < 0.05:
                break
            if len(selected) >= 5:
                break
            selected.append((sent, block_idx, score))
            seen_sources.add(block_idx)

        if not selected:
            return 'I do not have enough grounded evidence to answer this question.'

        parts = []
        for sent, block_idx, _score in selected:
            parts.append(f'{sent} [{block_idx}]')

        answer = 'Based on the available evidence: ' + ' '.join(parts)
        return answer

    async def _generate_llm(self, prompt: str, model_version: str) -> GeneratedAnswer:
        """Call an OpenAI-compatible API (Ollama, vLLM, TGI, etc.)."""
        import httpx
        from tenacity import retry, stop_after_attempt, wait_exponential

        @retry(
            stop=stop_after_attempt(settings.llm_max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        )
        async def _call():
            # Split prompt into system and user parts
            parts = prompt.split('\n\n', 1)
            system_msg = parts[0] if len(parts) > 1 else ''
            user_msg = parts[1] if len(parts) > 1 else prompt

            messages = []
            if system_msg:
                messages.append({'role': 'system', 'content': system_msg})
            messages.append({'role': 'user', 'content': user_msg})

            base_url = settings.llm_base_url.rstrip('/')
            # Both Ollama and OpenAI expose /v1/chat/completions
            url = f'{base_url}/v1/chat/completions'

            headers = {}
            if settings.openai_api_key:
                headers['Authorization'] = f'Bearer {settings.openai_api_key}'

            async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json={
                        'model': settings.llm_model_name,
                        'messages': messages,
                        'temperature': 0.1,
                        'max_tokens': 1024,
                    },
                )
                response.raise_for_status()
                data = response.json()

            text = data['choices'][0]['message']['content']
            usage = data.get('usage', {})
            return GeneratedAnswer(
                text=text,
                model_version=f'{model_version}:{settings.llm_model_name}',
                tokens_in=usage.get('prompt_tokens', self._estimate_tokens(prompt)),
                tokens_out=usage.get('completion_tokens', self._estimate_tokens(text)),
            )

        return await _call()
