from . import _almanet
from . import _shared

__all__ = [
    "session_pool",
    "new_session_pool",
]


class session_pool:

    def __init__(self):
        self.id = _shared.new_id()
        self.joined = False
        self.sessions: list[_almanet.Almanet] = []

    async def acquire(
        self,
        addresses: tuple[str, ...],
        number_of_sessions: int = 1,
    ) -> "session_pool":
        for _ in range(number_of_sessions):
            session = _almanet.new_session()
            await session.join(*addresses)
            self.sessions.append(session)
        self.joined = True
        return self

    async def release(
        self,
        *args,
        **kwargs,
    ):
        sessions, self.sessions = self.sessions, []
        for i in sessions:
            await i.leave(*args, **kwargs)

    def rotate(self) -> _almanet.Almanet:
        session = self.sessions.pop(0)
        self.sessions.append(session)
        return session


new_session_pool = session_pool
