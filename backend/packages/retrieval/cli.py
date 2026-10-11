"""CLI for interactive retrieval testing and ranked evidence inspection."""
import argparse
from typing import Any

from packages.retrieval.dense import DenseRetriever
from packages.retrieval.embeddings import BM25SparseEmbedder, FastEmbedDenseEmbedder
from packages.retrieval.hybrid import HybridRetriever
from packages.retrieval.models import RetrievalConfig
from packages.retrieval.qdrant_client import (
    DEFAULT_COLLECTION,
    create_qdrant_client,
    ensure_collection,
)
from packages.retrieval.reranker import FastEmbedReranker
from packages.retrieval.sparse import SparseRetriever


def format_evidence_table(results: list[Any]) -> str:
    """Format retrieval results into structured evidence table."""
    if not results:
        return "No matching evidence found."

    header = (
        f"{'Rank':<5} | {'Score':<8} | {'Company':<15} | {'Year':<6} | "
        f"{'Page':<6} | {'Section':<25} | {'Chunk ID':<36} | {'Preview'}"
    )
    separator = "-" * 135
    rows = [header, separator]

    for res in results:
        page_str = str(res.page_start) if res.page_start is not None else "-"
        sec = (res.section[:22] + "...") if len(res.section) > 25 else res.section
        preview = res.text.replace("\n", " ").strip()
        preview = (preview[:47] + "...") if len(preview) > 50 else preview
        row = (
            f"{res.rank:<5} | {res.score:<8.4f} | {res.company[:15]:<15} | {res.year:<6} | "
            f"{page_str:<6} | {sec:<25} | {res.chunk_id:<36} | {preview}"
        )
        rows.append(row)

    return "\n".join(rows)


def run_cli() -> None:
    parser = argparse.ArgumentParser(
        description="Run hybrid retrieval and inspect ranked evidence."
    )
    parser.add_argument("--query", "-q", type=str, required=True, help="Search query string")
    parser.add_argument("--company", "-c", type=str, default=None, help="Filter by company name")
    parser.add_argument("--year", "-y", type=int, default=None, help="Filter by fiscal year")
    parser.add_argument(
        "--doc-type", type=str, default=None, help="Filter by document type (e.g. 10-K)"
    )
    parser.add_argument(
        "--dense-k", type=int, default=30, help="Dense top candidates (default 30)"
    )
    parser.add_argument(
        "--sparse-k", type=int, default=30, help="Sparse top candidates (default 30)"
    )
    parser.add_argument(
        "--fusion-k", type=int, default=20, help="RRF fused candidates (default 20)"
    )
    parser.add_argument(
        "--rerank-k", type=int, default=10, help="Final reranked candidates (default 10)"
    )
    parser.add_argument(
        "--qdrant-url", type=str, default=None, help="Qdrant URL (defaults to memory if omitted)"
    )
    parser.add_argument(
        "--collection", type=str, default=DEFAULT_COLLECTION, help="Collection name"
    )

    args = parser.parse_args()

    client = create_qdrant_client(url=args.qdrant_url, in_memory=(args.qdrant_url is None))
    dense_embedder = FastEmbedDenseEmbedder()
    sparse_embedder = BM25SparseEmbedder()
    reranker = FastEmbedReranker()

    ensure_collection(
        client, collection_name=args.collection, dense_dim=dense_embedder.dimension
    )

    dense_retriever = DenseRetriever(
        client=client, embedder=dense_embedder, collection_name=args.collection
    )
    sparse_retriever = SparseRetriever(
        client=client, embedder=sparse_embedder, collection_name=args.collection
    )

    config = RetrievalConfig(
        dense_k=args.dense_k,
        sparse_k=args.sparse_k,
        fusion_k=args.fusion_k,
        rerank_k=args.rerank_k,
    )

    hybrid = HybridRetriever(
        dense_retriever=dense_retriever,
        sparse_retriever=sparse_retriever,
        reranker=reranker,
        config=config,
    )

    filters: dict[str, Any] = {}
    if args.company:
        filters["company"] = args.company
    if args.year:
        filters["year"] = args.year
    if args.doc_type:
        filters["document_type"] = args.doc_type

    print(f"\nSearching for: '{args.query}' with filters: {filters}...\n")
    results, diagnostics = hybrid.retrieve(query=args.query, filters=filters)

    print(format_evidence_table(results))
    print("\nDiagnostics:")
    print(
        f"  Dense:  {diagnostics.dense_candidates_count} candidates in "
        f"{diagnostics.dense_latency_ms:.1f}ms"
    )
    print(
        f"  Sparse: {diagnostics.sparse_candidates_count} candidates in "
        f"{diagnostics.sparse_latency_ms:.1f}ms"
    )
    print(
        f"  Fusion: {diagnostics.fused_candidates_count} candidates in "
        f"{diagnostics.fusion_latency_ms:.1f}ms"
    )
    print(
        f"  Rerank: {diagnostics.reranked_candidates_count} candidates in "
        f"{diagnostics.rerank_latency_ms:.1f}ms"
    )
    print(f"  Total:  {diagnostics.total_latency_ms:.1f}ms\n")


if __name__ == "__main__":
    run_cli()
