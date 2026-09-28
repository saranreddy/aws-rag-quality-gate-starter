"""Tests for evaluation framework."""

from unittest.mock import MagicMock, patch

from src.rag.evaluation import (
    evaluate_citation_accuracy,
    evaluate_correctness,
    evaluate_faithfulness,
    parse_judge_response,
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
    """Test citation accuracy with one correct and one incorrect citation."""
    answer = "The answer [1] is here [2]."
    citations = [
        {"number": 1, "source": "doc1.pdf"},
        {"number": 2, "source": "doc3.pdf"},  # Not in expected sources
    ]
    expected_sources = ["doc1.pdf", "doc2.pdf"]

    score = evaluate_citation_accuracy(answer, citations, expected_sources)

    # Precision: 1 correct out of 2 cited = 0.5
    # Citation usage: 1.0 (markers present)
    # Score: (0.5 + 1.0) / 2 = 0.75
    assert score == 0.75


def test_evaluate_citation_accuracy_one_of_multiple_expected():
    """Test citation accuracy with one correct citation when multiple are acceptable."""
    answer = "The answer [1] is here."
    citations = [
        {"number": 1, "source": "doc1.pdf"},
    ]
    expected_sources = ["doc1.pdf", "doc2.pdf"]

    score = evaluate_citation_accuracy(answer, citations, expected_sources)

    # Precision: 1 correct out of 1 cited = 1.0
    # Citation usage: 1.0 (markers present)
    # Score: (1.0 + 1.0) / 2 = 1.0
    assert score == 1.0


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


def test_parse_judge_response_plain_json():
    """Test parsing plain JSON response."""
    response = '{"score": 8, "reasoning": "Good"}'
    score, success = parse_judge_response(response)

    assert success is True
    assert score == 0.8


def test_parse_judge_response_markdown_fence():
    """Test parsing JSON wrapped in markdown code fence."""
    response = '```json\n{"score": 7, "reasoning": "Pretty good"}\n```'
    score, success = parse_judge_response(response)

    assert success is True
    assert score == 0.7


def test_parse_judge_response_markdown_fence_no_lang():
    """Test parsing JSON in markdown fence without language tag."""
    response = '```\n{"score": 9, "reasoning": "Excellent"}\n```'
    score, success = parse_judge_response(response)

    assert success is True
    assert score == 0.9


def test_parse_judge_response_with_text():
    """Test parsing JSON with extra text around markdown fence."""
    response = 'Here is my evaluation:\n```json\n{"score": 6, "reasoning": "OK"}\n```\nDone.'
    score, success = parse_judge_response(response)

    assert success is True
    assert score == 0.6


def test_parse_judge_response_invalid_json():
    """Test parsing invalid JSON returns failure."""
    response = '{"score": invalid}'
    score, success = parse_judge_response(response)

    assert success is False
    assert score == 0.0


def test_parse_judge_response_missing_score():
    """Test parsing JSON without score field returns failure."""
    response = '{"reasoning": "No score here"}'
    score, success = parse_judge_response(response)

    assert success is False
    assert score == 0.0


def test_evaluate_single_question_refusal_on_unanswerable():
    """Test that correct refusal on unanswerable question gets high scores."""

    question_data = {
        "question": "What is the meaning of life?",
        "expected_answer": "I don't know based on the provided documents.",
        "expected_sources": []  # Unanswerable
    }

    answer_data = {
        "answer": "I don't know based on the provided documents.",
        "citations": [],
        "token_usage": {"input_tokens": 10, "output_tokens": 5}
    }

    config = {
        "llm_model_id": "test-model",
        "aws_region": "us-east-1"
    }

    # Mock the LLM judge calls
    import src.rag.evaluation as eval_module
    original_correctness = eval_module.evaluate_correctness
    eval_module.evaluate_correctness = lambda *args, **kwargs: 1.0

    try:
        result = eval_module.evaluate_single_question(question_data, answer_data, config)

        # Correct refusal should get full faithfulness and citation scores
        assert result["scores"]["faithfulness"] == 1.0
        assert result["scores"]["citation_accuracy"] == 1.0
    finally:
        eval_module.evaluate_correctness = original_correctness


def test_evaluate_single_question_refusal_on_answerable():
    """Test that refusal on answerable question is scored as wrong."""

    question_data = {
        "question": "What is SOC 2?",
        "expected_answer": "SOC 2 is a compliance framework.",
        "expected_sources": ["doc1.pdf"]  # Answerable
    }

    answer_data = {
        "answer": "I don't know based on the provided documents.",
        "citations": [],
        "token_usage": {"input_tokens": 10, "output_tokens": 5}
    }

    config = {
        "llm_model_id": "test-model",
        "aws_region": "us-east-1"
    }

    # Mock the LLM judge calls
    import src.rag.evaluation as eval_module
    original_correctness = eval_module.evaluate_correctness
    eval_module.evaluate_correctness = lambda *args, **kwargs: 0.0  # Wrong answer

    try:
        result = eval_module.evaluate_single_question(question_data, answer_data, config)

        # Refusal on answerable question should not get special treatment
        # Faithfulness should be low (no context retrieved)
        assert result["scores"]["faithfulness"] == 0.2
        assert result["scores"]["citation_accuracy"] == 0.0
    finally:
        eval_module.evaluate_correctness = original_correctness
