import functools
import inspect

from . import _decoding_
from . import _schema_

__all__ = ["validate_execution"]


def validate_execution(
    function,
    *,
    validate_payload: bool = True,
    validate_return: bool = True,
):
    payload_annotation, return_annotation = _schema_.extract_annotations(function)

    if not validate_payload or payload_annotation is ...:
        payload_validator = lambda v: v
    else:
        payload_validator = _decoding_.serialize(payload_annotation)

    if not validate_return or return_annotation is ...:
        # raise RuntimeError(f'set {procedure} returning annotation')
        return_validator = lambda v: v
    else:
        return_validator = _decoding_.serialize(return_annotation)

    @functools.wraps(function)
    async def async_decorator(payload, *args, **kwargs):
        payload = payload_validator(payload)
        result = await function(payload, *args, **kwargs)
        return return_validator(result)

    if inspect.iscoroutinefunction(function):
        return async_decorator

    @functools.wraps(function)
    def decorator(payload, *args, **kwargs):
        payload = payload_validator(payload)
        result = function(payload, *args, **kwargs)
        return return_validator(result)

    return decorator
