from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORM
from app.schemas.document import ClientRef


class ContactOut(ORM):
    id: uuid.UUID
    wa_id: str
    phone: str | None
    profile_name: str | None
    last_inbound_at: datetime | None


class AgentRef(ORM):
    id: uuid.UUID
    full_name: str


class ConversationOut(ORM):
    id: uuid.UUID
    contact: ContactOut
    client_id: uuid.UUID | None
    client: ClientRef | None
    status: str
    handover_state: str
    assigned_agent: AgentRef | None
    last_message_at: datetime | None
    last_message_preview: str | None
    unread_count: int
    service_window_open: bool = False


class MessageOut(ORM):
    id: uuid.UUID
    conversation_id: uuid.UUID
    provider_message_id: str | None
    direction: str
    message_type: str
    sender: str
    sender_user_id: uuid.UUID | None
    recipient: str | None
    body: str | None
    template_key: str | None
    status: str
    timestamp: datetime
    sent_at: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None
    error: str | None
    error_code: str | None
    payload: dict[str, Any]


class AgentReply(BaseModel):
    body: str = Field(min_length=1, max_length=4096)


class SendTemplateRequest(BaseModel):
    client_id: uuid.UUID
    template_key: str
    body_params: list[str] = Field(default_factory=list, max_length=10)


class HandoverAction(BaseModel):
    action: str = Field(pattern="^(assign|take|resume_bot|close)$")
    agent_id: uuid.UUID | None = None


class SimulateInbound(BaseModel):
    phone: str
    text: str | None = Field(default=None, max_length=4096)
    profile_name: str | None = None
    media_base64: str | None = None
    media_mime: str | None = None
    media_filename: str | None = None
    caption: str | None = None


class AIChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)


class AIChatResponse(BaseModel):
    query: str
    answer: str
    columns: list[str]
    rows: list[dict[str, Any]]
    disclaimer: str
