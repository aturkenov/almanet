from uuid import UUID

import almanet

from . import __flow
from . import _invoice_sent
from . import _waiting_for_payment

__all__ = ["state_cancelled"]

state_cancelled = __flow.new_state(__flow.public.service, "CANCELLED")


@state_cancelled.transition_from(
    _invoice_sent.state_invoice_sent,
    _waiting_for_payment.state_waiting_for_payment,
)
@__flow.invoice_stage
async def mark_as_cancelled(
    invoice: __flow.public.invoice_model,
    **kwargs,
): ...


class invoice_cancelled(almanet.rpc_error):
    def __init__(
        self,
        invoice_id: UUID,
    ):
        self.invoice_id = invoice_id


@__flow.public.cancel_invoice.implements
async def cancel_invoice(
    payload: UUID,
    **kwargs,
):
    await mark_as_cancelled(payload)
    raise invoice_cancelled(payload)
