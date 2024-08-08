import asyncio
import functools

from . import _decoding
from . import _schema

__all__ = ["validate_execution"]


def validate_execution(
    function,
    payload_model=...,
    return_model=...,
):
    """
    Takes a function as input and returns a decorator.
    The decorator validates the input payload and output return of the function based on their annotations.

    Args:
    - function: the function to decorate with validator
    - payload_model: the model of the input
    - return_model: the model of the output
    """
    payload_model, return_model = _schema.extract_annotations(function, payload_model, return_model)
    payload_validator = _decoding.serialize(payload_model)
    return_validator = _decoding.serialize(return_model)

    @functools.wraps(function)
    async def decorator(payload, *args, **kwargs):
        payload = payload_validator(payload)
        result = function(payload, *args, **kwargs)
        if asyncio.iscoroutine(result):
            result = await result
        return return_validator(result)

    return decorator
