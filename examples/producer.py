import asyncio

import almanet
import pydantic

class newcomer(pydantic.BaseModel):
    id: str

async def main():
    # create new session
    session = almanet.new_session('localhost:4150')

    # join to your nsq network.
    async with session:
        print(f'joined session.id={session.id}')

        # publishing message to `net.example.newcomers` topic with 'hello, world' argument.
        await session.produce('net.example.newcomers', newcomer(id='test'))

asyncio.run(main())
