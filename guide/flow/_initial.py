from uuid import uuid4, UUID
import typing

import almanet

from . import _flow

__all__ = ["state_initial"]

state_initial = almanet.observable_state(_flow.public.service, "INITIAL")


@_flow.public.create.implements
@state_initial.transition_from(_flow.state_any)
async def _create(
    payload: str,
    context: typing.MutableMapping,
    **kwargs,
) -> UUID:
    order_pk = uuid4()
    context["pk"] = order_pk
    context["username"] = payload
    return order_pk
