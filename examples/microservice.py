import almanet

example_service = almanet.new_microservice("localhost:4150", prefix="net.example")

class access_denied(almanet.rpc_error):
    """Custom RPC exception"""

@example_service.procedure
async def greeting(
    session: almanet.Almanet,
    payload: str,  # is a data that was passed during invocation
) -> str:
    """
    Procedure that returns greeting message.
    """
    if payload == "guest":
        # you can raise custom exceptions
        # and the caller will have an error
        # see more about catching errors in `~/examples/caller.py` file.
        raise access_denied()
    return f"Hello, {payload}!"

if __name__ == "__main__":
    example_service.serve()
