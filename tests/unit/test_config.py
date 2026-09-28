"""Tests for configuration management."""

import tempfile
from pathlib import Path

import pytest

from src.rag.config import load_config, validate_config


def test_validate_config_success():
    """Test configuration validation with valid config."""
    config = {
        "aws_region": "us-east-1",
        "db_host": "mydb.rds.amazonaws.com",
        "embedding_model_id": "amazon.titan-embed-text-v2:0",
        "llm_model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    }
    validate_config(config)


def test_validate_config_missing_field():
    """Test configuration validation fails with missing required field."""
    config = {
        "aws_region": "us-east-1",
        "db_host": "mydb.rds.amazonaws.com",
    }
    with pytest.raises(ValueError, match="Missing required field"):
        validate_config(config)


def test_validate_config_placeholder_values():
    """Test configuration validation fails with placeholder values."""
    config = {
        "aws_region": "us-east-1",
        "db_host": "your-aurora-cluster.xxxxx.us-east-1.rds.amazonaws.com",
        "embedding_model_id": "amazon.titan-embed-text-v2:0",
        "llm_model_id": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    }
    with pytest.raises(ValueError, match="placeholder values"):
        validate_config(config)


def test_load_config_file_not_found():
    """Test loading config fails when file doesn't exist."""
    with pytest.raises(FileNotFoundError, match="Config file not found"):
        load_config("nonexistent.yaml")


def test_load_config_success():
    """Test loading config from YAML file."""
    config_content = """
aws_region: us-east-1
db_host: mydb.rds.amazonaws.com
db_port: 5432
db_name: ragdb
embedding_model_id: amazon.titan-embed-text-v2:0
llm_model_id: anthropic.claude-3-5-sonnet-20241022-v2:0
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(config_content)
        temp_path = f.name

    try:
        config = load_config(temp_path)
        assert config["aws_region"] == "us-east-1"
        assert config["db_host"] == "mydb.rds.amazonaws.com"
        assert config["embedding_model_id"] == "amazon.titan-embed-text-v2:0"
    finally:
        Path(temp_path).unlink()
