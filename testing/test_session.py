import asyncio
from datetime import datetime, timedelta
import json
from time import time

import pytest

import almanet


USE_ASYNCIO_EVENT_URI = "net.example.use_asyncio_event"

_event = asyncio.Event()


async def use_asyncio_event(payload: bytes, **kwargs) -> bytes:
    _event.set()
    return bytes()


class denied(almanet.rpc_exception):
    payload: str


GREET_URI = "net.example.greet"


async def greet(
    payload: bytes,
    **kwargs,
) -> bytes:
    name = json.loads(payload)
    if name == "guest":
        raise denied(name)
    result = f"Hello, {name}!"
    return result.encode()


async def test_rpc(
    delay=2,  # delay for the event
    n=256,  # number of calls
):
    session = almanet.clients.make_ansqd_tcp_session("localhost:4150")
    async with session:
        session.register(USE_ASYNCIO_EVENT_URI, use_asyncio_event)
        session.register(GREET_URI, greet)

        begin_time = datetime.now()
        session.delay_call(USE_ASYNCIO_EVENT_URI, None, delay)
        async with asyncio.timeout(delay + 1):
            await _event.wait()
            end_time = datetime.now()
            if end_time - begin_time > timedelta(seconds=delay):
                raise TimeoutError("Event was not sent in time")

        # happy path
        result = await session.call(GREET_URI, "Almanet")
        assert result.payload == b"Hello, Almanet!"

        # catching timeout exceptions
        with pytest.raises(TimeoutError):
            await session.call("net.example.not_exist", True, timeout=1)

        # catching rpc exceptions
        with pytest.raises(expected_exception=almanet.rpc_exception):
            await session.call(GREET_URI, "guest")

        # sequential calls - stress test
        begin_time = time()
        for _ in range(n):
            await session.call(GREET_URI, "test")
        end_time = time()
        test_duration = end_time - begin_time
        assert test_duration < 1

        # concurrent call - stress test
        begin_time = time()
        await asyncio.gather(*[session.call(GREET_URI, "test") for _ in range(n)])
        end_time = time()
        test_duration = end_time - begin_time
        assert test_duration < 1

    await asyncio.sleep(1)
