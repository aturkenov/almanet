import typing

import pydantic_core

from . import _session
from . import _shared

__all__ = [
    "remote_exception",
    "rpc_invalid_payload",
    "rpc_invalid_return",
    "remote_procedure_model",
    "remote_service",
    "new_remote_service",
]


class remote_exception(_session.rpc_exception):
    """
    Represents an remote procedure call exception.
    You can inherit from this class to create your own exceptions.
    """

    payload: typing.Any

    @classmethod
    def _make_from_payload(
        klass,
        v: bytes,
        *args,
        **kwargs,
    ) -> "remote_exception":
        """
        Returns instance of the class with the serialized payload.

        Raises:
        - pydantic_code.ValidationError
        """
        model = klass.__annotations__.get("payload", ...)
        serializer = _shared.serialize_json(model)
        payload = serializer(v)
        return klass(payload)


class rpc_invalid_payload(remote_exception):
    """
    Represents an invalid payload for a remote procedure call.
    """

    payload: typing.Any


class rpc_invalid_return(remote_exception):
    """
    Represents an invalid return value for a remote procedure call.
    """


class rpc_invalid_exception_payload(rpc_invalid_payload):
    """
    Represents an invalid payload for remote exception.
    """


@_shared.dataclass(kw_only=True, slots=True)
class remote_procedure_model[I, O](_shared.procedure_model[I, O]):
    service: "remote_service"
    uri: str = ...
    channel: str = _session.DEFAULT_CHANNEL
    exceptions: set[type[remote_exception]] = ...
    include_to_api: bool = False
    _has_implementation: bool = False

    def __post_init__(self):
        super(remote_procedure_model, self).__post_init__()
        if self.uri is ...:
            self.uri = ".".join([self.service.pre, self.name])
        self.exceptions.add(rpc_invalid_payload)
        self.exceptions.add(rpc_invalid_return)

    def execute(
        self,
        payload: I,
        session: _session.Almanet,
    ) -> typing.Awaitable[O]:
        return self.function(payload, session=session)

    async def _remote_execution(
        self,
        payload: bytes,
        session: _session.Almanet,
    ) -> bytes:
        """
        if called remotely
        """
        _session.logger.debug(f"remote calling {self.uri}")

        try:
            __payload = self.serialize_payload(payload)
        except pydantic_core.ValidationError as e:
            raise rpc_invalid_payload(str(e))

        result = await self.execute(__payload, session)

        # if not isinstance(result, self.return_model):
        #     raise rpc_invalid_return()

        return _shared.dump(result)

    class _local_execution_kwargs(_session.Almanet._call_kwargs):
        force_local: typing.NotRequired[bool]

    async def _local_execution(
        self,
        payload: I,
        **kwargs: typing.Unpack[_local_execution_kwargs],
    ) -> O:
        """
        if called locally

        Args:
        - force_local: if True, force local execution
        """
        _session.logger.debug(f"local calling {self.uri}")

        session = _session.get_active_session()

        force_local = kwargs.pop("force_local", True)
        if self._has_implementation and force_local:
            return await self.execute(payload, session)

        try:
            reply_event = await session.call(self.uri, payload, **kwargs)
            return self.serialize_return(reply_event.payload)
        except _session.rpc_exception as e:
            for etype in self.exceptions:
                if e.name == etype.__name__:
                    try:
                        raise etype._make_from_payload(e.payload)
                    except pydantic_core.ValidationError as e:
                        raise rpc_invalid_exception_payload(str(e))
            _session.logger.warning(f"{e.name} exception not define for {self.uri}")
            raise e

    def __call__(
        self,
        payload: I,
        **kwargs: typing.Unpack[_local_execution_kwargs],
    ) -> typing.Awaitable[O]:
        return self._local_execution(payload, **kwargs)

    def implements(
        self,
        real_function: _shared._function[I, O],
    ) -> "remote_procedure_model[I, O]":
        if self._has_implementation:
            raise ValueError("procedure already implemented")

        procedure = self.service.add_procedure(
            real_function,
            name=self.name,
            include_to_api=self.include_to_api,
            description=self.description,
            tags=self.tags,
            validate=self.validate,
            payload_model=self.payload_model,
            return_model=self.return_model,
            uri=self.uri,
            channel=self.channel,
            exceptions=self.exceptions,
        )

        self._has_implementation = True

        return procedure


class remote_service:
    def __init__(
        self,
        prepath: str,
        tags: set[str] | None = None,
        include_to_api: bool = False,
    ) -> None:
        self.pre: str = prepath
        self.default_tags: set[str] = set(tags or [])
        self.include_to_api: bool = include_to_api
        self.procedures: list[remote_procedure_model] = []
        self.background_tasks = _shared.background_tasks()
        self._post_join_event = _shared.observable_event()
        self._post_join_event.add_observer(self._share_all)
        _registry[self.pre] = self

    @property
    def routes(self) -> set[str]:
        return {f"{i.uri}:{i.channel}" for i in self.procedures}

    def post_join[T: typing.Callable](
        self,
        function: T,
    ) -> T:
        self._post_join_event.add_observer(function)
        return function

    class _register_procedure_kwargs(typing.TypedDict):
        name: typing.NotRequired[str]
        include_to_api: typing.NotRequired[bool]
        description: typing.NotRequired[str | None]
        tags: typing.NotRequired[set[str]]
        validate: typing.NotRequired[bool]
        payload_model: typing.NotRequired[typing.Any]
        return_model: typing.NotRequired[typing.Any]
        uri: typing.NotRequired[str]
        channel: typing.NotRequired[str]
        exceptions: typing.NotRequired[set[type[remote_exception]]]

    @typing.overload
    def public_procedure[I, O](
        self,
        function: _shared._function[I, O],
    ) -> remote_procedure_model[I, O]: ...

    @typing.overload
    def public_procedure[I, O](
        self,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> typing.Callable[[_shared._function[I, O]], remote_procedure_model[I, O]]: ...

    def public_procedure(
        self,
        function=None,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> remote_procedure_model | typing.Callable[[_shared._function], remote_procedure_model]:
        if function is None:
            return lambda function: remote_procedure_model(service=self, function=function, **kwargs)
        return remote_procedure_model(service=self, function=function, **kwargs)

    def add_procedure(
        self,
        function: typing.Callable,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> remote_procedure_model:
        procedure = remote_procedure_model(
            **kwargs,
            function=function,
            service=self,
            _has_implementation=True,
        )
        self.procedures.append(procedure)
        return procedure

    @typing.overload
    def procedure[I, O](
        self,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> typing.Callable[[_shared._function[I, O]], remote_procedure_model[I, O]]: ...

    @typing.overload
    def procedure[I, O](
        self,
        function: _shared._function[I, O],
    ) -> remote_procedure_model[I, O]: ...

    def procedure(
        self,
        function=None,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> remote_procedure_model | typing.Callable[[_shared._function], remote_procedure_model]:
        """
        Allows you to easily add procedures (functions) to a microservice by using a decorator.
        Returns a decorated function.
        """
        if function is None:
            return lambda function: self.add_procedure(function, **kwargs)
        return self.add_procedure(function, **kwargs)

    def _share_self_schema(
        self,
        session: _session.Almanet,
        **extra,
    ) -> None:
        async def procedure(*args, **kwargs):
            return {
                "session_id": session.id,
                "session_version": session.version,
                "routes": list(self.routes),
                **extra,
            }

        session.register(
            "_schema_.client",
            procedure,
            channel=session.id,
        )

    def _share_procedure_schema(
        self,
        session: _session.Almanet,
        registration: remote_procedure_model,
    ) -> None:
        tags = registration.tags | self.default_tags
        if len(tags) == 0:
            tags = {"default"}

        async def procedure(*args, **kwargs):
            return {
                "session_id": session.id,
                "session_version": session.version,
                "uri": registration.uri,
                "channel": registration.channel,
                "validate": registration.validate,
                "tags": tags,
                **registration.json_schema,
            }

        session.register(
            f"_schema_.{registration.uri}.{registration.channel}",
            procedure,
            channel=registration.channel,
        )

    def _share_all(
        self,
        session: _session.Almanet,
    ) -> None:
        _session.logger.info(f"Sharing {self.pre} procedures")

        for procedure in self.procedures:
            session.register(
                procedure.uri,
                procedure._remote_execution,
                channel=procedure.channel,
            )

            if procedure.include_to_api:
                self._share_procedure_schema(session, procedure)

        if self.include_to_api:
            self._share_self_schema(session)


new_remote_service = remote_service

_registry = {}


def get_service(
    uri: str,
) -> remote_service | None:
    """
    Returns the service object for the given uri.
    """
    return _registry.get(uri)
