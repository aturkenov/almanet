import functools
import inspect

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

    def dont_validate(v):
        return v

    payload_validator = dont_validate if payload_model is ... else _decoding.serialize(payload_model)

    return_validator = dont_validate if return_model is ... else _decoding.serialize(return_model)

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
