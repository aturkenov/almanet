import asyncio
import typing

from . import _almanet
from . import _shared

__all__ = [
    "microservice",
]


class microservice:
    """
    Represents a microservice that can be used to register procedures (functions) with a session.
    """

    class _kwargs(typing.TypedDict):
        """
        - prefix: is used to prepend a label to the procedure's topic.
        - tags: are used to categorize the procedures.
        """
        prefix: typing.NotRequired[str]
        tags: typing.NotRequired[typing.Set[str]]

    def __init__(
        self,
        session: _almanet.Almanet,
        **kwargs: typing.Unpack[_kwargs],
    ):
        self._routes = set()
        self.pre = kwargs.get('prefix')
        self.tags = set(kwargs.get('tags') or [])
        self.session = session

    def _share_self_schema(
        self,
        **extra,
    ):
        async def procedure(*args, **kwargs):
            return {
                'client': self.session.id,
                'version': self.session.version,
                'routes': list(self._routes),
                **extra,
            }

        self.session.register(
            '_api_schema_.client',
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
            tags = {'Default'}

        async def procedure(*args, **kwargs):
            return {
                'client': self.session.id,
                'version': self.session.version,
                'uri': uri,
                'channel': channel,
                'tags': tags,
                **extra,
            }

        self.session.register(
            f'_api_schema_.{uri}.{channel}',
            procedure,
            channel=channel,
        )

        self._routes.add(f'{uri}/{channel}')

    def _make_uri(
        self,
        subtopic: str,
    ) -> str:
        return f'{self.pre}.{subtopic}' if isinstance(self.pre, str) else subtopic

    class _register_procedure_kwargs(typing.TypedDict):
        label: typing.NotRequired[str]
        channel: typing.NotRequired[str]
        validate: typing.NotRequired[bool]
        include_to_api: typing.NotRequired[bool]
        title: typing.NotRequired[str]
        description: typing.NotRequired[str]
        tags: typing.NotRequired[set[str]]
        payload_model: typing.NotRequired[typing.Any]
        return_model: typing.NotRequired[typing.Any]

    def register_procedure(
        self,
        procedure: typing.Callable,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ):
        label = kwargs.get('label', procedure.__name__)
        uri = self._make_uri(label)

        if kwargs.get('validate', True):
            procedure = _shared.validate_execution(procedure)

        registration = self.session.register(uri, procedure, channel=kwargs.get('channel'))

        if kwargs.get('include_to_api', True):
            procedure_schema = _shared.describe_function(
                procedure,
                kwargs.get('description'),
                kwargs.get('payload_model', ...),
                kwargs.get('return_model', ...),
            )
            self._share_procedure_schema(
                uri,
                registration.channel,
                title=kwargs.get('title'),
                tags=kwargs.get('tags'),
                **procedure_schema,
            )

        return registration

    def procedure(
        self,
        function: typing.Callable | None = None,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ):
        """
        Allows you to easily add procedures (functions) to a microservice by using a decorator.
        Returns a decorated function.
        """
        if function is None:
            return lambda function: self.register_procedure(function, **kwargs)
        return self.register_procedure(function, **kwargs)

    def serve(self):
        """
        Runs an event loop to serve the microservice.
        """
        self.session._post_join_event.add_observer(
            self._share_self_schema
        )

        loop = asyncio.new_event_loop()
        loop.create_task(
            self.session.join()
        )
        loop.run_forever()
