"""WhatsApp document desk: identify the client, list their documents, send the chosen file.

    "I am Abhishek Sahu"  /  "9876543210"  →  identify  →  list of approved documents  →  tap one
    →  the PDF is sent in the chat (signed URL minted at send time, delivery + audit recorded)

Identity rules (the database decides, never the AI):
* A message from a client's registered WhatsApp number identifies that client directly.
* A name or number claimed from any *other* number is only trusted after an OTP sent to the
  registered number is typed back here. The reply is the same whether or not the claim matched,
  so the bot cannot be used to find out who is a client.
* A verified chat stays verified for WHATSAPP_IDENTITY_TTL_MINUTES; after that the client
  verifies again.
"""

from __future__ import annotations

import difflib
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import client_principal, system_principal
from app.core.errors import RateLimited, ValidationFailed
from app.core.logging import get_logger
from app.core.phone import mask_phone, normalize_indian_phone
from app.core.rate_limit import hit
from app.core.security import generate_otp, hash_token, now_utc
from app.models import Client, ClientOtp, Conversation, Document, Message, Organization
from app.models.enums import ClientStatus, DeliveryStatus, MessageSender, MessageStatus, MessageType, TemplateKey
from app.services import audit, messaging
from app.services.assistant import tools
from app.services.audit import AuditAction

log = get_logger("assistant.document_bot")

OTP_PURPOSE = "WHATSAPP_CHAT"
CTX_KEY = "doc_bot"
ROW_PREFIX = "doc:"
MENU_LIMIT = 10  # WhatsApp list messages hold at most 10 rows

_NAME = r"(?P<name>[a-z][a-z.' ]{1,60}?)"
_GREETING = r"(?:(?:hi|hello|hey|namaste|namaskar|good\s+(?:morning|afternoon|evening))\b[\s,!.]*)?"
_IDENTITY_PATTERNS = [
    re.compile(rf"^{_GREETING}(?:i\s+am|i'm|im|this\s+is|my\s+name\s+is|my\s+name's|name\s*[:\-])\s+{_NAME}[\s.!]*$", re.I),
    re.compile(rf"^{_GREETING}(?:main|mai|mein)\s+{_NAME}\s+(?:hoon|hu|hun|hai)[\s.!]*$", re.I),
    re.compile(rf"^{_GREETING}mera\s+naam\s+{_NAME}\s+(?:hai|he|h)[\s.!]*$", re.I),
]
_PHONE_CLAIM = re.compile(
    r"^\s*(?:(?:my\s+)?(?:registered\s+)?(?:mobile|phone|whatsapp)?\s*(?:number|no\.?)\s*(?:is)?\s*[:\-]?\s*)?"
    r"(\+?[\d\s\-]{10,17})\s*$",
    re.I,
)
_OTP_REPLY = re.compile(r"^\s*(\d{3})\s?(\d{3})\s*$")
_HONORIFICS = {"mr", "mrs", "ms", "miss", "shri", "sri", "smt", "dr", "ca", "ji", "sir", "madam"}
MENU_WORDS = {
    "documents",
    "document",
    "docs",
    "my documents",
    "show documents",
    "show my documents",
    "send documents",
    "list documents",
    "mere documents",
    "mere documents dikhao",
}
FUZZY_THRESHOLD = 0.85


@dataclass(frozen=True)
class Claim:
    kind: str  # "name" | "phone"
    value: str


# --- parsing ------------------------------------------------------------------------


def _norm_name(raw: str) -> str:
    words = re.sub(r"[^a-z ]+", " ", raw.lower()).split()
    return " ".join(w for w in words if w not in _HONORIFICS)


def parse_claim(text: str) -> Claim | None:
    """'I am Abhishek Sahu' / 'Mera naam Abhishek hai' / '98765 43210' → Claim, else None."""
    t = (text or "").strip()
    if not t or len(t) > 100:
        return None
    m = _PHONE_CLAIM.match(t)
    if m:
        try:
            return Claim("phone", normalize_indian_phone(m.group(1)))
        except ValidationFailed:
            return None
    for pat in _IDENTITY_PATTERNS:
        m = pat.match(t)
        if m:
            name = _norm_name(m.group("name"))
            if name and len(name.split()) <= 5:
                return Claim("name", name)
    return None


# --- identity -----------------------------------------------------------------------


def _state(conv: Conversation) -> dict:
    return dict((conv.context or {}).get(CTX_KEY) or {})


def _save_state(conv: Conversation, state: dict) -> None:
    conv.context = {**(conv.context or {}), CTX_KEY: state}


def acting_client(db: Session, conv: Conversation, registered: Client | None) -> Client | None:
    """The client this chat currently speaks for: an OTP-verified identity, else the registered one."""
    verified = _state(conv).get("verified")
    if verified and datetime.fromisoformat(verified["until"]) > now_utc():
        c = db.get(Client, uuid.UUID(verified["client_id"]))
        if c is not None and c.organization_id == conv.organization_id and c.status != ClientStatus.ARCHIVED:
            return c
    return registered


def find_client(db: Session, org_id: uuid.UUID, claim: Claim) -> Client | None:
    """Exactly one active client matching the claim, or None (no match, or ambiguous)."""
    base = select(Client).where(Client.organization_id == org_id, Client.status != ClientStatus.ARCHIVED)
    if claim.kind == "phone":
        return db.execute(base.where(Client.phone == claim.value)).unique().scalar_one_or_none()
    tokens = [t for t in claim.value.split() if len(t) >= 3] or claim.value.split()
    rows = db.execute(base.where(or_(*[Client.name.ilike(f"%{t}%") for t in tokens])).limit(200)).unique().scalars().all()
    scored = [(difflib.SequenceMatcher(None, claim.value, _norm_name(c.name)).ratio(), c) for c in rows]
    exact = [c for s, c in scored if s == 1.0]
    if exact:
        return exact[0] if len(exact) == 1 else None
    close = [c for s, c in scored if s >= FUZZY_THRESHOLD]
    return close[0] if len(close) == 1 else None


def _start_verification(db: Session, org: Organization, conv: Conversation, target: Client | None) -> None:
    """Send an OTP to the claimed client's registered number. The chat reply never reveals a match."""
    state = _state(conv)
    state.pop("pending", None)
    if target is not None:
        try:
            hit(f"wa_otp_target:{target.id}", 3, 600, fail_closed=True)  # don't let anyone spam a client with codes
        except RateLimited:
            target = None
    if target is not None:
        code = generate_otp(6)
        db.execute(
            update(ClientOtp)
            .where(ClientOtp.client_id == target.id, ClientOtp.purpose == OTP_PURPOSE, ClientOtp.consumed_at.is_(None))
            .values(consumed_at=now_utc())
        )
        otp = ClientOtp(
            organization_id=org.id,
            client_id=target.id,
            purpose=OTP_PURPOSE,
            code_hash=hash_token(f"{target.id}:{code}"),
            expires_at=now_utc() + timedelta(seconds=settings.OTP_TTL_SECONDS),
        )
        db.add(otp)
        db.flush()
        messaging.send_template_to_client(db, target, TemplateKey.OTP, [code], url_suffix=code, bypass_opt_in=True)
        state["pending"] = {"client_id": str(target.id), "otp_id": str(otp.id)}
        audit.record(
            db,
            system_principal(org.id),
            AuditAction.WHATSAPP_IDENTITY_CLAIMED,
            resource="client",
            resource_id=target.id,
            client_id=target.id,
            metadata={"from": mask_phone(conv.contact.phone) if conv.contact else None},
        )
    _save_state(conv, state)


def _check_otp(db: Session, org: Organization, conv: Conversation, code: str) -> Client | str:
    """Returns the verified Client, or an error message for the chat."""
    state = _state(conv)
    pending = state.get("pending") or {}
    otp = db.get(ClientOtp, uuid.UUID(pending["otp_id"])) if pending.get("otp_id") else None
    now = now_utc()
    if otp is None or otp.consumed_at is not None or otp.expires_at < now or otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        state.pop("pending", None)
        _save_state(conv, state)
        return "That code has expired. Send your registered name or mobile number again to get a new one."
    if otp.code_hash != hash_token(f"{otp.client_id}:{code}"):
        otp.attempts += 1
        audit.record(
            db,
            system_principal(org.id),
            AuditAction.CLIENT_OTP_FAILED,
            resource="client",
            resource_id=otp.client_id,
            client_id=otp.client_id,
        )
        if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
            otp.consumed_at = now
            state.pop("pending", None)
            _save_state(conv, state)
            return "Too many wrong attempts. Send your registered name or mobile number again to get a new code."
        return "That code is not correct. Please check and type it again."
    otp.consumed_at = now
    client = db.get(Client, otp.client_id)
    if client is None or client.organization_id != org.id or client.status == ClientStatus.ARCHIVED:
        return "Sorry, I couldn't verify that account. Please contact the office."
    until = now + timedelta(minutes=settings.WHATSAPP_IDENTITY_TTL_MINUTES)
    state.pop("pending", None)
    state["verified"] = {"client_id": str(client.id), "until": until.isoformat()}
    _save_state(conv, state)
    audit.record(
        db,
        client_principal(org.id, client.id),
        AuditAction.WHATSAPP_IDENTITY_VERIFIED,
        resource="client",
        resource_id=client.id,
        client_id=client.id,
        metadata={"from": mask_phone(conv.contact.phone) if conv.contact else None},
    )
    return client


# --- outbound -----------------------------------------------------------------------


def reply_text(db: Session, conv: Conversation, text: str) -> Message:
    return messaging.queue_message(
        db, conv.organization_id, messaging.Outbound(kind=MessageType.TEXT, body=text), conversation=conv, sender=MessageSender.BOT
    )


def prompt_identity(db: Session, org: Organization, conv: Conversation) -> Message:
    return reply_text(
        db,
        conv,
        f"Welcome to {org.name}! To get your documents, please tell me your registered name "
        '(for example: "I am Abhishek Sahu") or your registered mobile number.',
    )


def _doc_label(doc: Document) -> str:
    from app.services.delivery import DOC_LABELS

    return DOC_LABELS.get(doc.document_type, "Document")


def send_document_menu(db: Session, org: Organization, conv: Conversation, client: Client, docs: list[Document] | None = None) -> Message:
    ctx = tools.ToolContext(principal=client_principal(org.id, client.id), conversation_id=conv.id)
    if docs is None:
        docs = tools.list_client_documents(db, ctx, limit=MENU_LIMIT)
    docs = docs[:MENU_LIMIT]
    if not docs:
        return reply_text(
            db,
            conv,
            f"Hello {client.name}! No documents have been shared with you yet. The {org.name} team will send them here once they're ready.",
        )
    rows = []
    for d in docs:
        version = next((v for v in d.versions if v.id == d.approved_version_id), None)
        desc = " · ".join(x for x in (f"FY {d.financial_year}" if d.financial_year else None, version.file_name if version else None) if x)
        rows.append({"id": f"{ROW_PREFIX}{d.id}", "title": _doc_label(d)[:24], "description": desc[:72] or None})
    body = (
        f"Hello {client.name}! These are your documents with {org.name}. "
        "Tap *View documents* and choose the one you need — I'll send the file right here."
    )
    if len(docs) == MENU_LIMIT:
        body += '\n\nShowing your 10 most recent. For an older one, type it, e.g. "Balance sheet 2022-23".'
    return messaging.queue_message(
        db,
        org.id,
        messaging.Outbound(
            kind=MessageType.INTERACTIVE,
            body=body,
            list_sections=[{"title": "Your documents", "rows": rows}],
            list_button="View documents",
        ),
        conversation=conv,
        sender=MessageSender.BOT,
    )


def send_document_file(db: Session, org: Organization, conv: Conversation, client: Client, doc: Document) -> Message:
    """Send one approved document of THIS client as a WhatsApp file and record the delivery."""
    from app.services.delivery import create_delivery

    if doc.client_id != client.id or doc.organization_id != org.id or doc.deleted_at is not None:
        raise ValidationFailed("Document does not belong to this client")
    version = next((v for v in doc.versions if v.id == doc.approved_version_id), None)
    if version is None:
        raise ValidationFailed("Document has no approved version")
    delivery, _ = create_delivery(db, doc, version, initiated_by=None, channel="WHATSAPP_FILE")
    label = _doc_label(doc)
    fy = f" — FY {doc.financial_year}" if doc.financial_year else ""
    caption = f"{label}{fy}\n{org.name}\n\nNeed another? Type *documents*."
    msg = messaging.queue_message(
        db,
        org.id,
        messaging.Outbound(kind=MessageType.DOCUMENT, body=caption, file_name=version.file_name, version_id=version.id),
        conversation=conv,
        sender=MessageSender.BOT,
    )
    delivery.message_id = msg.id
    if msg.status == MessageStatus.FAILED:
        delivery.status = DeliveryStatus.FAILED
        delivery.error = f"{msg.error_code}: {msg.error}"
    audit.record(
        db,
        client_principal(org.id, client.id),
        AuditAction.DOCUMENT_DELIVERY_CREATED,
        resource="document",
        resource_id=doc.id,
        client_id=client.id,
        metadata={"delivery_id": str(delivery.id), "version": version.version_number, "via": "whatsapp_file"},
    )
    return msg


def _selected_document(db: Session, org: Organization, client: Client, row_id: str) -> Document | None:
    try:
        doc_id = uuid.UUID(row_id.removeprefix(ROW_PREFIX))
    except ValueError:
        return None
    ctx = tools.ToolContext(principal=client_principal(org.id, client.id))
    stmt = tools._available_docs_stmt(ctx).where(Document.id == doc_id)
    return db.execute(stmt).unique().scalar_one_or_none()


# --- entrypoint ---------------------------------------------------------------------


def handle(
    db: Session, *, org: Organization, conv: Conversation, registered: Client | None, text: str | None, reply_id: str | None
) -> bool:
    """Handle identity, OTP, menu and document-pick messages. Returns False to let the
    regular client assistant handle the message."""
    raw = (text or "").strip()
    state = _state(conv)

    # 1) OTP typed back after a name/number claim
    if state.get("pending"):
        m = _OTP_REPLY.match(raw)
        if m:
            result = _check_otp(db, org, conv, m.group(1) + m.group(2))
            if isinstance(result, str):
                reply_text(db, conv, result)
            else:
                send_document_menu(db, org, conv, result)
            return True

    client = acting_client(db, conv, registered)

    # 2) a document picked from the list
    if reply_id and reply_id.startswith(ROW_PREFIX):
        if client is None:
            prompt_identity(db, org, conv)
            return True
        doc = _selected_document(db, org, client, reply_id)
        if doc is None:
            reply_text(db, conv, "That document is no longer available. Type *documents* to see your current list.")
        else:
            send_document_file(db, org, conv, client, doc)
        return True

    # 3) "I am Abhishek Sahu" / "9876543210"
    claim = parse_claim(raw)
    if claim is not None:
        try:
            hit(f"wa_claim:{org.id}:{conv.contact_id}", 6, 3600, fail_closed=True)
        except RateLimited:
            reply_text(db, conv, "Too many attempts. Please try again later or contact the office.")
            return True
        target = find_client(db, org.id, claim)
        if target is not None and client is not None and target.id == client.id:
            send_document_menu(db, org, conv, client)
            return True
        if target is not None and registered is not None and target.id == registered.id:
            state.pop("verified", None)  # switching back to the number's own client
            state.pop("pending", None)
            _save_state(conv, state)
            send_document_menu(db, org, conv, registered)
            return True
        if target is None and client is not None and claim.kind == "name":
            return False  # an identified client saying "main ... hoon" that isn't a name: let the assistant answer
        _start_verification(db, org, conv, target)
        what = "number" if claim.kind == "phone" else "name"
        where = "that number" if claim.kind == "phone" else "the mobile number registered for that name"
        reply_text(
            db,
            conv,
            f"If that {what} is registered with {org.name}, I've sent a 6-digit verification code on WhatsApp to {where}. "
            "Please type the code here.\n\nNo code? Send your registered mobile number instead, or contact the office.",
        )
        return True

    # 4) "documents" → the list
    if client is not None and raw.lower().strip(" .!?") in MENU_WORDS:
        send_document_menu(db, org, conv, client)
        return True

    return False
