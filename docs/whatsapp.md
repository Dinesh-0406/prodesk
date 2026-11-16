# WhatsApp integration (official Meta Cloud API)

ProDesk talks to WhatsApp **only** through Meta's official WhatsApp Business Platform (Cloud API), using the Graph API at `https://graph.facebook.com/<version>`. It never uses WhatsApp Web automation, Selenium, unofficial libraries, QR-code sessions or browser automation.

Meta's console labels and policies change over time, so always confirm the current steps in Meta's own documentation: <https://developers.facebook.com/docs/whatsapp/cloud-api>. This guide contains no credentials. Every value below comes from your own Meta account.

## 1. Meta developer setup

1. Sign in at **developers.facebook.com** and create an app of type **Business**.
2. Add the **WhatsApp** product to the app.
3. Meta gives you a test phone number and a temporary access token, which are enough for development.

## 2. Business portfolio

Link the app to your **Meta Business portfolio** (business.facebook.com). Complete **business verification** before going live; it is needed for higher messaging limits and display-name approval.

## 3. WhatsApp Business Account (WABA)

The WhatsApp product creates or links a WABA. Note the **WhatsApp Business Account ID** (WhatsApp → API Setup). ProDesk uses it to sync template status.

## 4. Phone number

Add the firm's business phone number to the WABA and verify it by SMS or voice call. The number cannot be registered in the consumer WhatsApp app or WhatsApp Business app at the same time. Set a display name (subject to Meta review).

## 5. Phone Number ID

In **WhatsApp → API Setup**, copy the **Phone number ID** (this is not the phone number itself). ProDesk sends from `/{phone-number-id}/messages`. It also uses this ID to route incoming webhooks to the right firm, so each ID can belong to only one ProDesk organization.

## 6. Access token

The temporary token expires within about a day, so don't use it in production. For production:

1. In **Business settings → Users → System users**, create a system user (admin).
2. Assign it the app and the WABA with full control.
3. **Generate token** with the permissions `whatsapp_business_messaging` and `whatsapp_business_management`, choosing a non-expiring or long-lived expiry.
4. Enter it in **ProDesk → Settings → WhatsApp → Access token**. It is Fernet-encrypted at rest and never returned to the browser; the UI shows only `••••last4`. Alternatively, set the platform-wide `WHATSAPP_ACCESS_TOKEN`.

If Meta reports the token as expired or invalid (for example error 190), ProDesk marks the account **ERROR**, stops treating sends as successful, and notifies firm admins.

## 7. Webhook

In the app's **WhatsApp → Configuration** (Webhooks):

| Field | Value |
|---|---|
| Callback URL | `https://<api-domain>/api/v1/webhooks/whatsapp` (must be public HTTPS) |
| Verify token | the exact value of `WHATSAPP_VERIFY_TOKEN` |
| Webhook fields | subscribe to **`messages`** (covers inbound messages and sent/delivered/read/failed statuses) |

Also copy **App settings → Basic → App secret** into `WHATSAPP_APP_SECRET`. ProDesk rejects any POST without a valid `X-Hub-Signature-256` (HMAC-SHA256 of the raw body). A firm using its *own* Meta app can store that app's secret in Settings instead.

Processing rules:
- The webhook persists one `webhook_events` row per message or status, keyed by `msg:<wamid>` or `status:<wamid>:<status>`, using `ON CONFLICT DO NOTHING`. Meta retries and replays are dropped, and messages are also unique on `provider_message_id`.
- It returns `200` immediately. A worker does the processing: client lookup, AI, media download, replies.
- Media is fetched only from Meta-owned hosts (SSRF guard), then validated like any upload: extension, magic bytes, size, and no macro-enabled Office files.

## 8. Templates

Messages that the business starts (not replies inside the 24-hour window) must use **pre-approved templates**. Create these in **WhatsApp Manager → Message templates**. ProDesk's defaults (rename them freely):

| ProDesk key | Default name | Category | Body variables | Button |
|---|---|---|---|---|
| DOCUMENT_READY | `prodesk_document_ready` | Utility | client name, document, FY, firm | URL |
| DOCUMENT_REQUEST | `prodesk_document_request` | Utility | client, firm, request title, documents, due date | URL |
| DOCUMENT_REMINDER | `prodesk_document_reminder` | Utility | client, request, documents, due date | URL |
| PAYMENT_REMINDER | `prodesk_payment_reminder` | Utility | client, invoice no., amount, due date | URL |
| INVOICE_CREATED | `prodesk_invoice_created` | Utility | client, firm, invoice no., amount, due date | URL |
| TASK_COMPLETED | `prodesk_task_update` | Utility | client, task, status, firm | — |
| WELCOME | `prodesk_welcome` | Utility | client, firm | — |
| OTP | `prodesk_otp` | **Authentication** | code | Copy code |
| HUMAN_HANDOFF | `prodesk_human_handoff` | Utility | client, firm | — |

**URL buttons:** set the button URL in Meta to `https://<frontend-domain>/portal/{{1}}`. ProDesk fills `{{1}}` with `link/<token>` (document delivery), `requests` or `invoices`. The body text previews are in `backend/app/services/templates.py` and can be edited per firm in Settings.

**Authentication template (OTP):** create it as an Authentication template with a *Copy code* button. ProDesk sends the code both as body parameter 1 and as the button parameter, which is what Meta requires for this type.

**Approval is never assumed.** In ProDesk each template has a status (`NOT_SUBMITTED`, `PENDING`, `APPROVED`, `REJECTED`, `PAUSED`, `DISABLED`). Only `APPROVED` templates are sent. With the `meta` provider, new firms start at `NOT_SUBMITTED`. Set the status in Settings once Meta approves, or click **Sync status from Meta**, which reads `GET /{waba-id}/message_templates`.

Errors are handled without breaking the flow:

| Situation | ProDesk behaviour |
|---|---|
| Template not approved / paused / rejected (e.g. 132015/132016) | Message FAILED, template marked REJECTED with the error, admins notified, delivery marked FAILED with the reason |
| Invalid template / parameter mismatch (1320xx, 100) | Message FAILED with the error; template status kept; admins notified |
| Outside the 24-hour window (131047) / free-form not allowed | Blocked before sending; staff are told to use a template |
| Rate limit (130429, 131056, 80007, HTTP 429) | Retried with exponential backoff; per-org send rate limit as well |
| Expired or invalid token (190) | Account → ERROR, admins notified |
| Network or 5xx | Retried (up to 6 attempts) |

## 9. Policy awareness built in

- **Opt-in:** business-initiated templates require a recorded opt-in. Staff record it when creating the client, by CSV, or through a consent entry, and every change is written to `consent_records`.
- **Opt-out:** a client sending `STOP` (or "unsubscribe", "band karo") is opted out at once and gets one confirmation; `START` re-subscribes. Opted-out clients receive nothing else, including reminders.
- **Customer service window:** free-form replies are allowed only within 24 hours of the client's last message. The UI shows whether the window is open.
- **Message categories and cost:** Utility, Authentication and Marketing templates are billed differently by Meta, and business-initiated messages are not free. ProDesk sends only Utility and Authentication templates by default and never sends marketing. Check Meta's current pricing for India.
- **Reminders:** frequency, maximum count, quiet hours (firm timezone) and per-slot de-duplication all apply, to avoid spamming clients.

## 10. Production checklist

- [ ] Business verification done, display name approved, phone number registered on Cloud API
- [ ] System-user token with `whatsapp_business_messaging` + `whatsapp_business_management`
- [ ] `WHATSAPP_PROVIDER=meta`, `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_API_VERSION` set
- [ ] Webhook verified and subscribed to `messages`, reachable over HTTPS
- [ ] All nine templates created and approved; names mapped in Settings; statuses synced
- [ ] *Test connection* in Settings succeeds
- [ ] Send a test document to a staff member's own number and confirm delivered/read ticks arrive

## 11. Local testing

- `WHATSAPP_PROVIDER=mock` (the default) needs no Meta account. Outbound messages get fake `wamid.MOCK…` IDs and appear in the inbox. A template whose name starts with `rejected_` simulates a Meta rejection.
- **WhatsApp → Simulate client message** in the dashboard builds a Meta-format payload, signs it with `WHATSAPP_APP_SECRET`, and sends it through the real ingest → queue → worker path (development only).
- To test against real Meta from a laptop, expose the API with an HTTPS tunnel, use that URL as the callback, and use Meta's test number.

## 12. Environment variables

| Variable | Purpose |
|---|---|
| `WHATSAPP_PROVIDER` | `mock` or `meta` |
| `WHATSAPP_ACCESS_TOKEN` | Platform default token (per-firm tokens in Settings take precedence) |
| `WHATSAPP_PHONE_NUMBER_ID` | Default phone number ID |
| `WHATSAPP_BUSINESS_ACCOUNT_ID` | WABA ID (template sync) |
| `WHATSAPP_VERIFY_TOKEN` | Webhook verification handshake |
| `WHATSAPP_APP_SECRET` | Webhook signature validation |
| `WHATSAPP_API_VERSION` | Graph API version, e.g. `v21.0` (check Meta's changelog and keep it current) |
| `WHATSAPP_SEND_RATE_PER_MINUTE` | Per-firm send throttle |
