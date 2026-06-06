"""Citation service — converts retrieved chunks into API citation objects.

Includes content snippets and relevance tier for richer client display.
"""

from __future__ import annotations

from app.models.domain import RetrievedChunk

SNIPPET_MAX_LENGTH = 200


class CitationService:
    """Attach citation metadata to response."""

    def attach_citations(self, chunks: list[RetrievedChunk]) -> list[dict]:
        """Convert retrieved chunks into API citation objects."""
        return [
            {
                'doc_id': c.doc_id,
                'chunk_id': c.chunk_id,
                'title': c.title,
                'score': c.score,
                'snippet': c.content[:SNIPPET_MAX_LENGTH],
                'relevance': self._relevance_tier(c.score),
            }
            for c in chunks
        ]

    def _relevance_tier(self, score: float) -> str:
        if score >= 0.8:
            return 'high'
        if score >= 0.5:
            return 'medium'
        return 'low'
