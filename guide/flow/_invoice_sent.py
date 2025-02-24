from . import __flow

__all__ = ["state_invoice_sent"]

state_invoice_sent = __flow.new_state(__flow.public.service, "INVOICE_SENT")


@state_invoice_sent.observe(__flow.state_any)
@__flow.invoice_stage
async def send_invoice(
    invoice: __flow.public.invoice_model,
    **kwargs,
):
    """
    The logic of sending the invoice
    """
