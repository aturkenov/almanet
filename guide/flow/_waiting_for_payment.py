from . import __flow
from . import _invoice_sent

__all__ = ["state_waiting_for_payment"]

state_waiting_for_payment = __flow.new_state(__flow.public.service, "WAITING_FOR_PAYMENT")


@state_waiting_for_payment.observe(_invoice_sent.state_invoice_sent)
@__flow.invoice_stage
async def _wait_for_payment(
    invoice: __flow.public.invoice_model,
    **kwargs,
): ...
