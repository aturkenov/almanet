import typing

import almanet

from . import _flow
from . import _initial

__all__ = ["state_done"]

state_done = almanet.observable_state(_flow.public.service, "DONE")


@state_done.observe(_initial.state_initial)
async def _complete(
    context: typing.MutableMapping,
    **kwargs,
) -> None:
    order_pk = context["pk"]
    username = context["username"]
    print(f"{order_pk}: {username} is complete")
