"""Pytest configuration and fixtures."""

import pytest
from unittest.mock import MagicMock


@pytest.fixture
def mock_bedrock_client():
    """Mock Bedrock client for testing."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_s3_client():
    """Mock S3 client for testing."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_db_connection():
    """Mock database connection for testing."""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cursor
    return conn


@pytest.fixture
def sample_config():
    """Sample configuration for testing."""
    return {
        "aws_region": "us-east-1",
        "db_host": "localhost",
        "db_port": 5432,
        "db_name": "testdb",
        "db_secret_name": "test-secret",
        "embedding_model_id": "amazon.titan-embed-text-v2:0",
        "llm_model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "chunk_size": 512,
        "chunk_overlap": 50,
        "top_k": 5,
    }


@pytest.fixture
def sample_db_credentials():
    """Sample database credentials for testing."""
    return {
        "username": "testuser",
        "password": "testpass",
    }
