import asyncio

from . import _session
from . import _shared

__all__ = [
    "session_pool",
    "new_session_pool",
    "acquire_active_session",
]


class session_pool:
    def __init__(self):
        self.joined = False
        self.sessions: list[_session.Almanet] = []

    @property
    def count(self) -> int:
        return len(self.sessions)

    async def spawn(
        self,
        addresses: tuple[str, ...],
        number_of_sessions: int = 1,
    ) -> None:
        if number_of_sessions < 1:
            raise ValueError("number_of_sessions must be greater than 0")

        async with asyncio.TaskGroup() as g:
            for _ in range(number_of_sessions):
                session = _session.new_session()
                self.sessions.append(session)
                coroutine = session.join(*addresses)
                g.create_task(coroutine)

        self.joined = True

        _current_session_pool.set(self)

    async def kill(
        self,
        *args,
        **kwargs,
    ) -> None:
        sessions, self.sessions = self.sessions, []
        async with asyncio.TaskGroup() as g:
            for i in sessions:
                coroutine = i.leave(*args, **kwargs)
                g.create_task(coroutine)

        self.joined = False

        _current_session_pool.set(None)

    def rotate(self) -> _session.Almanet:
        session = self.sessions.pop(0)
        self.sessions.append(session)
        return session


new_session_pool = session_pool


_current_session_pool = _shared.new_concurrent_context()


def acquire_active_session() -> _session.Almanet:
    pool = _current_session_pool.get(None)
    if pool is None:
        return _session.get_active_session()
    return pool.rotate()
