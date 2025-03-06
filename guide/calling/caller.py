import asyncio

import almanet
import guide.microservice


async def main():
    # join to your network.
    session = almanet.new_session("localhost:4150")
    async with session:
        payload = "Aidar"

        # catching rpc exceptions with `try` and `except almanet.rpc_exception` statement
        try:
            result = await guide.microservice.greet(payload)
            print(result)
        except guide.microservice.access_denied as e:
            print(f"during call {guide.microservice.greet.uri}({payload}): {e}")


if __name__ == "__main__":
    asyncio.run(main())
