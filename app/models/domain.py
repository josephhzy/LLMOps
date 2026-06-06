from dataclasses import dataclass
from typing import Any


@dataclass
class RetrievedChunk:
    doc_id: str
    chunk_id: str
    title: str
    content: str
    score: float
    metadata: dict[str, Any]


@dataclass
class GeneratedAnswer:
    text: str
    model_version: str
    tokens_in: int
    tokens_out: int
