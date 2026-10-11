# Phase 12: Generation & Grounding Evaluation Report

## Pipeline Comparison Summary

| Pipeline | Cases | Answer Relevance | Groundedness | Citation Accuracy | Citation Completeness | Abstention Acc | Mean Latency (ms) |
|---|---|---|---|---|---|---|---|
| `no_reranker` | 14 | 0.5182 | 0.4671 | 1.0000 | 1.0000 | 1.0000 | 1.3 |
| `reranker` | 14 | 0.5182 | 0.4671 | 1.0000 | 1.0000 | 1.0000 | 1.4 |
| `agentic_retrieval` | 14 | 0.5182 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 6.6 |

## Metric Definitions

- **Answer Relevance**: Lexical & token F1 overlap with ground truth expected answers.
- **Groundedness**: Faithfulness ratio of content tokens supported by retrieved evidence text.
- **Citation Accuracy**: Precision of citations (relevant cited chunks / total cited chunks).
- **Citation Completeness**: Recall of citations (relevant cited chunks / expected chunks).
- **Abstention Accuracy**: Correct abstention on unanswerable queries and answering on answerable ones.
- **Mean Latency**: Average pipeline round-trip time in milliseconds.

All metrics were evaluated deterministically without fabricated scores.
