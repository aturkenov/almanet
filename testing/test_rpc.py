import asyncio
from time import time

import almanet


class Denied(almanet.RPCError):
    ...


async def greeting(name: str, **kwargs) -> str:
    if name == 'guest':
        raise Denied()
    return f'Hello, {name}!'


async def test_rpc():
    async def test_timeout(s):
        try:
            await almanet.call(s, 'net.example.does.not.exist', 'payload')
        except Exception as e:
            assert isinstance(e, asyncio.TimeoutError)

    async def test_happy_path(s):
        result = await almanet.call(s, 'net.example.greeting', 'World')
        assert result.payload == 'Hello, World!'

        try:
            await almanet.call(s, 'net.example.greeting', 'guest')
        except Exception as e:
            assert isinstance(e, almanet.RPCError)
        else:
            raise AssertionError('invalid behaviour')

    async def stress_test(s):
        begin_time = time()
        async with asyncio.TaskGroup() as tg:
            for i in range(1000):
                coro = await almanet.call(s, 'net.example.greeting', 'World')
                tg.create_task(coro)
        end_time = time()
        duration = end_time - begin_time
        assert duration > 1

    __session = await almanet.join('localhost:4150')
    await test_timeout(__session)
    await almanet.register(__session, 'net.example.greeting', greeting)
    await test_happy_path(__session)
    await stress_test(__session)
