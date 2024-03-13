import asyncio
import typing

import ansq

from wmproto import codec, protocol, shared

if typing.TYPE_CHECKING:
    from ansq.tcp.writer import Writer


class ANSQSession:

    def __init__(
        self,
        ID: str,
        codec: protocol.ICodec,
        addresses: typing.Sequence[str],
    ) -> None:
        self.ID = ID
        self.addresses = addresses
        self.codec = codec
        self.leave_callbacks = []
        self.writer: Writer

    async def connect(self) -> None:
        self.writer = await ansq.create_writer(
            nsqd_tcp_addresses=self.addresses,
        )
        self.leave_callbacks.append(self.writer.close)

        await protocol.post_join(self)

    async def produce(
        self,
        topic: str,
        message: str | bytes,
    ) -> None:
        await self.writer.pub(topic, message)

    async def consume(
        self,
        topic: str,
        channel: str,
    ) -> protocol.ReturnsConsumer:
        reader = await ansq.create_reader(
            nsqd_tcp_addresses=self.addresses,
            topic=topic,
            channel=channel,
        )
        self.leave_callbacks.append(reader.close)

        async def adapt():
            async for nsq_message in reader.messages():
                yield protocol.Message(
                    ID=nsq_message.id,
                    timestamp=nsq_message.timestamp,
                    body=nsq_message.body,
                    attempts=nsq_message.attempts,
                    commit_callback=nsq_message.fin,
                    rollback_callback=nsq_message.req,
                )

        return adapt(), reader.close

    async def leave(self) -> None:
        async with asyncio.TaskGroup() as tg:
            for callback in self.leave_callbacks:
                coro = callback()
                tg.create_task(coro)


async def join(
    *addresses: str,
    codec: protocol.ICodec = codec.JSONCodec(),
) -> protocol.ISession:
    session = ANSQSession(
        ID=shared.new_id(),
        codec=codec,
        addresses=addresses,
    )
    await session.connect()
    return session
