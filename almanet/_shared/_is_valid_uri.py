import re

__all__ = ["is_valid_uri"]

_uri_re = re.compile("^[a-zA-Z_][a-zA-Z0-9_]*$")


def is_valid_uri(v: str) -> bool:
    """
    Validate a URI string.

    The URI segment must:
    - have a length greater than 0
    - only contain Latin symbols and numbers
    - can include '.' and '_' symbols
    - not allow numbers as the first symbol

    Valid URIs:
    - "net.example.v2.greet"
    - "net.example.v2._test_greet"

    Args:
    - v: The URI string to validate
    """
    if not isinstance(v, str):
        return False

    segments = v.split('.')
    for s in segments:
        if not _uri_re.match(s):
            return False

    return True
