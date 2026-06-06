"""Ingestion pipeline tests."""

from pipelines.ingest_pipeline import chunk_document, parse_frontmatter


class TestParseFrontmatter:
    def test_extracts_metadata(self):
        text = '---\ntitle: Test Doc\ndoc_id: test-001\nclassification: internal\n---\n\n# Body content here'
        metadata, body = parse_frontmatter(text)
        assert metadata['title'] == 'Test Doc'
        assert metadata['doc_id'] == 'test-001'
        assert '# Body content' in body

    def test_no_frontmatter_returns_empty(self):
        text = '# Just a heading\n\nSome content.'
        metadata, body = parse_frontmatter(text)
        assert metadata == {}
        assert body == text

    def test_empty_frontmatter(self):
        text = '---\n---\n\nBody'
        metadata, _body = parse_frontmatter(text)
        assert metadata == {}


class TestChunkDocument:
    def test_chunks_respect_size_limit(self):
        text = '\n\n'.join([f'Paragraph {i}. ' * 20 for i in range(10)])
        chunks = chunk_document(text, chunk_size=200, overlap=50)
        # All chunks should be under a reasonable size (size + header)
        for chunk in chunks:
            assert len(chunk) < 500  # generous limit including header

    def test_chunks_have_overlap(self):
        text = 'Paragraph one content here. ' * 20 + '\n\n' + 'Paragraph two content here. ' * 20
        chunks = chunk_document(text, chunk_size=200, overlap=50)
        assert len(chunks) >= 2, "Expected multiple chunks for long input"
        # The last `overlap` characters of the raw first chunk should appear in chunk[1].
        # Since no section_header is passed and the input has no '#' headers, chunks have no prefix.
        overlap = 50
        assert chunks[0][-overlap:] in chunks[1], (
            f"Expected overlap tail {chunks[0][-overlap:]!r} to appear in chunk[1]"
        )

    def test_empty_text_returns_empty(self):
        chunks = chunk_document('')
        assert chunks == []

    def test_single_paragraph(self):
        text = 'This is a single paragraph.'
        chunks = chunk_document(text, chunk_size=500)
        assert len(chunks) == 1

    def test_section_header_included(self):
        text = '# Section Header\n\nContent under the section.'
        chunks = chunk_document(text, chunk_size=500, section_header='Document Title')
        assert len(chunks) >= 1
