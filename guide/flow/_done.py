import typing

import almanet

from . import __flow
from . import _new

__all__ = ["state_done"]

state_done = almanet.observable_state(__flow.public.service, "DONE")


@state_done.observe(_new.state_new)
async def _complete(
    context: typing.MutableMapping,
    **kwargs,
) -> None:
    order_pk = context["pk"]
    username = context["username"]
    print(f"{order_pk}: {username} is complete")
