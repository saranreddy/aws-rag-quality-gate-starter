"""Tests for evaluation framework."""

from unittest.mock import MagicMock, patch

from src.rag.evaluation import (
    evaluate_citation_accuracy,
    evaluate_correctness,
    evaluate_faithfulness,
)


@patch('src.rag.evaluation.boto3.client')
def test_evaluate_correctness(mock_boto_client):
    """Test correctness evaluation."""
    mock_bedrock = MagicMock()
    mock_boto_client.return_value = mock_bedrock

    mock_response = MagicMock()
    mock_response.__getitem__.return_value.read.return_value = b'''{
        "content": [{"text": "{\\"score\\": 8, \\"reasoning\\": \\"Good match\\"}"}]
    }'''
    mock_bedrock.invoke_model.return_value = mock_response

    score = evaluate_correctness(
        "What is 2+2?",
        "2+2 equals 4",
        "The answer is 4",
        "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "us-east-1"
    )

    assert score == 0.8


@patch('src.rag.evaluation.boto3.client')
def test_evaluate_faithfulness(mock_boto_client):
    """Test faithfulness evaluation."""
    mock_bedrock = MagicMock()
    mock_boto_client.return_value = mock_bedrock

    mock_response = MagicMock()
    mock_response.__getitem__.return_value.read.return_value = b'''{
        "content": [{"text": "{\\"score\\": 9, \\"reasoning\\": \\"Well grounded\\"}"}]
    }'''
    mock_bedrock.invoke_model.return_value = mock_response

    score = evaluate_faithfulness(
        "The sky is blue",
        ["The sky appears blue during daytime."],
        "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "us-east-1"
    )

    assert score == 0.9


def test_evaluate_citation_accuracy_perfect():
    """Test citation accuracy with perfect match."""
    answer = "The answer [1] is here [2]."
    citations = [
        {"number": 1, "source": "doc1.pdf"},
        {"number": 2, "source": "doc2.pdf"},
    ]
    expected_sources = ["doc1.pdf", "doc2.pdf"]

    score = evaluate_citation_accuracy(answer, citations, expected_sources)

    assert score == 1.0


def test_evaluate_citation_accuracy_partial():
    """Test citation accuracy with partial match."""
    answer = "The answer [1] is here."
    citations = [
        {"number": 1, "source": "doc1.pdf"},
    ]
    expected_sources = ["doc1.pdf", "doc2.pdf"]

    score = evaluate_citation_accuracy(answer, citations, expected_sources)

    assert score > 0.0
    assert score < 1.0


def test_evaluate_citation_accuracy_no_citations():
    """Test citation accuracy with no citations."""
    answer = "The answer is here."
    citations = []
    expected_sources = ["doc1.pdf"]

    score = evaluate_citation_accuracy(answer, citations, expected_sources)

    assert score == 0.0


def test_evaluate_citation_accuracy_no_expected():
    """Test citation accuracy with no expected sources."""
    answer = "The answer is here."
    citations = []
    expected_sources = []

    score = evaluate_citation_accuracy(answer, citations, expected_sources)

    assert score == 1.0
