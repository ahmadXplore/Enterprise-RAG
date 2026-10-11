"""Clean previous SEC 10-K and legal data from SQLite database, Qdrant vector collection, and parsed cache."""
import os
import shutil
import sqlite3
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, r"d:\RAG\backend")
from apps.api.app.config import get_settings
from packages.retrieval.qdrant_client import create_qdrant_client
from qdrant_client.models import Distance, VectorParams, SparseVectorParams

DB_PATH = r"d:\RAG\enterprise_rag_dev.db"
PARSED_DIR = r"d:\RAG\data\parsed"

print("=" * 60)
print("CLEANING PREVIOUS CORPUS DATA (SEC 10-K & LEGAL DATASETS)")
print("=" * 60)

# 1. Clean SQLite database
if os.path.exists(DB_PATH):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    tables_to_clear = [
        "message_citations",
        "messages",
        "conversations",
        "retrieval_runs",
        "queries",
        "document_chunks",
        "document_sections",
        "document_access",
        "ingestion_jobs",
        "document_versions",
        "documents"
    ]
    
    print("\n[1/3] Clearing old document records from SQLite...")
    for table in tables_to_clear:
        try:
            cursor.execute(f"DELETE FROM {table};")
            print(f"  Cleared table: {table}")
        except Exception as e:
            print(f"  Note for table {table}: {e}")
            
    conn.commit()
    conn.close()
    print("  SQLite database document tables cleared successfully.")

# 2. Reset Qdrant Collection
print("\n[2/3] Resetting Qdrant vector collection 'enterprise_rag_chunks'...")
try:
    settings = get_settings()
    client = create_qdrant_client(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    
    # Check if collection exists
    collections = [c.name for c in client.get_collections().collections]
    if "enterprise_rag_chunks" in collections:
        client.delete_collection("enterprise_rag_chunks")
        print("  Deleted existing collection 'enterprise_rag_chunks'.")
        
    # Recreate collection with dense (384-dim for BGE / all-MiniLM-L6-v2) and sparse vectors (BM25)
    client.create_collection(
        collection_name="enterprise_rag_chunks",
        vectors_config={
            "dense": VectorParams(size=384, distance=Distance.COSINE)
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams()
        }
    )
    print("  Recreated clean collection 'enterprise_rag_chunks' (384-dim Cosine + BM25 sparse).")
except Exception as e:
    print(f"  [WARNING] Qdrant reset error: {e}")

# 3. Clean parsed artifacts cache
print("\n[3/3] Clearing data/parsed artifacts cache...")
if os.path.exists(PARSED_DIR):
    for item in os.listdir(PARSED_DIR):
        if item == ".gitkeep":
            continue
        p = os.path.join(PARSED_DIR, item)
        if os.path.isdir(p):
            shutil.rmtree(p)
        else:
            os.remove(p)
    print("  Cleared old parsed document cache in data/parsed.")

print("\n" + "=" * 60)
print("PREVIOUS CORPUS DATA REMOVAL COMPLETE")
print("=" * 60)
