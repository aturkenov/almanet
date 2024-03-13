import uvloop
import wmproto


async def main():
    session = await wmproto.join('localhost:4150')

    print(f'joined session.id={session.ID}')

    consumer, stop = await wmproto.consume(session, 'net.example', channel='test')

    print('consuming begin')
    async for message in consumer:
        print('new event', message.body)
        await message.commit()
    print('consuming end')

    await wmproto.leave(session)


uvloop.run(main())
