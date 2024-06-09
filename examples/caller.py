import asyncio

import almanet

from examples import flow

async def main():
    # create new session
    session = almanet.new_session("localhost:4150")

    # join to your nsq network.
    async with session:
        print(f"joined session.id={session.id}")

        # calling the procedure `net.examples.greeting` with "Aidar" argument
        result = await session.call("net.example.greeting", "Aidar")
        # invocation result in `.payload` attribute.
        print("result", result.payload)

        # catching rpc exceptions with `try` and `except almanet.rpc_error` statement
        # validation error
        try:
            await session.call("net.example.greeting", 123)
        except almanet.rpc_error as e:
            print("during call net.example.greeting(123):", e)
        # custom exception
        try:
            await session.call("net.example.greeting", "guest")
        except almanet.rpc_error as e:
            print("during call net.example.greeting('guest'):", e)

        await flow.create(session, "Aidar")

asyncio.run(main())
