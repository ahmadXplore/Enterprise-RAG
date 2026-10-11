# PRD — Real-World Document Intelligence & RAG Platform

**Version:** 1.0  
**Status:** Build specification  
**Primary goal:** Build a production-style RAG system over real financial filings and legal contracts, with structure-aware ingestion, hybrid retrieval, reranking, grounded answers, citations, access control, evaluation, observability, and an agentic query workflow.

---

## 1. Product Summary

The product is a web-based **Document Intelligence & Retrieval-Augmented Generation platform** for asking questions over a heterogeneous corpus of real-world documents.

Initial corpus:

- 80 annual reports / 10-K filings:
  - 10 companies
  - fiscal/report years 2018–2025
- 25–50 CUAD commercial contracts
- DocLayNet is **not required for the first implementation**. It is a later benchmark/evaluation corpus for layout-heavy documents.

The product must not be presented as a simple “PDF chatbot.” Its purpose is to demonstrate an AI-engineering pipeline:

**ingestion → structure-aware parsing → normalization → semantic/lexical indexing → hybrid retrieval → reranking → query planning → grounded generation → citation validation → evaluation → observability**

---

## 2. Problem

Traditional document chat systems often flatten documents into plain text and perform a single vector search. This causes problems with:

- tables and financial figures
- headings and section hierarchy
- exact terminology and identifiers
- page/section provenance
- cross-document comparisons
- temporal filtering
- legal clause retrieval
- ambiguous queries
- unsupported questions
- hallucinated answers
- duplicate or obsolete document versions
- access restrictions
- measuring retrieval quality

The system therefore needs to preserve document structure and provenance while supporting multiple retrieval strategies.

---

## 3. Goals

### G1 — Reliable ingestion
Ingest HTML, PDF and other supported source formats without destroying structure.

### G2 — Structure preservation
Preserve:

- document
- page
- section
- heading
- paragraph
- table
- table row/cell
- figure/image metadata where available
- source URL
- filing/report year
- company
- document type
- contract metadata
- character/token offsets where available

### G3 — Hybrid retrieval
Use at least:

1. dense semantic retrieval
2. lexical/BM25 retrieval
3. rank fusion
4. reranking

Qdrant supports dense/sparse hybrid retrieval and multi-stage reranking; this architecture is therefore appropriate for the project. citeturn0search0turn0search3

### G4 — Grounded generation
The answer must be generated from retrieved evidence rather than from unsupported model knowledge.

### G5 — Citations
Every factual answer generated from the corpus must expose source citations containing enough information to locate the evidence.

### G6 — Abstention
If evidence is insufficient, the system must say that the available documents do not provide enough evidence.

### G7 — Cross-document reasoning
Support queries such as:

- compare revenue across two companies
- compare annual reports across years
- identify changes over time
- find clauses across contracts
- compare the same metric across companies

### G8 — Evaluation
Measure retrieval and answer quality with a manually curated evaluation set.

### G9 — Production-style engineering
Include:

- typed API contracts
- database migrations
- authentication
- RBAC
- structured logs
- tracing/metrics
- background jobs
- tests
- configuration management
- reproducible ingestion
- evaluation reports

---

## 4. Non-Goals

The first release will not attempt to:

- train a foundation model
- fine-tune an LLM
- ingest the entire SEC database
- ingest every possible document format
- build a general-purpose web search engine
- automatically crawl arbitrary websites
- guarantee legal or financial advice
- replace professional legal/accounting review
- require DocLayNet before the core system works

---

## 5. Users

### Admin
Can:

- upload/register documents
- trigger ingestion
- inspect ingestion failures
- manage users
- manage document access
- view system metrics
- run evaluations

### Analyst
Can:

- search documents
- ask questions
- filter by company/year/type
- inspect citations
- compare documents
- view retrieved evidence

### Viewer
Can:

- search permitted documents
- ask questions against permitted documents
- view citations

Viewer cannot manage ingestion or users.

---

## 6. Core Features

### F1 — Document Library
Display:

- company
- title
- document type
- fiscal/report year
- source
- status
- page count
- chunk count
- ingestion timestamp

### F2 — Advanced Filters

Filters:

- company
- year
- document type
- source
- access scope
- ingestion status

### F3 — Search
Support:

- natural-language search
- exact phrase search
- identifiers
- financial terms
- legal clauses
- semantic concepts

### F4 — RAG Chat
The user asks a question and receives:

- answer
- citations
- evidence snippets
- confidence/grounding state
- optional retrieval diagnostics

### F5 — Comparison
Support:

- company vs company
- year vs year
- document vs document
- contract vs contract

### F6 — Citation Viewer
A citation should show:

- document
- page/section if available
- source type
- exact evidence excerpt
- chunk ID
- source location

### F7 — Query Planning
The system classifies queries into:

- direct lookup
- semantic search
- comparison
- temporal
- aggregation/numerical
- legal clause
- unanswerable/insufficient evidence

### F8 — Agentic RAG
Use an agent graph only where multi-step reasoning is beneficial.

Example:

1. classify query
2. extract constraints
3. retrieve
4. check evidence coverage
5. retrieve again if needed
6. calculate/compare if required
7. generate answer
8. validate citations
9. return

LangGraph is appropriate for this orchestration because its persistence/checkpoint model supports resumable, stateful workflows. citeturn2search0turn2search11

### F9 — Evaluation Dashboard
Display:

- Recall@K
- MRR
- nDCG@K
- answer relevance
- faithfulness/groundedness
- citation correctness
- abstention accuracy
- latency
- token usage/cost where available

---

## 7. Functional Requirements

### FR-01
The system shall register each source document with a stable document ID.

### FR-02
The system shall compute a content hash to prevent accidental duplicate ingestion.

### FR-03
The system shall preserve original files separately from parsed artifacts.

### FR-04
The system shall store parser output in a lossless/structured representation where possible.

### FR-05
The system shall create chunks with deterministic IDs.

### FR-06
Each chunk shall retain provenance.

### FR-07
The retrieval system shall support metadata filtering.

### FR-08
The retrieval pipeline shall combine dense and lexical retrieval.

### FR-09
The retrieval pipeline shall support reranking.

### FR-10
The answer generator shall receive retrieved evidence and citation metadata.

### FR-11
The answer generator shall not invent citations.

### FR-12
The system shall validate that returned citations correspond to retrieved evidence.

### FR-13
The system shall support “insufficient evidence” responses.

### FR-14
The system shall log retrieval and generation traces.

### FR-15
The system shall support evaluation datasets independent of production queries.

---

## 8. Non-Functional Requirements

### Reliability
- deterministic ingestion
- retryable jobs
- idempotent indexing
- clear failure states

### Performance
Initial target:

- search: < 2 seconds excluding slow external LLM generation where possible
- first token: target < 5 seconds
- standard RAG response: target < 10 seconds

These are engineering targets, not guaranteed SLAs.

### Security
- API keys only through environment variables
- password hashing
- JWT/session authentication
- RBAC (ADMIN, ANALYST, VIEWER)
- **Pre-retrieval authorization enforcement**:
  - Authentication -> Authorization -> Resolve allowed document IDs / metadata scope -> Retriever -> Only authorized chunks -> Reranker -> LLM -> Citation validation -> Answer
  - **The LLM should never be responsible for deciding whether a user is allowed to see a document.** Access control is backend security logic enforced strictly before retrieval to prevent data leakage.
- **Agent tool sandboxing & allowlisting**:
  - LangGraph agents must never have unrestricted execution tools (e.g., `execute_shell()`, `run_sql()`, `arbitrary_http_request()`, `read_any_file()`).
  - Agents must strictly operate with specific, allowlisted tools with strongly typed, validated inputs.
- no secrets in source control
- audit logging for privileged actions

### Maintainability
- modular backend
- typed schemas
- migrations
- tests
- clear service boundaries

---

## 9. Success Criteria

The project is considered complete when:

1. All selected documents ingest successfully or have a documented failure reason.
2. Duplicate ingestion is prevented.
3. Structure and provenance survive parsing.
4. Hybrid retrieval beats at least one single-retriever baseline on the evaluation set.
5. Reranking improves or meaningfully changes retrieval quality on evaluated queries.
6. Answers contain verifiable citations.
7. Unsupported questions trigger abstention.
8. Cross-document and temporal queries work.
9. Evaluation results are reproducible.
10. The entire system can be demonstrated from a clean setup.

---

## 10. Recommended Product Positioning

Use:

> **Real-World Document Intelligence & Agentic RAG Platform**

Avoid:

> PDF Chatbot

The portfolio story should emphasize:

- document intelligence
- retrieval engineering
- agentic workflows
- evaluation
- grounding
- citations
- production architecture

---

## 11. Recommended Stack

### Frontend
- Next.js
- TypeScript
- App Router
- Tailwind CSS
- shadcn/ui
- TanStack Query
- Recharts

Next.js is a React framework with App Router support and is suitable for the interactive dashboard/application layer. citeturn0search2

### Backend
- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- pytest

FastAPI is strongly typed through Pydantic and can expose validated API schemas automatically. citeturn2search14

### Parsing
Primary:
- Docling

Fallback:
- Unstructured
- BeautifulSoup/lxml for targeted HTML cleanup

Docling supports HTML and advanced PDF understanding, including layout and tables, and can export structured JSON/HTML/Markdown/DocTags. citeturn2search8turn2search18

### Database
- PostgreSQL

Use PostgreSQL for:

- users
- roles
- documents
- metadata
- chunks
- ingestion jobs
- queries
- conversations
- citations
- evaluations
- audit logs

PostgreSQL supports JSONB and GIN indexing, plus native full-text search. citeturn1search0turn1search11

### Vector Search
- Qdrant

Use:

- dense vectors
- sparse/BM25-style retrieval
- metadata filters
- RRF
- reranking/multi-stage retrieval

Qdrant explicitly supports dense+sparse hybrid queries and multi-stage reranking. citeturn0search0turn0search3

### Orchestration
- LangGraph

### LLM
Provider abstraction:

1. Groq
2. OpenRouter
3. Ollama for local development/fallback

Groq exposes an OpenAI-compatible API, while OpenRouter provides a unified model API. Ollama exposes a local API for local-model development. citeturn3search0turn3search4turn3search6

### Embeddings
Start with:

- `sentence-transformers/all-MiniLM-L6-v2` for a lightweight dense baseline

Then benchmark a stronger embedding model if resources allow.

### Reranker
Start with a cross-encoder/reranker over top 20–50 candidates.

Use ColBERT/late interaction only as an advanced optimization after the baseline is measured.

### Background jobs
- Redis
- Celery

Use for:

- ingestion
- parsing
- chunking
- embedding
- indexing
- evaluation jobs

### Observability
- OpenTelemetry
- structured JSON logging
- LangSmith optional
- Prometheus/Grafana optional

---

## 12. Data Strategy

### Phase-1 Corpus

Financial:
- 80 annual reports / 10-Ks

Legal:
- 25–50 CUAD contracts

Layout benchmark:
- DocLayNet later

Do not block the core project on DocLayNet.

---

## 13. Main Product Flow

```text
User
  ↓
Next.js UI
  ↓
FastAPI (Authentication & Authorization)
  ↓
Resolve Allowed Document IDs / Scopes (Backend Security Logic)
  ↓
LangGraph Query Workflow (Allowlisted Tools Only)
  ↓
Query Classification
  ↓
Metadata / Filter Extraction (Merged with Allowed Security Scope)
  ↓
Dense Retrieval ─┐ (Filters strictly enforce authorized document IDs)
                  ├─→ Fusion → Reranker → Evidence Check
Lexical Retrieval┘
        ↓
Allowlisted Tools (e.g., Numerical / Comparison with validated schemas)
        ↓
Grounded LLM (Receives ONLY authorized chunks)
        ↓
Citation Validation
        ↓
Response
```

---

## 14. Risk Register

| Risk | Mitigation |
|---|---|
| Poor parsing | Parser validation + fallback |
| Table corruption | Preserve structured table representation |
| Hallucination | Evidence-only prompting + citation validation |
| Retrieval misses | Hybrid search + query expansion |
| Duplicate documents | Hash + source identifiers |
| Large ingestion time | Background workers |
| API limits | provider abstraction + retries |
| Weak evaluation | manually curated benchmark |
| Over-engineering | implement phases sequentially |
| Local hardware limits | use Colab/cloud for ingestion and external LLM APIs |

---

## 15. Definition of Done

A feature is done only when it has:

- implementation
- API schema
- validation
- tests
- logging
- error handling
- documentation
- UI integration where applicable
- evaluation if it affects retrieval/generation quality
