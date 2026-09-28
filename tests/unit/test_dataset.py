"""Tests for evaluation dataset validation."""

import json
from pathlib import Path

import pytest


def test_dataset_file_exists():
    """Test that dataset.jsonl file exists."""
    dataset_path = Path("eval/dataset.jsonl")
    assert dataset_path.exists(), "eval/dataset.jsonl not found"


def test_dataset_format():
    """Test that each line in dataset.jsonl is valid JSON with required fields."""
    dataset_path = Path("eval/dataset.jsonl")

    with open(dataset_path, 'r') as f:
        lines = f.readlines()

    assert len(lines) > 0, "Dataset file is empty"

    for i, line in enumerate(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            pytest.fail(f"Line {i+1} is not valid JSON")

        assert "question" in entry, f"Line {i+1} missing 'question' field"
        assert "expected_answer" in entry, f"Line {i+1} missing 'expected_answer' field"
        assert "expected_sources" in entry, f"Line {i+1} missing 'expected_sources' field"

        assert isinstance(entry["question"], str), f"Line {i+1} 'question' must be string"
        assert isinstance(entry["expected_answer"], str), f"Line {i+1} 'expected_answer' must be string"
        assert isinstance(entry["expected_sources"], list), f"Line {i+1} 'expected_sources' must be list"

        assert len(entry["question"]) > 0, f"Line {i+1} 'question' cannot be empty"
        assert len(entry["expected_answer"]) > 0, f"Line {i+1} 'expected_answer' cannot be empty"


def test_dataset_sources_exist():
    """Test that all referenced source documents exist in eval/documents/."""
    dataset_path = Path("eval/dataset.jsonl")
    documents_dir = Path("eval/documents")

    assert documents_dir.exists(), "eval/documents/ directory not found"

    existing_files = {f.name for f in documents_dir.iterdir() if f.is_file()}

    with open(dataset_path, 'r') as f:
        for i, line in enumerate(f):
            entry = json.loads(line)
            sources = entry["expected_sources"]

            for source in sources:
                assert source in existing_files, \
                    f"Line {i+1} references non-existent file: {source}. " \
                    f"Available files: {sorted(existing_files)}"


def test_dataset_has_answerable_and_unanswerable():
    """Test that dataset includes both answerable and unanswerable questions."""
    dataset_path = Path("eval/dataset.jsonl")

    answerable = 0
    unanswerable = 0

    with open(dataset_path, 'r') as f:
        for line in f:
            entry = json.loads(line)
            if len(entry["expected_sources"]) == 0:
                unanswerable += 1
                assert "don't know" in entry["expected_answer"].lower(), \
                    "Unanswerable questions should have 'I don't know' in expected answer"
            else:
                answerable += 1

    assert answerable > 0, "Dataset must include at least one answerable question"
    assert unanswerable > 0, "Dataset must include at least one unanswerable question"

    total = answerable + unanswerable
    assert total >= 15, f"Dataset should have at least 15 questions (found {total})"


def test_document_files_exist():
    """Test that evaluation documents directory contains sample files."""
    documents_dir = Path("eval/documents")

    files = list(documents_dir.glob("*"))
    files = [f for f in files if f.is_file()]

    assert len(files) >= 3, "Should have at least 3 sample documents"

    extensions = {f.suffix for f in files}
    assert ".md" in extensions or ".txt" in extensions, \
        "Should have at least one .md or .txt file"
