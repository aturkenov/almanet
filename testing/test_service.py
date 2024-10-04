import pytest

import almanet


async def test_service():
    async with almanet.new_session("localhost:4150") as session:
        import examples.microservice.greeting

        payload = "Almanet"
        expected_result = "Hello, Almanet!"

        # call by URI
        result = await session.call("examples.microservice.greeting.greeting", payload)
        assert result == expected_result

        # call by procedure
        result = await session.call(examples.microservice.greeting.greeting, payload)
        assert result == expected_result

        # catch validation error
        with pytest.raises(almanet.rpc_error):
            await session.call(examples.microservice.greeting.greeting, .123)  # type: ignore
