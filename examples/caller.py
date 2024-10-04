import asyncio

import almanet
import examples.microservice.greeting


async def main():
    # join to your network.
    async with almanet.new_session("localhost:4150") as session:
        payload = "Aidar"
        # catching rpc exceptions with `try` and `except almanet.rpc_error` statement
        try:
            # calling the procedure by URI (Uniform Resource Identifier)
            result = await session.call(examples.microservice.greeting.greeting, payload)
            print(result)
        except almanet.rpc_error as e:
            print(f"during call net.example.greeting({payload}): {e}")


asyncio.run(main())
