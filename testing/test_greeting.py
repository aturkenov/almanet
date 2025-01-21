import asyncio
import pytest

import almanet


testing_service = almanet.service("net.testing.microservice")


@testing_service.procedure
async def greet(
    session: almanet.Almanet,
    payload: str,
) -> str:
    return f"Hello, {payload}!"


@testing_service.procedure
async def _test_greet(
    session: almanet.Almanet,
    payload = None,
):
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
        await session.call(greet, .123)


@testing_service.post_join
async def __post_join(session: almanet.Almanet):
    await session.call(
        _test_greet,
        None,
    )


async def test_microservice():
    almanet.serve(
        "localhost:4150",
        services=[testing_service],
    )
    await asyncio.sleep(1)
