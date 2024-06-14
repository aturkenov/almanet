import almanet

example_service = almanet.new_microservice("localhost:4150")

state_any = almanet.observable_state(example_service, "order", "any")
state_initial = almanet.observable_state(example_service, "order", "initial")
state_complete = almanet.observable_state(example_service, "order", "complete")

@state_initial.transition_from(state_any)
async def create(
    session: almanet.Almanet,
    name: str,
    **kwargs,
) -> str:
    print('create: ', name)
    return f"Order {name} created!"

@state_complete.observe(state_initial)
async def _complete(
    session: almanet.Almanet,
    previous_result: str,
    **kwargs,
) -> None:
    print('_complete: ', previous_result)


if __name__ == "__main__":
    example_service.serve()
