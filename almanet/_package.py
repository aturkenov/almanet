import asyncio
import multiprocessing
import signal

from . import (
    _service,
    _session,
)

__all__ = [
    "serve_single",
    "serve_multiple",
]


def serve_single(
    client: _session.client_iface,
    service: _service.remote_service,
    *,
    stop_loop_on_exit: bool | None = None,
) -> None:
    if stop_loop_on_exit is None:
        stop_loop_on_exit = True

    session = _session.Almanet(client)

    async def begin() -> None:
        await session.join()
        await service._post_join_event.notify(session)

    async def end() -> None:
        await session.leave()
        if stop_loop_on_exit:
            loop.stop()

    loop = asyncio.get_event_loop()

    for s in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(s, lambda: loop.create_task(end()))

    loop.create_task(begin())
    if not loop.is_running():
        loop.run_forever()


def _initialize_new_process(
    client,
    service_uri: str,
    **kwargs,
) -> None:
    service = _service.get_service(service_uri)
    if service is None:
        raise ValueError(f"invalid service type {service_uri=}")

    serve_single(client, service, **kwargs)


def serve_multiple(
    sample_client: _session.client_iface,
    *services: _service.remote_service,
    **kwargs,
) -> None:
    if len(services) == 0:
        raise ValueError("must provide at least one service")

    if not all(isinstance(s, _service.remote_service) for s in services):
        raise TypeError("all services must be of type remote_service")

    processes: list[multiprocessing.Process] = []
    for s in services:
        client4process = sample_client.clone()
        process = multiprocessing.Process(
            target=_initialize_new_process,
            args=(client4process, s.pre),
            kwargs=kwargs,
        )
        process.start()
        processes.append(process)

    has_active_process = True
    while has_active_process:
        has_active_process = False

        for process in processes:
            if not process.is_alive():
                continue

            try:
                process.join()
            except KeyboardInterrupt:
                # termination signal to child processes already sent
                has_active_process = True
