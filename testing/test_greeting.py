import asyncio
import pytest

import almanet


testing_service = almanet.service("net.testing.microservice")


@testing_service.procedure
async def greeting(
    session: almanet.Almanet,
    payload: str,
) -> str:
    return f"Hello, {payload}!"


@testing_service.procedure
async def _test_greeting(
    session: almanet.Almanet,
    payload = None,
):
    payload = "Almanet"
    expected_result = "Hello, Almanet!"

    # call by URI
    result = await session.call("net.testing.microservice.greeting", payload)
    assert result == expected_result

    # call by procedure
    result = await session.call(greeting, payload)
    assert result == expected_result

    # catch validation error
    with pytest.raises(almanet.rpc_error):
        await session.call(greeting, .123)


@testing_service.post_join
async def __post_join(session: almanet.Almanet):
    await session.call(
        _test_greeting,
        None,
    )


async def test_microservice():
    almanet.serve(
        "localhost:4150",
        services=[testing_service],
    )
    await asyncio.sleep(1)
