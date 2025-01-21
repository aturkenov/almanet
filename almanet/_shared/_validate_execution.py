import asyncio

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

    async def decorator(*args, payload, **kwargs):
        payload = payload_validator(payload)
        result = function(*args, **kwargs, payload=payload)
        if asyncio.iscoroutine(result):
            result = await result
        return return_validator(result)

    return decorator
