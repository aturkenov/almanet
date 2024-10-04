import asyncio
import typing

__all__ = ["merge_streams", "make_closable"]


class close_stream(StopAsyncIteration):
    """
    Raise when you need to close an asynchronous stream.
    """


async def merge_streams(*streams):
    """
    Merges multiple asynchronous streams into a single stream.
    It takes any number of streams as arguments and continuously yields values from each stream.
    Close all streams when one of them is closed.
    """
    pending_tasks = [asyncio.create_task(anext(i)) for i in streams]

    def next_value(task):
        i = pending_tasks.index(task)
        s = streams[i]
        c = anext(s)
        pending_tasks[i] = asyncio.create_task(c)

    active = True
    while active:
        done_tasks, _ = await asyncio.wait(pending_tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done_tasks:
            result = task.result()
            if isinstance(result, close_stream):
                pending_tasks.remove(task)
                active = False
                continue
            yield result
            next_value(task)

    for task in pending_tasks:
        task.cancel()


def make_closable(
    stream,
    on_close: typing.Callable | None = None,
):
    """
    Makes an asynchronous stream closable.

    Args:
    - stream: is an asynchronous stream that you want to make closable.
    - on_close: is a callable that takes no arguments and returns an awaitable that completes when the stream is closed.
    """
    close_event = asyncio.Event()

    async def on_close_stream():
        await close_event.wait()
        if callable(on_close):
            result = on_close()
            if asyncio.iscoroutine(result):
                await result
        yield close_stream()

    new_stream = merge_streams(stream, on_close_stream())
    return new_stream, close_event.set
