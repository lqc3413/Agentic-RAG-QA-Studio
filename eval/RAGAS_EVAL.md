# Ragas Evaluation

This directory contains a small but complete Ragas-driven evaluation loop for the
project's RAG system.

## What It Measures

- `faithfulness`: whether the answer is supported by retrieved contexts.
- `answer_relevancy`: whether the answer addresses the question.
- `context_precision`: whether retrieved contexts are relevant and well ranked.
- `context_recall`: whether the retrieved contexts cover the reference context.
- `factual_correctness`: whether the answer matches the reference answer.

These metrics separate retrieval quality from generation quality, which makes it
easier to explain whether failures come from missing context, poor ranking, or
hallucinated / incomplete answers.

## Case Format

`eval/ragas_cases.json` is a list of cases:

```json
{
  "id": "mysql_bplus_tree",
  "question": "B+ Tree 的原理是什么？它在数据库索引中有什么优势？",
  "reference": "标准答案，用于 factual correctness。",
  "reference_contexts": ["标准答案依据的原文片段。"],
  "expected_sources": ["MySQL"],
  "tags": ["mysql", "index"]
}
```

## Commands

Validate the whole pipeline without calling an LLM judge:

```bash
python eval/ragas_eval.py --runner mock --evaluator mock
```

Run against a local FastAPI server and use Ragas:

```bash
python eval/ragas_eval.py --runner http --evaluator ragas --base-url http://127.0.0.1:8000
```

Real Ragas scoring needs a judge LLM and, for `answer_relevancy`, an embedding
model. Configure them with environment variables:

```env
RAGAS_API_KEY=your-judge-api-key
RAGAS_API_BASE_URL=https://your-openai-compatible-endpoint/v1
RAGAS_LLM_MODEL=gpt-4o-mini
RAGAS_EMBEDDING_MODEL=text-embedding-3-small
```

If these are not set, the script also checks the existing project variables
`OPENAI_COMPATIBLE_API_KEY`, `OPENAI_COMPATIBLE_API_BASE_URL`, `LLM_MODEL`, and
`DENSE_MODEL`.

Use an existing HTTP user instead of creating a temporary eval user:

```bash
python eval/ragas_eval.py --runner http --evaluator ragas --username alice --password "your-password"
```

Reports are written as JSON, Markdown, and CSV under `eval/ragas_reports/`.

## Interview Explanation

The evaluation loop first calls the RAG system, stores the generated answer and
the exact retrieved contexts, then asks Ragas to score the result. Retrieval is
measured with context precision and recall, while answer generation is measured
with faithfulness, answer relevancy, and factual correctness. This avoids relying
only on keyword matching and helps locate whether a bad answer is caused by
retrieval or generation.
