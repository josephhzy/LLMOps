from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    # Capped at 5000 to limit abuse surface (injection risk, LLM token cost)
    question: str = Field(..., min_length=3, max_length=5000)
    top_k: int = Field(default=5, ge=1, le=20)
    enable_citations: bool = True
    sources: list[str] | None = None


class Citation(BaseModel):
    doc_id: str
    chunk_id: str
    title: str
    score: float
    snippet: str = ''
    relevance: str = 'medium'


class QueryResponse(BaseModel):
    answer: str
    confidence: float
    citations: list[Citation]
    trace_id: str
    policy_action: str
