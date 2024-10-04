import asyncio
import logging
import typing

import pydantic_core

from . import _shared

if typing.TYPE_CHECKING:
    from . import _service

__all__ = [
    "client_iface",
    "invoke_event_model",
    "qmessage_model",
    "reply_event_model",
    "rpc_error",
    "Almanet",
    "new_session",
]


logger = logging.getLogger("almanet")
logger.setLevel(logging.DEBUG)


@_shared.dataclass(slots=True)
class qmessage_model[T: typing.Any]:
    """
    Represents a message in the queue.
    """

    id: str
    timestamp: int
    body: T
    attempts: int
    commit: typing.Callable[[], typing.Awaitable[None]]
    rollback: typing.Callable[[], typing.Awaitable[None]]


type returns_consumer[T: typing.Any] = tuple[typing.AsyncIterable[qmessage_model[T]], typing.Callable[[], None]]


class client_iface(typing.Protocol):
    """
    Interface for a client library.
    """

    async def connect(
        self,
        addresses: typing.Sequence[str],
    ) -> None:
        raise NotImplementedError()

    async def produce(
        self,
        topic: str,
        message: str | bytes,
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
    payload: typing.Any
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
    is_error: bool
    payload: typing.Any


class rpc_error(Exception):
    """
    Represents an RPC error.
    You can inherit from this class to create your own error.
    """

    __slots__ = ("name", "args")

    def __init__(
        self,
        *args,
        name: str | None = None,
    ) -> None:
        self.name = name or self.__class__.__name__
        self.args = args

    def __str__(self) -> str:
        return f"{self.name}{self.args}"


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

    @property
    def __doc__(self):
        return self.procedure.__doc__

    def __call__(self, *args, **kwargs):
        return self.procedure(*args, **kwargs)

    async def execute(
        self,
        invocation: invoke_event_model,
    ) -> reply_event_model:
        __log_extra = {"registration": str(self), "invocation": str(invocation)}
        try:
            logger.debug("trying to execute procedure", extra=__log_extra)
            reply_payload = await self.procedure(invocation.payload)
            return reply_event_model(call_id=invocation.id, is_error=False, payload=reply_payload)
        except Exception as e:
            if isinstance(e, rpc_error):
                error_name = e.name
                error_message = e.args
            elif isinstance(e, pydantic_core.ValidationError):
                error_name = "ValidationError"
                error_message = repr(e)
            else:
                error_name = "InternalError"
                error_message = "oops"
                logger.exception("during execute procedure", extra=__log_extra)
            return reply_event_model(
                call_id=invocation.id,
                is_error=True,
                payload={"name": error_name, "message": error_message},
            )


class Almanet:
    """
    Represents a session, connected to message broker.
    """

    @property
    def version(self) -> float:
        return 0

    def __init__(
        self,
        *addresses: str,
        client_class: type[client_iface] | None = None,
    ) -> None:
        if not all(isinstance(i, str) for i in addresses):
            raise ValueError("addresses must be a iterable of strings")
        self.id = _shared.new_id()
        self.joined = False
        self.addresses: typing.Sequence[str] = addresses
        self.task_pool = _shared.task_pool()
        if client_class is None:
            from . import _clients

            client_class = _clients.DEFAULT_CLIENT
        self._client: client_iface = client_class()
        self._post_join_event = _shared.observable()
        self._leave_event = _shared.observable()
        self._pending_replies: typing.MutableMapping[str, asyncio.Future[reply_event_model]] = {}
        self._invocations_switch = _shared.switch()

    async def _produce(
        self,
        uri: str,
        payload: typing.Any,
    ) -> None:
        try:
            message_body = _shared.dump(payload)
        except Exception as e:
            logger.error(f"during encode payload: {repr(e)}")
            raise e

        try:
            logger.debug(f"trying to produce {uri} topic")
            await self._client.produce(uri, message_body)
        except Exception as e:
            logger.exception(f"during produce {uri} topic")
            raise e

    def produce(
        self,
        uri: str,
        payload: typing.Any,
    ) -> asyncio.Task[None]:
        """
        Produce a message with a specified topic and payload.
        """
        return self.task_pool.schedule(self._produce(uri, payload))

    async def _serialize[T: typing.Any](
        self,
        messages_stream: typing.AsyncIterable[qmessage_model[bytes]],
        payload_model: type[T] | typing.Any = ...,
    ) -> typing.AsyncIterable[qmessage_model[T]]:
        serializer = _shared.serialize_json(payload_model)

        async for message in messages_stream:
            try:
                message.body = serializer(message.body)
            except:
                logger.exception("during decode payload")
                continue

            yield message  # type: ignore

    async def consume[T](
        self,
        topic: str,
        channel: str,
        *,
        payload_model: type[T] | typing.Any = ...,
    ) -> returns_consumer[T]:
        """
        Consume messages from a message broker with the specified topic and channel.
        It returns a tuple of a stream of messages and a function that can stop consumer.
        """
        logger.debug(f"trying to consume {topic}/{channel}")

        messages_stream, stop_consumer = await self._client.consume(topic, channel)
        self._leave_event.add_observer(stop_consumer)

        messages_stream = self._serialize(messages_stream, payload_model)

        return messages_stream, stop_consumer

    async def _consume_replies(
        self,
        ready_event: asyncio.Event,
    ) -> None:
        messages_stream, _ = await self.consume(
            f"_rpc_._reply_.{self.id}",
            channel="rpc-recipient",
        )
        logger.debug("reply event consumer begin")
        ready_event.set()
        async for message in messages_stream:
            __log_extra = {"incoming_message": str(message)}
            try:
                reply = reply_event_model(**message.body)
                __log_extra["reply"] = str(reply)
                logger.debug("new reply", extra=__log_extra)

                pending = self._pending_replies.get(reply.call_id)
                if pending is None:
                    logger.warning("pending event not found", extra=__log_extra)
                else:
                    pending.set_result(reply)
            except:
                logger.exception("during parse reply", extra=__log_extra)

            await message.commit()
            logger.debug("successful commit", extra=__log_extra)
        logger.debug("reply event consumer end")

    _call_only_args = tuple[str, typing.Any]

    class _call_only_kwargs(typing.TypedDict):
        timeout: typing.NotRequired[int]

    async def _call_only(
        self,
        *args: typing.Unpack[_call_only_args],
        **kwargs: typing.Unpack[_call_only_kwargs],
    ) -> reply_event_model:
        uri, payload = args
        timeout = kwargs.get("timeout") or 60

        invocation = invoke_event_model(
            id=_shared.new_id(),
            caller_id=self.id,
            payload=payload,
            reply_topic=f"_rpc_._reply_.{self.id}",
        )

        __log_extra = {"uri": uri, "timeout": timeout, "invoke_event": str(invocation)}
        logger.debug("trying to call", extra=__log_extra)

        pending_reply_event = asyncio.Future[reply_event_model]()
        self._pending_replies[invocation.id] = pending_reply_event

        try:
            async with asyncio.timeout(timeout):
                await self.produce(f"_rpc_.{uri}", invocation)

                reply_event = await pending_reply_event
                __log_extra["reply_event"] = str(reply_event)
                logger.debug("new reply event", extra=__log_extra)

                if reply_event.is_error:
                    raise rpc_error(
                        reply_event.payload["message"],
                        name=reply_event.payload["name"],
                    )

                return reply_event
        except Exception as e:
            logger.error(f"during call {uri}", extra={**__log_extra, "error": repr(e)})
            raise e
        finally:
            self._pending_replies.pop(invocation.id)

    def call_only(
        self,
        *args: typing.Unpack[_call_only_args],
        **kwargs: typing.Unpack[_call_only_kwargs],
    ) -> asyncio.Task[reply_event_model]:
        """
        Executes the remote procedure using the payload.
        """
        return self.task_pool.schedule(self._call_only(*args, **kwargs))

    class _call_kwargs[R](_call_only_kwargs):
        result_model: typing.NotRequired[type[R]]

    async def _call[I, O](
        self,
        topic: typing.Union[str, "_service.abstract_procedure_model[I, O]"],
        payload: I,
        **kwargs: typing.Unpack[_call_kwargs],
    ) -> O:
        result_model = kwargs.pop("result_model", ...)

        if isinstance(topic, str):
            uri = topic
        else:
            uri = topic.uri
            if result_model is ...:
                result_model = topic.return_model

        serialize_result = _shared.serialize(result_model)

        reply_event = await self._call_only(uri, payload, **kwargs)

        try:
            result = serialize_result(reply_event.payload)
        except pydantic_core.ValidationError as e:
            logger.error(f"invalid result from {uri}", extra={"error": repr(e)})
            raise e

        return result

    @typing.overload
    def call[I, O](
        self,
        topic: "_service.abstract_procedure_model[I, O]",
        payload: I,
        **kwargs: typing.Unpack[_call_kwargs],
    ) -> asyncio.Task[O]: ...

    @typing.overload
    def call[O](
        self,
        topic: str,
        payload: typing.Any,
        **kwargs: typing.Unpack[_call_kwargs[O]],
    ) -> asyncio.Task[O]: ...

    def call(self, *args, **kwargs):
        """
        Executes the remote procedure using the payload.
        Returns a instance of result model.
        """
        return self.task_pool.schedule(self._call(*args, **kwargs))

    async def _multicall_only(
        self,
        *args: typing.Unpack[_call_only_args],
        **kwargs: typing.Unpack[_call_only_kwargs],
    ) -> list[reply_event_model]:
        uri, payload = args
        timeout = kwargs.get("timeout") or 60

        invocation = invoke_event_model(
            id=_shared.new_id(),
            caller_id=self.id,
            payload=payload,
            reply_topic=f"_rpc_._replies_.{self.id}",
        )

        __log_extra = {"uri": uri, "timeout": timeout, "invoke_event": str(invocation)}

        messages_stream, stop_consumer = await self.consume(invocation.reply_topic, "rpc-recipient")

        result = []
        try:
            async with asyncio.timeout(timeout):
                await self.produce(f"_rpc_.{uri}", invocation)

                async for message in messages_stream:
                    try:
                        logger.debug("new reply event", extra=__log_extra)
                        reply = reply_event_model(**message.body)
                        result.append(reply)
                    except:
                        logger.exception("during parse reply event", extra=__log_extra)

                    await message.commit()
        except TimeoutError:
            stop_consumer()

        logger.debug(f"multicall {uri} done")

        return result

    def multicall_only(
        self,
        *args: typing.Unpack[_call_only_args],
        **kwargs: typing.Unpack[_call_only_kwargs],
    ) -> asyncio.Task[list[reply_event_model]]:
        """
        Execute simultaneously multiple procedures using the payload.
        """
        return self.task_pool.schedule(self._multicall_only(*args, **kwargs))

    async def _handle_invocation(
        self,
        registration: registration_model,
        message: qmessage_model,
    ):
        __log_extra = {"registration": str(registration), "incoming_message": str(message)}
        try:
            invocation = invoke_event_model(**message.body)
            __log_extra["invocation"] = str(invocation)
            logger.debug("new invocation", extra=__log_extra)

            if invocation.expired:
                logger.warning("invocation expired", extra=__log_extra)
            else:
                reply = await registration.execute(invocation)
                logger.debug("trying to reply", extra=__log_extra)
                await self.produce(invocation.reply_topic, reply)
        except:
            logger.exception("during execute invocation", extra=__log_extra)
        finally:
            await message.commit()
            logger.debug("successful commit", extra=__log_extra)

    async def _consume_invocations(
        self,
        registration: registration_model,
    ) -> None:
        logger.debug(f"trying to register {registration.uri}/{registration.channel}")
        messages_stream, _ = await self.consume(f"_rpc_.{registration.uri}", registration.channel)
        async for message in messages_stream:
            self.task_pool.schedule(self._handle_invocation(registration, message))
            await self._invocations_switch.access()
        logger.debug(f"consumer {registration.uri} down")

    def register(
        self,
        topic: str,
        procedure: typing.Callable,
        *,
        channel: str | None = None,
    ) -> registration_model:
        """
        Register a procedure with a specified topic and payload.
        Returns the created registration.
        """
        r = registration_model(
            uri=topic,
            channel=channel or "RPC",
            procedure=procedure,
            session=self,
        )

        self._post_join_event.add_observer(
            lambda: self.task_pool.schedule(self._consume_invocations(r), daemon=True),
        )

        return r

    async def join(self) -> None:
        """
        Join the session to message broker.
        """
        if self.joined:
            raise RuntimeError(f"session {self.id} already joined")

        if len(self.addresses) == 0:
            raise ValueError("addresses are not specified")

        logger.debug(f"trying to connect addresses={self.addresses}")

        await self._client.connect(self.addresses)

        consume_replies_ready = asyncio.Event()
        self.task_pool.schedule(
            self._consume_replies(consume_replies_ready),
            daemon=True,
        )
        await consume_replies_ready.wait()

        self.joined = True
        self._post_join_event.notify()
        logger.info(f"session {self.id} joined")

    async def __aenter__(self) -> "Almanet":
        if not self.joined:
            await self.join()
        return self

    async def leave(
        self,
        reason: str | None = None,
    ) -> None:
        """
        Leave the session from message broker.
        """
        if not self.joined:
            raise RuntimeError(f"session {self.id} not joined")
        self.joined = False

        logger.debug(f"trying to leave {self.id} session, reason: {reason}")

        self._invocations_switch.off()

        logger.debug(f"session {self.id} await task pool complete")
        await self.task_pool.complete()

        self._leave_event.notify()

        self._invocations_switch.on()

        logger.debug(f"session {self.id} trying to close connection")
        await self._client.close()

        # some tasks have not been completed yet
        await asyncio.sleep(0.1)

        logger.warning(f"session {self.id} left")

    async def __aexit__(
        self,
        exception_type=None,
        exception_value=None,
        exception_traceback=None,
    ) -> None:
        if self.joined:
            await self.leave()


new_session = Almanet
