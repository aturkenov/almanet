import asyncio
import inspect
import logging
import typing

import pydantic_core

from . import _shared_

__all__ = [
    "Almanet",
    "client_iface",
    "invoke_event_model",
    "qmessage_model",
    "reply_event_model",
    "rpc_error",
]


logger = logging.getLogger("almanet")
logger.setLevel(logging.INFO)


@_shared_.dataclass(slots=True)
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


@_shared_.dataclass(slots=True)
class invoke_event_model[T: typing.Any]:
    """
    Represents an invocation event.
    """

    id: str
    caller_id: str
    payload: T
    reply_topic: str

    @property
    def expired(self) -> bool:
        # TODO
        return False


@_shared_.dataclass(slots=True)
class reply_event_model[T: typing.Any]:
    """
    Represents a reply event.
    """

    call_id: str
    is_error: bool
    payload: T


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


@_shared_.dataclass(slots=True)
class registration_model:
    """
    Represents a registered procedure to call.
    """

    topic: str
    channel: str
    procedure: typing.Callable
    session: "Almanet"
    is_async: bool = False

    def __post_init__(self):
        if self.channel is None:
            self.channel = "RPC"

        if inspect.iscoroutinefunction(self.procedure):
            self.is_async = True

    async def execute(
        self,
        invocation: invoke_event_model,
    ) -> reply_event_model:
        __log_extra = {"registration": str(self), "invocation": str(invocation)}
        try:
            logger.debug("trying to execute procedure", extra=__log_extra)
            if self.is_async:
                reply_payload = await self.procedure(self.session, invocation.payload)
            else:
                reply_payload = await asyncio.to_thread(self.procedure, self.session, invocation.payload)
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

    class _kwargs(typing.TypedDict):
        id: typing.NotRequired[str]

    def __init__(
        self,
        *addresses: str,
        client: client_iface,
        **kwargs: typing.Unpack[_kwargs],
    ) -> None:
        if not all(isinstance(i, str) for i in addresses):
            raise ValueError("addresses must be a iterable of strings")
        self.addresses = addresses
        self._client = client
        self.__pending_replies: typing.MutableMapping[str, asyncio.Future[reply_event_model]] = {}
        self.__leave_callbacks: list[typing.Callable] = list()
        self.id = kwargs.get("id") or _shared_.new_id()
        self.joined = False
        self.task_pool = _shared_.task_pool()

    type __produce_args = tuple[str, typing.Any]

    async def __produce(
        self,
        topic: str,
        payload: typing.Any,
    ) -> None:
        try:
            message_body = _shared_.dump(payload)
        except Exception as e:
            logger.error(f"during encode payload: {repr(e)}")
            raise e

        try:
            logger.debug(f"trying to produce {topic} topic")
            await self._client.produce(topic, message_body)
        except Exception as e:
            logger.exception(f"during produce {topic} topic")
            raise e

    def produce(
        self,
        *args: typing.Unpack[__produce_args],
    ) -> asyncio.Task[None]:
        """
        Produce a message with a specified topic and payload.
        """
        return self.task_pool.schedule(
            self.__produce(*args)
        )

    async def _serialize[T: typing.Any](
        self,
        messages_stream: typing.AsyncIterable[qmessage_model[bytes]],
        payload_model: type[T] | typing.Any = ...,
    ) -> typing.AsyncIterable[qmessage_model[T]]:
        serializer = _shared_.serialize_json(payload_model)

        async for message in messages_stream:
            try:
                message.body = serializer(message.body)
            except:
                logger.exception("during decode payload")
                continue

            yield message  # type: ignore

    async def consume[T: typing.Any](
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
        self.__leave_callbacks.append(stop_consumer)

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

                pending = self.__pending_replies.get(reply.call_id)
                if pending is None:
                    logger.warning("pending event not found", extra=__log_extra)
                else:
                    pending.set_result(reply)
            except:
                logger.exception("during parse reply", extra=__log_extra)

            await message.commit()
            logger.debug("successful commit", extra=__log_extra)
        logger.debug("reply event consumer end")

    type __call_args = tuple[str, typing.Any]
    class __call_kwargs(typing.TypedDict):
        timeout: typing.NotRequired[int]

    async def __call(
        self,
        topic: str,
        payload: typing.Any,
        *,
        timeout: int = 60,
    ) -> reply_event_model:
        invocation = invoke_event_model(
            id=_shared_.new_id(),
            caller_id=self.id,
            payload=payload,
            reply_topic=f"_rpc_._reply_.{self.id}",
        )

        __log_extra = {"topic": topic, "timeout": timeout, "invoke_event": str(invocation)}
        logger.debug("trying to call", extra=__log_extra)

        pending_reply_event = asyncio.Future[reply_event_model]()
        self.__pending_replies[invocation.id] = pending_reply_event

        try:
            async with asyncio.timeout(timeout):
                await self.produce(f"_rpc_.{topic}", invocation)

                response = await pending_reply_event
                __log_extra["reply_event"] = str(response)
                logger.debug("new reply event", extra=__log_extra)

                if response.is_error:
                    raise rpc_error(
                        response.payload["message"],
                        name=response.payload["name"],
                    )
                return response
        except Exception as e:
            logger.error("during call", extra={**__log_extra, "error": repr(e)})
            raise e
        finally:
            self.__pending_replies.pop(invocation.id)

    def call(
        self,
        *args: typing.Unpack[__call_args],
        **kwargs: typing.Unpack[__call_kwargs],
    ) -> asyncio.Task[reply_event_model]:
        """
        Call a procedure with a specified topic and payload.
        Returns a reply event.
        """
        return self.task_pool.schedule(
            self.__call(*args, **kwargs)
        )

    type __multicall_args = tuple[str, typing.Any]
    class __multicall_kwargs(typing.TypedDict):
        timeout: typing.NotRequired[int]

    async def __multicall(
        self,
        topic: str,
        payload: typing.Any,
        *,
        timeout: int = 60,
    ) -> list[reply_event_model]:
        invocation = invoke_event_model(
            id=_shared_.new_id(),
            caller_id=self.id,
            payload=payload,
            reply_topic=f"_rpc_._replies_.{self.id}",
        )

        __log_extra = {"topic": topic, "timeout": timeout, "invoke_event": str(invocation)}

        messages_stream, stop_consumer = await self.consume(invocation.reply_topic, "rpc-recipient")

        result = []
        try:
            async with asyncio.timeout(timeout):
                await self.produce(f"_rpc_.{topic}", invocation)

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

        logger.debug(f"multicall {topic} done")

        return result

    async def multicall(
        self,
        *args: typing.Unpack[__multicall_args],
        **kwargs: typing.Unpack[__multicall_kwargs],
    ) -> asyncio.Task[list[reply_event_model]]:
        """
        Call simultaneously multiple procedures with a specified topic and payload.
        Returns a list of reply events.
        """
        return self.task_pool.schedule(
            self.__multicall(*args, **kwargs)
        )

    async def _consume_invocations(
        self,
        r: registration_model,
    ) -> None:
        logger.debug(f"trying to register {r.topic}/{r.channel}")
        messages_stream, _ = await self.consume(r.topic, r.channel)
        async for message in messages_stream:
            __log_extra = {"registration": str(r), "incoming_message": str(message)}
            try:
                invocation = invoke_event_model(**message.body)
                __log_extra["invocation"] = str(invocation)
                logger.debug("new invocation", extra=__log_extra)

                if invocation.expired:
                    logger.warning("invocation expired", extra=__log_extra)
                else:
                    reply = await r.execute(invocation)
                    logger.debug("trying to reply", extra=__log_extra)
                    await self.produce(invocation.reply_topic, reply)
            except:
                logger.exception("during parse invocation", extra=__log_extra)

            await message.commit()
            logger.debug("successful commit", extra=__log_extra)
        logger.debug(f"consumer {r.topic} down")

    async def register(
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
            topic=f"_rpc_.{topic}",
            channel=channel,  # type: ignore
            procedure=procedure,
            session=self,
        )

        # schedules a task in the task_pool to consume invocations for this registration.
        self.task_pool.schedule(self._consume_invocations(r))

        return r

    async def join(self) -> None:
        """
        Join the session to message broker.
        """
        if self.joined:
            raise RuntimeError(f"session {self.id} already joined")

        logger.debug(f"trying to connect addresses={self.addresses}")

        await self._client.connect(self.addresses)

        consume_replies_ready = asyncio.Event()
        self.task_pool.schedule(self._consume_replies(consume_replies_ready), daemon=True)
        await consume_replies_ready.wait()

        self.joined = True

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

        stop_consume_replies = self.__leave_callbacks.pop(0)

        for callback in self.__leave_callbacks:
            callback()

        logger.debug(f"session {self.id} await task pool complete")
        await self.task_pool.complete()

        stop_consume_replies()

        logger.debug(f"session {self.id} trying to close connection")
        await self._client.close()

        logger.warning(f"session {self.id} left")

    async def __aexit__(
        self,
        exception_type,
        exception_value,
        exception_traceback,
    ) -> None:
        if self.joined:
            await self.leave()
