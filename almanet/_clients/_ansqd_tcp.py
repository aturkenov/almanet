import typing

import ansq

from almanet import _session
from almanet import _shared

if typing.TYPE_CHECKING:
    from ansq.tcp.types import NSQMessage

__all__ = [
    "ansqd_tcp_client",
    "make_ansqd_tcp_session",
]


class ansqd_tcp_client:

    def __init__(
        self,
        *addresses: str,
    ):
        if len(addresses) == 0:
            raise ValueError("at least one address must be specified")

        if not all(isinstance(i, str) for i in addresses):
            raise ValueError("addresses must be a iterable of strings")

        self.addresses = addresses

    def clone(self) -> "ansqd_tcp_client":
        return ansqd_tcp_client(*self.addresses)

    async def connect(self) -> None:
        self.writer = await ansq.create_writer(
            nsqd_tcp_addresses=self.addresses,
        )

    async def close(self) -> None:
        await self.writer.close()

    async def produce(
        self,
        topic: str,
        message: str | bytes,
        delay: int,
    ) -> None:
        if delay > 0:
            await self.writer.dpub(topic, message, delay)
        else:
            await self.writer.pub(topic, message)

    async def _convert_ansq_message(
        self,
        ansq_messages_stream: typing.AsyncIterable["NSQMessage"],
    ) -> typing.AsyncIterable[_session.qmessage_model[bytes]]:
        async for ansq_message in ansq_messages_stream:
            almanet_message = _session.qmessage_model(
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
    ) -> _session.returns_consumer:
        reader = await ansq.create_reader(
            nsqd_tcp_addresses=self.addresses, topic=topic, channel=channel, connection_options=ansq.ConnectionOptions()
        )
        messages_stream = reader.messages()
        messages_stream = self._convert_ansq_message(messages_stream)
        # ansq does not close stream automatically
        return _shared.make_closable(messages_stream, reader.close)


def make_ansqd_tcp_session(*addresses: str) -> _session.Almanet:
    client = ansqd_tcp_client(*addresses)
    return _session.Almanet(client)
