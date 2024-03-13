import uvloop
import wmproto


async def main():
    session = await wmproto.join('localhost:4150')

    print(f'joined session.id={session.ID}')

    await wmproto.produce(session, 'net.example', 'hello, world')

    await wmproto.leave(session)


uvloop.run(main())
