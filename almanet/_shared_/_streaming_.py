import asyncio

__all__ = [
    "merge_streams",
    "make_closable"
]


async def merge_streams(
    *streams
):
    pending_tasks = [asyncio.create_task(anext(i)) for i in streams]
    active = True
    while active:
        done_tasks, _ = await asyncio.wait(pending_tasks, return_when=asyncio.FIRST_COMPLETED)
        for dt in done_tasks:
            result = dt.result()
            if isinstance(result, StopAsyncIteration):
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
    on_close = None,
):
    run_callback = asyncio.iscoroutinefunction(on_close)

    close_event = asyncio.Event()

    async def on_close_stream():
        await close_event.wait()
        if run_callback:
            await on_close()
        yield StopAsyncIteration()

    new_stream = merge_streams(stream, on_close_stream())
    return new_stream, close_event.set
