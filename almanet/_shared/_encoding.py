import typing

import pydantic

__all__ = [
    "dump",
]


def dump(v: typing.Any) -> bytes:
    if isinstance(v, bytes):
        return v

    if isinstance(v, str):
        return v.encode()

    codec = pydantic.RootModel(v)
    json_string = codec.model_dump_json()
    return json_string.encode()
