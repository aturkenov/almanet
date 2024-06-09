import asyncio

import fastapi
import almanet


class api_schema:

    def __init__(
        self,
        session: almanet.Almanet,
    ):
        self._session = session
        self.clients = []
        self.endpoints_schema = []

    def exist(
        self,
        topic: str,
        channel: str,
    ) -> bool:
        result = [i for i in self.endpoints_schema if i['topic'] == topic and i['channel'] == channel]
        return len(result) > 0

    async def fetch_endpoint_schema(
        self,
        topic: str,
        channel: str,
    ) -> dict:
        reply = await self._session.call(f'_api_schema_.{topic}.{channel}', None)
        return reply.payload

    async def add(
        self,
        topic: str,
        channel: str,
    ):
        if not self.exist(topic, channel):
            endpoint_schema = await self.fetch_endpoint_schema(topic, channel)
            print('new endpoint', endpoint_schema)
            self.endpoints_schema.append(endpoint_schema)

    async def consume(self):
        messages_stream, _ = await self._session.consume(
            '_api_schema_.new',
            channel=session.id,
            payload_model=list[str],
        )
        async for message in messages_stream:
            for route in message.body:
                topic, channel = route.split('/')
                await self.add(topic, channel)

    async def fetch_clients(self):
        replies = await self._session.multicall('_api_schema_.client', None, timeout=3)
        return [i.payload for i in replies if not i.is_error]

    async def run(self):
        print('trying to fetch clients')
        self.clients = await self.fetch_clients()
        print(self.clients)
        for c in self.clients:
            for route in c['routes']:
                topic, channel = route.split('/')
                await self.add(topic, channel)
        await self.consume()


session = almanet.new_session()
my_api_schema = api_schema(session)


async def initialize_session():
    await session.join('localhost:4150')
    asyncio.create_task(my_api_schema.run())


api_v1 = fastapi.APIRouter(
    prefix='/v1',
    on_startup=[initialize_session],
)


@api_v1.post('/endpoint/get-many')
async def get_many(
    limit: int = 10,
    offset: int = 0,
):
    return my_api_schema.endpoints_schema
