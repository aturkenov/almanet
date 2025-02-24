from datetime import datetime, timedelta
from uuid import uuid4, UUID

from . import __flow

__all__ = ["state_new"]

state_new = __flow.new_state(__flow.public.service, "NEW")


async def _insert(values):
    """
    INSERT INTO invoices VALUES {{unpack_values(values)}}
    """
    raise NotImplementedError()


@__flow.public.create_invoice.implements
@state_new.transition_from(__flow.state_any)
async def create_invoice(
    payload: __flow.public.create_invoice_payload,
    **kwargs,
) -> UUID:
    values = payload.model_dump()
    order_pk = uuid4()
    values["id"] = order_pk
    values["creation_time"] = datetime.now()
    values["expiration_time"] = datetime.now() + timedelta(days=payload.expiration_days)
    await _insert(values)
    return order_pk
