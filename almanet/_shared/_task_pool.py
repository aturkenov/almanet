import asyncio
import typing

__all__ = ["task_pool"]


class task_pool:
    """
    `asyncio.create_task` documentation has important note
    about avoiding a task disappearing mid-execution
    https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task
    https://github.com/python/cpython/issues/88831
    """

    def __init__(self):
        self._tasks = set[asyncio.Task]()
        self._daemons = set[asyncio.Task]()

    def schedule(
        self,
        coroutine: typing.Coroutine,
        *,
        daemon: bool = False,
    ) -> asyncio.Task:
        """
        Schedules a coroutine for execution in the event loop.

        Args:
        - coroutine: the coroutine to be scheduled as an asyncio task.
        - daemon: marks the task as a daemon and does not wait completion.
        """
        task = asyncio.create_task(coroutine)
        task.add_done_callback(lambda _: self._tasks.discard(task))
        self._tasks.add(task)
        if daemon:
            self._daemons.add(task)
        return task

    async def complete(self) -> None:
        """
        Awaits the completion of all non-daemon tasks in the pool.
        This method will block until all non-daemon tasks have finished executing.
        """
        pending_tasks = self._tasks - self._daemons
        if len(pending_tasks) > 0:
            await asyncio.wait(pending_tasks)
