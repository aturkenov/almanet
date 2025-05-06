import asyncio
from datetime import datetime
import json
from time import time

import pytest

import almanet


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


NOW_URI = "net.example.now"


async def now(*args, **kwargs) -> datetime:
    return datetime.now()


async def test_rpc(
    n=256,  # number of calls
):
    async with almanet.new_session("localhost:4150") as session:
        session.register(GREET_URI, greet)
        session.register(NOW_URI, now)

        # happy path
        result = await session.call(GREET_URI, "Almanet")
        assert result.payload == b"Hello, Almanet!"

        # concurrent calls
        await asyncio.gather(
            session.call(GREET_URI, "test"),
            session.call(NOW_URI, None),
        )

        # catching timeout exceptions
        with pytest.raises(TimeoutError):
            await session.call("net.example.not_exist", True, timeout=1)

        # catching rpc exceptions
        with pytest.raises(almanet.rpc_exception):
            await session.call(GREET_URI, b"guest")

        # sequential calls - stress test
        begin_time = time()
        for _ in range(n):
            await session.call(NOW_URI, None)
        end_time = time()
        test_duration = end_time - begin_time
        assert test_duration < 1

        # concurrent call - stress test
        begin_time = time()
        await asyncio.gather(*[session.call(NOW_URI, None) for _ in range(n)])
        end_time = time()
        test_duration = end_time - begin_time
        assert test_duration < 1

    await asyncio.sleep(1)
