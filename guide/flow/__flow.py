from uuid import UUID
import functools

import almanet

from . import flow as public

__all__ = [
    "public",
    "new_state",
    "state_any",
    "get_invoice",
    "save_invoice",
    "invoice_stage",
]


new_state = almanet.observable_state

state_any = almanet.observable_state(public.service, "ANY")


@public.get_invoice.implements
async def get_invoice(
    payload: UUID,
    session,
) -> public.invoice_model:
    """
    SELECT *
    FROM invoices
    WHERE id = :id
    """
    raise NotImplementedError()


async def save_invoice(
    payload: public.invoice_model,
) -> None:
    """
    UPDATE invoice {{set_values(values)}} WHERE id = :id
    """
    raise NotImplementedError()


class transition_denied(almanet.rpc_exception):
    def __init__(
        self,
        invoice_id: UUID,
        current_state: str,
        expected_states: set[almanet.observable_state],
    ):
        self.invoice_id = invoice_id
        self.current_state = current_state
        self.expected_states = expected_states

    def __str__(self) -> str:
        return f"invoice_id={self.invoice_id} current_state={self.current_state} expected_states={self.expected_states}"

    __repr__ = __str__


def invoice_stage(function):
    @functools.wraps(function)
    async def decorator(
        payload: UUID,
        context,
        transition: almanet.transition,
    ):
        invoice = await get_invoice(payload)

        if not (state_any in transition.sources or invoice.state in {i.label for i in transition.sources}):
            raise transition_denied(invoice.id, invoice.state, transition.sources)

        await function(invoice, context=context, transition=transition)

        await save_invoice(invoice)

        return payload

    return decorator
