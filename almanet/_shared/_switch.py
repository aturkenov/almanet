import asyncio

__all__ = ["switch"]


class switch:

    def __init__(self) -> None:
        self._pause_event = asyncio.Event()
        self.on()

    def off(self) -> None:
        self._pause_event.clear()

    def on(self) -> None:
        self._pause_event.set()

    def access(self):
        return self._pause_event.wait()
