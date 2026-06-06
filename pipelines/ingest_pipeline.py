"""Document ingestion pipeline.

Loads markdown documents with YAML frontmatter, chunks them with overlap,
generates embeddings, and upserts into ChromaDB. Tracks corpus versions
and document lifecycle via CorpusService.

Run: python -m pipelines.ingest_pipeline
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import yaml

from app.core.config import settings
from app.services.corpus_service import CorpusService
from app.services.embedding_service import EmbeddingService
from app.services.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body from markdown.

    Returns (metadata_dict, body_text). If no frontmatter found,
    returns empty dict and original text.
    """
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', text, re.DOTALL)
    if not match:
        return {}, text
    try:
        metadata = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        metadata = {}
    return metadata, match.group(2)


def chunk_document(
    text: str,
    chunk_size: int = 500,
    overlap: int = 100,
    section_header: str = '',
) -> list[str]:
    """Split text into overlapping chunks at paragraph boundaries.

    Strategy:
    1. Split on double newlines (paragraph-aware)
    2. Merge consecutive small paragraphs up to chunk_size characters
    3. Overlap by including text from the previous chunk boundary
    4. Prepend section context to each chunk for better retrieval
    """
    paragraphs = [p.strip() for p in re.split(r'\n\n+', text) if p.strip()]
    if not paragraphs:
        return []

    chunks = []
    current_chunk = ''
    current_header = section_header

    for para in paragraphs:
        # Track section headers for context
        if para.startswith('#'):
            current_header = para.lstrip('#').strip()

        if len(current_chunk) + len(para) + 2 > chunk_size and current_chunk:
            # Emit current chunk with section context
            chunk_text = f'[{current_header}] {current_chunk}' if current_header else current_chunk
            chunks.append(chunk_text.strip())
            # Start new chunk with overlap from end of previous
            if overlap > 0 and len(current_chunk) > overlap:
                current_chunk = current_chunk[-overlap:] + '\n\n' + para
            else:
                current_chunk = para
        else:
            current_chunk = f'{current_chunk}\n\n{para}' if current_chunk else para

    # Emit final chunk
    if current_chunk.strip():
        chunk_text = f'[{current_header}] {current_chunk}' if current_header else current_chunk
        chunks.append(chunk_text.strip())

    return chunks


def run_ingest(source_dir: str | None = None, output_dir: str | None = None) -> dict:
    """Main ingestion entrypoint.

    1. Glob all .md files in source_dir
    2. For each file: parse frontmatter, chunk, generate embeddings
    3. Upsert all chunks into ChromaDB with metadata
    4. Track document registration and corpus version via CorpusService
    """
    source_dir = source_dir or settings.sample_data_dir
    source_path = Path(source_dir)

    if not source_path.exists():
        logger.error('Source directory not found: %s', source_dir)
        return {'status': 'error', 'error': f'Source directory not found: {source_dir}'}

    md_files = sorted(source_path.glob('*.md'))
    if not md_files:
        logger.warning('No markdown files found in %s', source_dir)
        return {'status': 'empty', 'source_dir': source_dir}

    embedder = EmbeddingService()
    store = ChromaVectorStore()
    corpus = CorpusService(store=store)

    run_id = corpus.start_ingestion_run(source_dir)
    logger.info('Starting ingestion run %s from %s (%d files)', run_id, source_dir, len(md_files))

    all_ids = []
    all_embeddings = []
    all_documents = []
    all_metadatas = []
    errors = []
    docs_processed = 0

    for md_file in md_files:
        try:
            text = md_file.read_text(encoding='utf-8')
            metadata, body = parse_frontmatter(text)

            doc_id = metadata.get('doc_id', md_file.stem)
            title = metadata.get('title', md_file.stem)
            classification = metadata.get('classification', 'internal')

            # Register document in corpus governance
            corpus.register_document(doc_id, title, classification, str(md_file.name))

            # Chunk the document
            chunks = chunk_document(body, chunk_size=500, overlap=100, section_header=title)

            for i, chunk_text in enumerate(chunks):
                chunk_id = f'{doc_id}-c{i:03d}'
                all_ids.append(chunk_id)
                all_documents.append(chunk_text)
                all_metadatas.append(
                    {
                        'doc_id': doc_id,
                        'title': title,
                        'classification': classification,
                        'chunk_index': i,
                        'source_file': md_file.name,
                        'document_status': 'active',
                        'ingestion_run_id': run_id,
                        'corpus_version': corpus.current_version,
                    }
                )

            docs_processed += 1
            logger.info('Chunked %s: %d chunks', md_file.name, len(chunks))

        except Exception as e:
            errors.append(f'{md_file.name}: {e}')
            logger.error('Failed to process %s: %s', md_file.name, e)

    # Generate embeddings in batch
    if all_documents:
        logger.info('Generating embeddings for %d chunks...', len(all_documents))
        all_embeddings = embedder.embed_texts(all_documents)

        # Upsert into vector store
        store.upsert(
            ids=all_ids,
            embeddings=all_embeddings,
            documents=all_documents,
            metadatas=all_metadatas,
        )

    corpus.complete_ingestion_run(run_id, docs_processed, len(all_ids), errors)

    result = {
        'status': 'success',
        'ingestion_run_id': run_id,
        'corpus_version': corpus.current_version,
        'documents_processed': docs_processed,
        'chunks_created': len(all_ids),
        'errors': errors,
        'collection_name': settings.chroma_collection_name,
    }

    logger.info('Ingestion complete: %s', json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
    result = run_ingest()
    print(json.dumps(result, indent=2))
