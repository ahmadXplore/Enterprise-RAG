# BACKEND SCHEMA — FastAPI + LangGraph

## 1. Backend Responsibilities

The backend provides:

- authentication
- authorization
- document management
- ingestion jobs
- search
- RAG
- agent orchestration
- citations
- evaluation
- observability

---

# 2. Backend Structure

```text
apps/api/
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── api/
│   │   ├── deps.py
│   │   └── routes/
│   │       ├── auth.py
│   │       ├── users.py
│   │       ├── documents.py
│   │       ├── ingestion.py
│   │       ├── search.py
│   │       ├── chat.py
│   │       ├── evaluations.py
│   │       └── health.py
│   │
│   ├── core/
│   │   ├── security.py
│   │   ├── logging.py
│   │   └── exceptions.py
│   │
│   ├── models/
│   ├── schemas/
│   ├── repositories/
│   ├── services/
│   ├── retrieval/
│   ├── agents/
│   ├── llm/
│   └── workers/
│
└── tests/
```

---

# 3. API Versioning

Base:

```text
/api/v1
```

---

# 4. Authentication API

## POST /auth/register

Request:

```json
{
  "email": "user@example.com",
  "password": "********",
  "full_name": "User"
}
```

Response:

```json
{
  "user": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "User"
  }
}
```

---

## POST /auth/login

Response:

```json
{
  "access_token": "...",
  "token_type": "bearer"
}
```

---

## GET /auth/me

Returns authenticated user and roles.

---

# 5. Documents API

## GET /documents

Filters:

```text
company
year
document_type
status
page
page_size
```

---

## GET /documents/{document_id}

Returns:

```json
{
  "id": "...",
  "title": "...",
  "organization": "...",
  "report_year": 2025,
  "document_type": "annual_report",
  "status": "ready",
  "page_count": 320,
  "chunk_count": 1200
}
```

---

## POST /documents

Creates/registers a document.

---

## DELETE /documents/{document_id}

Admin-only.

Deletion must:

1. remove/revoke access
2. remove vector points
3. mark/delete DB records according to retention policy
4. record audit event

---

# 6. Ingestion API

## POST /documents/{document_id}/ingest

Returns:

```json
{
  "job_id": "uuid",
  "status": "queued"
}
```

---

## GET /ingestion/jobs/{job_id}

Returns:

```json
{
  "job_id": "...",
  "status": "running",
  "progress": 64,
  "stage": "embedding"
}
```

Stages:

```text
validation
parsing
normalization
chunking
embedding
indexing
completed
```

---

# 7. Search API

## POST /search

Request:

```json
{
  "query": "What was Apple's revenue in 2025?",
  "filters": {
    "companies": ["Apple"],
    "years": [2025]
  },
  "top_k": 10
}
```

Response:

```json
{
  "query_id": "...",
  "results": [
    {
      "chunk_id": "...",
      "document_id": "...",
      "score": 0.91,
      "text": "...",
      "company": "Apple",
      "year": 2025,
      "page": 12
    }
  ]
}
```

---

# 8. Chat API

## POST /chat

Request:

```json
{
  "conversation_id": "uuid",
  "message": "Compare Apple's revenue in 2024 and 2025."
}
```

Response:

```json
{
  "message_id": "...",
  "answer": "...",
  "grounded": true,
  "abstained": false,
  "citations": []
}
```

---

# 9. Streaming Chat

## POST /chat/stream

Use Server-Sent Events.

Events:

```text
query_started
query_classified
retrieval_started
retrieval_completed
reranking_completed
generation_started
token
citation
completed
error
```

Do not stream hidden reasoning.

---

# 10. Query State Schema

```python
class QueryState(TypedDict):
    query_id: str
    user_id: str
    raw_query: str
    normalized_query: str
    query_type: str
    filters: dict
    retrieval_candidates: list
    reranked_evidence: list
    calculations: list
    draft_answer: str | None
    citations: list
    grounded: bool
    abstained: bool
    errors: list
```

---

# 11. LangGraph Nodes

```text
resolve_access_scope (Backend security: resolve allowed document IDs from DB)
classify_query
extract_constraints
apply_access_filter (Merges security constraints into retrieval filters)
retrieve_dense (Constrained to allowed_document_ids)
retrieve_sparse (Constrained to allowed_document_ids)
fuse_results (RRF)
rerank
assess_evidence
expand_query
retrieve_comparison (Constrained to allowed_document_ids)
calculate (Allowlisted sandboxed tool)
generate (Receives ONLY authorized chunks)
validate_citations
finalize
```

Conditional routing:

```text
assess_evidence
    ├── insufficient → expand_query
    ├── numerical → calculate
    ├── comparison → retrieve_comparison
    └── sufficient → generate
```

---

# 12. Retrieval Service Interface

```python
class Retriever(Protocol):
    async def retrieve(
        self,
        query: str,
        filters: dict,
        top_k: int
    ) -> list[RetrievalResult]:
        ...
```

Implement:

```text
DenseRetriever
SparseRetriever
HybridRetriever
Reranker
```

---

# 13. RRF Interface

```python
class RankFusion:
    def fuse(
        self,
        dense_results,
        sparse_results
    ) -> list[RetrievalResult]:
        ...
```

Initial implementation:

```text
RRF
```

Later:

```text
weighted RRF
```

Tune weights only after evaluation.

---

# 14. LLM Service

```python
class LLMProvider(Protocol):
    async def generate(
        self,
        messages: list,
        response_schema: dict | None = None
    ) -> dict:
        ...

    async def stream(
        self,
        messages: list
    ):
        ...
```

Adapters:

```text
GroqProvider
OpenRouterProvider
OllamaProvider
```

---

# 15. Structured Generation

The LLM should return a validated schema:

```json
{
  "answer": "string",
  "citation_ids": ["chunk-id"],
  "grounded": true,
  "abstained": false
}
```

The backend must validate it before returning it.

---

# 16. Citation Service

Responsibilities:

```text
resolve citation IDs
verify retrieved evidence
attach metadata
reject unknown IDs
calculate citation coverage
```

Interface:

```python
class CitationValidator:
    async def validate(
        self,
        citations,
        retrieved_chunks
    ) -> CitationValidationResult:
        ...
```

---

# 17. Numerical Service

Allowed operations:

```text
add
subtract
multiply
divide
percentage_change
ratio
difference
average
sum
```

Input:

```json
{
  "operation": "percentage_change",
  "old": 100,
  "new": 120
}
```

Output:

```json
{
  "result": 20.0,
  "unit": "percent"
}
```

Every calculation must retain source chunk references.

---

# 18. Evaluation API

## POST /evaluations/runs

Start an evaluation.

## GET /evaluations/runs/{id}

Return:

```json
{
  "status": "completed",
  "metrics": {
    "recall_at_5": 0.82,
    "mrr": 0.76,
    "ndcg_at_10": 0.79,
    "groundedness": 0.91,
    "citation_accuracy": 0.95
  }
}
```

Values above are schema examples, not expected project results.

---

# 19. Health APIs

```text
GET /health
GET /health/db
GET /health/qdrant
GET /health/redis
GET /health/llm
```

---

# 20. Error Model

Standard response:

```json
{
  "error": {
    "code": "RETRIEVAL_UNAVAILABLE",
    "message": "Retrieval service is temporarily unavailable.",
    "request_id": "uuid"
  }
}
```

Never expose:

- stack traces
- API keys
- database credentials
- internal prompts
- hidden reasoning

---

# 21. Configuration

Environment variables:

```text
APP_ENV
DATABASE_URL
REDIS_URL
QDRANT_URL
QDRANT_API_KEY

JWT_SECRET
JWT_EXPIRE_MINUTES

LLM_PROVIDER
LLM_MODEL
GROQ_API_KEY
OPENROUTER_API_KEY

EMBEDDING_MODEL
RERANKER_MODEL

LOG_LEVEL
OTEL_EXPORTER_OTLP_ENDPOINT
```

Only required provider keys should be mandatory.

---

# 22. Backend Testing

### Unit
```text
test_chunking
test_rrf
test_filters
test_citation_validation
test_calculator
test_query_classifier
```

### Integration
```text
test_auth_flow
test_document_ingestion
test_search
test_chat
test_qdrant_integration
```

### Security
```text
test_viewer_cannot_ingest
test_user_cannot_access_restricted_document
test_admin_routes
```

---

# 23. API Documentation

FastAPI should expose OpenAPI documentation.

Every endpoint needs:

- request model
- response model
- status codes
- error schema
- authentication requirements
- examples

---

# 24. Backend Implementation Rule

Do not put retrieval logic inside route functions.

Bad:

```text
route → Qdrant → LLM → response
```

Good:

```text
route
 ↓
service
 ↓
agent/retrieval layer
 ↓
repository/provider
```

---

# 25. Pre-Retrieval Authorization Enforcement

The architecture strictly enforces pre-retrieval access control:

```text
User
 ↓
Authentication (JWT verification)
 ↓
Authorization (RBAC & Document Access queries)
 ↓
Allowed document IDs / metadata scope
 ↓
Retriever (Qdrant filter: document_id IN allowed_document_ids)
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

Enforcement details:
- Authorization resolution occurs strictly prior to invoking vector/lexical retrieval.
- PostgreSQL `document_access` and `user_roles` determine the set of accessible `document_id`s.
- This filter is non-overridable and is injected directly into retrieval query parameters.
- If a user has no access to any documents matching the query filters, retrieval yields 0 results and the system abstains without querying the LLM with sensitive context.

---

# 26. Agent Tool Allowlisting & Sandboxing

LangGraph agents must **never** be equipped with unrestricted or dangerous tools such as:
- `execute_shell()`
- `run_sql()`
- `arbitrary_http_request()`
- `read_any_file()`

Agents must strictly operate using an explicit allowlist of tools with validated Pydantic schemas:

1. `retrieve_authorized_evidence`:
   - Validated input schema specifying search query and optional user filters.
   - Automatically binds `allowed_document_ids` from query state; cannot be overridden by agent or user.
2. `execute_calculation`:
   - Validated input schema specifying `operation` (e.g., `percentage_change`, `add`, `subtract`, `ratio`) and operand numbers.
   - Deterministic execution in Python sandbox.
3. `get_document_metadata`:
   - Validated input schema specifying `document_id`.
   - Rejects IDs outside of the user's authorized document scope.

All tool inputs and returns are strictly typed. Any execution outside this allowlist is forbidden.
