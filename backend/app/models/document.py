from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantScoped, Timestamps, UUIDPk
from app.models.client import Client
from app.models.enums import DeliveryStatus, DocumentSource, DocumentStatus, DocumentType, VersionStatus


class Document(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_org_client", "organization_id", "client_id"),
        Index("ix_documents_org_status", "organization_id", "status"),
        Index("ix_documents_org_type_fy", "organization_id", "document_type", "financial_year"),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("clients.id", ondelete="CASCADE"))
    task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tasks.id", ondelete="SET NULL"))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(String(20), default=DocumentSource.STAFF)
    # Denormalised from current version for fast listing
    file_name: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(127))
    file_size: Mapped[int] = mapped_column(BigInteger)
    document_type: Mapped[str] = mapped_column(String(40), default=DocumentType.OTHER)
    financial_year: Mapped[str | None] = mapped_column(String(9))  # e.g. 2025-26
    assessment_year: Mapped[str | None] = mapped_column(String(9))
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default=DocumentStatus.UPLOADED)
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    approved_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extracted_metadata: Mapped[dict[str, Any]] = mapped_column(default=lambda: {})

    client: Mapped[Client] = relationship(lazy="joined")
    versions: Mapped[list[DocumentVersion]] = relationship(
        back_populates="document", order_by="DocumentVersion.version_number", lazy="selectin"
    )


class DocumentVersion(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version_number"),)

    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    file_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(127))
    file_size: Mapped[int] = mapped_column(BigInteger)
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default=VersionStatus.UPLOADED)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)
    storage_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    document: Mapped[Document] = relationship(back_populates="versions")


class DocumentDelivery(UUIDPk, Timestamps, TenantScoped, Base):
    """A secure, client-bound delivery link for a specific approved version."""

    __tablename__ = "document_deliveries"
    __table_args__ = (Index("ix_deliveries_org_doc", "organization_id", "document_id"),)

    document_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("documents.id", ondelete="CASCADE"))
    version_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("document_versions.id", ondelete="CASCADE"))
    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("clients.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(20), default="WHATSAPP")
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    status: Mapped[str] = mapped_column(String(20), default=DeliveryStatus.PENDING)
    message_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("messages.id", ondelete="SET NULL"))
    initiated_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
