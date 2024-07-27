from uuid import uuid4, UUID
import typing
import almanet

example_service = almanet.new_microservice("localhost:4150", prepath="net.order")

state_any = almanet.observable_state(example_service, "ANY")
state_initial = almanet.observable_state(example_service, "INITIAL")
state_complete = almanet.observable_state(example_service, "COMPLETE")


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


if __name__ == "__main__":
    example_service.serve()
