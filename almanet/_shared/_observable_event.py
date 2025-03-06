import asyncio
from . import _background_tasks

__all__ = ["observable_event"]


class observable_event:
    def __init__(self):
        self.task_pool = _background_tasks.background_tasks()
        self.observers = []

    def add_observer(self, function):
        self.observers.append(function)

    def observer(self, function):
        self.add_observer(function)
        return function

    def notify(self, *args, timeout: float | None = None, **kwargs):
        for observer in self.observers:
            result = observer(*args, **kwargs)
            if asyncio.iscoroutine(result):
                self.task_pool.schedule(result)

        return self.task_pool.complete(timeout)
