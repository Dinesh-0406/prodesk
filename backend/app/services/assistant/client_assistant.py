"""Client WhatsApp assistant.

    message → AI intent (structured) → backend tool (authorised) → DB facts → rendered reply

Replies are rendered deterministically from tool results, so the assistant can never claim
something (e.g. "your ITR has been filed") that the backend data does not say. It separates
*data retrieval* from *professional advice* and refers advice questions to the CA.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.context import client_principal
from app.core.logging import get_logger
from app.integrations.ai import get_ai_provider
from app.integrations.ai.base import ClientIntent, ClientIntentName
from app.models import Client, Conversation, Organization
from app.models.enums import SupportRequestType, TaskStatus
from app.services.assistant import tools
from app.services.delivery import DOC_LABELS, create_delivery, portal_link
from app.services.tasks import STATUS_LABELS

log = get_logger("assistant.client")
ADVICE_MARKERS = (
    "should i",
    "kya karu",
    "how much tax",
    "kitna tax",
    "save tax",
    "tax bachana",
    "legal",
    "penalty lagega",
    "is it allowed",
    "best option",
    "invest",
)
DATA_NOTE = "This is the status recorded by your CA's office in ProDesk."


@dataclass
class AssistantReply:
    text: str
    intent: ClientIntent
    actions: list[str] = field(default_factory=list)
    handoff: bool = False
    delivery: Any = None


def _fmt_date(d: Any) -> str:
    return d.strftime("%d %b %Y") if d else "—"


def _menu(org_name: str) -> str:
    return (
        f"I'm the {org_name} assistant. I can help you with:\n"
        '• Your ITR / GST / work status\n• Getting your documents (e.g. "send last year\'s balance sheet")\n'
        "• Pending documents you need to send\n• Invoices and pending payments\n"
        '• Uploading a document (just send the file here)\n• Talking to the CA team ("CA se baat karni hai")'
    )


def handle_client_message(db: Session, *, org: Organization, client: Client, conversation: Conversation, text: str) -> AssistantReply:
    ai = get_ai_provider()
    intent = ai.classify_client_message(text or "")
    ctx = tools.ToolContext(principal=client_principal(org.id, client.id), conversation_id=conversation.id)
    lowered = (text or "").lower()

    if intent.intent not in (ClientIntentName.HUMAN_HANDOFF,) and any(m in lowered for m in ADVICE_MARKERS):
        tools.create_support_request(db, ctx, request_type=SupportRequestType.QUERY, message=text)
        return AssistantReply(
            text="That sounds like a question that needs professional advice, so I've shared it with your CA. "
            "Someone from the team will get back to you.",
            intent=intent,
            actions=["support_request"],
        )

    handler = _HANDLERS.get(intent.intent, _unknown)
    try:
        reply = handler(db, ctx, intent, org, client, conversation, text)
    except Exception:
        log.exception("assistant_tool_failed", extra={"intent": intent.intent})
        reply = AssistantReply(text="Sorry, I couldn't fetch that right now. I've informed the team.", intent=intent)
    return reply


Handler = Any


def _itr_status(
    db: Session, ctx: tools.ToolContext, intent: ClientIntent, org: Organization, client: Client, conv: Conversation, text: str
) -> AssistantReply:
    fy = intent.financial_year
    tasks = tools.get_task_status(db, ctx, service_type="ITR", financial_year=fy)
    if not tasks:
        _support(db, ctx, text)
        return AssistantReply(
            text="I couldn't find an ITR filing task on record for you"
            + (f" for FY {fy}" if fy else "")
            + ". I've asked the team to update you.",
            intent=intent,
            actions=["support_request"],
        )
    t = tasks[0]
    label = STATUS_LABELS.get(t.status, t.status)
    lines = [f"ITR — {t.title}" + (f" (FY {t.financial_year})" if t.financial_year else ""), f"Status: {label}"]
    if t.status in (TaskStatus.FILED, TaskStatus.COMPLETED, TaskStatus.DELIVERED) and t.filed_at:
        lines.append(f"Marked as filed on {_fmt_date(t.filed_at)}" + (f" (ref {t.filing_reference})" if t.filing_reference else ""))
    elif t.due_date:
        lines.append(f"Target date: {_fmt_date(t.due_date)}")
    lines.append(DATA_NOTE)
    return AssistantReply(text="\n".join(lines), intent=intent)


def _support(db: Session, ctx: tools.ToolContext, text: str) -> bool:
    tools.create_support_request(db, ctx, request_type=SupportRequestType.QUERY, message=text)
    return True


def _task_status(
    db: Session, ctx: tools.ToolContext, intent: ClientIntent, org: Organization, client: Client, conv: Conversation, text: str
) -> AssistantReply:
    tasks = tools.get_task_status(
        db, ctx, service_type=intent.service_type.value if intent.service_type else None, financial_year=intent.financial_year
    )
    if not tasks:
        what = f"{intent.service_type.value} " if intent.service_type else ""
        return AssistantReply(
            text=f'I don\'t see any {what}work on record for you right now. If you were expecting something, reply "CA se baat karni hai".',
            intent=intent,
        )
    lines = ["Here is the latest on your work:"]
    for t in tasks[:5]:
        lines.append(
            f"• {t.title}: {STATUS_LABELS.get(t.status, t.status)}"
            + (f" (target {_fmt_date(t.due_date)})" if t.due_date and t.status not in ("COMPLETED", "DELIVERED", "FILED") else "")
        )
    lines.append(DATA_NOTE)
    return AssistantReply(text="\n".join(lines), intent=intent)


def _get_document(
    db: Session, ctx: tools.ToolContext, intent: ClientIntent, org: Organization, client: Client, conv: Conversation, text: str
) -> AssistantReply:
    if intent.document_type is None:
        docs = tools.list_client_documents(db, ctx, limit=8)
        if not docs:
            return AssistantReply(text="No documents have been shared with you yet.", intent=intent)
        lines = ["Which document do you need? Available:"] + [
            f"• {DOC_LABELS.get(d.document_type, d.document_type)}" + (f" FY {d.financial_year}" if d.financial_year else "") for d in docs
        ]
        return AssistantReply(text="\n".join(lines), intent=intent)
    doc = tools.get_document(
        db, ctx, document_type=intent.document_type.value, financial_year=intent.financial_year, relative_year=intent.relative_year
    )
    label = DOC_LABELS.get(intent.document_type.value, "document")
    if doc is None:
        tools.create_support_request(db, ctx, request_type=SupportRequestType.QUERY, message=f"Client requested: {text}")
        return AssistantReply(
            text=f"I couldn't find an approved {label}"
            + (f" for FY {intent.financial_year}" if intent.financial_year else "")
            + " in your records. I've asked the team to check and share it.",
            intent=intent,
            actions=["support_request"],
        )
    version = next(v for v in doc.versions if v.id == doc.approved_version_id)
    delivery, raw = create_delivery(db, doc, version, initiated_by=None)
    return AssistantReply(
        delivery=delivery,
        text=f"Here is your {label}"
        + (f" for FY {doc.financial_year}" if doc.financial_year else "")
        + f". Open it securely (you'll verify with an OTP):\n{portal_link(raw)}",
        intent=intent,
        actions=["delivery_link"],
    )


def _pending_docs(
    db: Session, ctx: tools.ToolContext, intent: ClientIntent, org: Organization, client: Client, conv: Conversation, text: str
) -> AssistantReply:
    pending = tools.get_pending_documents(db, ctx)
    if not pending:
        return AssistantReply(text="Good news — there are no pending document requests from us right now.", intent=intent)
    lines = ["These documents are pending:"]
    for r in pending:
        due = f" (due {_fmt_date(r['due_date'])})" if r["due_date"] else ""
        lines.append(f"*{r['title']}*{due}")
        lines += [f"  • {name}" for name in r["pending"]]
    lines.append("You can send the files right here in this chat.")
    return AssistantReply(text="\n".join(lines), intent=intent)


def _invoice(
    db: Session, ctx: tools.ToolContext, intent: ClientIntent, org: Organization, client: Client, conv: Conversation, text: str
) -> AssistantReply:
    invoices = tools.get_invoice(db, ctx, open_only=False, limit=3)
    if not invoices:
        return AssistantReply(text="There are no invoices on record for you.", intent=intent)
    from app.core.config import settings

    lines = ["Your recent invoices:"]
    for i in invoices:
        lines.append(
            f"• {i.invoice_number}: Rs. {i.total:,.2f} — {i.status.replace('_', ' ').title()}"
            + (f", balance Rs. {i.balance_due:,.2f}" if i.balance_due > 0 and i.status != "PAID" else "")
        )
    lines.append(f"View and pay securely: {settings.FRONTEND_URL}/portal/invoices")
    return AssistantReply(text="\n".join(lines), intent=intent)


def _payment(
    db: Session, ctx: tools.ToolContext, intent: ClientIntent, org: Organization, client: Client, conv: Conversation, text: str
) -> AssistantReply:
    s = tools.get_payment_status(db, ctx)
    if s["open_invoices"] == 0:
        return AssistantReply(text="You have no pending payments with us. Thank you!", intent=intent)
    from app.core.config import settings

    lines = [f"Total pending: Rs. {s['outstanding']:,.2f} across {s['open_invoices']} invoice(s)."]
    for inv in s["invoices"]:
        lines.append(f"• {inv['number']}: Rs. {inv['balance']:,.2f}, due {_fmt_date(inv['due_date'])}")
    lines.append(f"Pay securely: {settings.FRONTEND_URL}/portal/invoices")
    return AssistantReply(text="\n".join(lines), intent=intent)


def _upload(
    db: Session, ctx: tools.ToolContext, intent: ClientIntent, org: Organization, client: Client, conv: Conversation, text: str
) -> AssistantReply:
    conv.context = {**(conv.context or {}), "awaiting_upload": True}
    pending = tools.get_pending_documents(db, ctx)
    extra = ""
    if pending:
        extra = "\nWe're waiting for: " + ", ".join(n for r in pending for n in r["pending"])
    return AssistantReply(text="Sure — please send the file (PDF, JPG, PNG, Word or Excel) here in this chat." + extra, intent=intent)


def _appointment(
    db: Session, ctx: tools.ToolContext, intent: ClientIntent, org: Organization, client: Client, conv: Conversation, text: str
) -> AssistantReply:
    tools.create_support_request(db, ctx, request_type=SupportRequestType.APPOINTMENT, message=text)
    return AssistantReply(
        text="I've requested an appointment for you. The team will confirm a time shortly.", intent=intent, actions=["support_request"]
    )


def _faq(
    db: Session, ctx: tools.ToolContext, intent: ClientIntent, org: Organization, client: Client, conv: Conversation, text: str
) -> AssistantReply:
    faqs = (org.settings or {}).get("faqs", [])
    idx = get_ai_provider().match_faq(text, faqs)
    if idx is not None:
        return AssistantReply(text=str(faqs[idx]["answer"]), intent=intent)
    tools.create_support_request(db, ctx, request_type=SupportRequestType.QUERY, message=text)
    return AssistantReply(
        text="I've passed your question to the team; they'll reply here soon.", intent=intent, actions=["support_request"]
    )


def _handoff(
    db: Session, ctx: tools.ToolContext, intent: ClientIntent, org: Organization, client: Client, conv: Conversation, text: str
) -> AssistantReply:
    return AssistantReply(text=f"Connecting you with the {org.name} team. Someone will reply here shortly.", intent=intent, handoff=True)


def _unknown(
    db: Session, ctx: tools.ToolContext, intent: ClientIntent, org: Organization, client: Client, conv: Conversation, text: str
) -> AssistantReply:
    return AssistantReply(text=_menu(org.name), intent=intent)


_HANDLERS: dict[ClientIntentName, Handler] = {
    ClientIntentName.GET_ITR_STATUS: _itr_status,
    ClientIntentName.GET_TASK_STATUS: _task_status,
    ClientIntentName.GET_DOCUMENT: _get_document,
    ClientIntentName.GET_PENDING_DOCUMENTS: _pending_docs,
    ClientIntentName.GET_INVOICE: _invoice,
    ClientIntentName.GET_PAYMENT_STATUS: _payment,
    ClientIntentName.UPLOAD_DOCUMENT: _upload,
    ClientIntentName.APPOINTMENT_REQUEST: _appointment,
    ClientIntentName.FAQ: _faq,
    ClientIntentName.HUMAN_HANDOFF: _handoff,
    ClientIntentName.UNKNOWN: _unknown,
}
