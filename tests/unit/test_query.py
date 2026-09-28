"""Tests for query handling."""

from unittest.mock import MagicMock, patch

from src.rag.query import generate_answer, retrieve_chunks


@patch('src.rag.query.register_vector')
@patch('src.rag.query.psycopg2.connect')
def test_retrieve_chunks(mock_connect, mock_register_vector):
    """Test retrieving chunks from database."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_connect.return_value = mock_conn

    mock_cursor.fetchall.return_value = [
        ("doc1.pdf", 1, 0, "chunk text 1", 0, 100, {"source": "doc1.pdf"}, 0.1),
        ("doc2.pdf", 2, 1, "chunk text 2", 100, 200, {"source": "doc2.pdf"}, 0.2),
    ]

    embedding = [0.1] * 1024
    chunks = retrieve_chunks(embedding, 5, "localhost", 5432, "testdb", "user", "pass")

    assert len(chunks) == 2
    assert chunks[0]["document_id"] == "doc1.pdf"
    assert chunks[0]["chunk_text"] == "chunk text 1"
    assert chunks[1]["document_id"] == "doc2.pdf"

    mock_conn.close.assert_called_once()


@patch('src.rag.query.boto3.client')
def test_generate_answer(mock_boto_client):
    """Test generating answer with LLM."""
    mock_bedrock = MagicMock()
    mock_boto_client.return_value = mock_bedrock

    mock_body = MagicMock()
    mock_body.read.return_value = b'''{
        "content": [{"text": "The answer is 42 [1]."}],
        "usage": {"input_tokens": 100, "output_tokens": 50}
    }'''
    mock_response = {"body": mock_body}
    mock_bedrock.invoke_model.return_value = mock_response

    context_chunks = [
        {
            "document_id": "test.pdf",
            "page_number": 1,
            "chunk_index": 0,
            "chunk_text": "The answer is 42.",
            "start_offset": 0,
            "end_offset": 17,
            "metadata": {},
            "distance": 0.1,
        }
    ]

    result = generate_answer(
        "What is the answer?",
        context_chunks,
        "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "us-east-1"
    )

    assert "answer" in result
    assert result["answer"] == "The answer is 42 [1]."
    assert len(result["citations"]) == 1
    assert result["citations"][0]["number"] == 1
    assert result["citations"][0]["source"] == "test.pdf"
    assert result["token_usage"]["input_tokens"] == 100
    assert result["token_usage"]["output_tokens"] == 50


@patch('src.rag.ingest.embed_text')
@patch('src.rag.query.register_vector')
@patch('src.rag.query.psycopg2.connect')
def test_query_rag_no_chunks(mock_connect, mock_register_vector, mock_embed_text):
    """Test query when no chunks are retrieved."""
    from src.rag.query import query_rag

    mock_embed_text.return_value = [0.1, 0.2, 0.3]

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_connect.return_value = mock_conn
    mock_cursor.fetchall.return_value = []

    config = {
        "aws_region": "us-east-1",
        "db_host": "localhost",
        "db_port": 5432,
        "db_name": "testdb",
        "embedding_model_id": "amazon.titan-embed-text-v2:0",
        "llm_model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "top_k": 5,
    }

    db_credentials = {"username": "user", "password": "pass"}

    result = query_rag("test question", config, db_credentials)

    assert result["answer"] == "I don't know based on the provided documents."
    assert result["citations"] == []
    assert result["retrieved_chunks"] == 0
