"""Deterministic rule-based AI provider supporting English + Hinglish.

Good enough to run ProDesk end-to-end without an LLM, and used in tests.
"""

from __future__ import annotations

import re
from typing import Any

from app.integrations.ai.base import (
    AIProvider,
    ClientIntent,
    ClientIntentName,
    DocumentSuggestion,
    StaffQuery,
    StaffQueryName,
)
from app.models.enums import DocumentType, ServiceType

DOC_KEYWORDS: list[tuple[DocumentType, tuple[str, ...]]] = [
    (DocumentType.ITR_ACKNOWLEDGEMENT, ("itr ack", "acknowledgement", "itr-v", "itrv", "itr v")),
    (DocumentType.ITR_COMPUTATION, ("computation",)),
    (DocumentType.BALANCE_SHEET, ("balance sheet", "balancesheet", "balance_sheet", "bs ")),
    (DocumentType.PROFIT_LOSS, ("profit", "p&l", "pnl", "profit and loss")),
    (DocumentType.GST_RETURN, ("gstr", "gst return")),
    (DocumentType.GST_CERTIFICATE, ("gst certificate", "gst registration", "reg-06")),
    (DocumentType.TDS_DOCUMENT, ("tds", "form 16", "form16", "26as")),
    (DocumentType.AUDIT_REPORT, ("audit report", "3cd", "3cb", "audit")),
    (DocumentType.BANK_STATEMENT, ("bank statement", "statement", "passbook")),
    (DocumentType.PAN, ("pan card", "pan")),
    (DocumentType.AADHAAR, ("aadhaar", "aadhar")),
    (DocumentType.RECEIPT, ("receipt",)),
    (DocumentType.INVOICE, ("invoice", "bill")),
]

HANDOFF = ("ca se baat", "human", "agent", "baat karni", "call me", "talk to", "connect karo", "insaan", "person")
UPLOAD = ("upload", "bhejna hai", "send document", "attach", "submit document", "jama karna")
PENDING = (
    "pending documents",
    "kaunse documents",
    "documents pending",
    "kya chahiye",
    "which documents",
    "missing documents",
    "documents baaki",
)
PAYMENT = ("payment", "kitna pending", "dues", "outstanding", "balance due", "paisa", "fees pending")
APPOINT = ("appointment", "meeting", "milna", "schedule", "visit")
STATUS = ("status", "kya hua", "update", "progress", "filed", "kahan tak")
WANT = ("bhejo", "send", "chahiye", "share", "download", "de do", "dedo", "need", "give")


def _norm(text: str) -> str:
    return " " + re.sub(r"\s+", " ", text.lower()).strip() + " "


def _detect_doc_type(t: str) -> DocumentType | None:
    for dtype, words in DOC_KEYWORDS:
        if any(w in t for w in words):
            return dtype
    return None


def _detect_fy(t: str) -> tuple[str | None, int | None]:
    m = re.search(r"(20\d{2})\s*[-/]\s*(\d{2,4})", t)
    if m:
        start = int(m.group(1))
        return f"{start}-{str(start + 1)[-2:]}", None
    m = re.search(r"\bfy\s*(20\d{2})\b", t)
    if m:
        start = int(m.group(1))
        return f"{start}-{str(start + 1)[-2:]}", None
    if any(w in t for w in ("pichle saal", "last year", "previous year", "pichhle saal", "last fy")):
        return None, -1
    if any(w in t for w in ("is saal", "this year", "current year", "current fy")):
        return None, 0
    return None, None


class MockAIProvider(AIProvider):
    name = "mock"

    def classify_client_message(self, text: str) -> ClientIntent:
        t = _norm(text)
        fy, rel = _detect_fy(t)
        dtype = _detect_doc_type(t)
        base: dict[str, Any] = {
            "financial_year": fy,
            "relative_year": rel,
            "language": "hi-en" if re.search(r"\b(kya|hai|mera|mujhe|bhejo|karo)\b", t) else "en",
        }

        def mk(intent: ClientIntentName, confidence: float, **extra: Any) -> ClientIntent:
            return ClientIntent.model_validate({"intent": intent, "confidence": confidence, **base, **extra})

        if any(w in t for w in HANDOFF):
            return mk(ClientIntentName.HUMAN_HANDOFF, 0.95)
        if any(w in t for w in PENDING):
            return mk(ClientIntentName.GET_PENDING_DOCUMENTS, 0.9)
        if any(w in t for w in UPLOAD):
            return mk(ClientIntentName.UPLOAD_DOCUMENT, 0.9)
        if any(w in t for w in APPOINT):
            return mk(ClientIntentName.APPOINTMENT_REQUEST, 0.85)
        if any(w in t for w in PAYMENT) and "invoice" not in t:
            return mk(ClientIntentName.GET_PAYMENT_STATUS, 0.9)
        if "itr" in t and any(w in t for w in STATUS) and not any(w in t for w in WANT):
            return mk(ClientIntentName.GET_ITR_STATUS, 0.9, service_type=ServiceType.ITR)
        if "gst" in t and any(w in t for w in STATUS) and not any(w in t for w in WANT):
            return mk(ClientIntentName.GET_TASK_STATUS, 0.85, service_type=ServiceType.GST)
        if dtype == DocumentType.INVOICE or "invoice" in t:
            return mk(ClientIntentName.GET_INVOICE, 0.85)
        if dtype and any(w in t for w in WANT):
            return mk(ClientIntentName.GET_DOCUMENT, 0.85, document_type=dtype)
        if any(w in t for w in STATUS):
            svc = next((s for s in ServiceType if s.value.lower() in t), None)
            return mk(ClientIntentName.GET_TASK_STATUS, 0.6, service_type=svc)
        if dtype:
            return mk(ClientIntentName.GET_DOCUMENT, 0.6, document_type=dtype)
        if "?" in t or any(w in t for w in (" how ", " kaise ", " what ", " kya ", " timing", " fees", " address")):
            return mk(ClientIntentName.FAQ, 0.5)
        return mk(ClientIntentName.UNKNOWN, 0.0)

    def classify_staff_query(self, text: str) -> StaffQuery:
        t = _norm(text)
        svc = next((s for s in ServiceType if f" {s.value.lower()} " in t), None)
        m = re.search(r"(?:haven'?t|have not|not|nahi)\s+(?:submitted|sent|uploaded|provided)\s+(.+?)[\s?.]*$", t.strip())
        if m:
            return StaffQuery(query=StaffQueryName.CLIENTS_MISSING_DOCUMENT, document_name=m.group(1).strip(" ?.")[:100])
        m = re.search(r"assigned to(?: employee)?\s+([a-z][a-z .]{1,60})", t)
        if m and "client" in t:
            return StaffQuery(query=StaffQueryName.CLIENTS_BY_EMPLOYEE, employee_name=m.group(1).strip(" ?."))
        if "pending document" in t or ("pending" in t and "document" in t):
            return StaffQuery(query=StaffQueryName.CLIENTS_WITH_PENDING_DOCUMENTS)
        if "overdue" in t and "task" in t:
            return StaffQuery(query=StaffQueryName.OVERDUE_TASKS, service_type=svc)
        if ("unpaid" in t or "outstanding" in t or "overdue" in t) and "invoice" in t:
            return StaffQuery(query=StaffQueryName.UNPAID_INVOICES)
        if "this week" in t and "task" in t:
            return StaffQuery(query=StaffQueryName.TASKS_DUE_THIS_WEEK, service_type=svc)
        return StaffQuery(query=StaffQueryName.UNSUPPORTED)

    def match_faq(self, text: str, faqs: list[dict[str, Any]]) -> int | None:
        words = {w for w in re.findall(r"[a-z]{3,}", text.lower())}
        best, best_score = None, 0
        for i, faq in enumerate(faqs):
            q_words = {w for w in re.findall(r"[a-z]{3,}", str(faq.get("question", "")).lower())}
            kw = {str(k).lower() for k in faq.get("keywords", [])}
            score = len(words & q_words) + 2 * len(words & kw)
            if score > best_score:
                best, best_score = i, score
        return best if best_score >= 2 else None

    def suggest_document_metadata(self, file_name: str, text_excerpt: str) -> DocumentSuggestion:
        t = _norm(file_name.replace("_", " ").replace("-", " ") + " " + text_excerpt[:2000])
        dtype = _detect_doc_type(t)
        fy, _ = _detect_fy(_norm(file_name + " " + text_excerpt[:2000]))
        m = re.search(r"assessment year\s*:?\s*(20\d{2})\s*-\s*(\d{2})", t)
        if not fy and m:
            ay_start = int(m.group(1))
            fy = f"{ay_start - 1}-{str(ay_start)[-2:]}"
        return DocumentSuggestion(document_type=dtype, financial_year=fy, confidence=0.6 if dtype else 0.0)
