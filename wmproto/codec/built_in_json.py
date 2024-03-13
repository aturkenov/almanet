import json
import typing

from wmproto import shared


class JSONCodec:

    def __init__(
        self,
        serialize: typing.Callable = None
    ) -> None:
        self._serialize = serialize

    def encode(
        self,
        v: typing.Any,
    ) -> str | bytes:
        if isinstance(v, shared.Dumpable):
            v = v.dump()
        return json.dumps(v, default=self._serialize)

    def decode(
        self,
        v: str | bytes,
    ) -> typing.Any:
        return json.loads(v)
