from uuid import UUID

import almanet

from . import __flow
from . import _waiting_for_payment

__all__ = ["state_payment_checking"]

state_payment_checking = __flow.new_state(__flow.public.service, "PAYMENT_CHECKING")


class payment_not_found(almanet.rpc_error):
    def __init__(
        self,
        invoice_id: UUID,
    ):
        self.invoice_id = invoice_id


@state_payment_checking.observe(_waiting_for_payment.state_waiting_for_payment)
@__flow.invoice_stage
async def check_payment(
    invoice: __flow.public.invoice_model,
    **kwargs,
):
    if invoice.id.int % 2 == 0:
        raise payment_not_found(invoice.id)
