import asyncio
import typing

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
        with _shared.use_span(self.session._tracing_span):
            with _shared.new_span(
                f"execution {self.channel}/{self.uri}",
                attributes={
                    "registration": str(self),
                    "invocation": str(invocation),
                },
            ) as span:
                try:
                    reply_payload = await self.procedure(invocation.payload)
                    return reply_event_model(call_id=invocation.id, is_error=False, payload=reply_payload)
                except Exception as e:
                    span.record_exception(e)
                    if isinstance(e, rpc_error):
                        error_name = e.name
                        error_message = e.args
                    elif isinstance(e, _shared.validation_error):
                        error_name = "ValidationError"
                        error_message = repr(e)
                    else:
                        error_name = "InternalError"
                        error_message = "oops"
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
        with _shared.new_span(
            "producing",
            attributes={"uri": uri},
        ) as span:
            message_body = _shared.dump(payload)
            span.add_event("sending")
            await self._client.produce(uri, message_body)

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
            with _shared.new_span("serialization") as span:
                try:
                    message.body = serializer(message.body)
                except Exception as e:
                    span.record_exception(e, {"message": str(message)})
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
        with _shared.new_span(
            "consuming",
            attributes={
                "uri": topic,
                "channel": channel,
            },
        ):
            messages_stream, stop_consumer = await self._client.consume(topic, channel)
            self._leave_event.add_observer(stop_consumer)

            messages_stream = self._serialize(messages_stream, payload_model)

            return messages_stream, stop_consumer

    async def _consume_replies(
        self,
        ready_event: asyncio.Event,
    ) -> None:
        with _shared.new_span("replies consumer") as span:
            messages_stream, _ = await self.consume(
                f"_rpc_._reply_.{self.id}",
                channel="rpc-recipient",
            )
            ready_event.set()

            async for message in messages_stream:
                span.add_event("new reply event", attributes={"message": str(message)})

                try:
                    reply = reply_event_model(**message.body)
                except Exception as e:
                    span.record_exception(e, {"incoming_message": str(message)})

                pending = self._pending_replies.get(reply.call_id)
                if pending is None:
                    span.record_exception(
                        Exception("pending event not found"),
                        {"incoming_message": str(message)}
                    )
                else:
                    pending.set_result(reply)

                await message.commit()

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

        with _shared.new_span(
            "only calling",
            attributes={
                "uri": uri,
                "timeout": timeout,
                "invoke_event": str(invocation),
            },
        ) as span:
            pending_reply_event = asyncio.Future[reply_event_model]()
            self._pending_replies[invocation.id] = pending_reply_event

            try:
                async with asyncio.timeout(timeout):
                    await self.produce(f"_rpc_.{uri}", invocation)

                    reply_event = await pending_reply_event
                    span.add_event("reply", attributes={"reply_event": str(reply_event)})

                    if reply_event.is_error:
                        raise rpc_error(
                            reply_event.payload["message"],
                            name=reply_event.payload["name"],
                        )
                    return reply_event
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

        with _shared.new_span(
            "calling",
            attributes={
                "uri": uri,
                "result_model": str(result_model),
            },
        ):
            serialize_result = _shared.serialize(result_model)
            reply_event = await self._call_only(uri, payload, **kwargs)
            result = serialize_result(reply_event.payload)
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

        with _shared.new_span(
            "only multicalling",
            attributes={
                "uri": uri,
                "timeout": timeout,
                "invoke_event": str(invocation),
            },
        ) as span:
            messages_stream, stop_consumer = await self.consume(
                invocation.reply_topic,
                "rpc-recipient",
            )

            result = []
            try:
                async with asyncio.timeout(timeout):
                    await self.produce(f"_rpc_.{uri}", invocation)

                    async for message in messages_stream:
                        try:
                            span.add_event("new reply event", attributes={"message": str(message)})
                            reply = reply_event_model(**message.body)
                            result.append(reply)
                        except Exception as e:
                            span.record_exception(e)

                        await message.commit()
            except TimeoutError:
                stop_consumer()

            span.add_event("done")

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
        with _shared.new_span(
            "_handle_invocation",
            attributes={
                "registration": str(registration),
                "incoming_message": str(message),
            },
        ) as span:
            try:
                invocation = invoke_event_model(**message.body)
                span.add_event("new invocation", {"invocation": str(invocation)})

                if invocation.expired:
                    span.add_event("invocation expired")
                else:
                    reply = await registration.execute(invocation)
                    span.add_event("replying", {"reply_event": str(reply)})
                    await self.produce(invocation.reply_topic, reply)
            finally:
                await message.commit()

    async def _consume_invocations(
        self,
        registration: registration_model,
    ) -> None:
        with _shared.new_span(
            "_consume_invocations",
            attributes={"registration": str(registration)},
        ):
            messages_stream, _ = await self.consume(
                f"_rpc_.{registration.uri}",
                registration.channel,
            )
            async for message in messages_stream:
                self.task_pool.schedule(self._handle_invocation(registration, message))
                await self._invocations_switch.access()

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
        with _shared.new_span("registration") as span:
            r = registration_model(
                uri=topic,
                channel=channel or "RPC",
                procedure=procedure,
                session=self,
            )
            span.set_attribute("registration", str(r))

            self._post_join_event.add_observer(
                lambda: self.task_pool.schedule(self._consume_invocations(r), daemon=True),
            )

            return r

    async def join(self) -> None:
        """
        Join the session to message broker.
        """
        with _shared.new_span(
            "session",
            attributes={
                "id": self.id,
                "addresses": self.addresses,
            },
            end_on_exit=False,
        ) as span:
            self._tracing_span = span

            if self.joined:
                raise RuntimeError(f"session {self.id} already joined")

            if len(self.addresses) == 0:
                raise ValueError("addresses are not specified")

            await self._client.connect(self.addresses)

            span.add_event("schedule replies consumer")
            consume_replies_ready = asyncio.Event()
            self.task_pool.schedule(
                self._consume_replies(consume_replies_ready),
                daemon=True,
            )
            await consume_replies_ready.wait()

            self.joined = True

            span.add_event("notify post join event observers")
            self._post_join_event.notify()

    async def __aenter__(self) -> "Almanet":
        if not self.joined:
            await self.join()
        return self

    async def leave(
        self,
        reason: str = '-',
    ) -> None:
        """
        Leave the session from message broker.
        """
        with _shared.use_span(
            self._tracing_span,
            end_on_exit=True,
        ) as span:
            span.add_event("leaving", attributes={"reason": reason})            

            if not self.joined:
                raise RuntimeError(f"session {self.id} not joined")
            self.joined = False

            span.add_event("disable receiving invocation events")
            self._invocations_switch.off()

            span.add_event("await task pool complete")
            await self.task_pool.complete()

            span.add_event("notify leave event observers")
            self._leave_event.notify()

            span.add_event("enable receiving invocation events")
            self._invocations_switch.on()

            span.add_event("close connection")
            await self._client.close()

            # some tasks have not been completed yet
            await asyncio.sleep(0.1)

    async def __aexit__(
        self,
        exception_type=None,
        exception_value=None,
        exception_traceback=None,
    ) -> None:
        if self.joined:
            await self.leave()


new_session = Almanet
