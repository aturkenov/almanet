import asyncio
import signal

from . import _service
from . import _session_pool

__all__ = ["serve"]


def serve(
    *addresses: str,
    services: list[_service.service] = [],
) -> None:
    for service in services:
        if not isinstance(service, _service.service):
            raise ValueError("must be an instance of service")

    session_pool = _session_pool.new_session_pool()

    async def begin() -> None:
        await session_pool.join(addresses, len(services))
        for service in services:
            service._post_join_event.notify(session_pool)

    async def end() -> None:
        await session_pool.leave()
        loop.stop()

    try:
        loop = asyncio.get_running_loop()        
    except:
        loop = asyncio.new_event_loop()

    for s in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(s, lambda: loop.create_task(end()))

    loop.create_task(begin())
    if not loop.is_running():
        loop.run_forever()
