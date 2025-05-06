import asyncio
import pytest

from datetime import datetime

import almanet
import pydantic


testing_service = almanet.remote_service("net.testing.microservice")


class access_denied_payload(pydantic.BaseModel):
    reason: str
    datetime: datetime


class access_denied(almanet.remote_exception):
    payload: access_denied_payload


@testing_service.procedure(
    exceptions={access_denied},
)
async def greet(
    payload: str,
    session: almanet.Almanet,
) -> str:
    if not isinstance(session, almanet.Almanet):
        pytest.fail("session is not an instance of almanet")
    if payload == "guest":
        raise access_denied(
            access_denied_payload(
                reason="because you are guest",
                datetime=datetime.now(),
            )
        )
    if payload == "not_exist":
        await asyncio.sleep(2)
        raise access_denied(
            access_denied_payload(
                reason="user not found",
                datetime=datetime.now(),
            )
        )
    return f"Hello, {payload}!"


@testing_service.post_join
async def __post_join(session: almanet.Almanet):
    payload = "Almanet"
    expected_result = "Hello, Almanet!"

    # happy path
    result = await greet(payload, force_local=False)
    assert result == expected_result

    # catch timeout error
    with pytest.raises(asyncio.TimeoutError):
        await greet("not_exist", force_local=False, timeout=1)  # type: ignore

    # catch validation error
    with pytest.raises(almanet.rpc_invalid_payload):
        await greet(123, force_local=False)  # type: ignore

    try:
        await greet("guest", force_local=False)

        raise Exception("invalid behavior")
    # catch custom exception
    except access_denied as e:
        assert isinstance(e.payload.reason, str)
        assert isinstance(e.payload.datetime, datetime)

    almanet.logger.debug("done!!!!!!!!!!!!!!!!")


async def test_service():
    almanet.serve_single(["localhost:4150"], testing_service)
    await asyncio.sleep(4)
