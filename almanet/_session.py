import asyncio
import logging
import typing

from . import _shared

__all__ = [
    "logger",
    "client_iface",
    "invoke_event_model",
    "qmessage_model",
    "reply_event_model",
    "rpc_exception",
    "Almanet",
    "get_active_session",
]


logger = logging.getLogger("almanet")

DEFAULT_CHANNEL = "almanet.python"


@_shared.dataclass(slots=True)
class qmessage_model[T: bytes]:
    """
    Represents a message in the queue.
    """

    id: str
    timestamp: int
    body: T
    attempts: int
    commit: typing.Callable[[], typing.Awaitable[None]]
    rollback: typing.Callable[[], typing.Awaitable[None]]


type returns_consumer[T: bytes] = tuple[typing.AsyncIterable[qmessage_model[T]], typing.Callable[[], None]]


class client_iface(typing.Protocol):
    """
    Interface for a client library.
    """

    def clone(self) -> "client_iface":
        raise NotImplementedError()

    async def connect(
        self,
    ) -> None:
        raise NotImplementedError()

    async def produce(
        self,
        topic: str,
        message: str | bytes,
        delay: int,
    ) -> None:
        raise NotImplementedError()

    async def consume(
        self,
        topic: str,
        channel: str,
    ) -> returns_consumer[bytes]:
        raise NotImplementedError()

    async def close(self) -> None:
        raise NotImplementedError()


@_shared.dataclass(slots=True)
class invoke_event_model:
    """
    Represents an invocation event.
    """

    id: str
    caller_id: str
    payload: bytes
    reply_topic: str

    @property
    def expired(self) -> bool:
        # TODO
        return False


@_shared.dataclass(slots=True)
class reply_event_model:
    """
    Represents a reply event.
    """

    call_id: str
    is_exception: bool
    payload: bytes


@_shared.dataclass(slots=True)
class _reply_exception_model:
    name: str
    payload: bytes


class rpc_exception(Exception):
    __slots__ = ("name", "payload")

    def __init__(
        self,
        payload: typing.Any = None,
        name: str | None = None,
    ) -> None:
        self.name = name or self.__class__.__name__
        self.payload = payload

    def __str__(self) -> str:
        return f"{self.name}: {self.payload}"


@_shared.dataclass(slots=True)
class registration_model:
    """
    Represents a registered procedure to call.
    """

    uri: str
    channel: str
    procedure: typing.Callable
    session: "Almanet"

    @property
    def __name__(self):
        return self.uri

    async def execute(
        self,
        invocation: invoke_event_model,
    ) -> reply_event_model:
        __log_extra = {"registration": str(self), "invocation": str(invocation)}
        try:
            logger.debug(f"trying to execute procedure {self.uri}", extra=__log_extra)
            reply_payload = await self.procedure(
                invocation.payload,
                session=self.session,
            )
            is_exception = False
        except Exception as e:
            is_exception = True

            if isinstance(e, rpc_exception):
                reply_exception = _reply_exception_model(e.name, _shared.dump(e.payload))
            else:
                logger.exception("during execute procedure", extra=__log_extra)
                reply_exception = _reply_exception_model("InternalError", b"oops")

            reply_payload = _shared.dump(reply_exception)

        return reply_event_model(
            call_id=invocation.id,
            is_exception=is_exception,
            payload=reply_payload,
        )


class Almanet:
    """
    Represents a session, connected to message broker.
    """

    def __init__(
        self,
        client: client_iface,
    ) -> None:
        self.id = _shared.new_id()
        self.reply_topic = f"_rpc_._reply_.{self.id}#ephemeral"
        self.joined = False
        self._client = client
        self._background_tasks = _shared.background_tasks()
        self._post_join_event = _shared.observable_event()
        self._leave_event = _shared.observable_event()
        self._pending_replies: typing.MutableMapping[str, asyncio.Future[reply_event_model]] = {}

    @property
    def version(self) -> float:
        return 0.1

    async def _produce(
        self,
        uri: str,
        payload: typing.Any,
        delay: int = 0,
    ) -> None:
        try:
            message_body = _shared.dump(payload)
        except Exception as e:
            logger.error(f"during encode payload: {repr(e)}")
            raise e

        try:
            logger.debug(f"trying to produce {uri} topic")
            await self._client.produce(uri, message_body, delay=delay)
        except Exception as e:
            logger.exception(f"during produce {uri} topic")
            raise e

    def produce(
        self,
        uri: str,
        payload: typing.Any,
        delay: int = 0,
    ) -> asyncio.Task[None]:
        """
        Produce a message with a specified topic and payload.
        """
        return self._background_tasks.schedule(self._produce(uri, payload, delay=delay))

    async def consume(
        self,
        topic: str,
        channel: str,
    ) -> returns_consumer:
        """
        Consume messages from a message broker with the specified topic and channel.
        It returns a tuple of a stream of messages and a function that can stop consumer.
        """
        logger.debug(f"trying to consume {topic}:{channel}")

        messages_stream, stop_consumer = await self._client.consume(topic, channel)

        def __stop_consumer():
            logger.warning(f"trying to stop consumer {topic}")
            stop_consumer()

        self._leave_event.add_observer(__stop_consumer)

        return messages_stream, __stop_consumer

    async def _consume_replies(
        self,
        ready_event: asyncio.Event,
    ) -> None:
        messages_stream, _ = await self.consume(
            self.reply_topic,
            channel=f"{DEFAULT_CHANNEL}#ephemeral",
        )
        logger.debug("reply event consumer begin")
        serializer = _shared.serialize_json(reply_event_model)
        ready_event.set()
        async for message in messages_stream:
            __log_extra = {"incoming_message": str(message)}
            try:
                reply_event = serializer(message.body)
                __log_extra["reply_event"] = str(reply_event)
                logger.debug("new reply", extra=__log_extra)

                pending = self._pending_replies.get(reply_event.call_id)
                if pending is None:
                    logger.warning("pending event not found", extra=__log_extra)
                else:
                    pending.set_result(reply_event)
            except:
                logger.exception("during parse reply", extra=__log_extra)

            await message.commit()
            logger.debug("successful commit", extra=__log_extra)
        logger.debug("reply event consumer end")

    _call_args = tuple[str, typing.Any]

    class _call_kwargs(typing.TypedDict):
        timeout: typing.NotRequired[int]

    async def _delay_call(
        self,
        uri: str,
        payload: typing.Any,
        delay: int = 0,
        /,
        _invocation_id: str | None = None,
        _reply_topic: str = "",
    ) -> None:
        invocation = invoke_event_model(
            id=_invocation_id or _shared.new_id(),
            caller_id=self.id,
            payload=_shared.dump(payload),
            reply_topic=_reply_topic,
        )

        __log_extra = {"invoke_event": str(invocation)}
        logger.debug(f"trying to call {uri=} {delay=}", extra=__log_extra)

        await self._produce(f"_rpc_.{uri}", invocation, delay=delay)

    def delay_call(
        self,
        uri: str,
        payload,
        delay: int = 0,
    ) -> None:
        self._background_tasks.schedule(self._delay_call(uri, payload, delay))

    async def _call(
        self,
        uri: str,
        payload,
        timeout: int = 60,
    ) -> reply_event_model:
        invocation_id = _shared.new_id()

        __log_extra = {"uri": uri, "timeout": timeout, "invocation_id": invocation_id}

        try:
            async with asyncio.timeout(timeout):
                pending_reply_event = asyncio.Future[reply_event_model]()
                self._pending_replies[invocation_id] = pending_reply_event

                await self._delay_call(
                    uri,
                    payload,
                    _invocation_id=invocation_id,
                    _reply_topic=self.reply_topic,
                )

                reply_event = await pending_reply_event
                __log_extra["reply_event"] = str(reply_event)
                logger.debug(f"invocation {uri=} respond", extra=__log_extra)

                if reply_event.is_exception:
                    serializer = _shared.serialize_json(_reply_exception_model)
                    reply_exception = serializer(reply_event.payload)
                    raise rpc_exception(
                        reply_exception.payload,
                        name=reply_exception.name,
                    )

                return reply_event
        except Exception as e:
            logger.error(f"during call {uri}: {e!r}", extra={**__log_extra, "error": str(e)})
            raise e
        finally:
            self._pending_replies.pop(invocation_id)

    def call(
        self,
        uri: str,
        payload,
        **kwargs: typing.Unpack[_call_kwargs],
    ) -> asyncio.Task[reply_event_model]:
        """
        Executes the remote procedure using the payload.
        Returns a instance of result model.
        """
        return self._background_tasks.schedule(self._call(uri, payload, **kwargs))

    async def _multicall(
        self,
        uri: str,
        payload,
        timeout: int = 60,
    ) -> list[reply_event_model]:
        reply_topic = f"_rpc_._replies_.{_shared.new_id()}#ephemeral"

        __log_extra = {"uri": uri, "timeout": timeout, "reply_topic": reply_topic}

        messages_stream, stop_consumer = await self.consume(
            reply_topic,
            f"{DEFAULT_CHANNEL}#ephemeral"
        )

        serializer = _shared.serialize_json(reply_event_model)

        result = []
        try:
            async with asyncio.timeout(timeout):
                await self._delay_call(
                    uri,
                    payload,
                    _reply_topic=reply_topic,
                )

                async for message in messages_stream:
                    try:
                        logger.debug("new reply event", extra=__log_extra)
                        reply_event = serializer(message.body)
                        result.append(reply_event)
                    except:
                        logger.exception("during parse reply event", extra=__log_extra)

                    await message.commit()
        except TimeoutError:
            stop_consumer()

        logger.debug(f"multicall {uri} done")

        return result

    def multicall(
        self,
        uri: str,
        payload,
        **kwargs: typing.Unpack[_call_kwargs],
    ) -> asyncio.Task[list[reply_event_model]]:
        """
        Execute simultaneously multiple procedures using the payload.
        """
        return self._background_tasks.schedule(self._multicall(uri, payload, **kwargs))

    async def _on_message(
        self,
        registration: registration_model,
        message: qmessage_model[bytes],
    ):
        __log_extra = {"registration": str(registration), "incoming_message": str(message)}
        serializer = _shared.serialize_json(invoke_event_model)
        try:
            invocation = serializer(message.body)
            __log_extra["invocation"] = str(invocation)
            logger.debug("new invocation", extra=__log_extra)

            if invocation.expired:
                logger.warning("invocation expired", extra=__log_extra)
            else:
                reply_event = await registration.execute(invocation)
                if len(invocation.reply_topic) > 0:
                    logger.debug(f"trying to reply {registration.uri}", extra=__log_extra)
                    await self._produce(invocation.reply_topic, reply_event)
        except:
            logger.exception("during execute invocation", extra=__log_extra)
        finally:
            await message.commit()
            logger.debug("successful commit", extra=__log_extra)

    async def _consume_invocations(
        self,
        registration: registration_model,
    ) -> None:
        logger.debug(f"trying to register {registration.uri}:{registration.channel}")
        messages_stream, _ = await self.consume(f"_rpc_.{registration.uri}", registration.channel)
        async for message in messages_stream:
            self._background_tasks.schedule(self._on_message(registration, message))
            if not self.joined:
                break
        logger.debug(f"consumer {registration.uri} down")

    def register(
        self,
        topic: str,
        procedure: typing.Callable,
        *,
        channel: str = "main",
    ) -> registration_model:
        """
        Register a procedure with a specified topic and payload.
        Returns the created registration.
        """
        if not self.joined:
            raise RuntimeError(f"session {self.id} not joined")

        logger.debug(f"scheduling registration {topic}")

        registration = registration_model(
            uri=topic,
            channel=channel,
            procedure=procedure,
            session=self,
        )

        self._background_tasks.schedule(self._consume_invocations(registration), daemon=True)

        return registration

    async def join(
        self,
    ) -> None:
        """
        Join the session to message broker.
        """
        if self.joined:
            raise RuntimeError(f"session {self.id} already joined")

        logger.debug("trying to connect")

        await self._client.connect()

        consume_replies_ready = asyncio.Event()
        self._background_tasks.schedule(
            self._consume_replies(consume_replies_ready),
            daemon=True,
        )
        await consume_replies_ready.wait()

        _active_session.set(self)

        self.joined = True
        await self._post_join_event.notify()
        logger.info(f"session {self.id} joined")

    async def __aenter__(self) -> "Almanet":
        if not self.joined:
            await self.join()
        return self

    async def leave(
        self,
        reason: str | None = None,
        timeout: float = 60,
    ) -> None:
        """
        Leave the session from message broker.
        """
        if not self.joined:
            raise RuntimeError(f"session {self.id} not joined")

        _active_session.set(None)

        self.joined = False

        logger.debug(f"trying to leave {self.id} session, reason: {reason}")

        logger.debug(f"session {self.id} await task pool complete")
        await self._background_tasks.complete(timeout=timeout)

        await self._leave_event.notify(timeout=timeout)

        logger.debug(f"session {self.id} trying to close connection")
        await self._client.close()

        logger.warning(f"session {self.id} left")

    async def __aexit__(self, etype, evalue, etraceback) -> None:
        if self.joined:
            await self.leave()


_active_session = _shared.new_concurrent_context()


def get_active_session() -> Almanet:
    session = _active_session.get(None)
    if session is None:
        raise RuntimeError("active session not found")
    return session
