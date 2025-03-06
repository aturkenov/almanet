import asyncio
import pytest

import almanet


testing_service = almanet.remote_service("net.testing.microservice")


class denied(almanet.rpc_exception): ...


@testing_service.procedure(
    exceptions={denied},
)
async def greet(
    payload: str,
    session: almanet.Almanet,
) -> str:
    if payload == "guest":
        raise denied()
    return f"Hello, {payload}!"


@testing_service.post_join
async def __post_join(session: almanet.Almanet):
    payload = "Almanet"
    expected_result = "Hello, Almanet!"

    # happy path
    result = await greet(payload, _force_local=False)
    assert result == expected_result

    # catch validation error
    with pytest.raises(almanet.invalid_rpc_payload):
        await greet(123, _force_local=False)  # type: ignore

    # catch custom exception
    with pytest.raises(denied):
        await greet("guest", _force_local=False)


async def test_microservice():
    almanet.serve(
        "localhost:4150",
        services=[testing_service],
    )
    await asyncio.sleep(1)
