import typing

from . import _shared

if typing.TYPE_CHECKING:
    from . import _session_pool

__all__ = [
    "service",
    "new_service",
]


@_shared.dataclass
class abstract_procedure_model[I, O]:
    service: "service"
    procedure: typing.Callable[[I], typing.Awaitable[O]]
    path: str = ...
    include_to_api: bool = True
    description: str = None
    tags: set[str] = ...
    validate: bool = True
    payload_model: typing.Any = ...
    return_model: typing.Any = ...
    _has_implementation: bool = False
    _schema: typing.Mapping = ...

    def __post_init__(self):
        if not callable(self.procedure):
            raise ValueError("decorated function must be callable")
        if not isinstance(self.path, str):
            self.path = self.procedure.__name__
        self.payload_model, self.return_model = _shared.extract_annotations(
            self.procedure, self.payload_model, self.return_model
        )
        self._schema = _shared.describe_function(
            self.procedure,
            self.description,
            payload_annotation=self.payload_model,
            return_annotation=self.return_model,
        )
        self.description = self._schema["description"]
        if self.validate:
            self.procedure = _shared.validate_execution(self.procedure, self.payload_model, self.return_model)
        if self.tags is ...:
            self.tags = set()

    @property
    def uri(self):
        return '.'.join([self.service.pre, self.path])

    def __call__(self, *args, **kwargs):
        return self.procedure(*args, **kwargs)

    def implements[F: typing.Callable[..., typing.Awaitable]](
        self,
        real_function: F,
    ) -> F:
        if self._has_implementation:
            raise ValueError("procedure already implemented")
        self._has_implementation = True

        self.service.add_procedure(
            real_function,
            path=self.path,
            include_to_api=self.include_to_api,
            description=self.description,
            tags=self.tags,
            validate=self.validate,
            payload_model=self.payload_model,
            return_model=self.return_model,
        )

        return real_function


class service:
    def __init__(
        self,
        prepath: str = '',
        tags: set[str] | None = None,
    ) -> None:
        self.channel = "service"
        self.pre: str = prepath
        self.default_tags: set[str] = set(tags or [])
        self.procedures: list[abstract_procedure_model] = []
        self.task_pool = _shared.task_pool()
        self._post_join_event = _shared.observable()
        self._post_join_event.add_observer(self._share_all)

    @property
    def routes(self) -> set[str]:
        return {f"{i.uri}:{self.channel}" for i in self.procedures}

    def post_join[T: typing.Callable](
        self,
        function: T,
    ) -> T:
        self._post_join_event.add_observer(
            lambda *args, **kwargs: self.task_pool.schedule(function(*args, **kwargs))
        )
        return function

    class _register_procedure_kwargs(typing.TypedDict):
        path: typing.NotRequired[str]
        include_to_api: typing.NotRequired[bool]
        description: typing.NotRequired[str]
        tags: typing.NotRequired[set[str]]
        validate: typing.NotRequired[bool]
        payload_model: typing.NotRequired[typing.Any]
        return_model: typing.NotRequired[typing.Any]

    def add_procedure(
        self,
        function: typing.Callable,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> abstract_procedure_model:
        procedure = abstract_procedure_model(self, function, **kwargs)
        self.procedures.append(procedure)
        return procedure

    type _function[I, O] = typing.Callable[[I], typing.Awaitable[O]]

    @typing.overload
    def procedure[I, O](
        self,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> typing.Callable[[_function[I, O]], abstract_procedure_model[I, O]]: ...

    @typing.overload
    def procedure[I, O](
        self,
        function: _function[I, O],
    ) -> abstract_procedure_model[I, O]: ...

    def procedure[F: typing.Callable](
        self,
        function: F | None = None,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> F:
        """
        Allows you to easily add procedures (functions) to a microservice by using a decorator.
        Returns a decorated function.
        """
        if function is None:
            return lambda function: self.add_procedure(function, **kwargs)  # type: ignore
        return self.add_procedure(function, **kwargs)  # type: ignore

    @typing.overload
    def abstract_procedure[I, O](
        self,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> typing.Callable[[_function[I, O]], abstract_procedure_model[I, O]]: ...

    @typing.overload
    def abstract_procedure[I, O](
        self,
        function: _function[I, O],
    ) -> abstract_procedure_model[I, O]: ...

    def abstract_procedure(
        self,
        function: _function | None = None,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> abstract_procedure_model | typing.Callable[[_function], abstract_procedure_model]:
        if function is None:
            return lambda function: abstract_procedure_model(self, function, **kwargs)
        return abstract_procedure_model(self, function, **kwargs)

    def _share_self_schema(
        self,
        **extra,
    ) -> None:
        async def procedure(*args, **kwargs):
            return {
                "session_id": self.session.id,
                "routes": list(self.routes),
                **extra,
            }

        self.session.register(
            "_api_schema_.client",
            procedure,
            channel=self.session.id,
        )

    def _share_procedure_schema(
        self,
        registration: abstract_procedure_model,
    ) -> None:
        tags = registration.tags | self.default_tags
        if len(tags) == 0:
            tags = {"Default"}

        async def procedure(*args, **kwargs):
            return {
                "session_id": self.session.id,
                "uri": registration.uri,
                "validate": registration.validate,
                "payload_model": registration.payload_model,
                "return_model": registration.return_model,
                "tags": tags,
                **registration._schema,
            }

        self.session.register(
            f"_api_schema_.{registration.uri}.{self.channel}",
            procedure,
            channel=self.channel,
        )

    def _share_all(
        self,
        session_pool: "_session_pool.session_pool",
    ) -> None:
        self.session = session_pool.rotate()

        self._share_self_schema()

        for registration in self.procedures:
            for session in session_pool.sessions:
                session.register(
                    registration.uri,
                    registration.procedure,
                    channel=self.channel,
                )

            if registration.include_to_api:
                self._share_procedure_schema(
                    registration,
                )


new_service = service
