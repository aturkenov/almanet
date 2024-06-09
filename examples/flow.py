import almanet

my_service = almanet.new_service("localhost:4150")

state_any = almanet.observable_state("user", "any", my_service)
state_initial = almanet.observable_state("user", "initial", my_service)
state_complete = almanet.observable_state("user", "complete", my_service)


@state_any.transition(target=state_initial)
async def create(
    name: str,
    **kwargs,
) -> str:
    print('create: ', name)
    return f"Hello, {name}!"


@state_initial.observer(target=state_complete)
async def _complete(
    previous_result: str,
    **kwargs,
) -> None:
    print('_complete: ', previous_result)


if __name__ == "__main__":
    my_service.serve()
