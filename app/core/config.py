from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = 'LLM Ops'
    env: str = 'dev'
    log_level: str = 'INFO'

    # Model routing
    default_model: str = 'text-main'  # placeholder routing label — not a real model ID; only surfaced in GET /v1/admin/versions; ModelRouter hardcodes the same label independently

    # Version tracking
    prompt_version: str = 'grounded_answer:v1'
    retriever_version: str = 'hybrid:v1'
    policy_version: str = 'policy:v1'

    # Vector DB
    chroma_persist_dir: str = './chroma_data'
    chroma_collection_name: str = 'llm_ops_docs'

    # Embeddings
    embedding_model: str = 'all-MiniLM-L6-v2'
    embedding_device: str = 'cpu'

    # Generation backend
    generation_backend: str = 'template'  # template | ollama | openai_compat
    llm_base_url: str = 'https://api.openai.com'
    llm_model_name: str = 'gpt-4o-mini'
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 2
    openai_api_key: str = ''

    # Reranker
    reranker_backend: str = 'tfidf'  # tfidf | cross_encoder
    cross_encoder_model: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'

    # Verification
    verification_backend: str = (
        'tfidf'  # placeholder — not yet read by any service; VerificationService unconditionally uses TF-IDF
    )
    grounding_threshold: float = 0.3

    # NLI shadow-mode — runs NLI verifier alongside TF-IDF and logs both
    # scores to the audit event. TF-IDF remains the policy gate. Disabled
    # by default because the model is ~180MB and adds a cross-encoder
    # forward pass per claim/chunk pair.
    nli_shadow_enabled: bool = False
    nli_model_name: str = 'cross-encoder/nli-deberta-v3-base'
    nli_entailment_threshold: float = 0.70

    # Data
    sample_data_dir: str = './data/sample_docs'

    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    @field_validator('grounding_threshold')
    @classmethod
    def grounding_threshold_must_be_between_0_and_1(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError(f'grounding_threshold must be between 0 and 1, got {v}')
        return v

    @field_validator('generation_backend')
    @classmethod
    def generation_backend_must_be_valid(cls, v: str) -> str:
        allowed = ('template', 'ollama', 'openai_compat')
        if v not in allowed:
            raise ValueError(f'generation_backend must be one of {allowed}, got {v!r}')
        return v

    @field_validator('reranker_backend')
    @classmethod
    def reranker_backend_must_be_valid(cls, v: str) -> str:
        allowed = ('tfidf', 'cross_encoder')
        if v not in allowed:
            raise ValueError(f'reranker_backend must be one of {allowed}, got {v!r}')
        return v


settings = Settings()
