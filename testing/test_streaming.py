import asyncio

from almanet._shared._streaming import make_closable


async def test_make_closable():
    delay = 0.1

    async def stream(n):
        for i in range(n):
            await asyncio.sleep(delay)
            yield i

    n = 64
    closable_stream, close = make_closable(stream(n))

    async with asyncio.timeout(n * delay + 1):
        async for v in closable_stream:
            if v > 32:
                close()
