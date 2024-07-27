import asyncio

from . import _task_pool

__all__ = ["observable"]


class observable:
    def __init__(
        self,
        task_pool: _task_pool.task_pool,
    ):
        self.observers = []
        self._task_pool = task_pool

    def add_observer(self, function):
        self.observers.append(function)

    def observer(self, function):
        self.add_observer(function)
        return function

    def notify(self, *args, **kwargs):
        for observer in self.observers:
            # FIXME
            maybe_coroutine = observer(*args, **kwargs)
            if asyncio.iscoroutine(maybe_coroutine):
                self._task_pool.schedule(maybe_coroutine)
