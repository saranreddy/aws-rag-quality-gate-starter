"""Tests for multi-format document ingestion (.txt, .md, .pdf)."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.rag.ingest import extract_text_from_text_file, process_document


def test_extract_text_from_txt_file():
    """Test extracting text from a plain text file."""
    test_content = "This is a test document.\nIt has multiple lines.\nAnd some content."

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(test_content)
        temp_path = f.name

    try:
        pages = extract_text_from_text_file(temp_path)

        assert len(pages) == 1, "Text file should return 1 page"
        assert pages[0][0] == test_content, "Content should match"
        assert pages[0][1] == 1, "Page number should be 1"
    finally:
        Path(temp_path).unlink()


def test_extract_text_from_md_file():
    """Test extracting text from a Markdown file."""
    test_content = "# Header\n\nThis is **bold** text.\n\n- List item 1\n- List item 2"

    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(test_content)
        temp_path = f.name

    try:
        pages = extract_text_from_text_file(temp_path)

        assert len(pages) == 1
        assert pages[0][0] == test_content
        assert pages[0][1] == 1
    finally:
        Path(temp_path).unlink()


def test_extract_text_empty_file():
    """Test extracting text from an empty file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        temp_path = f.name

    try:
        pages = extract_text_from_text_file(temp_path)

        assert len(pages) == 1
        assert pages[0][0] == ""
        assert pages[0][1] == 1
    finally:
        Path(temp_path).unlink()


@patch('src.rag.ingest.embed_text')
@patch('src.rag.ingest.register_vector')
@patch('src.rag.ingest.psycopg2.connect')
@patch('src.rag.ingest.boto3.client')
def test_process_document_txt(mock_boto_client, mock_db_connect, mock_register_vector, mock_embed):
    """Test processing a .txt document."""

    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    def mock_download(bucket, key, local_path):
        with open(local_path, 'w') as f:
            f.write("Sample text content for testing.")

    mock_s3.download_file.side_effect = mock_download
    mock_embed.return_value = [0.1] * 1024

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_db_connect.return_value = mock_conn

    config = {
        "aws_region": "us-east-1",
        "db_host": "localhost",
        "db_port": 5432,
        "db_name": "testdb",
        "embedding_model_id": "amazon.titan-embed-text-v2:0",
        "chunk_size": 512,
        "chunk_overlap": 50,
    }

    db_credentials = {"username": "user", "password": "pass"}

    result = process_document("test-bucket", "test.txt", config, db_credentials)

    assert result["status"] == "success"
    assert result["total_chunks"] > 0
    assert result["document_id"] == "test.txt"


@patch('src.rag.ingest.embed_text')
@patch('src.rag.ingest.register_vector')
@patch('src.rag.ingest.psycopg2.connect')
@patch('src.rag.ingest.boto3.client')
def test_process_document_md(mock_boto_client, mock_db_connect, mock_register_vector, mock_embed):
    """Test processing a .md document."""

    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    def mock_download(bucket, key, local_path):
        with open(local_path, 'w') as f:
            f.write("# Markdown Header\n\nSome markdown content.")

    mock_s3.download_file.side_effect = mock_download
    mock_embed.return_value = [0.1] * 1024

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_db_connect.return_value = mock_conn

    config = {
        "aws_region": "us-east-1",
        "db_host": "localhost",
        "db_port": 5432,
        "db_name": "testdb",
        "embedding_model_id": "amazon.titan-embed-text-v2:0",
        "chunk_size": 512,
        "chunk_overlap": 50,
    }

    db_credentials = {"username": "user", "password": "pass"}

    result = process_document("test-bucket", "test.md", config, db_credentials)

    assert result["status"] == "success"
    assert result["document_id"] == "test.md"


@patch('src.rag.ingest.register_vector')
@patch('src.rag.ingest.psycopg2.connect')
@patch('src.rag.ingest.boto3.client')
def test_process_document_unsupported_format(mock_boto_client, mock_db_connect, mock_register_vector):
    """Test that unsupported file formats raise an error."""

    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    def mock_download(bucket, key, local_path):
        with open(local_path, 'w') as f:
            f.write("content")

    mock_s3.download_file.side_effect = mock_download

    config = {
        "aws_region": "us-east-1",
        "db_host": "localhost",
        "embedding_model_id": "amazon.titan-embed-text-v2:0",
    }

    db_credentials = {"username": "user", "password": "pass"}

    with pytest.raises(ValueError, match="Unsupported file type"):
        process_document("test-bucket", "test.docx", config, db_credentials)
