import uvloop

import wmproto


async def main():
    session = await wmproto.join('localhost:4150')

    print(f'joined session.id={session.ID}')

    result = await wmproto.call(session, 'net.example.greeting', 'Aidar')
    print('result', result.payload)

    await wmproto.leave(session)


uvloop.run(main())
