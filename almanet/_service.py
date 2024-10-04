import asyncio
import signal
import typing

from . import _almanet
from . import _shared

__all__ = [
    "service_model",
    "new_service",
    "service_group_model",
    "new_service_group",
]


@_shared.dataclass
class abstract_procedure_model[I, O]:
    microservice: "service_model"
    procedure: typing.Callable[[I], typing.Awaitable[O]]
    path: str = ...
    channel: str | None = None
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
        if not isinstance(self.path, str):
            self.path = self.procedure.__name__
        if not isinstance(self.description, str):
            self.description = self.procedure.__doc__
        self.payload_model, self.return_model = _shared.extract_annotations(
            self.procedure, self.payload_model, self.return_model
        )

    @property
    def uri(self):
        return self.microservice._make_uri(self.path)

    def implements[F: typing.Callable[..., typing.Awaitable]](
        self,
        real_function: F,
    ) -> F:
        if self._has_implementation:
            raise ValueError("procedure already implemented")
        self._has_implementation = True

        self.microservice.register_procedure(
            real_function,
            path=self.path,
            channel=self.channel,
            include_to_api=self.include_to_api,
            description=self.description,
            tags=self.tags,
            validate=self.validate,
            payload_model=self.payload_model,
            return_model=self.return_model,
        )

        return real_function


class service_model:

    def __init__(
        self,
        prepath: str,
        tags: set[str] | None = None,
        session: _almanet.Almanet | None = None,
    ) -> None:
        self.pre: str = prepath
        self.tags: set[str] = set(tags or [])
        self._routes: set[str] = set()
        self.session: _almanet.Almanet = session or _almanet.new_session()
        self.session._post_join_event.add_observer(self._share_self_schema)

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
        sub: str,
    ) -> str:
        return f"{self.pre}.{sub}" if isinstance(self.pre, str) else sub

    class _register_procedure_kwargs(typing.TypedDict):
        path: typing.NotRequired[str]
        channel: typing.NotRequired[str | None]
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
    ) -> "_almanet.registration_model":
        if not callable(procedure):
            raise ValueError("decorated function must be callable")

        path = kwargs.pop("path", procedure.__name__)
        uri = self._make_uri(path)

        payload_model = kwargs.pop("payload_model", ...)
        return_model = kwargs.pop("return_model", ...)
        if kwargs.get("validate", True):
            procedure = _shared.validate_execution(procedure, payload_model, return_model)

        registration = self.session.register(
            uri,
            procedure,
            channel=kwargs.get("channel"),
        )
        kwargs["channel"] = registration.channel

        if kwargs.get("include_to_api", True):
            procedure_schema = _shared.describe_function(
                procedure,
                kwargs.pop("description", None),
                payload_model,
                return_model,
            )
            self._share_procedure_schema(
                uri,
                **kwargs,  # type: ignore
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
        return self.register_procedure(function, **kwargs)  # type: ignore

    type _abstract_function[I, O] = typing.Callable[[I], typing.Awaitable[O]]

    @typing.overload
    def abstract_procedure[I, O](
        self,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> typing.Callable[[_abstract_function[I, O]], abstract_procedure_model[I, O]]: ...

    @typing.overload
    def abstract_procedure[I, O](
        self,
        function: _abstract_function[I, O],
    ) -> abstract_procedure_model[I, O]: ...

    def abstract_procedure(
        self,
        function: _abstract_function | None = None,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> abstract_procedure_model | typing.Callable[[_abstract_function], abstract_procedure_model]:
        if function is None:
            return lambda function: abstract_procedure_model(self, function, **kwargs)
        return abstract_procedure_model(self, function, **kwargs)


new_service = service_model


class service_group_model:

    def __init__(
        self,
        *addresses: str,
    ) -> None:
        self.addresses: typing.Sequence[str] = addresses
        self.services: list[service_model] = []

    def include(
        self, 
        s: service_model,
    ) -> None:
        if not isinstance(s, service_model):
            raise ValueError("must be an instance of service")
        self.services.append(s)

    def serve(self) -> None:
        """
        Runs an event loop to serve the mounted services.
        """
        async def begin() -> None:
            async with asyncio.TaskGroup() as tg:
                for i in self.services:
                    i.session.addresses = self.addresses
                    c = i.session.join()
                    tg.create_task(c)

        async def end() -> None:
            async with asyncio.TaskGroup() as tg:
                for i in self.services:
                    c = i.session.leave()
                    tg.create_task(c)

            loop.stop()

        loop = asyncio.new_event_loop()

        loop.create_task(begin())

        for s in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(s, lambda: loop.create_task(end()))

        loop.run_forever()


new_service_group = service_group_model
