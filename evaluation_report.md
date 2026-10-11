# Retrieval Engine Benchmark Report

## 1. Overall Pipeline Comparison

| Pipeline | Recall@5 | Recall@10 | MRR | nDCG@5 | nDCG@10 | Avg Latency (ms) |
|---|---|---|---|---|---|---|
| **Dense only** | 0.0909 | 0.0909 | 0.0909 | 0.0909 | 0.0909 | 4.98 |
| **Sparse only** | 0.0909 | 0.0909 | 0.0909 | 0.0909 | 0.0909 | 0.15 |
| **Hybrid (Dense + Sparse + RRF)** | 0.0909 | 0.0909 | 0.0909 | 0.0909 | 0.0909 | 5.02 |
| **Hybrid + Reranker** | 0.0909 | 0.0909 | 0.0909 | 0.0909 | 0.0909 | 5.11 |

## 2. Performance by Query Category (Hybrid + Reranker)

| Category | Cases | Recall@5 | Recall@10 | MRR | nDCG@5 | nDCG@10 |
|---|---|---|---|---|---|---|
| `direct_lookup` | 20 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `temporal` | 20 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `comparison` | 20 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `numerical` | 15 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `legal` | 15 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `cross_document` | 10 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| `unanswerable` | 10 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
