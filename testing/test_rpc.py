import asyncio
from datetime import datetime
from time import time

import pytest

import almanet


class denied(almanet.rpc_error): ...


async def greet(
    session, 
    payload: str
) -> str:
    if payload == "guest":
        raise denied()
    return f"Hello, {payload}!"


async def now(*args, **kwargs) -> datetime:
    return datetime.now()


async def test_rpc(
    n = 1000,
):
    session = almanet.new_session("localhost:4150")

    async with session:
        session.register("net.example.greet", greet)
        session.register("net.example.now", now)

        # happy path
        result = await session.call("net.example.greet", "Almanet")
        assert result == "Hello, Almanet!"

        # concurrent calls
        await asyncio.gather(
            session.call("net.example.greet", payload="test"),
            session.call("net.example.now", payload=None),
        )

        # catching rpc exceptions
        with pytest.raises(TimeoutError):
            await session.call("net.example.not_exist", True, timeout=1)

        # catching rpc exceptions
        with pytest.raises(almanet.rpc_error):
            await session.call("net.example.greet", "guest")

        # sequential calls - stress test
        begin_time = time()
        for _ in range(n):
            await session.call("net.example.now", payload=None)
        end_time = time()
        test_duration = end_time - begin_time
        assert test_duration < 1

        # concurrent call - stress test
        begin_time = time()
        await asyncio.gather(
            *[session.call("net.example.now", payload=None) for _ in range(n)]
        )
        end_time = time()
        test_duration = end_time - begin_time
        assert test_duration < 1
