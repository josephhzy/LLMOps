"""Corpus governance service — document lifecycle management.

Tracks document status (active, superseded, revoked), corpus versions,
and ingestion runs. Ensures revoked documents are excluded from retrieval.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.audit import audit
from app.core.logging import get_logger
from app.domain.models import DocumentStatus
from app.services.vector_store import ChromaVectorStore

logger = get_logger(__name__)

CORPUS_STATE_PATH = Path('data/corpus_state.json')


class CorpusService:
    """Document lifecycle and corpus version management."""

    def __init__(self, store: ChromaVectorStore | None = None) -> None:
        self.store = store or ChromaVectorStore()
        self._state = self._load_state()

    def _load_state(self) -> dict:
        if CORPUS_STATE_PATH.exists():
            return json.loads(CORPUS_STATE_PATH.read_text())
        return {
            'current_version': None,
            'documents': {},
            'ingestion_runs': [],
        }

    def _save_state(self) -> None:
        CORPUS_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CORPUS_STATE_PATH.write_text(json.dumps(self._state, indent=2))

    @property
    def current_version(self) -> str | None:
        """Public accessor for current corpus version."""
        return self._state['current_version']

    def register_document(self, doc_id: str, title: str, classification: str, source_file: str) -> None:
        """Register a document in the corpus."""
        self._state['documents'][doc_id] = {
            'doc_id': doc_id,
            'title': title,
            'classification': classification,
            'source_file': source_file,
            'status': DocumentStatus.ACTIVE,
            'registered_at': datetime.now(UTC).isoformat(),
            'revoked_at': None,
            'revoked_reason': None,
            'superseded_by': None,
        }
        self._save_state()

    def revoke_document(self, doc_id: str, reason: str) -> bool:
        """Revoke a document. Updates both state and vector store metadata."""
        doc = self._state['documents'].get(doc_id)
        if not doc:
            logger.warning('revoke_not_found', doc_id=doc_id)
            return False

        doc['status'] = DocumentStatus.REVOKED
        doc['revoked_at'] = datetime.now(UTC).isoformat()
        doc['revoked_reason'] = reason
        self._save_state()

        # Update vector store via public API
        self._update_chunk_status(doc_id, DocumentStatus.REVOKED)
        audit.log_event(
            'corpus',
            'system',
            'revoke_document',
            target=doc_id,
            outcome='success',
            details={'reason': reason},
        )
        logger.info('document_revoked', doc_id=doc_id, reason=reason)
        return True

    def supersede_document(self, old_doc_id: str, new_doc_id: str) -> bool:
        """Mark a document as superseded by a newer version."""
        old_doc = self._state['documents'].get(old_doc_id)
        if not old_doc:
            return False

        old_doc['status'] = DocumentStatus.SUPERSEDED
        old_doc['superseded_by'] = new_doc_id
        self._save_state()

        self._update_chunk_status(old_doc_id, DocumentStatus.SUPERSEDED)
        logger.info('document_superseded', old=old_doc_id, new=new_doc_id)
        return True

    def _update_chunk_status(self, doc_id: str, status: str) -> None:
        """Update document_status in vector store via public update_metadata API."""
        try:
            # Use the public API to find and update chunks
            # ChromaVectorStore.update_metadata handles the collection access
            collection = self.store._get_collection()
            results = collection.get(where={'doc_id': doc_id}, include=['metadatas'])
            if results['ids']:
                updated_metadatas = [{**meta, 'document_status': status} for meta in results['metadatas']]
                self.store.update_metadata(ids=results['ids'], metadatas=updated_metadatas)
        except Exception as e:
            logger.error('chunk_status_update_failed', doc_id=doc_id, error=str(e))

    def get_document(self, doc_id: str) -> dict | None:
        """Get document metadata."""
        return self._state['documents'].get(doc_id)

    def list_documents(self, status_filter: str | None = None) -> list[dict]:
        """List all documents, optionally filtered by status."""
        docs = list(self._state['documents'].values())
        if status_filter:
            docs = [d for d in docs if d['status'] == status_filter]
        return docs

    def get_corpus_status(self) -> dict:
        """Get corpus-level statistics."""
        docs = self._state['documents']
        status_counts: dict[str, int] = {}
        for doc in docs.values():
            s = doc['status']
            status_counts[s] = status_counts.get(s, 0) + 1

        return {
            'current_version': self._state['current_version'],
            'total_documents': len(docs),
            'status_counts': status_counts,
            'total_chunks': self.store.count(),
            'ingestion_runs': len(self._state['ingestion_runs']),
        }

    def start_ingestion_run(self, source_dir: str) -> str:
        """Start a new ingestion run. Returns run ID."""
        run_id = f'run-{uuid.uuid4().hex[:12]}'
        corpus_version = f'v{len(self._state["ingestion_runs"]) + 1}'

        run: dict[str, Any] = {
            'run_id': run_id,
            'source_dir': source_dir,
            'corpus_version': corpus_version,
            'started_at': datetime.now(UTC).isoformat(),
            'completed_at': None,
            'documents_processed': 0,
            'chunks_created': 0,
            'errors': [],
        }
        self._state['ingestion_runs'].append(run)
        self._state['current_version'] = corpus_version
        self._save_state()
        return run_id

    def complete_ingestion_run(self, run_id: str, docs_processed: int, chunks_created: int, errors: list[str]) -> None:
        """Complete an ingestion run with stats."""
        for run in self._state['ingestion_runs']:
            if run['run_id'] == run_id:
                run['completed_at'] = datetime.now(UTC).isoformat()
                run['documents_processed'] = docs_processed
                run['chunks_created'] = chunks_created
                run['errors'] = errors
                break
        self._save_state()
