# APP FLOW DIAGRAM — Real-World Document Intelligence & Agentic RAG Platform

## 1. High-Level Application Flow

```mermaid
flowchart TD
    A[User Opens Application] --> B[Login / Authenticate]
    B --> C{Authorize Role}
    C -->|Admin| D[Admin Dashboard]
    C -->|Analyst| E[Analyst Workspace]
    C -->|Viewer| F[Viewer Workspace]

    D --> G[Document Library]
    D --> H[Ingestion Jobs]
    D --> I[Evaluation Dashboard]
    D --> J[User & Access Management]

    E --> K[Search / Ask]
    F --> K

    K --> L[Query API]
    L --> SEC[Backend Auth Logic: Resolve Allowed Document IDs]
    SEC --> M[LangGraph Query Workflow: Sandboxed & Allowlisted Tools Only]

    M --> N[Classify Query]
    N --> O[Extract Constraints & Bind Allowed Document Scope]

    O --> Q[Dense Retrieval: Filtered to Allowed Document IDs]
    O --> R[Lexical Retrieval: Filtered to Allowed Document IDs]

    Q --> S[RRF Fusion]
    R --> S

    S --> T[Reranker]
    T --> U{Enough Evidence?}

    U -->|No| V[Query Expansion / Second Retrieval: Scoped]
    V --> Q

    U -->|Yes| W{Query Type}
    W -->|Numerical| X[Sandboxed Calculator: Validated Inputs]
    W -->|Comparison| Y[Multi-document Retrieval: Scoped]
    W -->|Normal| Z[Grounded Generation: Receives Only Authorized Chunks]

    X --> Z
    Y --> Z

    Z --> AA[Citation Validation]
    AA --> AB{Valid?}

    AB -->|No| AC[Regenerate / Repair]
    AC --> AA

    AB -->|Yes| AD[Response]
    AD --> AE[Answer + Citations + Evidence]

    AE --> AF[Conversation History]
```

---

# 2. Document Ingestion Flow

```mermaid
flowchart TD
    A[Admin Uploads / Registers Document]
    A --> B[Validate File]
    B --> C[Calculate SHA-256]
    C --> D{Duplicate?}

    D -->|Yes| E[Return Existing Document]
    D -->|No| F[Create Document Record]

    F --> G[Create Ingestion Job]
    G --> H[Queue Worker]
    H --> I[Parser Selection]

    I --> J[Docling]
    J --> K{Parsing Successful?}

    K -->|No| L[Fallback Parser]
    L --> M{Fallback Successful?}
    M -->|No| N[Mark Failed + Store Error]
    M -->|Yes| O[Normalize]
    K -->|Yes| O[Normalize]

    O --> P[Extract Structure]
    P --> Q[Extract Metadata]
    Q --> R[Semantic Chunking]
    R --> S[Generate Embeddings]
    S --> T[Generate Sparse Representation]
    T --> U[Index Qdrant]
    U --> V[Mark Document Ready]
```

---

# 3. Search Flow

```mermaid
sequenceDiagram
    participant U as User
    participant W as Web
    participant API as FastAPI
    participant PG as PostgreSQL
    participant G as LangGraph
    participant Q as Qdrant
    participant R as Reranker
    participant L as LLM

    U->>W: Enter question
    W->>API: POST /queries (Bearer token)
    Note over API,PG: Backend Security Logic (Pre-Retrieval)
    API->>PG: Authenticate user & fetch allowed_document_ids
    PG-->>API: Allowed document IDs list
    API->>G: Start workflow (passes query + non-overridable allowed_document_ids)

    Note over G,Q: Retrieval strictly filtered by allowed_document_ids
    G->>Q: Dense retrieval (payload filter: doc_id IN allowed_document_ids)
    G->>Q: Sparse retrieval (payload filter: doc_id IN allowed_document_ids)
    Q-->>G: Authorized candidate chunks ONLY

    G->>G: RRF fusion
    G->>R: Rerank authorized candidates
    R-->>G: Ranked authorized evidence

    G->>G: Evidence check

    alt Evidence insufficient
        G->>Q: Expanded retrieval (strictly authorized scope)
        Q-->>G: Additional authorized evidence
    end

    Note over G,L: LLM receives ONLY authorized chunks (LLM never decides access)
    G->>L: Grounded prompt + authorized evidence
    L-->>G: Draft answer + citation IDs

    G->>G: Validate citations against retrieved authorized evidence
    G-->>API: Validated response
    API-->>W: Stream response
    W-->>U: Answer + citations
```

---

# 4. Numerical Question Flow

```mermaid
flowchart TD
    A[Question] --> B[Query Classifier]
    B --> C[Numerical Query]
    C --> D[Retrieve Source Values]
    D --> E[Validate Units / Periods]
    E --> F[Python Calculator]
    F --> G[Calculated Result]
    G --> H[LLM Explanation]
    H --> I[Citation Validation]
    I --> J[Final Answer]
```

The model should not be the authoritative calculator.

---

# 5. Comparison Flow

```mermaid
flowchart TD
    A[Comparison Query]
    A --> B[Extract Entities]
    B --> C[Extract Metric]
    C --> D[Extract Time Period]
    D --> E[Create Retrieval Subqueries]

    E --> F[Entity A Retrieval]
    E --> G[Entity B Retrieval]

    F --> H[Normalize Evidence]
    G --> H

    H --> I[Structured Comparison]
    I --> J[Optional Calculation]
    J --> K[Grounded Generation]
    K --> L[Citation Validation]
    L --> M[Comparison Response]
```

---

# 6. Legal Contract Flow

```mermaid
flowchart TD
    A[Legal Query] --> B[Identify Clause Type]
    B --> C[Metadata Filter]
    C --> D[Lexical Retrieval]
    C --> E[Dense Retrieval]
    D --> F[Fusion]
    E --> F
    F --> G[Reranker]
    G --> H[Clause Evidence]
    H --> I[Grounded Answer]
    I --> J[Citations]
```

---

# 7. Admin Ingestion UI Flow

```text
Admin Dashboard
      ↓
Documents
      ↓
Add Document
      ↓
Select source type
      ↓
Upload / register source
      ↓
Validate metadata
      ↓
Start ingestion
      ↓
Job status
      ↓
Parsing
      ↓
Chunking
      ↓
Embedding
      ↓
Indexing
      ↓
Ready
```

---

# 8. Evaluation Flow

```mermaid
flowchart TD
    A[Evaluation Dataset] --> B[Run Retrieval]
    B --> C[Calculate Recall@K]
    B --> D[Calculate MRR]
    B --> E[Calculate nDCG]

    B --> F[Generate Answers]
    F --> G[Groundedness Evaluation]
    F --> H[Answer Relevance]
    F --> I[Citation Accuracy]
    F --> J[Abstention Accuracy]

    C --> K[Evaluation Report]
    D --> K
    E --> K
    G --> K
    H --> K
    I --> K
    J --> K

    K --> L[Dashboard]
```

---

# 9. Failure Flow

```mermaid
flowchart TD
    A[Request] --> B{Authenticated?}
    B -->|No| C[401]
    B -->|Yes| D{Authorized?}
    D -->|No| E[403]
    D -->|Yes| F[Run Query]

    F --> G{Retrieval Error?}
    G -->|Yes| H[Retry / Fallback]
    H --> I{Recovered?}
    I -->|No| J[Controlled Error]

    G -->|No| K{Evidence Available?}
    K -->|No| L[Abstain]
    K -->|Yes| M[Generate]

    M --> N{Citation Valid?}
    N -->|No| O[Repair / Regenerate]
    N -->|Yes| P[Return]
```

---

# 10. UX Principle

The primary screen should make the system's reasoning traceable:

```text
Question
   ↓
Answer
   ↓
Sources
   ↓
Evidence
   ↓
Document
   ↓
Page / Section
```

Do not expose hidden chain-of-thought. Expose concise, auditable retrieval information only:

- query type
- filters
- number of retrieved candidates
- selected sources
- citations
- latency

---

# 11. Main Screens

```text
/login
/dashboard
/search
/chat
/documents
/documents/[id]
/documents/[id]/preview
/evaluations
/evaluations/[id]
/admin/users
/admin/jobs
/settings
```

---

# 12. Security Enforcement & Tool Sandboxing Flow

## 12.1 Pre-Retrieval Authorization vs. Data Leak Anti-Pattern

### ❌ Dangerous Anti-Pattern (LLM-Decided Access / Unfiltered Retrieval)
```text
User A
  ↓
Question
  ↓
Retriever (No Pre-Filtering)
  ↓
❌ Retrieves a document User A isn't authorized to see
  ↓
LLM (Prompted: "Only show if user has access")
  ↓
⚠️ DATA LEAK: Chunks already exposed in prompt context / token stream
```

### ✅ Enforced Architecture (Pre-Retrieval Backend Security Logic)
```text
User
  ↓
Authentication (JWT)
  ↓
Authorization (PostgreSQL roles & document_access)
  ↓
Allowed document IDs / metadata scope
  ↓
Retriever (Qdrant filter: document_id IN allowed_document_ids)
  ↓
Only authorized chunks retrieved
  ↓
Reranker
  ↓
LLM (Receives ONLY authorized evidence)
  ↓
Citation validation
  ↓
Answer
```

> **Rule:** The LLM should never be responsible for deciding whether a user is allowed to see a document. That is backend security logic.

## 12.2 Agent Tool Sandboxing

LangGraph agents are strictly prohibited from possessing unrestricted tools:

| Prohibited Tools | Reason |
|---|---|
| `execute_shell()` | Potential arbitrary code execution on host |
| `run_sql()` | Potential SQL injection and direct bypass of access controls |
| `arbitrary_http_request()` | SSRF and unauthenticated egress risks |
| `read_any_file()` | Arbitrary filesystem access / credential leakage |

### Allowed Tools (Strictly Validated Inputs)
- `retrieve_authorized_evidence`: Constrained to the user's `allowed_document_ids`.
- `calculator`: Sandboxed mathematical evaluations with typed numbers and allowed operators.
- `document_metadata`: Bounded read-only lookup of accessible document properties.
