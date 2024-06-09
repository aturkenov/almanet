from uuid import uuid4

__all__ = [
    "new_id",
]


def new_id() -> str:
    v = uuid4()
    return v.hex
