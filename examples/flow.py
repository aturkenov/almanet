from uuid import uuid4
import typing
import almanet

example_service = almanet.new_microservice("localhost:4150", prefix="net.order")

state_any = almanet.observable_state(example_service, "any")
state_initial = almanet.observable_state(example_service, "initial")
state_complete = almanet.observable_state(example_service, "complete")

@state_initial.transition_from(state_any)
async def create(
    payload: str,
    context: typing.MutableMapping,
    **kwargs,
) -> str:
    order_pk = uuid4()
    context['pk'] = order_pk
    context['name'] = payload
    return f'new order<{order_pk}>'

@state_complete.observe(state_initial)
async def _complete(
    context: typing.MutableMapping,
    **kwargs,
) -> None:
    order_pk = context['pk']
    name = context['name']
    print(f'{order_pk}: {name} is complete')

if __name__ == "__main__":
    example_service.serve()
