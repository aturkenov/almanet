import asyncio
import typing

__all__ = [
    "merge_streams",
    "make_closable"
]


class close_stream(StopAsyncIteration):
    """
    Raise when you need to close an asynchronous stream.
    """


async def merge_streams(*streams):
    """
    Merges multiple asynchronous streams into a single stream.
    It takes in any number of streams as arguments and continuously yields values from each stream until all streams are exhausted.
    """
    pending_tasks = [asyncio.create_task(anext(i)) for i in streams]
    active = True
    while active:
        done_tasks, _ = await asyncio.wait(pending_tasks, return_when=asyncio.FIRST_COMPLETED)
        for dt in done_tasks:
            result = dt.result()
            if isinstance(result, close_stream):
                active = False
                continue
            yield result

            i = -1
            for pt in pending_tasks:
                i += 1
                if pt is not dt:
                    continue

                s = streams[i]
                pending_tasks[i] = asyncio.create_task(anext(s))
                break


def make_closable(
    stream,
    on_close: typing.Callable[[], typing.Awaitable[None]] | None = None,
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
        if asyncio.iscoroutinefunction(on_close):
            await on_close()
        yield close_stream()

    new_stream = merge_streams(stream, on_close_stream())
    return new_stream, close_event.set
