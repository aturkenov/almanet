import contextvars

from . import _new_id

__all__ = ["new_concurrent_context"]


def new_concurrent_context[T](*args, **kwargs) -> contextvars.ContextVar[T]:
    name = _new_id.new_id()
    return contextvars.ContextVar(name, *args, **kwargs)
