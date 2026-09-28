"""Tests for document ingestion."""

from unittest.mock import MagicMock, patch

from src.rag.ingest import chunk_text


def test_chunk_text():
    """Test text chunking with overlap."""
    text = "a" * 1000
    chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)

    assert len(chunks) > 0
    assert all(len(chunk[0]) <= 100 for chunk in chunks)

    chunks[0][0]
    assert chunks[0][1] == 0
    assert chunks[0][2] == 100


def test_chunk_text_short():
    """Test chunking text shorter than chunk size."""
    text = "short text"
    chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)

    assert len(chunks) == 1
    assert chunks[0][0] == text
    assert chunks[0][1] == 0
    assert chunks[0][2] == len(text)


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

    store_chunks(chunks, "localhost", 5432, "testdb", "user", "pass")

    assert mock_cursor.execute.called
    mock_conn.commit.assert_called_once()
    mock_conn.close.assert_called_once()
