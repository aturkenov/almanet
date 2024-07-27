import typing
from ._almanet import *
from . import _clients as clients
from ._flow import *
from ._microservice import *

__all__ = [
    *_almanet.__all__,
    "clients",
    "new_session",
    *_flow.__all__,
    *_microservice.__all__,
    "new_microservice",
]


def new_session(
    *addresses: str,
    client_klass: type[client_iface] = clients.DEFAULT_CLIENT,
    **kwargs: typing.Unpack[Almanet._kwargs],
) -> Almanet:
    """
    Returns a new instance of Almanet session.
    """
    return Almanet(*addresses, client=client_klass(), **kwargs)


def new_microservice(
    *addresses: str,
    session: Almanet | None = None,
    **kwargs: typing.Unpack[microservice._kwargs],
) -> microservice:
    """
    Returns a new instance of microservice.
    """
    if session is None:
        session = new_session(*addresses)
    return microservice(session, **kwargs)
