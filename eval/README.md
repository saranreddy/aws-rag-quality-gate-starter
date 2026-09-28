# Evaluation Dataset

This directory contains the evaluation dataset and sample documents for the quality gate.

## Structure

- `dataset.jsonl`: Test questions with expected answers and sources
- `documents/`: Sample document corpus for testing

## Dataset Format

Each line in `dataset.jsonl` is a JSON object with:

```json
{
  "question": "The question to ask",
  "expected_answer": "The expected answer for correctness evaluation",
  "expected_sources": ["list", "of", "expected", "source", "documents"]
}
```

## Usage

The evaluation script (`scripts/run_eval.py`) uses this dataset to:
1. Query the RAG system with each question
2. Evaluate correctness (vs expected_answer)
3. Evaluate faithfulness (answer grounded in retrieved context)
4. Evaluate citation accuracy (citations match expected_sources)

## Adding Test Cases

To add more test cases:

1. Add corresponding documents to `documents/`
2. Append questions to `dataset.jsonl`
3. Ensure expected_sources match document filenames
