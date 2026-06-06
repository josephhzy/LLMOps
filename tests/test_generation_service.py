"""Generation service tests."""

import pytest

from app.services.generation_service import GenerationService


@pytest.fixture
def gen_service():
    return GenerationService()


@pytest.fixture
def sample_prompt():
    return (
        'You are a secure internal assistant.\n'
        'Answer only from the provided evidence.\n\n'
        'Question:\n'
        'What is the incident response procedure?\n\n'
        'Evidence:\n'
        '[1] Incident Response SOP\n'
        'The first step in incident response is to triage the event and classify its severity level from P1 to P4.\n\n'
        '[2] Incident Response SOP\n'
        'After triage, the analyst must notify the duty officer within 15 minutes for P1 incidents.\n\n'
        'Produce a concise grounded answer with direct support from the evidence.'
    )


@pytest.mark.asyncio
async def test_template_backend_returns_answer(gen_service, sample_prompt):
    result = await gen_service.generate(sample_prompt, 'text_qa')
    assert result.text
    assert len(result.text) > 10


@pytest.mark.asyncio
async def test_template_backend_includes_evidence(gen_service, sample_prompt):
    result = await gen_service.generate(sample_prompt, 'text_qa')
    # Should reference evidence content
    assert 'triage' in result.text.lower() or 'incident' in result.text.lower()


@pytest.mark.asyncio
async def test_template_backend_includes_citations(gen_service, sample_prompt):
    result = await gen_service.generate(sample_prompt, 'text_qa')
    # Template backend adds citation markers
    assert '[1]' in result.text or '[2]' in result.text


@pytest.mark.asyncio
async def test_template_backend_token_counts(gen_service, sample_prompt):
    result = await gen_service.generate(sample_prompt, 'text_qa')
    assert result.tokens_in > 0
    assert result.tokens_out > 0


@pytest.mark.asyncio
async def test_template_backend_model_version(gen_service, sample_prompt):
    result = await gen_service.generate(sample_prompt, 'text_qa')
    assert 'template' in result.model_version


@pytest.mark.asyncio
async def test_generate_empty_evidence():
    service = GenerationService()
    prompt = (
        'You are a secure internal assistant.\n\n'
        'Question:\n'
        'What is quantum computing?\n\n'
        'Evidence:\n\n'
        'Produce a concise grounded answer.'
    )
    result = await service.generate(prompt, 'text_qa')
    assert 'do not have enough' in result.text.lower()
