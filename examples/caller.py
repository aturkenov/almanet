import asyncio

import almanet


async def main():
    # create new session
    session = almanet.new_session("localhost:4150")

    # join to your nsq network.
    async with session:
        # calling the procedure by URI (Uniform Resource Identifier)
        result = await session.call("net.example.greeting", "Aidar")

        # invocation result
        print("result", result)

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


asyncio.run(main())
