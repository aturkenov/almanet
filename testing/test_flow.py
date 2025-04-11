import asyncio

import almanet


testing_service = almanet.remote_service("net.testing.microservice")

new_state = lambda label: almanet.observable_state(testing_service, label)
initial_state = new_state("INITIAL")
ready_state = new_state("READY")
completed_state = new_state("COMPLETED")


@testing_service.procedure
@ready_state.transition_from(initial_state)
async def make_ready(
    payload: str,
    session: almanet.Almanet,
    transition: almanet.transition,
):
    return payload


expected_value = "Hello, Almanet!"


@completed_state.observe(ready_state)
async def _complete(
    payload: str,
    session: almanet.Almanet,
    transition: almanet.transition,
):
    assert payload == expected_value


@testing_service.post_join
async def __post_join(session: almanet.Almanet):
    await make_ready(expected_value)


async def test_flow():
    almanet.serve(
        ["localhost:4150"],
        testing_service,
    )
    await asyncio.sleep(1)
