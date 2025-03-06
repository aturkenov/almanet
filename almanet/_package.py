import asyncio
import signal

from . import _service
from . import _session_pool

__all__ = ["serve"]


def serve(
    *addresses: str,
    services: list[_service.remote_service] = [],
) -> None:
    if len(addresses) == 0:
        raise ValueError("must provide at least one address")

    if len(services) == 0:
        raise ValueError("must provide at least one service")

    for service in services:
        if not isinstance(service, _service.remote_service):
            raise ValueError("must be an instance of service")

    session_pool = _session_pool.new_session_pool()

    async def begin() -> None:
        await session_pool.spawn(addresses, len(services))
        for s in services:
            await s._post_join_event.notify(session_pool)

    async def end() -> None:
        await session_pool.kill()
        loop.stop()

    loop = asyncio.get_event_loop()

    for s in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(s, lambda: loop.create_task(end()))

    loop.create_task(begin())
    if not loop.is_running():
        loop.run_forever()
