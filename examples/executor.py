import asyncio
import signal

import uvloop
import wmproto


async def exit_signal():
    loop = asyncio.get_running_loop()
    on_exit = asyncio.Event()
    required_signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
    for s in required_signals:
        loop.add_signal_handler(s, lambda: on_exit.set())
    await on_exit.wait()


class Denied(wmproto.RPCError):
    ...


async def greeting(name: str, **kwargs):
    if name == 'Putin':
        raise Denied()
    return f'Hello, {name}!'


async def main():
    session = await wmproto.join('localhost:4150')

    print(f'joined session.id={session.ID}')

    await wmproto.register(session, 'net.example.greeting', greeting)

    await exit_signal()

    await wmproto.leave(session)


uvloop.run(main())
