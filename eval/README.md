# Evaluation Dataset

This directory contains the evaluation dataset and sample documents for the quality gate.

## Structure

- `dataset.jsonl`: 21 test questions with expected answers and sources
- `documents/`: Sample CloudSync SaaS help center documentation

## Sample Documents

The corpus includes 4 documents for a fictional cloud storage company (CloudSync):

1. **product-features.md**: Product features, pricing plans, supported file types (Markdown)
2. **privacy-policy.txt**: Privacy policy, data collection, user rights (Plain text)
3. **api-documentation.md**: API endpoints, authentication, rate limits (Markdown)
4. **support-faq.txt**: Frequently asked questions, account/billing, technical support (Plain text)

These documents cover typical SaaS help center content: features, pricing, security, APIs, and support.

## Dataset Format

Each line in `dataset.jsonl` is a JSON object with:

```json
{
  "question": "The question to ask",
  "expected_answer": "The expected answer for correctness evaluation",
  "expected_sources": ["list", "of", "expected", "source", "documents"]
}
```

**21 questions total**:
- 18 answerable questions with expected sources
- 3 unanswerable questions (expected: "I don't know based on the provided documents")

## Evaluation Metrics

The quality gate evaluates three dimensions:

1. **Correctness** (LLM-as-judge): Does the answer match the expected answer?
2. **Faithfulness** (LLM-as-judge): Is the answer grounded in the retrieved context?
3. **Citation Accuracy** (deterministic): Do citations reference the expected sources?

Default thresholds (configurable in `config/config.yaml`):
- Correctness: 0.7
- Faithfulness: 0.8
- Citation Accuracy: 0.9

## Usage

Upload evaluation documents to S3:

```bash
aws s3 cp eval/documents/ s3://YOUR-DOCUMENTS-BUCKET/ --recursive
```

Wait for ingestion to complete (check CloudWatch Logs), then run:

```bash
python scripts/run_eval.py
```

## Adding Test Cases

To expand the dataset:

1. Add new documents to `documents/` (supports .md, .txt, .pdf)
2. Upload to S3 and wait for ingestion
3. Append questions to `dataset.jsonl` with expected answers and sources
4. Include some unanswerable questions (empty expected_sources)
5. Run evaluation and adjust thresholds if needed
