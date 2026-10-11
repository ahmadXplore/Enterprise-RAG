"""Information Retrieval evaluation metrics: Recall@K, MRR, and nDCG@K."""

import math


def recall_at_k(
    retrieved_chunk_ids: list[str],
    expected_chunk_ids: list[str],
    k: int = 10,
) -> float:
    """Calculate Recall@K.

    Proportion of expected relevant chunk IDs present in the top-K retrieved chunk IDs.
    For unanswerable queries (where expected_chunk_ids is empty):
    Returns 1.0 (all 0 expected items retrieved).
    """
    if not expected_chunk_ids:
        return 1.0

    if k <= 0 or not retrieved_chunk_ids:
        return 0.0

    retrieved_set = set(retrieved_chunk_ids[:k])
    expected_set = set(expected_chunk_ids)

    relevant_retrieved = len(retrieved_set.intersection(expected_set))
    return float(relevant_retrieved) / float(len(expected_set))


def mrr(
    retrieved_chunk_ids: list[str],
    expected_chunk_ids: list[str],
) -> float:
    """Calculate Mean Reciprocal Rank (MRR).

    Reciprocal rank of the FIRST relevant chunk ID in the retrieved list:
    1 / rank (1-indexed). Returns 0.0 if no relevant chunk is retrieved.
    For unanswerable queries (where expected_chunk_ids is empty):
    Returns 1.0 if nothing retrieved, else 0.0.
    """
    if not expected_chunk_ids:
        return 1.0 if not retrieved_chunk_ids else 0.0

    expected_set = set(expected_chunk_ids)
    for rank, chunk_id in enumerate(retrieved_chunk_ids, start=1):
        if chunk_id in expected_set:
            return 1.0 / float(rank)

    return 0.0


def dcg_at_k(
    retrieved_chunk_ids: list[str],
    relevance_grades: dict[str, int],
    k: int = 10,
) -> float:
    """Calculate Discounted Cumulative Gain at K.

    DCG@K = sum((2^rel - 1) / log2(rank + 1))
    """
    if k <= 0 or not retrieved_chunk_ids:
        return 0.0

    dcg = 0.0
    for rank, chunk_id in enumerate(retrieved_chunk_ids[:k], start=1):
        rel = relevance_grades.get(chunk_id, 0)
        if rel > 0:
            dcg += (math.pow(2.0, rel) - 1.0) / math.log2(rank + 1.0)
    return dcg


def ndcg_at_k(
    retrieved_chunk_ids: list[str],
    relevance_grades: dict[str, int],
    k: int = 10,
) -> float:
    """Calculate Normalized Discounted Cumulative Gain at K (nDCG@K).

    nDCG@K = DCG@K / IDCG@K
    Returns 1.0 if IDCG is 0.0 (e.g. unanswerable query with no relevant documents).
    """
    if not relevance_grades:
        return 1.0

    actual_dcg = dcg_at_k(retrieved_chunk_ids, relevance_grades, k=k)

    # Calculate Ideal DCG (IDCG) by sorting all relevant grades descending
    sorted_grades = sorted(relevance_grades.values(), reverse=True)
    if not sorted_grades or sorted_grades[0] <= 0:
        return 1.0

    idcg = 0.0
    for rank, rel in enumerate(sorted_grades[:k], start=1):
        if rel > 0:
            idcg += (math.pow(2.0, rel) - 1.0) / math.log2(rank + 1.0)

    if idcg <= 0.0:
        return 1.0

    return actual_dcg / idcg


# ─────────────────────────────────────────────────────────────────────────────
# Generation & Grounding Evaluation Metrics (Phase 12)
# ─────────────────────────────────────────────────────────────────────────────


def _tokenize(text: str) -> list[str]:
    """Helper: lowercase word tokenization."""
    import re

    return re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())


def answer_relevance(
    generated_answer: str,
    expected_answer: str | None,
    question: str,
) -> float:
    """Calculate answer relevance.

    If expected_answer is available: computes token F1 between generated and expected answers.
    Otherwise: computes lexical coverage of key query tokens in the generated answer.
    Returns a score between 0.0 and 1.0.
    """
    if not generated_answer or not generated_answer.strip():
        return 0.0

    gen_tokens = _tokenize(generated_answer)
    if not gen_tokens:
        return 0.0

    target_text = expected_answer if expected_answer else question
    target_tokens = _tokenize(target_text)
    if not target_tokens:
        return 1.0

    gen_set = set(gen_tokens)
    target_set = set(target_tokens)
    intersection = gen_set.intersection(target_set)

    if not intersection:
        return 0.0

    precision = len(intersection) / len(gen_set)
    recall = len(intersection) / len(target_set)
    f1 = 2.0 * (precision * recall) / (precision + recall)
    return round(min(max(f1, 0.0), 1.0), 4)


def groundedness(
    generated_answer: str,
    evidence_texts: list[str],
) -> float:
    """Calculate groundedness / faithfulness score.

    Measures the proportion of content tokens (length > 3) in the generated answer
    that appear in the provided evidence texts.
    Returns 1.0 if answer is empty or fully supported; lower if answer introduces external tokens.
    """
    if not generated_answer or not generated_answer.strip():
        return 1.0

    gen_tokens = [t for t in _tokenize(generated_answer) if len(t) > 3]
    if not gen_tokens:
        return 1.0

    all_evidence = " ".join(evidence_texts)
    evidence_token_set = set(_tokenize(all_evidence))

    if not evidence_token_set:
        return 0.0

    supported = sum(1 for t in gen_tokens if t in evidence_token_set)
    return round(supported / len(gen_tokens), 4)


def citation_accuracy(
    cited_chunk_ids: list[str],
    expected_chunk_ids: list[str],
) -> float:
    """Calculate citation precision (accuracy).

    Proportion of cited chunk IDs that are actually relevant (present in expected_chunk_ids).
    If no citations are made and none are expected: 1.0.
    If citations are made but none are expected (unanswerable): 0.0.
    """
    if not cited_chunk_ids:
        return 1.0 if not expected_chunk_ids else 0.0

    if not expected_chunk_ids:
        return 0.0

    expected_set = set(expected_chunk_ids)
    valid_cited = sum(1 for cid in cited_chunk_ids if cid in expected_set)
    return round(valid_cited / len(cited_chunk_ids), 4)


def citation_completeness(
    cited_chunk_ids: list[str],
    expected_chunk_ids: list[str],
) -> float:
    """Calculate citation recall (completeness).

    Proportion of expected relevant chunk IDs that were cited in the answer.
    If no chunks are expected: 1.0.
    """
    if not expected_chunk_ids:
        return 1.0

    if not cited_chunk_ids:
        return 0.0

    cited_set = set(cited_chunk_ids)
    covered = sum(1 for cid in set(expected_chunk_ids) if cid in cited_set)
    return round(covered / len(set(expected_chunk_ids)), 4)


def abstention_correctness(
    abstained: bool,
    is_unanswerable: bool,
) -> bool:
    """Verify if the model correctly abstained on unanswerable questions
    and answered when evidence was present."""
    return bool(abstained == is_unanswerable)
