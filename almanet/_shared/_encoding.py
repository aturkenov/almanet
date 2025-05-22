import typing

import pydantic

__all__ = [
    "dump",
]


def dump(v: typing.Any) -> bytes:
    if isinstance(v, bytes):
        return v

    codec = pydantic.RootModel(v)
    json_string = codec.model_dump_json()
    return json_string.encode()
