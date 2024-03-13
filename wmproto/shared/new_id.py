from uuid import uuid4


def new_id() -> str:
    v = str(uuid4())
    return v.replace('-', '_')

