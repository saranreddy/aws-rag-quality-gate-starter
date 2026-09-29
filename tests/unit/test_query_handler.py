"""Tests for query Lambda handler."""

import importlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))


@patch.dict(os.environ, {
    "DB_HOST": "test-host",
    "DB_SECRET_NAME": "test-secret",
    "USE_HYBRID_RETRIEVAL": "true"
})
@patch('rag.query.query_rag')
@patch('rag.config.get_db_credentials')
def test_query_handler_reads_use_hybrid_retrieval_true(mock_get_creds, mock_query_rag):
    """Test that handler reads USE_HYBRID_RETRIEVAL=true correctly."""
    from lambda_handlers.query_handler import handler

    mock_get_creds.return_value = {"username": "user", "password": "pass"}
    mock_query_rag.return_value = {
        "answer": "Test answer",
        "citations": [],
        "token_usage": {"input_tokens": 10, "output_tokens": 5},
        "retrieved_chunks": 3,
    }

    event = {
        "body": json.dumps({"question": "What is the answer?"})
    }
    context = MagicMock()
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"

    response = handler(event, context)

    assert response["statusCode"] == 200

    call_args = mock_query_rag.call_args
    config = call_args[0][1]
    assert config["use_hybrid_retrieval"] is True


@patch.dict(os.environ, {
    "DB_HOST": "test-host",
    "DB_SECRET_NAME": "test-secret",
    "USE_HYBRID_RETRIEVAL": "false"
})
@patch('rag.query.query_rag')
@patch('rag.config.get_db_credentials')
def test_query_handler_reads_use_hybrid_retrieval_false(mock_get_creds, mock_query_rag):
    """Test that handler reads USE_HYBRID_RETRIEVAL=false correctly."""
    import lambda_handlers.query_handler
    importlib.reload(lambda_handlers.query_handler)
    from lambda_handlers.query_handler import handler

    mock_get_creds.return_value = {"username": "user", "password": "pass"}
    mock_query_rag.return_value = {
        "answer": "Test answer",
        "citations": [],
        "token_usage": {"input_tokens": 10, "output_tokens": 5},
        "retrieved_chunks": 3,
    }

    event = {
        "body": json.dumps({"question": "What is the answer?"})
    }
    context = MagicMock()
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"

    response = handler(event, context)

    assert response["statusCode"] == 200

    call_args = mock_query_rag.call_args
    config = call_args[0][1]
    assert config["use_hybrid_retrieval"] is False


@patch.dict(os.environ, {
    "DB_HOST": "test-host",
    "DB_SECRET_NAME": "test-secret",
})
@patch('rag.query.query_rag')
@patch('rag.config.get_db_credentials')
def test_query_handler_defaults_use_hybrid_retrieval_true(mock_get_creds, mock_query_rag):
    """Test that handler defaults to USE_HYBRID_RETRIEVAL=true when not set."""
    import lambda_handlers.query_handler
    importlib.reload(lambda_handlers.query_handler)
    from lambda_handlers.query_handler import handler

    mock_get_creds.return_value = {"username": "user", "password": "pass"}
    mock_query_rag.return_value = {
        "answer": "Test answer",
        "citations": [],
        "token_usage": {"input_tokens": 10, "output_tokens": 5},
        "retrieved_chunks": 3,
    }

    event = {
        "body": json.dumps({"question": "What is the answer?"})
    }
    context = MagicMock()
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"

    response = handler(event, context)

    assert response["statusCode"] == 200

    call_args = mock_query_rag.call_args
    config = call_args[0][1]
    assert config["use_hybrid_retrieval"] is True


@patch.dict(os.environ, {
    "DB_HOST": "test-host",
    "DB_SECRET_NAME": "test-secret",
    "TOP_K": "15"
})
@patch('rag.query.query_rag')
@patch('rag.config.get_db_credentials')
def test_query_handler_reads_top_k(mock_get_creds, mock_query_rag):
    """Test that handler reads TOP_K correctly."""
    import lambda_handlers.query_handler
    importlib.reload(lambda_handlers.query_handler)
    from lambda_handlers.query_handler import handler

    mock_get_creds.return_value = {"username": "user", "password": "pass"}
    mock_query_rag.return_value = {
        "answer": "Test answer",
        "citations": [],
        "token_usage": {"input_tokens": 10, "output_tokens": 5},
        "retrieved_chunks": 3,
    }

    event = {
        "body": json.dumps({"question": "What is the answer?"})
    }
    context = MagicMock()
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"

    response = handler(event, context)

    assert response["statusCode"] == 200

    call_args = mock_query_rag.call_args
    config = call_args[0][1]
    assert config["top_k"] == 15


@patch.dict(os.environ, {
    "DB_HOST": "test-host",
    "DB_SECRET_NAME": "test-secret",
})
@patch('rag.query.query_rag')
@patch('rag.config.get_db_credentials')
def test_query_handler_defaults_top_k_to_10(mock_get_creds, mock_query_rag):
    """Test that handler defaults TOP_K to 10 when not set."""
    import lambda_handlers.query_handler
    importlib.reload(lambda_handlers.query_handler)
    from lambda_handlers.query_handler import handler

    mock_get_creds.return_value = {"username": "user", "password": "pass"}
    mock_query_rag.return_value = {
        "answer": "Test answer",
        "citations": [],
        "token_usage": {"input_tokens": 10, "output_tokens": 5},
        "retrieved_chunks": 3,
    }

    event = {
        "body": json.dumps({"question": "What is the answer?"})
    }
    context = MagicMock()
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test"

    response = handler(event, context)

    assert response["statusCode"] == 200

    call_args = mock_query_rag.call_args
    config = call_args[0][1]
    assert config["top_k"] == 10
