# FRONTEND SCHEMA — Next.js + TypeScript

## 1. Frontend Responsibilities

The frontend provides:

- authentication UI
- document library
- search
- chat
- citations
- document inspection
- evaluation dashboard
- ingestion monitoring
- admin controls

---

# 2. Frontend Stack

```text
Next.js
TypeScript
App Router
Tailwind CSS
shadcn/ui
TanStack Query
Recharts
React Hook Form
Zod
```

---

# 3. Frontend Structure

```text
apps/web/
├── app/
│   ├── (auth)/
│   │   ├── login/
│   │   └── register/
│   │
│   ├── dashboard/
│   ├── search/
│   ├── chat/
│   │   └── [conversationId]/
│   ├── documents/
│   │   ├── page.tsx
│   │   └── [id]/
│   ├── evaluations/
│   ├── admin/
│   │   ├── users/
│   │   └── jobs/
│   └── settings/
│
├── components/
│   ├── chat/
│   ├── search/
│   ├── documents/
│   ├── citations/
│   ├── evaluation/
│   ├── admin/
│   └── ui/
│
├── lib/
│   ├── api.ts
│   ├── auth.ts
│   ├── query-client.ts
│   └── validators.ts
│
├── hooks/
├── types/
└── styles/
```

---

# 4. Route Map

```text
/login
/register

/dashboard

/search
/chat/[conversationId]

/documents
/documents/[id]

/evaluations
/evaluations/[id]

/admin/users
/admin/jobs

/settings
```

---

# 5. Global Layout

```text
┌─────────────────────────────────────────────────────────────┐
│ Logo              Search                    User / Settings │
├──────────────┬──────────────────────────────────────────────┤
│ Dashboard    │                                              │
│ Search       │              Main Content                    │
│ Chat         │                                              │
│ Documents    │                                              │
│ Evaluations  │                                              │
│              │                                              │
│ Admin        │                                              │
└──────────────┴──────────────────────────────────────────────┘
```

---

# 6. Dashboard

Cards:

```text
Documents
Ready Documents
Chunks Indexed
Queries
Average Latency
Grounded Answers
```

Charts:

```text
Queries over time
Retrieval latency
Answer latency
Query type distribution
Evaluation metrics
```

---

# 7. Search Page

Components:

```text
SearchInput
FilterPanel
SearchResults
ResultCard
CitationPreview
Pagination
```

Filters:

```text
Company
Year
Document Type
Section
```

Search result:

```text
┌─────────────────────────────────────────────┐
│ Apple — Annual Report 2025                  │
│ Risk Factors · Page 42                      │
│                                             │
│ ...matching evidence...                     │
│                                             │
│ [Open document] [View evidence]             │
└─────────────────────────────────────────────┘
```

---

# 8. Chat Page

Layout:

```text
┌───────────────────────────────────────────────────────────┐
│ Conversation                                               │
├───────────────────────────────────────────────────────────┤
│ User: What changed in Apple's revenue from 2024 to 2025?  │
│                                                           │
│ Assistant:                                                │
│ ...answer...                                               │
│                                                           │
│ Sources:                                                  │
│ [1] Apple 2025 Annual Report · Page 31                   │
│ [2] Apple 2024 Annual Report · Page 30                   │
├───────────────────────────────────────────────────────────┤
│ Ask a question...                                  [Send] │
└───────────────────────────────────────────────────────────┘
```

---

# 9. Citation Component

```text
CitationCard

Document
Company
Year
Section
Page
Evidence
Open document
```

Example:

```text
[1] Apple — 2025 Annual Report
Section: Net Sales
Page: 31

"Revenue increased..."

[Open source]
```

---

# 10. Evidence Drawer

Clicking a citation opens:

```text
┌───────────────────────────────────────────┐
│ Evidence                                  │
├───────────────────────────────────────────┤
│ Document: Apple 2025 Annual Report        │
│ Section: Financial Statements             │
│ Page: 31                                  │
│                                           │
│ [highlighted evidence]                    │
│                                           │
│ Chunk ID: 8e2...                          │
└───────────────────────────────────────────┘
```

Do not show hidden model reasoning.

---

# 11. Document Page

Sections:

```text
Document metadata
Ingestion status
Section tree
Search within document
Evidence
Related chunks
```

Example:

```text
Apple — 2025 Annual Report

Company: Apple
Year: 2025
Type: Annual Report
Status: Ready

Sections
├── Business
├── Risk Factors
├── Financial Statements
│   ├── Income Statement
│   ├── Balance Sheet
│   └── Cash Flows
└── Notes
```

---

# 12. Admin Documents Page

Table:

```text
Document | Company | Year | Type | Status | Chunks | Actions
```

Actions:

```text
View
Re-ingest
Re-index
Delete
View logs
```

---

# 13. Ingestion Job Page

Progress:

```text
Validation       ✓
Parsing          ✓
Normalization    ✓
Chunking         ✓
Embedding        ████████░░
Indexing         pending
```

Show:

```text
job ID
started
current stage
progress
errors
retry count
```

---

# 14. Evaluation Dashboard

Top cards:

```text
Recall@5
MRR
nDCG@10
Groundedness
Citation Accuracy
Abstention Accuracy
```

Charts:

```text
Retriever comparison
Reranker improvement
Latency distribution
Query-type performance
```

Comparison:

```text
Dense only
Sparse only
Hybrid
Hybrid + Reranker
```

The dashboard should report measured results without visually declaring an untested system “best.”

---

# 15. Query Diagnostics

Optional expandable panel:

```text
Query Type: COMPARISON

Filters:
Company: Apple
Years: 2024, 2025

Dense Candidates: 30
Sparse Candidates: 30
Fused: 20
Reranked: 10

Evidence: Sufficient

Latency:
Retrieval: 420 ms
Reranking: 310 ms
Generation: 2.1 s
```

Do not display chain-of-thought.

---

# 16. Authentication State

Frontend auth state:

```typescript
type User = {
  id: string;
  email: string;
  fullName: string;
  roles: string[];
};
```

Route protection:

```text
/admin/* → ADMIN
/documents/manage → ADMIN
/evaluations/manage → ADMIN
```

Backend remains the authoritative authorization layer.

---

# 17. API Client

Use a typed API client.

Example:

```typescript
type SearchRequest = {
  query: string;
  filters?: {
    companies?: string[];
    years?: number[];
    documentTypes?: string[];
  };
  topK?: number;
};
```

Do not duplicate backend schemas manually where generation is practical.

Preferred:

```text
FastAPI OpenAPI
      ↓
TypeScript client/types
      ↓
Next.js
```

---

# 18. State Management

Use:

### TanStack Query
For:

- documents
- jobs
- evaluations
- search requests
- user data

### React local state
For:

- input
- modal visibility
- temporary filters
- UI state

### URL state
For:

- search filters
- pagination
- document IDs

Avoid a large global state store unless actual requirements appear.

---

# 19. Streaming

Chat should use SSE.

Frontend event handler:

```text
query_started
retrieval_started
retrieval_completed
generation_started
token
citation
completed
error
```

The UI should progressively render answer tokens while keeping citation rendering synchronized.

---

# 20. Responsive Design

Must work on:

```text
Desktop
Laptop
Tablet
Mobile
```

Priority is desktop/laptop because the application is an analyst-oriented document system.

---

# 21. Visual Design

Recommended style:

```text
Professional
Dark/light mode
Dense information layout
Minimal animation
Strong typography
Technical/enterprise feel
```

Avoid:

```text
overly futuristic neon UI
excessive gradients
gaming dashboard aesthetics
large decorative animations
```

The UI should look like an internal enterprise intelligence tool.

---

# 22. Accessibility

Required:

- keyboard navigation
- visible focus states
- semantic buttons
- labels for inputs
- accessible dialogs
- sufficient contrast
- screen-reader-friendly citation labels

---

# 23. Frontend Testing

Use:

```text
Vitest
React Testing Library
Playwright
```

Tests:

```text
login
document filtering
search
citation opening
chat
streaming
role-based navigation
admin controls
```

---

# 24. Frontend Error States

Every data screen needs:

```text
Loading
Empty
Error
Retry
Success
```

Example:

```text
No documents match your filters.

[Clear filters]
```

---

# 25. Performance Rules

- paginate document lists
- virtualize long result lists if needed
- lazy-load heavy document preview components
- cache GET requests
- debounce search input
- avoid sending full documents to the browser
- stream chat output
- never expose Qdrant credentials to the client

---

# 26. Frontend Definition of Done

A screen is complete only when:

- API integration works
- loading state exists
- error state exists
- empty state exists
- mobile layout works
- access rules are respected
- tests exist for important interactions
