# TRD — Real-World Document Intelligence & Agentic RAG Platform

**Version:** 1.0  
**Architecture:** Modular monolith + background workers + vector database

---

# 1. Architecture

```text
                         ┌──────────────────────┐
                         │      Next.js UI      │
                         │ TypeScript / App     │
                         └──────────┬───────────┘
                                    │ HTTPS
                                    ▼
                         ┌──────────────────────┐
                         │      FastAPI         │
                         │ REST + Auth + SSE    │
                         └──────┬───────┬───────┘
                                │       │
                   ┌────────────┘       └─────────────┐
                   ▼                                  ▼
          ┌────────────────┐                  ┌────────────────┐
          │ PostgreSQL     │                  │ Redis          │
          │ metadata/auth  │                  │ queue/cache    │
          └────────────────┘                  └───────┬────────┘
                                                     │
                                                     ▼
                                            ┌──────────────────┐
                                            │ Celery Workers    │
                                            └────────┬─────────┘
                                                     │
                 ┌───────────────────────────────────┼─────────────────┐
                 ▼                                   ▼                 ▼
        ┌─────────────────┐                 ┌────────────────┐  ┌──────────────┐
        │ Docling         │                 │ Embedding      │  │ Evaluation   │
        │ Parsing         │                 │ + Chunking     │  │ Workers      │
        └────────┬────────┘                 └───────┬────────┘  └──────────────┘
                 │                                  │
                 ▼                                  ▼
        ┌─────────────────┐                ┌────────────────────┐
        │ Parsed artifacts│                │ Qdrant             │
        │ JSON/HTML/etc.  │                │ dense + sparse     │
        └─────────────────┘                └────────────────────┘

                           Query path
                                │
                                ▼
                       ┌──────────────────┐
                       │ LangGraph        │
                       │ query workflow   │
                       └────────┬─────────┘
                                │
                 ┌──────────────┼───────────────┐
                 ▼              ▼               ▼
              Filters       Retrieval       Calculator
                              │
                       Dense + Sparse
                              │
                              ▼
                           Reranker
                              │
                              ▼
                         Evidence Gate
                              │
                              ▼
                           LLM
                              │
                              ▼
                     Citation Validator
```

---

# 2. Architectural Principles

## 2.1 Separate source, parsed content and index

Never treat the vector database as the source of truth.

```text
Original file
    ↓
Parsed artifact
    ↓
Normalized document model
    ↓
Chunks
    ↓
Vector index
```

PostgreSQL stores authoritative metadata and relationships.

Qdrant stores retrieval representations.

---

# 3. Repository Structure

```text
enterprise-rag/
│
├── apps/
│   ├── api/
│   ├── worker/
│   └── web/
│
├── packages/
│   ├── schemas/
│   ├── retrieval/
│   ├── ingestion/
│   ├── evaluation/
│   └── llm/
│
├── data/
│   ├── raw/
│   ├── parsed/
│   ├── normalized/
│   └── evaluation/
│
├── infra/
│   ├── docker/
│   └── migrations/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── evaluation/
│
├── scripts/
├── notebooks/
├── docs/
├── .env.example
├── docker-compose.yml
└── README.md
```

---

# 4. Document Processing Pipeline

```text
Source Registration
        ↓
File Validation
        ↓
SHA-256 Hash
        ↓
Parser Selection
        ↓
Docling
        ↓
Structured Document
        ↓
Normalization
        ↓
Semantic Chunking
        ↓
Metadata Enrichment
        ↓
Embedding
        ↓
Sparse Index
        ↓
Qdrant
```

Docling should be the primary parser because it supports multiple formats and preserves structural information such as tables. citeturn2search1turn2search8

---

# 5. Normalized Document Model

Every parser must output the same internal representation.

```json
{
  "document_id": "uuid",
  "source_type": "sec_10k",
  "title": "...",
  "organization": "...",
  "report_year": 2025,
  "document_type": "annual_report",
  "sections": [],
  "pages": [],
  "tables": [],
  "source_uri": "...",
  "content_hash": "sha256..."
}
```

---

# 6. Chunking Strategy

Do not use only fixed-size character splitting.

Use hierarchical semantic chunking:

```text
Document
 └── Section
      └── Subsection
           ├── Paragraph chunk
           ├── Table chunk
           └── Adjacent context chunk
```

Each chunk should contain:

```text
chunk_id
document_id
section_id
page_start
page_end
heading_path
chunk_type
text
table_html
token_count
company
year
document_type
```

Recommended initial limits:

- target: 500–800 tokens
- overlap: 50–100 tokens
- table chunks: preserve table as a single logical unit when possible
- very large tables: split by row groups while preserving headers

These are initial parameters and must be evaluated rather than treated as universally optimal.

---

# 7. Embedding Strategy

Baseline:

```text
Dense:
all-MiniLM-L6-v2
384 dimensions
```

For each chunk:

```text
chunk text → dense embedding
```

Keep the embedding model configurable.

Do not hard-code model dimensions throughout the codebase.

---

# 8. Lexical Retrieval

Use:

- BM25
- exact phrase matching
- metadata filtering

For financial/legal corpora, exact terms matter:

```text
"revenue"
"operating income"
"Section 2.1"
"termination"
"indemnification"
"FY2024"
```

Qdrant supports sparse vectors and hybrid retrieval; RRF is suitable as the initial fusion method. citeturn0search3turn0search7

---

# 9. Retrieval Pipeline

```text
Query
 ↓
Query normalization
 ↓
Intent classification
 ↓
Metadata extraction
 ↓
Dense retrieval top 30
 ↓
Sparse/BM25 retrieval top 30
 ↓
RRF fusion top 20
 ↓
Reranker top 10
 ↓
Evidence coverage check
 ↓
Answer
```

Initial values:

```text
dense_k = 30
sparse_k = 30
fusion_k = 20
rerank_k = 10
```

Tune these using the evaluation dataset.

---

# 10. Query Types

```text
DIRECT
COMPARISON
TEMPORAL
NUMERICAL
LEGAL
CROSS_DOCUMENT
UNANSWERABLE
```

Example:

### Direct
“What was NVIDIA's revenue in 2024?”

### Comparison
“How did NVIDIA's revenue compare with AMD?”

### Temporal
“How did Apple's operating margin change from 2019 to 2025?”

### Legal
“Which contracts contain a change-of-control clause?”

### Unanswerable
“What was Apple's revenue in 2035?”

---

# 11. Numerical Reasoning

Do not ask the LLM to perform all arithmetic.

Use:

```text
retrieved values
      ↓
structured extraction
      ↓
Python calculator
      ↓
verified result
      ↓
LLM explanation
```

Example:

```text
2024 revenue = X
2025 revenue = Y

growth = ((Y - X) / X) * 100
```

The LLM should explain the calculation and cite the source values.

---

# 12. Agent Graph

Use LangGraph for orchestration.

```text
START
  ↓
resolve_access_scope (Backend security logic: Allowed document IDs)
  ↓
classify_query
  ↓
extract_constraints
  ↓
retrieve (Dense + Sparse constrained strictly to authorized documents)
  ↓
assess_evidence
  ├── insufficient → expand_query → retrieve (Authorized scope)
  ├── numerical → calculate (Sandboxed tool)
  ├── comparison → retrieve_comparison_set (Authorized scope)
  └── sufficient → generate
                         ↓
                  validate_citations
                         ↓
                       END
```

LangGraph persistence can checkpoint graph state and support resumable workflows. citeturn2search0

### Agent Tool Sandboxing Rule
LangGraph agents must only be provided with specific, allowlisted tools with validated Pydantic schemas. Agents must **never** have access to unrestricted tools like `execute_shell()`, `run_sql()`, `arbitrary_http_request()`, or `read_any_file()`.

---

# 13. LLM Provider Abstraction

Implement:

```python
class LLMProvider(Protocol):
    async def generate(...)
    async def stream(...)
```

Adapters:

```text
GroqProvider
OpenRouterProvider
OllamaProvider
```

Never make the application depend directly on one provider.

Groq documents OpenAI-compatible API access; OpenRouter exposes a unified model API; Ollama provides a local API. citeturn3search0turn3search4turn3search6

---

# 14. Prompt Architecture

System prompt:

- answer only from supplied evidence
- distinguish facts from calculations
- never fabricate citations
- if evidence is insufficient, abstain
- do not silently infer missing values

Context:

```text
[CITATION 1]
Document:
Company:
Year:
Section:
Page:
Chunk:
Evidence:
```

Answer schema:

```json
{
  "answer": "...",
  "citations": [
    {
      "chunk_id": "...",
      "document_id": "...",
      "page": 10
    }
  ],
  "grounded": true,
  "abstained": false
}
```

---

# 15. Citation Validation

Before returning the answer:

1. Extract citation IDs from model output.
2. Verify IDs exist in retrieved evidence.
3. Verify cited chunks were actually passed to the model.
4. Reject unknown citations.
5. Optionally run an evidence-support classifier.
6. Return validated citations only.

---

# 16. Security

## 16.1 Pre-Retrieval Authorization Architecture

```text
User
  ↓
Authentication
  ↓
Authorization
  ↓
Allowed document IDs / metadata scope
  ↓
Retriever
  ↓
Only authorized chunks
  ↓
Reranker
  ↓
LLM
  ↓
Citation validation
  ↓
Answer
```

### Critical Security Rule:
**The LLM should never be responsible for deciding whether a user is allowed to see a document. That's backend security logic.**

Anti-Pattern (Data Leak):
```text
User A
  ↓
Question
  ↓
Retriever
  ↓
❌ Retrieves a document User A isn't authorized to see
  ↓
LLM
  ↓
Data leaked
```

Pre-retrieval enforcement requirements:
1. Backend resolves authenticated user and authorization roles.
2. Backend queries PostgreSQL (`document_access` / `documents`) to obtain the exact list of `allowed_document_ids` for the user.
3. The retriever (both dense and sparse/BM25) MUST inject mandatory Qdrant payload filters restricting retrieval to the user's `allowed_document_ids`.
4. Only authorized chunks ever reach the reranker and LLM context window.
5. Document filtering must happen before retrieval results reach the LLM. Never rely on the frontend or LLM to enforce access control.

Authentication:

```text
JWT access token
refresh token
password hash
```

Authorization:

```text
ADMIN
ANALYST
VIEWER
```

## 16.2 Agent Tool Sandboxing & Allowlisting

LangGraph agents must **never** have unrestricted tools such as:
- `execute_shell()`
- `run_sql()`
- `arbitrary_http_request()`
- `read_any_file()`

Agents must strictly operate with specific, allowlisted tools with validated Pydantic input schemas:
- `retrieve_authorized_evidence`: Executes dense/sparse retrieval with non-overridable user authorization filters.
- `calculator`: Sandboxed arithmetic and financial computations with strict float/int validation.
- `document_metadata`: Read-only metadata queries bounded to authorized documents.

All tool inputs and outputs must be validated by Pydantic schemas. Unvalidated or arbitrary system/database access is strictly prohibited.

---

# 17. Database

PostgreSQL is the system of record.

Use:

- UUID primary keys
- timestamps
- JSONB for flexible parser metadata
- indexes on company/year/type
- GIN where appropriate
- PostgreSQL full-text search only as an auxiliary capability

PostgreSQL provides JSONB indexing and native full-text search capabilities. citeturn1search0turn1search4

---

# 18. Qdrant Collection

Collection:

```text
document_chunks
```

Payload:

```json
{
  "chunk_id": "...",
  "document_id": "...",
  "company": "Apple",
  "year": 2025,
  "document_type": "annual_report",
  "section": "Risk Factors",
  "page_start": 23,
  "page_end": 24,
  "chunk_type": "paragraph"
}
```

Vectors:

```text
dense
sparse
```

Advanced stage:

```text
multi-vector / late interaction reranking
```

Qdrant supports named vectors, sparse/dense combinations, RRF and multi-stage queries. citeturn0search3

---

# 19. Background Jobs

Jobs:

```text
register_document
parse_document
normalize_document
chunk_document
embed_document
index_document
reindex_document
run_evaluation
```

Every job needs:

```text
job_id
status
started_at
finished_at
error
retry_count
document_id
```

---

# 20. Observability

Track:

```text
request_id
user_id
query_id
retrieval_latency
embedding_latency
reranker_latency
llm_latency
total_latency
retrieved_count
reranked_count
citation_count
abstained
token_usage
provider
model
```

---

# 21. Testing

### Unit
- chunker
- metadata extraction
- citation validator
- query classifier
- access filter
- numerical calculator

### Integration
- API + PostgreSQL
- API + Qdrant
- ingestion + parser
- retrieval pipeline

### Evaluation
- retrieval metrics
- answer metrics
- citation metrics

---

# 22. Deployment

Development:

```text
Docker Compose
├── api
├── worker
├── postgres
├── redis
└── qdrant
```

Production:

```text
Next.js hosting
FastAPI hosting
managed PostgreSQL
managed Qdrant
managed Redis
external LLM provider
```

---

# 23. Engineering Constraint

Do not implement everything at once.

Build in this order:

```text
Data
→ Parser
→ Chunking
→ Retrieval
→ RAG
→ Evaluation
→ Agent
→ Auth
→ UI polish
→ Deployment
```

This order prevents building a beautiful frontend around an unvalidated retrieval system.
