from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORM
from app.schemas.document import ClientRef


class InvoiceItemIn(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    sac_code: str | None = Field(default=None, max_length=10)
    quantity: Decimal = Field(default=Decimal("1"), gt=0, le=Decimal("100000"))
    unit_price: Decimal = Field(ge=0, le=Decimal("100000000"))
    tax_rate: Decimal = Field(default=Decimal("18"), ge=0, le=Decimal("28"))


class InvoiceCreate(BaseModel):
    client_id: uuid.UUID
    task_id: uuid.UUID | None = None
    issue_date: date | None = None
    due_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)
    items: list[InvoiceItemIn] = Field(min_length=1, max_length=50)


class InvoiceItemOut(ORM):
    id: uuid.UUID
    description: str
    sac_code: str | None
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal
    amount: Decimal
    tax_amount: Decimal


class InvoiceOut(ORM):
    id: uuid.UUID
    client_id: uuid.UUID
    client: ClientRef
    task_id: uuid.UUID | None
    invoice_number: str
    issue_date: date
    due_date: date
    subtotal: Decimal
    tax: Decimal
    total: Decimal
    amount_paid: Decimal
    balance_due: Decimal
    currency: str
    status: str
    notes: str | None
    sent_at: datetime | None
    paid_at: datetime | None
    items: list[InvoiceItemOut]
    created_at: datetime


class ManualPaymentIn(BaseModel):
    amount: Decimal = Field(gt=0)
    method: str = Field(default="BANK_TRANSFER", max_length=40)
    reference: str = Field(min_length=2, max_length=100)
    paid_at: datetime | None = None


class PaymentOut(ORM):
    id: uuid.UUID
    invoice_id: uuid.UUID
    client_id: uuid.UUID
    client: ClientRef
    provider: str
    provider_payment_id: str
    amount: Decimal
    currency: str
    method: str | None
    status: str
    paid_at: datetime
    verified_via: str
    created_at: datetime


class CheckoutResponse(BaseModel):
    provider: str
    order_id: str
    amount_paise: int
    currency: str
    key_id: str
    invoice_number: str
    firm_name: str


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str = Field(min_length=3, max_length=100)
    razorpay_payment_id: str = Field(min_length=3, max_length=100)
    razorpay_signature: str = Field(min_length=10, max_length=200)
