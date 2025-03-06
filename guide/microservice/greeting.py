import almanet

__all__ = [
    "access_denied",
    "greet",
]

service = almanet.new_remote_service(__name__)


class access_denied(almanet.rpc_exception):
    """Custom RPC exception"""


@service.public_procedure
async def greet(payload: str) -> str:
    """
    Procedure that returns greeting message.

    Raises:
        - access_denied if `payload` is `"guest"`
    """
    ...
