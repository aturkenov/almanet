import typing
from ._almanet_ import *
from . import _clients_ as clients
from ._flow_ import *
from ._service_ import *

__all__ = [
    *_almanet_.__all__,
    "clients",
    'new_session',
    *_flow_.__all__,
    *_service_.__all__,
    'new_service',
]


def new_session(
    *addresses: str,
    client_klass: type[client_iface] = clients.DEFAULT_CLIENT,
    **kwargs: typing.Unpack[Almanet._kwargs],
) -> Almanet:
    return Almanet(
        *addresses,
        client=client_klass(),
        **kwargs
    )


def new_service(
    *addresses: str,
    session: Almanet | None = None,
    **kwargs: typing.Unpack[service._kwargs],
) -> service:
    if session is None:
        session = new_session(*addresses)
    return service(session, **kwargs)
