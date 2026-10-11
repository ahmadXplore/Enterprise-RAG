"""CLI entrypoint for running benchmark evaluation."""
import argparse
from pathlib import Path

from packages.evaluation.dataset import load_benchmark_dataset
from packages.evaluation.runner import BenchmarkRunner
from packages.retrieval.dense import DenseRetriever
from packages.retrieval.embeddings import BM25SparseEmbedder, FastEmbedDenseEmbedder
from packages.retrieval.hybrid import HybridRetriever
from packages.retrieval.qdrant_client import (
    DEFAULT_COLLECTION,
    create_qdrant_client,
    ensure_collection,
)
from packages.retrieval.reranker import FastEmbedReranker
from packages.retrieval.sparse import SparseRetriever


def main() -> None:
    parser = argparse.ArgumentParser(description="Run retrieval evaluation benchmark suite.")
    parser.add_argument(
        "--config", "-c", type=str, default=None, help="Path to config file or custom dataset"
    )
    parser.add_argument(
        "--json-report", type=str, default="evaluation_report.json", help="Output JSON report path"
    )
    parser.add_argument(
        "--md-report", type=str, default="evaluation_report.md", help="Output Markdown report path"
    )
    parser.add_argument(
        "--qdrant-url", type=str, default=None, help="Qdrant URL (defaults to in-memory)"
    )
    parser.add_argument(
        "--collection", type=str, default=DEFAULT_COLLECTION, help="Qdrant collection name"
    )

    args = parser.parse_args()

    dataset_path = Path(args.config) if args.config else None
    cases = load_benchmark_dataset(dataset_path)

    print(f"Loaded {len(cases)} benchmark cases.")

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
    hybrid_retriever = HybridRetriever(
        dense_retriever=dense_retriever,
        sparse_retriever=sparse_retriever,
        reranker=reranker,
    )

    runner = BenchmarkRunner(
        dense_retriever=dense_retriever,
        sparse_retriever=sparse_retriever,
        hybrid_retriever=hybrid_retriever,
    )

    print("Running comparative benchmark across 4 pipelines...")
    results = runner.run_benchmark(cases)

    json_path = Path(args.json_report)
    md_path = Path(args.md_report)
    runner.save_reports(results, json_output_path=json_path, md_output_path=md_path)

    md_report = runner.generate_markdown_report(results)
    print("\n" + md_report)
    print(f"Reports saved to {json_path} and {md_path}")


if __name__ == "__main__":
    main()
