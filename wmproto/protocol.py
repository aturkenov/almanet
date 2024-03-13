import asyncio
import logging
import typing

from . import shared


logger = logging.getLogger('wmproto')
logger.setLevel(logging.INFO)


class ICodec(typing.Protocol):

    def encode(
        self,
        v: typing.Any,
    ) -> str | bytes:
        raise NotImplemented()

    def decode(
        self,
        v: str | bytes,
    ) -> typing.Any:
        raise NotImplemented()


class Message[T: typing.Any]:

    __slots__ = ('ID', 'timestamp', 'body', 'attempts', 'commit', 'rollback')

    def __init__(
        self,
        ID: str,
        timestamp: int,
        body: T,
        attempts: int,
        commit_callback: typing.Callable,
        rollback_callback: typing.Callable,
    ) -> None:
        self.ID = ID
        self.timestamp = timestamp
        self.body = body
        self.attempts = attempts
        self.commit = commit_callback
        self.rollback = rollback_callback

    def __str__(self) -> str:
        return f'Message(ID={self.ID}, attempts={self.attempts})'


class Invoke[T: typing.Any](shared.Dumpable):

    __slots__ = ('ID', 'callerID', 'payload')
    __exportable__ = __slots__

    def __init__(
        self,
        ID: str,
        callerID: str,
        payload: T,
    ) -> None:
        self.ID = ID
        self.callerID = callerID
        self.payload = payload

    @property
    def expired(self) -> bool:
        # TODO
        return False

    def __str__(self) -> str:
        return f'Invoke(ID={self.ID}, callerID={self.callerID})'


class Reply[T: typing.Any](shared.Dumpable):

    __slots__ = ('CID', 'isError', 'payload')
    __exportable__ = __slots__

    def __init__(
        self,
        CID: str,
        isError: bool,
        payload: T,
    ) -> None:
        self.CID = CID
        self.isError = isError
        self.payload = payload

    def __str__(self) -> str:
        return f'Invoke(CID={self.CID}, isError={self.isError})'


type ReturnsConsumer[T: typing.Any] = tuple[typing.AsyncIterable[Message[T]], typing.Callable]


class ISession(typing.Protocol):

    ID: str
    codec: ICodec

    async def produce(
        self,
        topic: str,
        message: str | bytes,
    ) -> None:
        raise NotImplemented()

    async def consume(
        self,
        topic: str,
        channel: str,
    ) -> ReturnsConsumer:
        raise NotImplemented()

    async def leave(self) -> None:
        raise NotImplemented()


async def produce[T: typing.Any](
    session: ISession,
    topic: str,
    payload: T,
) -> None:
    """
    Produces `payload` to `topic`.
    """
    __log_extra = {'session_id': session.ID, 'topic': topic}
    message = session.codec.encode(payload)
    logger.debug('trying to produce', extra=__log_extra)
    try:
        await session.produce(topic, message)
    except Exception as e:
        logger.exception('during produce', extra=__log_extra)
        raise e


class RPCError[T: typing.Any](Exception):

    __slots__ = ('name', 'args')

    def __init__(
        self,
        *args: T,
        name: str | None = None,
    ) -> None:
        self.name = name or self.__class__.__name__
        self.args = args

    def __str__(self) -> str:
        return f'{self.name}{self.args}'


_pending_map: typing.MutableMapping[str, asyncio.Future[Reply]] = {}


async def call[O: typing.Any](
    session: ISession,
    topic: str,
    payload: typing.Any,
    *,
    timeout: int = 60,
) -> Reply[O]:
    __log_extra = {'session_id': session.ID, 'topic': topic, 'timeout': timeout}
    logger.debug('trying to call', extra=__log_extra)
    async with asyncio.timeout(timeout):
        invocation = Invoke(
            ID=shared.new_id(),
            callerID=session.ID,
            payload=payload,
        )

        pending = asyncio.Future[Reply]()
        _pending_map[invocation.ID] = pending

        await produce(session, f'rpc.{topic}', invocation)

        response = await pending

        if response.isError:
            raise RPCError(
                response.payload['message'],
                name=response.payload['name'],
            )

        return response


async def consume[T: typing.Any](
    session: ISession,
    topic: str,
    *,
    channel: str,
) -> ReturnsConsumer[T]:
    __log_extra = {'session_id': session.ID, 'topic': topic, 'channel': channel}
    logger.debug('trying to consume', extra=__log_extra)
    consumer, stop_consumer = await session.consume(topic, channel)

    async def decode_stream():
        async for message in consumer:
            try:
                message.body = session.codec.decode(message.body)
            except:
                logger.exception('during decode message body', extra=__log_extra)
                continue

            yield message

    return decode_stream(), stop_consumer


async def _consume_replies(
    session: ISession,
) -> None:
    __consumer, _ = await consume(
        session,
        f'rpc.reply.{session.ID}',
        channel='recipient',
    )
    async for message in __consumer:
        __log_extra = {'session_id': session.ID, 'message': str(message)}
        try:
            reply = Reply(**message.body)
            __log_extra['reply'] = str(reply)
            logger.debug('new reply', extra=__log_extra)

            pending = _pending_map.get(reply.CID)
            if pending is None:
                logger.error('pending not found', extra=__log_extra)
            else:
                pending.set_result(reply)
        except:
            logger.exception('during parse reply', extra=__log_extra)

        await message.commit()
        logger.debug('successful commit', extra=__log_extra)


async def post_join(
    session: ISession,
) -> None:
    asyncio.create_task(
        _consume_replies(session)
    )


class Registration:

    def __init__(
        self,
        topic: str,
        channel: str,
        procedure: typing.Callable,
    ) -> None:
        self.topic = f'rpc.{topic}'
        self.channel = channel
        self.procedure = procedure

    def __str__(self) -> str:
        return f'Registration(topic={self.topic}, channel={self.channel})'

    async def execute(
        self,
        invocation: Invoke,
    ) -> Reply:
        __log_extra = {'registration': str(self), 'invocation': str(invocation)}
        try:
            logger.debug('trying to execute procedure', extra=__log_extra)
            reply_payload = await self.procedure(invocation.payload)
            return Reply(CID=invocation.ID, isError=False, payload=reply_payload)
        except Exception as e:
            if isinstance(e, RPCError):
                name = e.name
                message = e.args
            else:
                name = 'InternalError'
                message = 'oops'
                logger.exception('during execute procedure', extra=__log_extra)
            return Reply(CID=invocation.ID, isError=True, payload={'name': name, 'message': message})


async def _consume_invocations(
    session: ISession,
    registration: Registration,
) -> None:
    __consumer, _ = await consume(
        session,
        registration.topic,
        channel=registration.channel,
    )
    async for message in __consumer:
        __log_extra = {'session_id': session.ID, 'registration': str(registration), 'message': str(message)}
        try:
            invocation = Invoke(**message.body)
            __log_extra['invocation'] = str(invocation)
            logger.debug('new invocation', extra=__log_extra)

            if invocation.expired:
                logger.warning('invocation expired', extra=__log_extra)
            else:
                reply = await registration.execute(invocation)
                logger.debug('trying to reply', extra=__log_extra)
                recipient_topic = f'rpc.reply.{invocation.callerID}'
                await produce(session, recipient_topic, reply)
        except:
            logger.exception('during parse invocation', extra=__log_extra)

        await message.commit()
        logger.debug('successful commit', extra=__log_extra)


async def register(
    session: ISession,
    topic: str,
    procedure: typing.Callable,
    *,
    channel: str = 'RPC',
) -> None:
    __log_extra = {'session_id': session.ID, 'topic': topic, 'channel': channel}
    logger.debug('trying to register', extra=__log_extra)
    registration = Registration(topic, channel, procedure)
    asyncio.create_task(
        _consume_invocations(session, registration)
    )


async def leave(
    session: ISession,
    reason: str | None = None,
) -> None:
    __log_extra = {'session_id': session.ID, 'reason': reason}
    logger.debug('trying to leave', extra=__log_extra)
    await session.leave()
    logger.warning('left', extra=__log_extra)
