import typing

import ansq

from almanet import _almanet
from almanet import _shared

if typing.TYPE_CHECKING:
    from ansq.tcp.types import NSQMessage

__all__ = ["ansq_client"]


class ansq_client:

    async def connect(
        self,
        addresses: typing.Sequence[str],
    ) -> None:
        self.addresses = addresses
        self.writer = await ansq.create_writer(
            nsqd_tcp_addresses=addresses,
        )

    async def close(self) -> None:
        await self.writer.close()

    async def produce(
        self,
        topic: str,
        message: str | bytes,
    ) -> None:
        await self.writer.pub(topic, message)

    async def _convert_ansq_message(
        self,
        ansq_messages_stream: typing.AsyncIterable['NSQMessage'],
    ) -> typing.AsyncIterable[_almanet.qmessage_model[bytes]]:
        async for ansq_message in ansq_messages_stream:
            almanet_message = _almanet.qmessage_model(
                id=ansq_message.id,
                timestamp=ansq_message.timestamp,
                body=ansq_message.body,
                attempts=ansq_message.attempts,
                commit=ansq_message.fin,
                rollback=ansq_message.req,
            )
            yield almanet_message

    async def consume(
        self,
        topic: str,
        channel: str,
    ) -> _almanet.returns_consumer[bytes]:
        reader = await ansq.create_reader(
            nsqd_tcp_addresses=self.addresses,
            topic=topic,
            channel=channel,
            connection_options=ansq.ConnectionOptions()
        )
        messages_stream = reader.messages()
        messages_stream = self._convert_ansq_message(messages_stream)
        # ansq does not close stream automatically
        return _shared.make_closable(messages_stream, reader.close)
