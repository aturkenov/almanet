import almanet

from . import greeting as public


@public.greet.implements
async def _greet(
    payload: str,  # is a data that was passed during invocation
    session: almanet.Almanet,
) -> str:
    if payload == "guest":
        # you can raise custom exceptions
        # and the caller will have an error
        # see more about catching errors in `~/guide/calling/caller.py` file.
        raise public.access_denied()
    return f"Hello, {payload}!"


@public.service.procedure
async def greet(
    payload: str,  # is a data that was passed during invocation
    session: almanet.Almanet,
) -> str:
    if payload == "guest":
        # you can raise custom exceptions
        # and the caller will have an error
        # see more about catching errors in `~/guide/calling/caller.py` file.
        raise public.access_denied()
    return f"Hello, {payload}!"
