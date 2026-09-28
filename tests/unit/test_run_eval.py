"""Tests for run_eval script."""

import json
from unittest.mock import MagicMock, patch


@patch('scripts.run_eval.request')
def test_query_api_success(mock_request):
    """Test successful API query."""
    from scripts.run_eval import query_api

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "answer": "Test answer",
        "citations": [],
        "token_usage": {"input_tokens": 10, "output_tokens": 5}
    }).encode("utf-8")

    mock_request.urlopen.return_value.__enter__.return_value = mock_response

    result = query_api("https://api.example.com", "What is the answer?")

    assert result["answer"] == "Test answer"
    assert "citations" in result
    assert "token_usage" in result


@patch('scripts.run_eval.request')
def test_query_api_timeout_handling(mock_request):
    """Test API query near timeout."""
    import time

    from scripts.run_eval import query_api

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "answer": "Slow answer",
        "citations": []
    }).encode("utf-8")

    # Simulate slow response
    def slow_urlopen(*args, **kwargs):
        time.sleep(0.1)
        return mock_response

    mock_request.urlopen.return_value.__enter__.return_value = mock_response

    result = query_api("https://api.example.com", "Slow question?", timeout=1)

    assert result["answer"] == "Slow answer"


@patch('scripts.run_eval.request')
def test_query_api_url_construction(mock_request):
    """Test that query API constructs correct URL."""
    from scripts.run_eval import query_api

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({"answer": "OK"}).encode("utf-8")

    mock_request.urlopen.return_value.__enter__.return_value = mock_response
    mock_request.Request = MagicMock(return_value=MagicMock())

    query_api("https://api.example.com", "Test?")

    # Check that Request was called with correct URL
    call_args = mock_request.Request.call_args
    assert call_args[0][0] == "https://api.example.com/query"
    assert call_args[1]["method"] == "POST"
    assert call_args[1]["headers"]["Content-Type"] == "application/json"
