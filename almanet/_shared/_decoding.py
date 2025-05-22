import typing

import pydantic
import pydantic_core

__all__ = [
    "serialize",
    "serialize_json",
    "serialize_any_json",
]


def serialize[T: typing.Any](
    annotation: type[T] | typing.Any = ...,
) -> typing.Callable[[typing.Any], T]:
    if annotation is ...:
        return lambda v: v

    model = pydantic.TypeAdapter(annotation)
    return model.validate_python


def serialize_json[T: typing.Any](
    annotation: type[T] | typing.Any = ...,
) -> typing.Callable[[bytes | str], T]:
    if annotation is ...:
        return lambda v: pydantic_core.from_json(v)

    model = pydantic.TypeAdapter(annotation)
    return model.validate_json


serialize_any_json = serialize_json(...)
