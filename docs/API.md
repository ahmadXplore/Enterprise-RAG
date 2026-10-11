# Enterprise RAG — API Specification

Complete reference documentation for the Enterprise Document Intelligence & Agentic RAG Platform REST and Server-Sent Events (SSE) APIs.

---

## 1. Overview & Security Conventions

- **Base URL**: `http://localhost:8000` (or configured host)
- **Version Prefix**: `/api/v1`
- **Authentication**: Bearer JWT (`Authorization: Bearer <TOKEN>`) or `rag_access_token` HttpOnly cookie.
- **Roles & RBAC**:
  - `VIEWER`: Read-only access to authorized documents, search, chat, and query.
  - `ANALYST`: Query, search, view evaluation benchmarks, upload documents.
  - `ADMIN`: Full administrative control, user role management, system health, document permissions.
- **Pre-Retrieval Access Control**: All retrieval operations resolve user document access permissions prior to searching the vector index.
- **Response Format**: JSON (or `text/event-stream` for streaming endpoints).
- **Error Format**:
  ```json
  {
    "detail": {
      "code": "ERROR_CODE",
      "message": "Human-readable explanation",
      "details": {}
    }
  }
  ```

---

## 2. Health & Diagnostics Endpoints

### 2.1 Overall System Health
- **Endpoint**: `GET /health`
- **Auth**: None
- **Description**: Returns overall system readiness status and dependency states.
- **Response `200 OK`**:
  ```json
  {
    "status": "ok",
    "version": "0.1.0",
    "components": {
      "database": "connected",
      "redis": "connected",
      "qdrant": "connected",
      "llm": "ready"
    }
  }
  ```

### 2.2 Component Health Checks
- `GET /health/db` — Relational database connection check.
- `GET /health/redis` — Redis cache & rate-limiter check.
- `GET /health/qdrant` — Qdrant vector database connectivity & collection status.
- `GET /health/llm` — LLM provider connectivity & model readiness.

---

## 3. Authentication & User Management

### 3.1 Register User
- **Endpoint**: `POST /api/v1/auth/register`
- **Auth**: None
- **Request Body**:
  ```json
  {
    "email": "analyst@example.com",
    "password": "Password123!",
    "full_name": "Test Analyst"
  }
  ```
- **Response `201 Created`**:
  ```json
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "analyst@example.com",
    "full_name": "Test Analyst",
    "is_active": true,
    "roles": ["VIEWER"]
  }
  ```

### 3.2 Login
- **Endpoint**: `POST /api/v1/auth/login`
- **Auth**: None (Rate limited)
- **Request Body**:
  ```json
  {
    "email": "analyst@example.com",
    "password": "Password123!"
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "expires_in": 3600,
    "roles": ["VIEWER"]
  }
  ```
  *(Also sets `rag_access_token` HttpOnly cookie)*

### 3.3 Get Current User Profile
- **Endpoint**: `GET /api/v1/auth/me`
- **Auth**: Bearer JWT (`VIEWER`+)
- **Response `200 OK`**: Returns current authenticated user record.

### 3.4 User Administration
- **Endpoint**: `GET /api/v1/users`
- **Auth**: Bearer JWT (`ADMIN` only)
- **Description**: List registered users and their RBAC role assignments.

---

## 4. Document Management & Ingestion

### 4.1 List Documents
- **Endpoint**: `GET /api/v1/documents`
- **Auth**: Bearer JWT (`VIEWER`+)
- **Description**: Returns all documents that the current user has permission to access.

### 4.2 Get Document Details
- **Endpoint**: `GET /api/v1/documents/{document_id}`
- **Auth**: Bearer JWT (`VIEWER`+)
- **Description**: Returns metadata, chunk statistics, and processing status of a document.

### 4.3 Upload & Register Document
- **Endpoint**: `POST /api/v1/documents/upload`
- **Auth**: Bearer JWT (`ANALYST` or `ADMIN`)
- **Content-Type**: `multipart/form-data`
- **Form Fields**: `file` (File), `company` (string, optional), `year` (int, optional), `document_type` (string, optional).

### 4.4 Document Ingestion Status
- **Endpoint**: `GET /api/v1/ingestion/jobs/{job_id}`
- **Auth**: Bearer JWT (`ANALYST` or `ADMIN`)
- **Description**: Polls status of document parsing, chunking, and vector indexing (`queued` -> `parsing` -> `indexing` -> `completed` / `failed`).

---

## 5. Retrieval & Search

### 5.1 Hybrid Search
- **Endpoint**: `POST /api/v1/search`
- **Auth**: Bearer JWT (`VIEWER`+)
- **Request Body**:
  ```json
  {
    "query": "What were the primary revenue drivers in fiscal 2024?",
    "top_k": 5,
    "company": "Apple Inc.",
    "year": 2024
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "results": [
      {
        "chunk_id": "chunk_7f1c9d2b",
        "document_id": "doc_a1b2c3d4",
        "company": "Apple Inc.",
        "year": 2024,
        "section": "Item 7. Management's Discussion and Analysis",
        "content": "Net sales increased 2% or $7.7 billion during 2024 compared to 2023...",
        "dense_score": 0.824,
        "sparse_score": 14.21,
        "rrf_score": 0.0321
      }
    ],
    "total_retrieved": 5
  }
  ```

---

## 6. Agentic Query & Chat

### 6.1 Agentic RAG Query
- **Endpoint**: `POST /api/v1/query`
- **Auth**: Bearer JWT (`VIEWER`+)
- **Rate Limit**: 10 requests / min per user
- **Request Body**:
  ```json
  {
    "question": "What were Apple Inc. net sales in fiscal 2024?",
    "company": "Apple Inc.",
    "year": 2024
  }
  ```
- **Response `200 OK`**:
  ```json
  {
    "answer": "In fiscal year 2024, Apple Inc. reported total net sales of $391,035 million, compared to $383,285 million in 2023 [chunk_7f1c9d2b].",
    "citation_ids": ["chunk_7f1c9d2b"],
    "grounded": true,
    "abstained": false,
    "query_type": "DIRECT",
    "retrieval_attempts": 1
  }
  ```

### 6.2 Synchronous Chat
- **Endpoint**: `POST /api/v1/chat`
- **Auth**: Bearer JWT (`VIEWER`+)
- **Request Body**:
  ```json
  {
    "message": "Summarize key risk factors in Item 1A",
    "conversation_id": "conv_9e8f7a6b"
  }
  ```

### 6.3 Streaming Chat (Server-Sent Events)
- **Endpoint**: `POST /api/v1/chat/stream`
- **Auth**: Bearer JWT (`VIEWER`+)
- **Accept**: `text/event-stream`
- **Request Body**:
  ```json
  {
    "message": "Summarize key risk factors in Item 1A",
    "conversation_id": "conv_9e8f7a6b"
  }
  ```
- **Stream Event Lifecycle**:
  1. `event: query_started` — Initializing workflow.
  2. `event: query_classified` — Question typology (`DIRECT`, `TEMPORAL`, `COMPARISON`, `NUMERICAL`, `LEGAL`).
  3. `event: retrieval_started` — Commencing vector search.
  4. `event: retrieval_completed` — Retrieved candidate chunks.
  5. `event: reranking_completed` — Cross-encoder candidate ranking.
  6. `event: generation_started` — Commencing LLM answer synthesis.
  7. `event: token` — Individual streamed response tokens `{"delta": "..."}`.
  8. `event: citation` — Verified evidence chunk IDs `{"chunk_id": "..."}`.
  9. `event: completed` — Final answer payload and summary metrics.
  10. `event: error` — Error notification (if stream fails).

---

## 7. Evaluation & Benchmarks

### 7.1 Run Evaluation Suite
- **Endpoint**: `POST /api/v1/evaluations/run`
- **Auth**: Bearer JWT (`ANALYST` or `ADMIN`)
- **Request Body**:
  ```json
  {
    "test_dataset": "standard_benchmark_110",
    "configurations": ["hybrid_rrf", "reranked", "agentic"]
  }
  ```

### 7.2 Get Latest Evaluation Benchmark Results
- **Endpoint**: `GET /api/v1/evaluations/latest`
- **Auth**: Bearer JWT (`VIEWER`+)
- **Description**: Returns the latest empirical ablation study metrics (Recall@5, Recall@10, MRR, nDCG, Groundedness, Citation Accuracy).
