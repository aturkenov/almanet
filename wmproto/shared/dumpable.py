import typing


class Dumpable:

    __exportable__: typing.Tuple[str, ...]

    def dump(self) -> typing.Mapping:
        result = {}
        for name in self.__exportable__:
            v = getattr(self, name)
            if isinstance(v, Dumpable):
                result[name] = v.dump()
            else:
                result[name] = v
        return result
