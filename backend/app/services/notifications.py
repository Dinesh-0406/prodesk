"""NotificationService: one entry point, pluggable channels (in-app, email, WhatsApp; SMS later)."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import Perm
from app.core.security import now_utc
from app.models import Notification, User
from app.models.enums import NotificationChannel, NotificationStatus
from app.workers.dispatch import enqueue_on_commit


class NotificationChannelProvider(ABC):
    channel: NotificationChannel

    @abstractmethod
    def dispatch(self, db: Session, notification: Notification) -> None: ...


class InAppChannel(NotificationChannelProvider):
    channel = NotificationChannel.IN_APP

    def dispatch(self, db: Session, notification: Notification) -> None:
        notification.status = NotificationStatus.SENT
        notification.sent_at = now_utc()


class EmailChannel(NotificationChannelProvider):
    channel = NotificationChannel.EMAIL

    def dispatch(self, db: Session, notification: Notification) -> None:
        enqueue_on_commit(db, "notifications.send_email", notification_id=str(notification.id))


CHANNELS: dict[NotificationChannel, NotificationChannelProvider] = {
    NotificationChannel.IN_APP: InAppChannel(),
    NotificationChannel.EMAIL: EmailChannel(),
}


def notify_users(
    db: Session,
    org_id: uuid.UUID,
    user_ids: list[uuid.UUID],
    *,
    type_: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
    data: dict[str, Any] | None = None,
    channels: tuple[NotificationChannel, ...] = (NotificationChannel.IN_APP,),
) -> list[Notification]:
    out: list[Notification] = []
    for uid in dict.fromkeys(user_ids):
        for ch in channels:
            n = Notification(
                organization_id=org_id,
                user_id=uid,
                channel=ch,
                type=type_,
                title=title[:255],
                body=body,
                link=link,
                data=data or {},
                status=NotificationStatus.PENDING,
            )
            db.add(n)
            db.flush()
            CHANNELS[ch].dispatch(db, n)
            out.append(n)
    return out


def users_with_permission(db: Session, org_id: uuid.UUID, perm: Perm) -> list[uuid.UUID]:
    users = db.execute(select(User).where(User.organization_id == org_id, User.is_active.is_(True))).unique().scalars()
    return [u.id for u in users if any(p.code == perm.value for p in u.role.permissions)]


def notify_permission(db: Session, org_id: uuid.UUID, perm: Perm, **kw: Any) -> list[Notification]:
    return notify_users(db, org_id, users_with_permission(db, org_id, perm), **kw)


def notify_client_owner(
    db: Session, org_id: uuid.UUID, assigned_employee_id: uuid.UUID | None, *, fallback_perm: Perm = Perm.WHATSAPP_MANAGE, **kw: Any
) -> list[Notification]:
    """Notify the client's assigned employee, or firm admins if unassigned."""
    if assigned_employee_id:
        return notify_users(db, org_id, [assigned_employee_id], **kw)
    return notify_permission(db, org_id, fallback_perm, **kw)
