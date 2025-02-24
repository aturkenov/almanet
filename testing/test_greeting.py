import asyncio
import pytest

import almanet


testing_service = almanet.service("net.testing.microservice")


@testing_service.procedure
async def greet(
    payload: str,
    session: almanet.Almanet,
) -> str:
    return f"Hello, {payload}!"


@testing_service.post_join
async def __post_join(session: almanet.Almanet):
    payload = "Almanet"
    expected_result = "Hello, Almanet!"

    # call by URI
    result = await session.call("net.testing.microservice.greet", payload)
    assert result == expected_result

    # call by procedure
    result = await session.call(greet, payload)
    assert result == expected_result

    # catch validation error
    with pytest.raises(almanet.rpc_error):
        await session.call(greet, .123)  # type: ignore


async def test_microservice():
    almanet.serve(
        "localhost:4150",
        services=[testing_service],
    )
    await asyncio.sleep(1)
