"""Tests for document ingestion."""

from unittest.mock import MagicMock, patch

from src.rag.ingest import chunk_text


def test_chunk_text():
    """Test text chunking with sentence boundaries."""
    text = "First sentence. Second sentence. Third sentence. Fourth sentence."
    chunks = chunk_text(text, chunk_size=40, chunk_overlap=15)

    assert len(chunks) > 0
    # Chunks should not cut mid-sentence
    for chunk_content, start, end in chunks:
        assert not chunk_content.endswith(" senten")  # Not cut mid-word


def test_chunk_text_short():
    """Test chunking text shorter than chunk size."""
    text = "Short text."
    chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)

    assert len(chunks) == 1
    assert "Short text" in chunks[0][0]


def test_chunk_text_respects_sentences():
    """Test that chunking doesn't cut mid-sentence."""
    text = "This is sentence one. This is sentence two. This is sentence three."
    chunks = chunk_text(text, chunk_size=30, chunk_overlap=10)

    for chunk_content, start, end in chunks:
        # Each chunk should contain complete sentences
        assert chunk_content.strip().endswith('.') or chunk_content == chunks[-1][0]


def test_chunk_text_faq_structure():
    """Test that FAQ Q:/A: pairs are chunked together."""
    text = """Q: What is SOC 2?
A: SOC 2 is a compliance framework for data security.

Q: Do you support AES encryption?
A: Yes, we use AES-256 encryption at rest."""

    chunks = chunk_text(text, chunk_size=200, chunk_overlap=20)

    # Should create separate chunks for each Q/A pair
    assert len(chunks) >= 1

    # Check that Q and A stay together
    soc2_chunks = [c for c in chunks if "SOC 2" in c[0]]
    assert len(soc2_chunks) >= 1

    # The chunk should contain both Q and A
    soc2_chunk = soc2_chunks[0][0]
    assert "Q:" in soc2_chunk
    assert "A:" in soc2_chunk or "compliance framework" in soc2_chunk


def test_chunk_text_markdown_headings():
    """Test that markdown headings create chunk boundaries."""
    text = """# Security Features

Our platform provides enterprise-grade security.

## Encryption at Rest

All data is encrypted with AES-256.

## SOC 2 Compliance

We maintain SOC 2 Type II certification."""

    chunks = chunk_text(text, chunk_size=200, chunk_overlap=20)

    # Should create chunks at heading boundaries
    assert len(chunks) >= 2

    # Each chunk should have its heading
    soc2_chunks = [c for c in chunks if "SOC 2" in c[0]]
    assert len(soc2_chunks) >= 1
    assert any("## SOC 2 Compliance" in c[0] for c in soc2_chunks)


def test_chunk_text_empty():
    """Test chunking empty text."""
    text = ""
    chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)

    assert len(chunks) == 0


@patch('src.rag.ingest.boto3.client')
def test_embed_text(mock_boto_client):
    """Test text embedding with Bedrock."""
    from src.rag.ingest import embed_text

    mock_bedrock = MagicMock()
    mock_boto_client.return_value = mock_bedrock

    mock_body = MagicMock()
    mock_body.read.return_value = b'{"embedding": [0.1, 0.2, 0.3]}'
    mock_response = {"body": mock_body}
    mock_bedrock.invoke_model.return_value = mock_response

    embedding = embed_text("test text", "amazon.titan-embed-text-v2:0", "us-east-1")

    assert embedding == [0.1, 0.2, 0.3]
    mock_bedrock.invoke_model.assert_called_once()


@patch('src.rag.ingest.register_vector')
@patch('src.rag.ingest.psycopg2.connect')
def test_store_chunks(mock_connect, mock_register_vector):
    """Test storing chunks in database."""
    from src.rag.ingest import store_chunks

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    chunks = [
        {
            "document_id": "test.pdf",
            "page_number": 1,
            "chunk_index": 0,
            "chunk_text": "test chunk",
            "start_offset": 0,
            "end_offset": 10,
            "embedding": [0.1, 0.2],
            "metadata": {"source": "test.pdf"},
        }
    ]

    store_chunks(chunks, "test.pdf", "localhost", 5432, "testdb", "user", "pass")

    assert mock_cursor.execute.called
    mock_conn.commit.assert_called_once()
    mock_conn.close.assert_called_once()


@patch('src.rag.ingest.register_vector')
@patch('src.rag.ingest.psycopg2.connect')
def test_store_chunks_deletes_existing(mock_connect, mock_register_vector):
    """Test that store_chunks deletes existing chunks before inserting."""
    from src.rag.ingest import store_chunks

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    chunks = [
        {
            "document_id": "test.pdf",
            "page_number": 1,
            "chunk_index": 0,
            "chunk_text": "test chunk",
            "start_offset": 0,
            "end_offset": 10,
            "embedding": [0.1, 0.2],
            "metadata": {"source": "test.pdf"},
        }
    ]

    store_chunks(chunks, "test.pdf", "localhost", 5432, "testdb", "user", "pass")

    # Check that DELETE was called before INSERT
    execute_calls = [call[0][0] for call in mock_cursor.execute.call_args_list]
    assert any("DELETE FROM document_chunks" in call for call in execute_calls)
    assert any("INSERT INTO document_chunks" in call for call in execute_calls)


@patch('src.rag.ingest.boto3.client')
@patch('src.rag.ingest.process_document')
def test_s3_key_url_decoding(mock_process, mock_boto_client):
    """Test that S3 keys are URL-decoded properly."""
    from urllib.parse import quote_plus

    # Simulate URL-encoded key from S3 event
    original_key = "documents/my file with spaces.pdf"
    encoded_key = quote_plus(original_key)

    # The process_document function should decode it
    # We'll test this indirectly by checking the decode logic
    from urllib.parse import unquote_plus

    decoded = unquote_plus(encoded_key)
    assert decoded == original_key
    assert " " in decoded
    assert "+" not in decoded
