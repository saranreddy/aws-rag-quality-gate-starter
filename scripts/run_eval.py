#!/usr/bin/env python3
"""Run evaluation quality gate against the RAG system."""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from urllib import request
from urllib.error import URLError

# Add repo root to sys.path so 'src' can be imported
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag.config import load_config
from src.rag.evaluation import evaluate_single_question


def load_eval_dataset(dataset_path: str) -> List[Dict[str, Any]]:
    """Load evaluation dataset from JSONL file.

    Args:
        dataset_path: Path to dataset.jsonl

    Returns:
        List of question dictionaries
    """
    questions = []
    with open(dataset_path, "r") as f:
        for line in f:
            questions.append(json.loads(line))
    return questions


def query_api(api_url: str, question: str, timeout: int = 60) -> Dict[str, Any]:
    """Call the deployed query API endpoint.

    Args:
        api_url: API Gateway URL
        question: Question to query
        timeout: Request timeout in seconds

    Returns:
        Query response dictionary
    """
    req_data = json.dumps({"question": question}).encode("utf-8")
    req = request.Request(
        f"{api_url}/query",
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    start_time = time.time()
    try:
        with request.urlopen(req, timeout=timeout) as response:
            elapsed = time.time() - start_time
            result = json.loads(response.read().decode("utf-8"))
            if elapsed > timeout * 0.9:
                print(f"  Warning: Query took {elapsed:.1f}s (near timeout)")
            return result
    except URLError as e:
        print(f"  Error calling API: {e}")
        raise


def run_evaluation(config: Dict[str, Any]) -> Dict[str, Any]:
    """Run full evaluation against the RAG system.

    Args:
        config: Configuration dictionary (must include api_gateway_url or api_url)

    Returns:
        Evaluation results
    """
    # Support both api_gateway_url (docs) and api_url (legacy) keys
    api_url = config.get("api_gateway_url") or config.get("api_url")
    if not api_url:
        raise ValueError("api_gateway_url must be set in config for evaluation")

    dataset_path = config.get("eval_dataset_path", "eval/dataset.jsonl")
    questions = load_eval_dataset(dataset_path)

    results = []

    for i, question_data in enumerate(questions):
        print(f"\nEvaluating question {i+1}/{len(questions)}: {question_data['question'][:60]}...")

        answer_data = query_api(api_url, question_data["question"])

        eval_result = evaluate_single_question(question_data, answer_data, config)
        results.append(eval_result)

        print(f"  Correctness: {eval_result['scores']['correctness']:.2f}")
        print(f"  Faithfulness: {eval_result['scores']['faithfulness']:.2f}")
        print(f"  Citation Accuracy: {eval_result['scores']['citation_accuracy']:.2f}")

    avg_scores = {
        "correctness": sum(r["scores"]["correctness"] for r in results) / len(results),
        "faithfulness": sum(r["scores"]["faithfulness"] for r in results) / len(results),
        "citation_accuracy": sum(r["scores"]["citation_accuracy"] for r in results) / len(results),
    }

    # Calculate total token usage from all questions
    total_input_tokens = sum(r["token_usage"].get("input_tokens", 0) for r in results)
    total_output_tokens = sum(r["token_usage"].get("output_tokens", 0) for r in results)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_questions": len(results),
        "average_scores": avg_scores,
        "total_token_usage": {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
        },
        "detailed_results": results,
    }


def check_thresholds(results: Dict[str, Any], thresholds: Dict[str, float]) -> bool:
    """Check if results meet threshold requirements.

    Args:
        results: Evaluation results
        thresholds: Threshold configuration

    Returns:
        True if all thresholds are met, False otherwise
    """
    avg_scores = results["average_scores"]

    # Add per-metric pass/fail to results
    metric_results = {}
    passed = True

    print("\n" + "=" * 60)
    print("EVALUATION QUALITY GATE")
    print("=" * 60)

    for metric, score in avg_scores.items():
        threshold = thresholds.get(metric, 0.0)
        metric_passed = score >= threshold
        status = "✓ PASS" if metric_passed else "✗ FAIL"
        print(f"{metric:20s}: {score:.3f} (threshold: {threshold:.3f}) {status}")

        metric_results[metric] = {
            "score": score,
            "threshold": threshold,
            "passed": metric_passed,
        }

        if not metric_passed:
            passed = False

    print("=" * 60)

    if passed:
        print("✓ All metrics passed! Quality gate: PASS")
    else:
        print("✗ Some metrics below threshold. Quality gate: FAIL")

    print("=" * 60)

    # Add gate result to results dict
    results["gate_passed"] = passed
    results["metric_results"] = metric_results

    return passed


def save_report(results: Dict[str, Any], output_dir: str = "eval/reports") -> None:
    """Save evaluation report as JSON and markdown.

    Args:
        results: Evaluation results
        output_dir: Output directory for reports
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    json_path = f"{output_dir}/eval_report_{timestamp}.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nJSON report saved to: {json_path}")

    md_path = f"{output_dir}/eval_report_{timestamp}.md"
    with open(md_path, "w") as f:
        f.write("# RAG Evaluation Report\n\n")
        f.write(f"**Timestamp:** {results['timestamp']}\n\n")
        f.write(f"**Total Questions:** {results['total_questions']}\n\n")

        f.write("## Average Scores\n\n")
        f.write("| Metric | Score |\n")
        f.write("|--------|-------|\n")
        for metric, score in results["average_scores"].items():
            f.write(f"| {metric} | {score:.3f} |\n")

        f.write("\n## Detailed Results\n\n")
        for i, result in enumerate(results["detailed_results"]):
            f.write(f"### Question {i+1}\n\n")
            f.write(f"**Q:** {result['question']}\n\n")
            f.write(f"**A:** {result['answer']}\n\n")
            f.write(f"**Scores:** Correctness={result['scores']['correctness']:.2f}, ")
            f.write(f"Faithfulness={result['scores']['faithfulness']:.2f}, ")
            f.write(f"Citation Accuracy={result['scores']['citation_accuracy']:.2f}\n\n")

            if result['citations']:
                f.write("**Citations:**\n")
                for citation in result['citations']:
                    f.write(f"- [{citation['number']}] {citation['source']} (Page {citation['page']})\n")
                f.write("\n")

            f.write("---\n\n")

    print(f"Markdown report saved to: {md_path}")


def main() -> int:
    """Main entry point for evaluation script.

    Returns:
        Exit code: 0 if quality gate passes, 1 if it fails
    """
    try:
        config = load_config("config/config.yaml")
    except FileNotFoundError:
        print("Error: config/config.yaml not found")
        print("Copy config/config.example.yaml to config/config.yaml and configure it")
        return 1

    print("Running RAG evaluation quality gate...")

    try:
        results = run_evaluation(config)
        save_report(results)

        thresholds = config.get("eval_thresholds", {
            "correctness": 0.7,
            "faithfulness": 0.8,
            "citation_accuracy": 0.9,
        })

        passed = check_thresholds(results, thresholds)

        return 0 if passed else 1

    except Exception as e:
        print(f"\nError during evaluation: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
