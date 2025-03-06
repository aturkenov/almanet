import asyncio
import pytest

from datetime import datetime

import almanet
import pydantic


testing_service = almanet.remote_service("net.testing.microservice")


class access_denied_payload(pydantic.BaseModel):
    reason: str
    datetime: datetime


class access_denied(almanet.rpc_exception):
    payload: access_denied_payload


@testing_service.procedure(
    exceptions={access_denied},
)
async def greet(
    payload: str,
    session: almanet.Almanet,
) -> str:
    if payload == "guest":
        raise access_denied(
            access_denied_payload(
                reason="because you are guest",
                datetime=datetime.now(),
            )
        )
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

    try:
        await greet("guest", _force_local=False)
        raise Exception("invalid behavior")
    # catch custom exception
    except access_denied as e:
        assert isinstance(e.payload.reason, str)
        assert isinstance(e.payload.datetime, datetime)


async def test_microservice():
    almanet.serve(
        "localhost:4150",
        services=[testing_service],
    )
    await asyncio.sleep(1)
