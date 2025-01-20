import almanet

service = almanet.new_service(__name__)


class access_denied(almanet.rpc_error):
    """Custom RPC exception"""


@service.abstract_procedure
async def greeting(payload: str) -> str:
    """
    Procedure that returns greeting message.

    Raises:
        - access_denied if `payload` is `"guest"`
    """
    ...
