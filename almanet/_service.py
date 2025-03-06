import typing

from . import _session_pool
from . import _session
from . import _shared

__all__ = [
    "invalid_rpc_payload",
    "invalid_rpc_return",
    "remote_procedure_model",
    "remote_service",
    "new_remote_service",
]


class invalid_rpc_payload(_session.rpc_exception, _shared.invalid_payload): ...


class invalid_rpc_return(_session.rpc_exception, _shared.invalid_payload): ...


@_shared.dataclass(kw_only=True, slots=True)
class remote_procedure_model[I, O](_shared.procedure_model[I, O]):
    service: "remote_service"
    exceptions: set[type[_session.rpc_exception]] = ...
    include_to_api: bool = False
    _has_implementation: bool = False

    @property
    def uri(self):
        return ".".join([self.service.pre, self.name])

    def __post_init__(self):
        super(remote_procedure_model, self).__post_init__()
        self.exceptions.add(invalid_rpc_payload)
        self.exceptions.add(invalid_rpc_return)

    async def __call__(
        self,
        payload: I,
        *args,
        session: _session.Almanet | None = None,
        _force_local: bool = True,
        **kwargs,
    ) -> O:
        _session.logger.debug(f"Calling {self.uri}")

        if session is None:
            session = _session_pool.acquire_active_session()

        if self._has_implementation and _force_local:
            try:
                return await super(remote_procedure_model, self).__call__(payload, *args, session=session, **kwargs)
            except _shared.invalid_payload as e:
                raise invalid_rpc_payload(*e.args)
            except _shared.invalid_return as e:
                raise invalid_rpc_return(*e.args)

        try:
            return await session.call(self.uri, payload, result_model=self.return_model)
        except _session.rpc_exception as e:
            for etype in self.exceptions:
                if e.name == etype.__name__:
                    raise etype(*e.args)
            raise e

    def implements(
        self,
        real_function: _shared._function[I, O],
    ) -> "remote_procedure_model[I, O]":
        if self._has_implementation:
            raise ValueError("procedure already implemented")
        self._has_implementation = True

        procedure = self.service.add_procedure(
            real_function,
            name=self.name,
            include_to_api=self.include_to_api,
            description=self.description,
            tags=self.tags,
            validate=self.validate,
            payload_model=self.payload_model,
            return_model=self.return_model,
        )
        return procedure


class remote_service:
    def __init__(
        self,
        prepath: str = "",
        tags: set[str] | None = None,
        include_to_api: bool = False,
    ) -> None:
        self.channel = "service"
        self.pre: str = prepath
        self.default_tags: set[str] = set(tags or [])
        self.include_to_api: bool = include_to_api
        self.procedures: list[remote_procedure_model] = []
        self.background_tasks = _shared.background_tasks()
        self._post_join_event = _shared.observable_event()
        self._post_join_event.add_observer(self._share_all)

    @property
    def routes(self) -> set[str]:
        return {f"{i.uri}:{self.channel}" for i in self.procedures}

    def post_join[T: typing.Callable](
        self,
        function: T,
    ) -> T:
        def decorator(
            session_pool: "_session_pool.session_pool",
            *args,
            **kwargs,
        ):
            session = session_pool.rotate()
            coroutine = function(session, *args, **kwargs)
            self.background_tasks.schedule(coroutine)

        self._post_join_event.add_observer(decorator)
        return function

    class _register_procedure_kwargs(typing.TypedDict):
        name: typing.NotRequired[str]
        include_to_api: typing.NotRequired[bool]
        description: typing.NotRequired[str | None]
        tags: typing.NotRequired[set[str]]
        validate: typing.NotRequired[bool]
        payload_model: typing.NotRequired[typing.Any]
        return_model: typing.NotRequired[typing.Any]
        exceptions: typing.NotRequired[set[type[_session.rpc_exception]]]

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
        **extra,
    ) -> None:
        async def procedure(*args, **kwargs):
            return {
                "session_id": self.session.id,
                "session_version": self.session.version,
                "routes": list(self.routes),
                **extra,
            }

        self.session.register(
            "_schema_.client",
            procedure,
            channel=self.session.id,
        )

    def _share_procedure_schema(
        self,
        registration: remote_procedure_model,
    ) -> None:
        tags = registration.tags | self.default_tags
        if len(tags) == 0:
            tags = {"Default"}

        async def procedure(*args, **kwargs):
            return {
                "session_id": self.session.id,
                "session_version": self.session.version,
                "uri": registration.uri,
                "validate": registration.validate,
                "payload_model": registration.payload_model,
                "return_model": registration.return_model,
                "tags": tags,
                **registration._schema,
            }

        self.session.register(
            f"_schema_.{registration.uri}.{self.channel}",
            procedure,
            channel=self.channel,
        )

    def _share_all(
        self,
        session_pool: "_session_pool.session_pool",
    ) -> None:
        _session.logger.info(f"Sharing {self.pre} procedures")

        self.session = session_pool.rotate()
        if session_pool.count > 1:
            # if there are multiple sessions, we want to share the procedures with all but exclude the current session
            available_sessions = [i for i in session_pool.sessions if i is not self.session]
        else:
            available_sessions = session_pool.sessions

        for procedure in self.procedures:
            for session in available_sessions:
                session.register(
                    procedure.uri,
                    procedure.__call__,
                    channel=self.channel,
                )

            if procedure.include_to_api:
                self._share_procedure_schema(procedure)

        if self.include_to_api:
            self._share_self_schema()


new_remote_service = remote_service
