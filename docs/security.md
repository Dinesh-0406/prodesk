# ProDesk security

These are the controls ProDesk implements, mapped to common OWASP risks. Where a test proves a control, it is named. ProDesk does **not** claim any certification or legal compliance status.

## Identity and sessions

| Control | Implementation |
|---|---|
| Password hashing | Argon2id (`argon2-cffi`); minimum 10 characters with mixed character classes |
| Access tokens | HS256 JWT, 15 minutes, claims `sub, org, typ, ver, jti`; `typ` separates staff, client and file tokens |
| Refresh tokens | Opaque 48-byte tokens, stored **HMAC-hashed**, rotated on every use; **reuse revokes the whole family** (`test_refresh_rotation_and_reuse_detection`) |
| Refresh transport | httpOnly, `SameSite=Strict` cookie scoped to `/api/v1/auth` (`Secure` in production); access token kept in memory, not localStorage |
| Logout | Refresh token revoked and access `jti` denylisted in Redis until expiry (`test_logout_revokes_access_token`) |
| Immediate revocation | `token_version` bump on password reset, role change or deactivation (`test_role_change_invalidates_existing_session`) |
| Brute force | Per-IP rate limits (fail-closed if Redis is down) plus account lockout after 5 failures for 15 minutes (`test_login_lockout_and_rate_limit`) |
| Enumeration | Identical errors for unknown user and wrong password; reset and OTP requests always return the same message |
| Reset/activation | Single-use, hashed, time-limited (30 minutes / 72 hours) action tokens |
| Client auth | Phone **+ 6-digit OTP** (hashed, 5 minutes, 5 attempts, then burned); 3 requests per phone per 10 minutes; a **phone number alone never grants access** (`test_otp_security`, E2E test) |

## Authorization and tenant isolation

- Every query is scoped by organization in one place (`services/scope.py`, `TenantRepository`).
- Visibility within a firm: staff without `CLIENT_VIEW_ALL` see only assigned clients and their documents, tasks, conversations and invoices. Client principals see only themselves.
- Out-of-scope reads return **404**, so record existence isn't leaked.
- Permission checks happen in services (`principal.require(...)`), never in the UI alone. The UI hides controls only as a hint.
- Tests: `test_org_a_cannot_access_org_b_resources`, `test_org_a_cannot_read_org_b_conversations`, `test_employee_only_sees_assigned_clients`, `test_employee_permission_restrictions`, `test_client_token_cannot_use_staff_api`, `test_super_admin_has_no_tenant_data_access`, and the E2E checks Client A → Client B and Org A → Org B.

## Documents

Before any download, ProDesk checks: **authenticated principal → organization → client ownership/visibility → permission → document and version status**.

- Clients can download only the **current approved version** of staff-prepared documents (or files they uploaded themselves). Drafts are invisible to them (`test_client_cannot_download_unapproved_or_staff_drafts`).
- Downloads use **short-lived signed URLs** (5 minutes): S3 presigned GET, or HMAC-signed JWT tokens for local storage. Tokens are bound to version + organization; tampered, guessed, expired or cross-org tokens are rejected (`test_signed_url_download_and_tampering`, `test_expired_signed_url`, `test_signed_token_cannot_cross_orgs`).
- WhatsApp links carry an opaque, hashed, expiring **delivery token**, not a file URL. The public link endpoint reveals only the firm name and a masked phone number.
- Deleting a document makes it inaccessible immediately, including outstanding signed URLs, and a worker securely deletes every stored version (`test_delete_makes_document_inaccessible_and_purges_storage`).
- Every view and download is audit-logged with actor, IP and version.

## File upload security

- Allowed: PDF, JPG, PNG, DOC/DOCX, XLS/XLSX. The **extension and magic bytes must agree**; Office files are opened as ZIP or OLE and **macro-enabled files are rejected** (`test_rejects_disguised_and_unsupported_files`).
- Size limit (`MAX_UPLOAD_MB`, default 25) is enforced while reading, before storage.
- Storage keys are random (`<org>/documents/<uuid4hex>`) and never derived from file names. File names are sanitised for display only.
- The local provider validates keys and resolves paths inside its root (path traversal guard). Files are written `0600` and never served statically.
- Files are always served as `Content-Disposition: attachment` (inline only for PDF/images when previewing), with `X-Content-Type-Options: nosniff` and `CSP: sandbox`. Uploaded content is never executed.

## Webhooks

- WhatsApp: `X-Hub-Signature-256` HMAC over the raw body using a constant-time comparison; failures return 401 and write a `WEBHOOK_REJECTED` audit entry (`test_fake_webhook_rejected`).
- Razorpay: `X-Razorpay-Signature` HMAC (`test_payment_webhook_signature_and_idempotency`).
- **Replay and duplicates:** unique `(provider, event_key)` with `ON CONFLICT DO NOTHING`, plus unique message and payment IDs. Replays cause no duplicate messages, replies or payments (`test_duplicate_webhook_is_idempotent`). Timestamps aren't used to reject events because Meta legitimately retries for days; idempotency is the defence.
- Tenant routing comes from `phone_number_id` (unique per organization; hijack attempts return 409, `test_phone_number_id_cannot_be_hijacked`).

## Payments

The frontend never decides that a payment succeeded. ProDesk checks the signature (`HMAC(order|payment, key_secret)`) **and** fetches the payment from the provider to confirm status `captured`, the matching order and the exact amount. Recording is idempotent on `provider_payment_id`. Tests: `test_forged_payment_signature_rejected`, `test_payment_verified_server_side` (replay), `test_client_cannot_pay_or_verify_other_clients_invoice`.

## Other OWASP items

| Risk | Mitigation |
|---|---|
| SQL injection | SQLAlchemy bound parameters only; no raw SQL built from input; the AI never produces SQL |
| XSS | React escapes output; no `dangerouslySetInnerHTML`; nginx CSP `default-src 'self'`; API responses carry `CSP: default-src 'none'` |
| CSRF | Bearer tokens in headers; the refresh cookie is `SameSite=Strict` and path-scoped; CORS is limited to configured origins |
| Clickjacking | `X-Frame-Options: DENY`, `frame-ancestors 'none'` |
| SSRF | Outbound calls go only to fixed hosts (Graph API, Razorpay, OpenAI); Meta media URLs must be HTTPS on Meta-owned domains and redirects aren't followed |
| CSV injection | Report exports prefix `= + - @` cells with `'` (`test_csv_formula_injection_neutralised`) |
| Rate abuse | Redis fixed-window limits on login, refresh, reset, OTP, portal link/download/upload/checkout, webhooks, AI, downloads and WhatsApp sending |
| Secret leakage | Secrets only from env or encrypted DB columns (Fernet); per-firm tokens are write-only in the API; logs and audit metadata pass through a redactor (password, token, secret, otp, signature, authorization); OTP message bodies and payloads are masked after sending (`test_otp_message_body_is_redacted`, `test_whatsapp_settings_never_expose_tokens`, `test_audit_logs_have_no_secrets`) |
| Insecure config | `APP_ENV=production` refuses to start with default or missing `SECRET_KEY`/`ENCRYPTION_KEY` or missing provider secrets; dev tools (simulator, mock checkout, dev OTP display) are disabled |
| Request tracing | Request ID on every response and log line; paths containing tokens are masked in access logs |

## AI safety

- The AI classifies only; tools enforce organization, client, permission and ownership checks (`test_tools_enforce_client_ownership`).
- Replies are rendered from database facts. "Filed" appears only when the task really is FILED (`test_ai_never_claims_filed_without_backend_data`). Unapproved documents are never offered (`test_unapproved_documents_never_offered_by_ai`).
- Advice questions are routed to a human (`test_advice_questions_are_routed_to_ca`). FAQ answers come only from the firm's own configured FAQ list.
- The OpenAI prompt tells the model to ignore instructions inside user messages; its output is schema-validated, with a rule-based fallback.

## Privacy architecture (Indian context)

The building blocks a firm needs for its obligations, for example under the Digital Personal Data Protection Act, 2023. ProDesk does not by itself make a firm compliant.

- **Notice and consent:** append-only `consent_records` (purpose, granted/withdrawn, channel, notice version, recorder, evidence). WhatsApp opt-in and opt-out always write here.
- **Access control:** RBAC, assignment-based visibility, OTP for clients.
- **Audit trail:** `audit_logs` for logins, data changes, views and downloads, messages, payments and permission changes; secrets are never stored there.
- **Data export:** `GET /clients/{id}/export` returns a machine-readable JSON of the client's data.
- **Erasure:** `POST /clients/{id}/erase` securely deletes files and anonymises personal fields. Firms must first check statutory retention duties for financial records.
- **Retention:** per-firm `privacy.document_retention_days`; a daily job securely deletes stored files of documents archived longer than that.
- **Security event logging:** failed logins, OTP failures, refresh-token reuse and rejected webhooks are audit actions.
- **Data residency:** deploy in `ap-south-1` (Mumbai) for S3, RDS and ElastiCache if required.

## Known limitations

- Rate limiting is fixed-window (simple, slightly bursty at window edges).
- The local storage "secure delete" overwrites before unlinking, which is not guaranteed on copy-on-write or SSD filesystems. Production should use S3 with versioning and lifecycle rules that expire noncurrent versions.
- MFA for staff is not implemented yet (recommended next step).
- Antivirus scanning of uploads is not included; add a ClamAV or S3 malware-scanning step in `documents.process` for production.
