from . import greeting as public


@public.greeting.implements
async def greeting(
    payload: str,  # is a data that was passed during invocation
) -> str:
    if payload == "guest":
        # you can raise custom exceptions
        # and the caller will have an error
        # see more about catching errors in `~/examples/caller.py` file.
        raise public.access_denied()
    return f"Hello, {payload}!"
