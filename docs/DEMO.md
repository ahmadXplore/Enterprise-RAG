# Enterprise RAG — Demo Guide & Walkthrough

This guide walks through demonstrating the Enterprise RAG platform for presentations, code reviews, and portfolio demonstration.

---

## 1. Quick Demonstration Workflow

### Step 1: Start Infrastructure & API
```bash
# 1. Start Vector Store and Cache via Docker Compose
docker compose up -d

# 2. Start Backend API
uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Step 2: Health Checks Verification
Verify all services are healthy:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/db
curl http://localhost:8000/health/qdrant
curl http://localhost:8000/health/redis
curl http://localhost:8000/health/llm
```

---

## 2. Interactive Scenarios

### Scenario A: Authentication & RBAC
1. Register a test user:
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"analyst@example.com","password":"Password123!","full_name":"Test Analyst"}'
```
2. Login to acquire a JWT token:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"analyst@example.com","password":"Password123!"}'
```

### Scenario B: Pre-Retrieval Document Access Control
- Demonstrate that a user without assigned document permissions receives an immediate, safe abstention without invoking paid LLM tokens or searching restricted vector collections:
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"question":"What are the confidential severance terms?"}'
```
**Expected Response**:
```json
{
  "answer": "You do not have access to any documents. Please contact an administrator to request access.",
  "citation_ids": [],
  "grounded": false,
  "abstained": true,
  "query_type": "DIRECT"
}
```

### Scenario C: Hybrid Retrieval & Evidence Inspection
- Execute a hybrid search query with metadata filtering:
```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"query":"revenue growth and segment performance", "top_k": 5}'
```

### Scenario D: Streaming Agentic RAG with Live Progress
- Connect to SSE streaming endpoint `/api/v1/chat/stream`:
```bash
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"message":"Summarize the key risk factors in Item 1A"}'
```
Observe sequential Server-Sent Events:
- `query_started`
- `query_classified`
- `retrieval_started`
- `retrieval_completed`
- `reranking_completed`
- `generation_started`
- `token` chunks
- `citation` chunk IDs
- `completed` payload

---

## 3. Screenshots & Visual Assets
 
| View | Asset | Description & Key Components |
|:---|:---:|:---|
| **System Dashboard** | ![System Dashboard](screenshots/dashboard.png) | High-level corpus statistics (142 docs, 18.4k chunks), active ingestion job monitor, queries/hour & latency trends. |
| **Agentic Chat** | ![Agentic Chat](screenshots/chat_interface.png) | Multi-turn streaming chat, live pipeline step indicators (Classifier -> Extractor -> Retriever -> Reranker -> Validator), verified citation badges, groundedness score. |
| **Evidence Inspector** | ![Evidence Inspector](screenshots/evidence_viewer.png) | Document chunk viewer highlighting cited segments alongside dense score, sparse score, RRF fusion score, and cross-encoder score. |
| **Evaluation Study** | ![Evaluation Study](screenshots/evaluation_dashboard.png) | Empirical benchmark ablation study visualizer across 110 labeled test cases comparing 6 retrieval & agentic pipeline configurations. |


---

## 4. Video Recording Script (3-Minute Tour)

- **0:00 - 0:30**: Introduction & Architecture overview (Pre-retrieval security, dual dense/sparse vector search).
- **0:30 - 1:15**: Document Ingestion demo (Deduplication, normalization, chunk indexing in Qdrant).
- **1:15 - 2:00**: Live Agentic Query (SSE streaming, evidence retrieval, citation validation).
- **2:00 - 2:40**: Evaluation & Ablation results (Presenting the 6-pipeline comparison report and metrics).
- **2:40 - 3:00**: Reliability hardening & concluding highlights.
