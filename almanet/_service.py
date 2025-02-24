import typing

from . import _shared
from . import _session_pool

__all__ = [
    "service",
    "new_service",
]


class _function[I, O](typing.Protocol):
    __name__: str

    async def __call__(
        self,
        payload: I,
        *args,
        **kwargs,
    ) -> O: ...


@_shared.dataclass
class procedure_model[I, O]:
    service: "service"
    function: _function[I, O]
    path: str = ...
    description: str | None = None
    tags: set[str] = ...
    include_to_api: bool = True
    validate: bool = True
    payload_model: typing.Any = ...
    return_model: typing.Any = ...
    _has_implementation: bool = False
    _schema: typing.Mapping = ...

    def __post_init__(self):
        if not callable(self.function):
            raise ValueError("decorated function must be callable")
        if not isinstance(self.path, str):
            self.path = self.function.__name__
        self.payload_model, self.return_model = _shared.extract_annotations(
            self.function, self.payload_model, self.return_model
        )
        self._schema = _shared.describe_function(
            self.function,
            self.description,
            payload_annotation=self.payload_model,
            return_annotation=self.return_model,
        )
        self.description = self._schema["description"]
        if self.validate:
            self.function = _shared.validate_execution(self.function, self.payload_model, self.return_model)
        if self.tags is ...:
            self.tags = set()

    @property
    def uri(self):
        return '.'.join([self.service.pre, self.path])

    def __call__(self, payload: I) -> typing.Awaitable[O]:
        session = _session_pool.acquire_active_session()

        if self._has_implementation:
            return self.function(payload, session=session)

        return session.call(self.uri, payload, result_model=self.return_model)

    def implements(
        self,
        real_function: _function[I, O],
    ) -> "procedure_model[I, O]":
        if self._has_implementation:
            raise ValueError("procedure already implemented")
        self._has_implementation = True

        procedure = self.service.add_procedure(
            real_function,
            path=self.path,
            include_to_api=self.include_to_api,
            description=self.description,
            tags=self.tags,
            validate=self.validate,
            payload_model=self.payload_model,
            return_model=self.return_model,
        )
        return procedure


class service:
    def __init__(
        self,
        prepath: str = '',
        tags: set[str] | None = None,
    ) -> None:
        self.channel = "service"
        self.pre: str = prepath
        self.default_tags: set[str] = set(tags or [])
        self.procedures: list[procedure_model] = []
        self.background_tasks = _shared.background_tasks()
        self._post_join_event = _shared.observable()
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
        path: typing.NotRequired[str]
        include_to_api: typing.NotRequired[bool]
        description: typing.NotRequired[str | None]
        tags: typing.NotRequired[set[str]]
        validate: typing.NotRequired[bool]
        payload_model: typing.NotRequired[typing.Any]
        return_model: typing.NotRequired[typing.Any]

    @typing.overload
    def public_procedure[I, O](
        self,
        function: _function[I, O],
    ) -> procedure_model[I, O]: ...

    @typing.overload
    def public_procedure[I, O](
        self,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> typing.Callable[[_function[I, O]], procedure_model[I, O]]: ...

    def public_procedure(
        self,
        function = None,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> procedure_model | typing.Callable[[_function], procedure_model]:
        if function is None:
            return lambda function: procedure_model(self, function, **kwargs)
        return procedure_model(self, function, **kwargs)

    def add_procedure(
        self,
        function: typing.Callable,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> procedure_model:
        procedure = procedure_model(
            self,
            function,
            **kwargs,
            _has_implementation=True,
        )
        self.procedures.append(procedure)
        return procedure

    @typing.overload
    def procedure[I, O](
        self,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> typing.Callable[[_function[I, O]], procedure_model[I, O]]: ...

    @typing.overload
    def procedure[I, O](
        self,
        function: _function[I, O],
    ) -> procedure_model[I, O]: ...

    def procedure(
        self,
        function = None,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> procedure_model | typing.Callable[[_function], procedure_model]:
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
        registration: procedure_model,
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
        self.session = session_pool.rotate()

        self._share_self_schema()

        for procedure in self.procedures:
            for session in session_pool.sessions:
                session.register(
                    procedure.uri,
                    procedure.function,
                    channel=self.channel,
                )

            if procedure.include_to_api:
                self._share_procedure_schema(procedure)


new_service = service
