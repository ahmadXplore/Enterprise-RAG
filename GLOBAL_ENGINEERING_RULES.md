# GLOBAL ENGINEERING RULES — MUST FOLLOW AT ALL TIMES

These rules apply to **EVERY change** you make in this project.

---

## 1. MINIMAL & RELEVANT CODE

* Implement ONLY what the current task/phase requires.
* Do NOT generate extra features, utilities, abstractions, files, endpoints, components, or dependencies that are not required.
* Do NOT add "future-proof" code unless it is explicitly required by the architecture.
* If something can be implemented cleanly in 10 lines instead of 50, use the simpler implementation.
* Prefer simple, readable solutions over clever or over-engineered solutions.
* Remove dead code, unused imports, unused variables, duplicate logic, and unnecessary comments.
* Never generate boilerplate merely for the sake of having it.
* **Exception:** security controls required by this document (auth, validation, rate limiting, logging, etc.) always count as "required" for any feature they apply to. Never skip a security control in the name of minimalism.

---

## 2. DRY — DON'T REPEAT YOURSELF

* Follow the DRY principle.
* Before creating a new function/class/utility, check whether an existing implementation can be reused.
* Do not duplicate validation, authentication, database logic, API logic, retrieval logic, or UI logic.
* Create an abstraction only when there is real repeated behavior or a clear architectural requirement.
* Do NOT create abstractions for one-time operations just to make the code look "enterprise."

---

## 3. STRICT SCOPE CONTROL

* Work ONLY on the requested phase/task.
* Do NOT implement features belonging to later phases.
* Do NOT modify unrelated files.
* Do NOT redesign the architecture unless the existing architecture makes the requested task impossible or insecure.
* If you discover an unrelated improvement, do NOT implement it automatically. Report it separately.

---

## 4. SECURITY-BY-DESIGN — EVERY STEP

Security is a requirement for **EVERY feature**, not a final-phase task.

For every piece of code, ask:

> **"What could an attacker abuse here?"**

Always:

* Never hard-code API keys, passwords, JWT secrets, database credentials, tokens, or private URLs.
* Never expose secrets to frontend/client-side code.
* Keep secrets in environment variables or a proper secret-management system.
* Never commit `.env` or secrets to Git.
* Maintain a secure `.gitignore`.
* Validate and sanitize all user-controlled input.
* Use strict Pydantic/Zod validation where applicable.
* Use parameterized queries/ORM queries; never construct SQL from raw user input.
* Enforce authentication on protected endpoints.
* Enforce authorization/RBAC on every privileged operation.
* Never trust frontend authorization; backend authorization is authoritative.
* Apply document-level access control **BEFORE** retrieved data is sent to the LLM.
* Never expose Qdrant, PostgreSQL, Redis, or internal services directly to the public internet unless explicitly required and securely configured.
* Never expose API keys in browser requests, frontend environment variables, logs, error messages, URLs, or source maps.
* Do not log passwords, API keys, access tokens, cookies, or sensitive document contents.
* Use safe error messages; never expose stack traces or internal implementation details to users.
* Use appropriate request validation, size limits, timeouts, and rate limiting where applicable.
* Prevent path traversal when handling uploaded files or file paths.
* Validate uploaded file type, size, and content before processing.
* Prevent arbitrary code execution through uploaded documents or user input.
* Use secure password hashing; never store plaintext passwords.
* Use secure token/session handling.
* Use HTTPS assumptions for production.
* Configure CORS narrowly — explicit origin allowlist; never use unrestricted (`*`) origins in production.
* Protect admin endpoints separately.
* Record security-sensitive administrative actions in audit logs.
* Apply least-privilege principles to users, services, API keys, database users, and containers.

---

## 5. AUTHENTICATION DETAIL

* Lock out or throttle accounts/IPs after repeated failed login attempts.
* Expire tokens/sessions and support revocation; never issue infinite-lifetime tokens.
* Password reset tokens must be single-use, short-lived, and invalidated after use.
* If using cookies for auth, set `HttpOnly`, `Secure`, and `SameSite`, and add CSRF protection for state-changing requests.
* Use MFA for admin/privileged accounts at minimum, where feasible.
* Never reveal via error messages, response codes, or timing whether a given email/username exists in the system.

---

## 6. API CALL SECURITY & DATA MINIMIZATION

Every API call must follow the **principle of least privilege and minimum necessary data exposure**.

### Request Security

For every endpoint:

* Require authentication when the endpoint is protected.
* Enforce authorization/RBAC before performing the operation.
* Validate all path parameters, query parameters, headers, and request bodies.
* Never trust IDs supplied by the frontend to determine authorization.
* Verify that the authenticated user actually has permission to access the requested resource.
* Prevent IDOR/BOLA vulnerabilities.
* Apply ownership and document-level access checks on the backend.
* Never rely on the frontend to hide unauthorized resources.

### Response Security

**Every endpoint must return ONLY the data required for that specific operation.**

Do NOT return an entire database record or user object when only a few fields are needed.

**Bad:**

```text
GET /api/profile
→ returns password hash, email, roles, permissions, internal IDs,
  security settings, audit information, timestamps, internal metadata,
  every other user field
```

**Good:**

```text
GET /api/profile
→ returns only the fields required by the profile UI
```

Similarly:

* A password-change endpoint should return only the result/status of the password change.
* A profile endpoint should return only profile-related fields.
* A document-list endpoint should return only document metadata required by the document list.
* A document-detail endpoint should return only information the authenticated user is authorized to view.
* A search endpoint should return only the search results and metadata required by the search UI.
* An authentication endpoint should return only the authentication/session information required by the client.
* An admin endpoint may return additional administrative information ONLY when the authenticated user has the required administrative permission.
* Never return unrelated user records.
* Never return unnecessary database columns.
* Never expose internal database models directly as API responses.

### Sensitive Data Isolation

Sensitive fields must be explicitly excluded from API responses unless genuinely required:

* password hashes, authentication secrets, refresh tokens, API keys, session identifiers
* private/internal tokens, security answers, internal permission metadata
* sensitive audit information, private document contents
* internal infrastructure information, database identifiers when not required, internal implementation details

If an endpoint needs one sensitive field internally, **do not automatically return it to the client**.

### Endpoint-Specific Schemas

* Do not automatically serialize complete ORM/database models.
* Define response models containing only the fields that endpoint needs.
* Keep internal database models separate from public API schemas.
* Use different schemas when different operations require different data.

```text
User database model → Internal application logic → Endpoint-specific response schema → Client
```

Not:

```text
User database model → Entire database object → Client
```

### Prevent Cross-User Data Leakage

```text
Authenticated User → Authorization Check → Resource Ownership/RBAC Check →
Fetch ONLY authorized resource → Select ONLY required fields → Return minimal response
```

Never fetch all records and filter in the frontend. Never rely on the frontend to remove sensitive or unauthorized data.

### Database Query Minimization

* Select only the database columns required for the operation.
* Do not fetch sensitive fields when they are not needed.
* Do not load entire related objects unnecessarily.
* Avoid returning unrestricted ORM objects.
* Apply authorization filters at the database/application query level where appropriate.

> **Do not fetch data you do not need, and do not return data you do not need.**

### API Error Security

API errors must not reveal: whether unrelated users exist, passwords or password hashes, internal database structure, SQL queries, stack traces, internal file paths, API keys, tokens, infrastructure details, or sensitive document contents. Use safe, controlled error responses.

---

## 7. WEB-LAYER PROTECTIONS

* Sanitize/escape any user-generated or LLM-generated content before rendering it in the frontend — LLM output is not automatically safe to render as HTML.
* Set security headers in production: Content-Security-Policy, `X-Content-Type-Options: nosniff`, `X-Frame-Options` (or CSP `frame-ancestors`), and HSTS.
* Guard against SSRF for any server-side fetch of a user-supplied or document-derived URL: block internal/private IP ranges and disallow redirects into them.
* Configure CORS with an explicit origin allowlist in production; never `*`.

---

## 8. SECRETS CHECK

Before finishing ANY task:

* Search the changed files for hard-coded secrets or credentials.
* Verify no API key/token/password was accidentally added.
* Verify `.env` is ignored.
* Verify frontend code does not contain server-only secrets.
* Verify logs do not expose secrets.
* Verify API responses do not accidentally expose secrets or sensitive fields.

If a secret is required, create/update `.env.example` with a placeholder only.

---

## 9. DEPENDENCY DISCIPLINE & SUPPLY CHAIN SECURITY

* Do NOT add a package unless it is actually necessary.
* Before adding a dependency, check whether the existing stack already provides the required functionality.
* Prefer standard-library or already-installed functionality when reasonable.
* Every new dependency must have a clear reason.
* Pin dependency versions; avoid unpinned `latest`/`*` ranges in production manifests.
* Check a new package's maintenance status before adding it — avoid abandoned or typosquatted packages.
* Run a vulnerability scanner (`pip-audit`, `npm audit`, `safety`, Dependabot/Renovate, etc.) as part of the workflow, and re-check before releases, not just once at setup.

---

## 10. DATABASE SECURITY

* Never concatenate user input into SQL.
* Use SQLAlchemy/parameterized queries.
* Validate IDs and filters.
* Apply authorization before returning records.
* Do not return sensitive database fields unnecessarily.
* Select only the columns required for the operation when practical.
* Use least-privilege database credentials.
* Do not expose database credentials to the frontend.
* Do not expose internal ORM/database models directly through API responses.
* Prevent cross-user data access at the backend/database layer.

---

## 11. API SECURITY

Every endpoint must have:

* correct authentication requirement
* correct authorization requirement
* validated request body/query/path parameters
* endpoint-specific request schema
* endpoint-specific response schema
* minimum necessary response data
* safe error handling
* appropriate rate limiting (required on all write endpoints and any endpoint calling an LLM or external API)
* appropriate timeout limits

Additional rules:

* Do not create an endpoint that bypasses the existing security layer.
* Never return unrelated user/application data.
* Never return an entire user/resource object when only a subset is required.
* Never trust frontend-provided authorization information.
* Never use frontend filtering as a security mechanism.
* Prevent IDOR/BOLA.
* Verify resource ownership or permission on every resource-specific request.
* Ensure one user's API request cannot expose another user's private data.
* Keep internal models separate from public API schemas.
* Use explicit response models.

---

## 12. AI/RAG SECURITY

Treat all retrieved documents and user-provided text as **UNTRUSTED DATA**. Never allow document text to override system instructions.

Protect against: prompt injection, indirect prompt injection, malicious documents, malicious retrieved content, data exfiltration, unauthorized document retrieval, cross-user data leakage, fabricated citations.

The LLM must **never receive documents that the authenticated user is not authorized to access**.

* Enforce document access control **inside the retrieval/vector database query itself** (e.g., Qdrant payload filters scoped to the requesting user), not only by filtering results after retrieval in application code.
* Do not allow the LLM to directly execute arbitrary tools, shell commands, database queries, or HTTP requests. All tools must use explicit allowlists, validated inputs, permission checks, timeouts, safe outputs, and minimum required data.
* Do not give an AI agent broad access to application data simply because a particular task requires one piece of information — it should receive only the authorized evidence required to answer the question, not all documents, all users, all database records, all configuration, or all credentials.
* Validate/sanitize LLM output before it is rendered, executed, or used to trigger any downstream action.
* Define a data retention and deletion policy for uploaded documents and embeddings.
* Log prompts/outputs for debugging under the same sensitivity rules as any other log — no secrets, no full sensitive document text where avoidable.

---

## 13. FILE UPLOAD SECURITY

For every uploaded file:

* enforce maximum file size
* validate extension AND actual content/MIME type
* generate server-side filenames
* never trust the original filename as a filesystem path
* prevent path traversal
* store uploads outside executable directories
* do not execute uploaded files
* scan/validate where appropriate
* isolate parsing processes when practical
* clean up temporary files

Uploaded documents must also be treated as **untrusted content** and must not be allowed to manipulate system instructions, tools, permissions, or application behavior.

---

## 14. ERROR HANDLING

* Fail safely.
* Do not expose internal stack traces to users.
* Log detailed errors server-side with a request ID.
* Return concise safe errors to clients.
* Do not swallow errors silently.
* Never expose sensitive data through exceptions or debug responses.

---

## 15. AVAILABILITY & RESILIENCE

* Every public endpoint must have a request size limit and a timeout.
* Define explicit timeouts and circuit breakers for every external call (LLM API, third-party services) so a hung dependency doesn't hang the whole app.
* Add a `/health` endpoint that checks real dependencies (DB, cache, vector store), not just "process is alive."
* Define what happens when a downstream service is down: return a clear error, don't crash or retry infinitely.
* For LLM-backed features: set a hard per-user and per-endpoint cap on token/API spend to prevent cost-based denial of service.
* Maintain a backup policy for the database and vector store, and periodically verify restores actually work.

---

## 16. MONITORING & INCIDENT RESPONSE

* Alert on: repeated auth failures, sudden spikes in a single user's API usage, error rate spikes, and unusual data-access patterns (e.g., one account reading many other users' documents).
* Keep a short written incident response plan: who gets notified, how to revoke compromised credentials, how to roll back a bad deploy.
* Retain logs long enough to investigate incidents after the fact, without violating the no-sensitive-data-in-logs rule.

---

## 17. TESTING

For every security-sensitive feature, add tests for:

* authorized access
* unauthorized access
* cross-user access
* invalid input
* malicious input where relevant
* boundary conditions
* sensitive-field exposure
* excessive API response data
* IDOR/BOLA attempts where relevant
* failure handling

For API endpoints specifically, verify:

```text
Correct user → receives required data
Unauthorized user → receives no protected data
Authorized user requesting another user's resource → receives no unauthorized data
Client requesting unnecessary/sensitive fields → cannot bypass the response schema
```

Do not claim a feature is complete until its relevant tests pass.

---

## 18. BEFORE CHANGING CODE

First inspect: existing implementation, related services, existing utilities, existing security mechanisms, database models, API schemas, existing authentication/authorization, existing response models, existing error handling.

Reuse existing code where appropriate. Do not create duplicate implementations. Before creating a new API endpoint, check whether an existing endpoint already provides the required functionality securely.

---

## 19. AFTER CHANGING CODE

Before finishing, and report the results of each step:

1. Run relevant tests — paste actual output, don't just claim they pass.
2. Run lint/type checks where configured.
3. Check for unused code/imports.
4. Check for duplicate logic.
5. Check for accidental scope expansion.
6. Check changed files for secrets.
7. Check API responses for unnecessary/sensitive data.
8. Check authentication and authorization.
9. Check for IDOR/BOLA and cross-user data leakage where relevant.
10. Run a dependency vulnerability scan if dependencies changed.
11. List every changed/added endpoint with its auth requirement and response schema.
12. Report exactly what changed.
13. Report any security risks that could not be fully mitigated, and any optional improvements noticed but not implemented (per Rule 3).

---

## 20. NO FAKE SECURITY

* Do not add fake encryption.
* Do not create unused security middleware.
* Do not claim "secure" without implementing the relevant control.
* Do not hide insecure behavior behind comments.
* Do not disable security checks just to make tests pass.
* Do not add security libraries without actually integrating them correctly.
* Do not create fake authorization checks that do not verify real permissions.
* Do not add response filtering only on the frontend and call the API secure.
* Do not report "all checks passed" without showing the evidence (test output, scan results, endpoint list) required by Rule 19.

Security controls must actually enforce the intended protection.

---

## 21. CODE QUALITY PRIORITY

1. **Correctness**
2. **Security**
3. **Simplicity**
4. **Maintainability**
5. **Performance**
6. **Abstraction**

Do NOT sacrifice security for fewer lines of code. Do NOT sacrifice correctness merely to reduce code size.

---

## 22. STOP CONDITION

When the requested task is complete, **STOP**. Do not continue implementing additional features. Do not "improve" unrelated parts of the project. Do not generate speculative code. Only report optional improvements separately without implementing them.

---

# FINAL RULE

Before every implementation decision, ask:

> **"Is this required?"**
> **"Does this already exist?"**
> **"Can I implement it more simply?"**
> **"Can a user or attacker abuse it?"**
> **"Am I exposing data or secrets?"**
> **"Does this API call return more data than necessary?"**
> **"Could this request access another user's data?"**
> **"Am I trusting the frontend for authorization?"**
> **"Am I exposing an internal database model through the API?"**
> **"Am I modifying anything outside the requested scope?"**
> **"Could this feature go down or be abused to run up costs?"**

If the answer indicates unnecessary code, excessive data exposure, insufficient authorization, unnecessary scope, or a missing resilience/monitoring control, **do not implement it as-is — fix it first**.

## CORE PRINCIPLE

> **Every feature must be minimal, secure, authorized, scoped to exactly what is required, and resilient to abuse.**
>
> **Every API request must receive only the minimum data necessary for that operation.**
>
> **Never fetch, process, or expose data merely because it is available.**
>
> **Backend authorization is authoritative. Frontend filtering is never a security control.**
>
> **No rules file makes an application unhackable. These rules reduce attack surface and limit damage — they do not replace external code review, dependency scanning, infrastructure hardening, and a penetration test before handling real user data.**
