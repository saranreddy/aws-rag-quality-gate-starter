"""Evaluation framework: LLM-as-judge for correctness, faithfulness, and citation accuracy."""

import json
import re
from typing import Any, Dict, List, Tuple

import boto3


def parse_judge_response(response_text: str) -> Tuple[float, bool]:
    """Parse judge response, handling markdown code fences.

    Args:
        response_text: Raw response from judge LLM

    Returns:
        Tuple of (score_0_to_1, parse_success)
    """
    # Try to extract JSON from markdown code fences
    json_match = re.search(r'```(?:json)?\s*\n?\s*(\{.*?\})\s*\n?```', response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
    else:
        json_str = response_text.strip()

    try:
        evaluation = json.loads(json_str)
        score = evaluation.get("score")
        if score is None:
            return 0.0, False
        return float(score) / 10.0, True
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(f"Warning: Failed to parse judge response: {e}")
        print(f"Raw response: {response_text[:200]}")
        return 0.0, False


def evaluate_correctness(
    question: str,
    answer: str,
    expected_answer: str,
    llm_model_id: str,
    region: str,
) -> float:
    """Evaluate answer correctness using LLM-as-judge.

    Args:
        question: Original question
        answer: Generated answer
        expected_answer: Expected/reference answer
        llm_model_id: Bedrock LLM model ID
        region: AWS region

    Returns:
        Correctness score (0.0 to 1.0)
    """
    bedrock = boto3.client("bedrock-runtime", region_name=region)

    prompt = f"""Evaluate if the generated answer is correct compared to the expected answer.

Question: {question}

Expected Answer: {expected_answer}

Generated Answer: {answer}

Score the correctness from 0 to 10:
- 10: Perfect match, all key information present
- 7-9: Mostly correct, minor omissions or imprecision
- 4-6: Partially correct, missing important details
- 1-3: Mostly incorrect, significant errors
- 0: Completely wrong or "I don't know" when answer is knowable

Output only a JSON object with: {{"score": <number>, "reasoning": "<brief explanation>"}}"""

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": prompt}],
    })

    response = bedrock.invoke_model(
        modelId=llm_model_id,
        body=body,
        contentType="application/json",
        accept="application/json",
    )

    result = json.loads(response["body"].read())
    answer_text = result["content"][0]["text"]

    score, success = parse_judge_response(answer_text)
    if not success:
        print(f"Warning: Correctness judge parse failed for question: {question[:50]}...")
    return score


def evaluate_faithfulness(
    answer: str,
    context_chunks: List[str],
    llm_model_id: str,
    region: str,
) -> float:
    """Evaluate answer faithfulness/groundedness in context.

    Args:
        answer: Generated answer
        context_chunks: Context passages used
        llm_model_id: Bedrock LLM model ID
        region: AWS region

    Returns:
        Faithfulness score (0.0 to 1.0)
    """
    bedrock = boto3.client("bedrock-runtime", region_name=region)

    context_text = "\n\n".join(context_chunks)

    prompt = f"""Evaluate if the answer is faithful to (grounded in) the provided context.

Context:
{context_text}

Answer to evaluate:
{answer}

Score faithfulness from 0 to 10:
- 10: All claims in answer are directly supported by context
- 7-9: Mostly grounded, minor reasonable inferences
- 4-6: Some claims not supported by context
- 1-3: Many claims contradict or add unsupported information
- 0: Answer completely fabricated or contradicts context

Output only a JSON object with: {{"score": <number>, "reasoning": "<brief explanation>"}}"""

    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": prompt}],
    })

    response = bedrock.invoke_model(
        modelId=llm_model_id,
        body=body,
        contentType="application/json",
        accept="application/json",
    )

    result = json.loads(response["body"].read())
    answer_text = result["content"][0]["text"]

    score, success = parse_judge_response(answer_text)
    if not success:
        print(f"Warning: Faithfulness judge parse failed for answer: {answer[:50]}...")
    return score


def evaluate_citation_accuracy(
    answer: str,
    citations: List[Dict[str, Any]],
    expected_sources: List[str],
) -> float:
    """Evaluate citation accuracy using deterministic checks.

    Args:
        answer: Generated answer
        citations: List of citation dictionaries
        expected_sources: List of expected source documents

    Returns:
        Citation accuracy score (0.0 to 1.0)
    """
    if not citations:
        return 0.0 if expected_sources else 1.0

    cited_sources = {citation["source"] for citation in citations}
    expected_set = set(expected_sources)

    if not expected_set:
        return 1.0 if not cited_sources else 0.8

    intersection = cited_sources & expected_set
    union = cited_sources | expected_set

    jaccard_score = len(intersection) / len(union) if union else 0.0

    has_citations_in_answer = any(
        f"[{citation['number']}]" in answer
        for citation in citations
    )
    citation_usage_score = 1.0 if has_citations_in_answer else 0.5

    return (jaccard_score + citation_usage_score) / 2.0


def evaluate_single_question(
    question_data: Dict[str, Any],
    answer_data: Dict[str, Any],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Evaluate a single question's answer against expected results.

    Args:
        question_data: Dictionary with question, expected_answer, expected_sources
        answer_data: Dictionary with answer, citations from query_rag
        config: Configuration dictionary

    Returns:
        Evaluation results with scores
    """
    correctness = evaluate_correctness(
        question_data["question"],
        answer_data["answer"],
        question_data["expected_answer"],
        config["llm_model_id"],
        config["aws_region"],
    )

    # Pass full chunk text to faithfulness judge instead of truncated snippets
    context_chunks = [citation.get("full_text", citation["snippet"]) for citation in answer_data.get("citations", [])]
    faithfulness = evaluate_faithfulness(
        answer_data["answer"],
        context_chunks if context_chunks else ["No context retrieved"],
        config["llm_model_id"],
        config["aws_region"],
    )

    citation_accuracy = evaluate_citation_accuracy(
        answer_data["answer"],
        answer_data.get("citations", []),
        question_data.get("expected_sources", []),
    )

    return {
        "question": question_data["question"],
        "answer": answer_data["answer"],
        "scores": {
            "correctness": correctness,
            "faithfulness": faithfulness,
            "citation_accuracy": citation_accuracy,
        },
        "citations": answer_data.get("citations", []),
        "token_usage": answer_data.get("token_usage", {}),
    }
