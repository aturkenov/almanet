from uuid import uuid4, UUID
import typing
import almanet

service = almanet.new_service(__name__)

state_any = almanet.observable_state(service, "ANY")
state_initial = almanet.observable_state(service, "INITIAL")
state_complete = almanet.observable_state(service, "COMPLETE")


@service.procedure
@state_initial.transition_from(state_any)
async def create(
    payload: str,
    context: typing.MutableMapping,
    **kwargs,
) -> UUID:
    order_pk = uuid4()
    context["pk"] = order_pk
    context["username"] = payload
    return order_pk


@state_complete.observe(state_initial)
async def _complete(
    context: typing.MutableMapping,
    **kwargs,
) -> None:
    order_pk = context["pk"]
    username = context["username"]
    print(f"{order_pk}: {username} is complete")
