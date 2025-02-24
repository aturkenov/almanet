from . import __flow
from . import _payment_checking

__all__ = ["state_success"]

state_success = __flow.new_state(__flow.public.service, "SUCCESS")


@state_success.observe(_payment_checking.state_payment_checking)
@__flow.invoice_stage
async def _complete(
    invoice: __flow.public.invoice_model,
    **kwargs,
):
    print(f"{invoice.id}: is completed")
