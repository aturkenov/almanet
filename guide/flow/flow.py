from uuid import UUID
import almanet

__all__ = [
    "service",
    "create",
]

service = almanet.new_service(__name__)


@service.abstract_procedure
async def create(payload: str) -> UUID: ...
