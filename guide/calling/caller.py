import asyncio

import almanet
import guide.microservice


async def main():
    # join to your network.
    async with almanet.new_session("localhost:4150") as session:
        payload = "Aidar"

        # catching rpc exceptions with `try` and `except almanet.rpc_error` statement
        try:
            result = await session.call(guide.microservice.greet, payload)
            # or calling the procedure by URI (Uniform Resource Identifier)
            # result = await session.call("guide.microservice.greeting.greet", payload)
            print(result)
        except almanet.rpc_error as e:
            print(f"during call {guide.microservice.greet.uri}({payload}): {e}")


if __name__ == '__main__':
    asyncio.run(main())
