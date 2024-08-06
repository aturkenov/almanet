import asyncio
import typing

from . import _almanet
from . import _shared

__all__ = [
    "microservice",
]


@_shared.dataclass
class abstract_procedure_model:
    microservice: "microservice"
    procedure: typing.Callable
    label: str = ...
    include_to_api: bool = True
    description: str | None = None
    tags: set[str] | None = None
    validate: bool = True
    payload_model: typing.Any = ...
    return_model: typing.Any = ...
    _has_implementation: bool = False

    def __post_init__(self):
        if not callable(self.procedure):
            raise ValueError("decorated function must be callable")
        if not isinstance(self.label, str):
            self.label = self.procedure.__name__
        if not isinstance(self.description, str):
            self.description = self.procedure.__doc__
        self.payload_model, self.return_model = _shared.extract_annotations(
            self.procedure, self.payload_model, self.return_model
        )

    @property
    def uri(self):
        return self.microservice._make_uri(self.label)

    def implements[F: typing.Callable](
        self,
        real_function: F,
    ) -> F:
        if self._has_implementation:
            raise ValueError("procedure already implemented")
        self._has_implementation = True

        return self.microservice.register_procedure(
            real_function,
            label=self.label,
            include_to_api=self.include_to_api,
            description=self.description,
            tags=self.tags,
            validate=self.validate,
            payload_model=self.payload_model,
            return_model=self.return_model,
        )  # type: ignore


class microservice:
    """
    Represents a microservice that can be used to register procedures (functions) with a session.
    """

    class _kwargs(typing.TypedDict):
        """
        - prepath: is used to prepend a path to the procedure's topic.
        - tags: are used to categorize the procedures.
        """

        prepath: typing.NotRequired[str]
        tags: typing.NotRequired[typing.Set[str]]

    def __init__(
        self,
        session: _almanet.Almanet,
        **kwargs: typing.Unpack[_kwargs],
    ):
        self._routes = set()
        self.pre = kwargs.get("prepath")
        self.tags = set(kwargs.get("tags") or [])
        self.session = session

    def _share_self_schema(
        self,
        **extra,
    ) -> None:
        async def procedure(*args, **kwargs):
            return {
                "client": self.session.id,
                "version": self.session.version,
                "routes": list(self._routes),
                **extra,
            }

        self.session.register(
            "_api_schema_.client",
            procedure,
            channel=self.session.id,
        )

    def _share_procedure_schema(
        self,
        uri: str,
        channel: str,
        tags: set[str] | None = None,
        **extra,
    ) -> None:
        if tags is None:
            tags = set()
        tags |= self.tags
        if len(tags) == 0:
            tags = {"Default"}

        async def procedure(*args, **kwargs):
            return {
                "client": self.session.id,
                "version": self.session.version,
                "uri": uri,
                "channel": channel,
                "tags": tags,
                **extra,
            }

        self.session.register(
            f"_api_schema_.{uri}.{channel}",
            procedure,
            channel=channel,
        )

        self._routes.add(f"{uri}/{channel}")

    def _make_uri(
        self,
        subtopic: str,
    ) -> str:
        return f"{self.pre}.{subtopic}" if isinstance(self.pre, str) else subtopic

    class _register_procedure_kwargs(typing.TypedDict):
        label: typing.NotRequired[str]
        include_to_api: typing.NotRequired[bool]
        description: typing.NotRequired[str | None]
        tags: typing.NotRequired[set[str] | None]
        validate: typing.NotRequired[bool]
        payload_model: typing.NotRequired[typing.Any]
        return_model: typing.NotRequired[typing.Any]

    def register_procedure(
        self,
        procedure: typing.Callable,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> _almanet.registration_model:
        if not callable(procedure):
            raise ValueError("decorated function must be callable")

        label = kwargs.pop("label", procedure.__name__)
        uri = self._make_uri(label)

        payload_model = kwargs.pop("payload_model", ...)
        return_model = kwargs.pop("return_model", ...)
        if kwargs.get("validate", True):
            procedure = _shared.validate_execution(procedure, payload_model, return_model)

        registration = self.session.register(uri, procedure)

        if kwargs.get("include_to_api", True):
            procedure_schema = _shared.describe_function(
                procedure,
                kwargs.pop("description"),
                payload_model,
                return_model,
            )
            self._share_procedure_schema(
                uri,
                registration.channel,
                **kwargs,
                **procedure_schema,
            )

        return registration

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
            return lambda function: self.register_procedure(function, **kwargs)  # type: ignore
        return self.register_procedure(function, **kwargs)

    @typing.overload
    def abstract_procedure(
        self,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> typing.Callable[[typing.Callable], abstract_procedure_model]: ...

    @typing.overload
    def abstract_procedure(
        self,
        function: typing.Callable,
    ) -> abstract_procedure_model: ...

    def abstract_procedure(
        self,
        function: typing.Callable | None = None,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> abstract_procedure_model | typing.Callable[..., abstract_procedure_model]:
        if function is None:
            return lambda function: abstract_procedure_model(self, function, **kwargs)
        return abstract_procedure_model(self, function, **kwargs)

    def serve(self) -> None:
        """
        Runs an event loop to serve the microservice.
        """
        self.session._post_join_event.add_observer(self._share_self_schema)

        loop = asyncio.new_event_loop()
        loop.create_task(self.session.join())
        loop.run_forever()
