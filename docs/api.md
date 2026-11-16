# ProDesk API

- Base path: `/api/v1`. The interactive OpenAPI docs are at **`/docs`** (Swagger) and `/redoc`; the schema is at `/openapi.json`.
- Auth: `Authorization: Bearer <access token>`. Staff tokens come from `/auth/login`; client tokens come from `/portal/auth/verify-otp`.
- Pagination: `?page=1&page_size=25` (max 100) returns `{items, total, page, page_size}`.
- Errors always use the same envelope:

```json
{ "error": { "code": "VALIDATION_FAILED", "message": "Request validation failed", "details": [...] }, "request_id": "…" }
```

Common codes: `AUTH_REQUIRED`, `INVALID_TOKEN`, `TOKEN_EXPIRED`, `FORBIDDEN`, `NOT_FOUND` (also used for cross-tenant access), `CONFLICT`/`DUPLICATE_PHONE`, `VALIDATION_FAILED`, `RATE_LIMITED`, `FILE_TYPE_MISMATCH`, `TEMPLATE_NOT_APPROVED`, `OUTSIDE_SERVICE_WINDOW`.

Every response carries `X-Request-ID` (send your own to correlate). `X-Correlation-ID` is propagated into worker jobs.

## Endpoints

### Auth (`/auth`)
| Method | Path | Notes |
|---|---|---|
| POST | `/auth/register` | Create firm + first FIRM_ADMIN (rate limited) |
| POST | `/auth/login` | Returns access + refresh tokens; also sets an httpOnly refresh cookie. Lockout after 5 failures |
| POST | `/auth/refresh` | Rotates the refresh token (body or cookie); reuse revokes the token family |
| POST | `/auth/logout` | Revokes the refresh token and denylists the access token `jti` |
| GET | `/auth/me` | Current user, organization, permissions |
| POST | `/auth/password-reset/request` · `/confirm` | Single-use, 30-minute token; never reveals whether the account exists |
| POST | `/auth/activate` · `/auth/verify-email` | Invitation activation / email verification |
| POST | `/auth/change-password` | Invalidates all sessions |

### Organizations and users
`GET/PATCH /organizations/current` (profile, working hours, notifications, reminders, invoice, privacy, FAQs, onboarding step) · `POST /organizations/current/logo` · `GET /organizations` and `POST /organizations/{id}/status` (SUPER_ADMIN only) · `GET/POST /users` (invite) · `PATCH /users/{id}` (role, active) · `GET /roles`

### Clients (`/clients`)
`GET` (q, status, client_type, assigned_employee_id, sort, order, paging) · `POST` · `GET /{id}` · `GET /{id}/summary` · `GET /{id}/timeline` · `PATCH /{id}` · `POST /{id}/archive` · `POST /import` (CSV) · `GET /import/template` · `POST /{id}/consents` · `POST /{id}/whatsapp/welcome` · `GET /{id}/export` (privacy export) · `POST /{id}/erase`

### Documents (`/documents`)
`GET` (q, client_id, document_type, financial_year, status, source, sort) · `POST` (multipart: file, client_id, document_type, financial_year, …) · `GET /{id}` (versions, deliveries, access history) · `PATCH /{id}` · `POST /{id}/versions` · `POST /{id}/submit` · `POST /{id}/approve` `{note, deliver}` · `POST /{id}/reject` · `POST /{id}/deliver` · `POST /{id}/archive` · `DELETE /{id}` · `POST /{id}/download-url?inline=&version_id=` returns `{url, expires_at}`

`GET /files/{signed-token}` streams a local-storage file for a valid, unexpired token (S3 uses presigned URLs instead).

### Work
`/tasks` (`bucket=overdue|today|week|mine|completed|open`, filters) · `GET /tasks/buckets` · `POST/GET/PATCH /tasks/{id}` (`notify_client` sends TASK_COMPLETED on FILED/COMPLETED)

`/document-requests` (`GET`, `POST`, `GET /{id}`, `POST /{id}/items/{item}?received=`, `POST /{id}/items/{item}/upload`, `POST /{id}/remind`, `POST /{id}/cancel`)

`/compliance` (`GET ?start&end&category`, `POST`, `DELETE /{id}`) · `/support-requests` (`GET`, `PATCH /{id}`)

### WhatsApp
| Method | Path | Notes |
|---|---|---|
| GET | `/webhooks/whatsapp` | Meta verification (`hub.mode`, `hub.verify_token`, `hub.challenge`) |
| POST | `/webhooks/whatsapp` | Signature check → idempotent persist → queue → 200 |
| GET/PUT | `/whatsapp/account` | Tokens are write-only; responses show only `access_token_set` and a masked hint |
| POST | `/whatsapp/account/verify` | Checks credentials against the Graph API |
| GET/PATCH | `/whatsapp/templates[/{id}]` | Map keys to Meta template names and set approval status |
| POST | `/whatsapp/templates/sync` | Pull real status from Meta |
| POST | `/whatsapp/send-template` | Manual template send (OTP excluded) |
| POST | `/whatsapp/simulate/inbound` | **Development + mock only** |
| GET | `/conversations` · `/conversations/{id}` · `/conversations/{id}/messages` | Inbox |
| POST | `/conversations/{id}/messages` | Agent reply (24-hour window enforced) |
| POST | `/conversations/{id}/handover` | `{action: take | assign | resume_bot | close, agent_id?}` |

### Billing
`/invoices` (`GET`, `POST`, `GET /{id}`, `POST /{id}/send`, `POST /{id}/cancel`, `POST /{id}/payments` for manual payments) · `GET /payments` · `POST /webhooks/razorpay` (signature + idempotency)

### Insights
`GET /reports/dashboard` · `GET /reports` · `GET /reports/{name}` · `GET /reports/{name}/csv` · `POST /ai/assistant` `{question}` · `GET /search?q=` · `GET /notifications` · `POST /notifications/read` · `GET /audit-logs` · `GET /jobs/{task_id}`

Reports: `client-growth`, `pending-documents`, `document-delivery`, `task-completion`, `whatsapp-activity`, `invoice-collection`, `employee-workload`, `overdue-tasks`.

### Client portal (`/portal`, client token)
`POST /auth/request-otp` · `POST /auth/verify-otp` · `GET /link/{token}` (public; returns firm name + masked phone only) · `POST /link/{token}/download` · `GET /me` · `GET /dashboard` · `GET /documents` · `POST /documents/{id}/download-url` · `GET /document-requests` · `POST /document-requests/{id}/upload` · `GET /tasks` · `GET /invoices[/{id}]` · `POST /invoices/{id}/checkout` · `POST /payments/verify` · `POST /payments/mock-complete` (dev) · `GET /payments` · `GET /messages` · `GET/POST /support`

### Health
`GET /health` (liveness) · `GET /health/ready` (DB + migration revision, Redis, storage, provider modes; returns 503 when degraded)

## Example: upload, approve, deliver

```bash
TOKEN=$(curl -s localhost:8000/api/v1/auth/login -H 'content-type: application/json' \
  -d '{"email":"admin@demo.example.com","password":"Demo@12345"}' | jq -r .access_token)
DOC=$(curl -s localhost:8000/api/v1/documents -H "Authorization: Bearer $TOKEN" \
  -F file=@ITR-V.pdf -F client_id=$CLIENT -F document_type=ITR_ACKNOWLEDGEMENT -F financial_year=2025-26 | jq -r .id)
curl -s -X POST localhost:8000/api/v1/documents/$DOC/approve -H "Authorization: Bearer $TOKEN" \
  -H 'content-type: application/json' -d '{"deliver": true}'
```
