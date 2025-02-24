from datetime import datetime
from uuid import UUID

import almanet
import pydantic

__all__ = [
    "service",
    "create_invoice",
    "cancel_invoice",
]

service = almanet.new_service(__name__)


class invoice_model(pydantic.BaseModel):
    id: UUID
    state: str
    phone: str
    amount: float
    creation_time: datetime
    expiration_time: datetime


class create_invoice_payload(pydantic.BaseModel):
    phone: str
    amount: float
    expiration_days: int = 7


@service.abstract_procedure
async def create_invoice(payload: create_invoice_payload) -> UUID: ...


@service.abstract_procedure
async def cancel_invoice(payload: UUID) -> None: ...


@service.abstract_procedure
async def get_invoice(payload: UUID) -> invoice_model: ...
