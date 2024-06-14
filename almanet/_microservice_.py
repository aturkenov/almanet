import asyncio
import typing

from . import _almanet_
from . import _shared_

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
        session: _almanet_.Almanet,
        **kwargs: typing.Unpack[_kwargs],
    ):
        self._post_join_callbacks = []
        self._routes = set()
        self.pre = kwargs.get('prefix')
        self.tags = set(kwargs.get('tags') or [])
        self.session = session

    async def _share_self_schema(
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

        await self.session.register(
            '_api_schema_.client',
            procedure,
            channel=self.session.id,
        )

    async def _share_procedure_schema(
        self,
        topic: str,
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
                'topic': topic,
                'channel': channel,
                'tags': tags,
                **extra,
            }

        await self.session.register(
            f'_api_schema_.{topic}.{channel}',
            procedure,
            channel=channel,
        )

        self._routes.add(f'{topic}/{channel}')

    def _make_topic(
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

    async def _register_procedure(
        self,
        procedure: typing.Callable,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ):
        label = kwargs.get('label', procedure.__name__)
        topic = self._make_topic(label)

        if kwargs.get('validate', True):
            procedure = _shared_.validate_execution(procedure)

        registration = await self.session.register(topic, procedure, channel=kwargs.get('channel'))

        if kwargs.get('include_to_api', True):
            procedure_schema = _shared_.describe_function(
                procedure,
                kwargs.get('description'),
                kwargs.get('payload_model', ...),
                kwargs.get('return_model', ...),
            )
            await self._share_procedure_schema(
                topic,
                registration.channel,
                title=kwargs.get('title'),
                tags=kwargs.get('tags'),
                **procedure_schema,
            )

    def add_procedure(
        self,
        procedure: typing.Callable,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ) -> None:
        """
        Allows you to add a procedure to be registered with the session.
        The procedure is scheduled to be registered after the session has joined.
        """
        self._post_join_callbacks.append(
            lambda: self._register_procedure(procedure, **kwargs)
        )

    def procedure(
        self,
        function: typing.Callable | None = None,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ):
        """
        Allows you to easily add procedures (functions) to a microservice by using a decorator.
        Returns a decorated function.
        """
        def decorate(function):
            self.add_procedure(function, **kwargs)
            return function

        if function is None:
            return decorate
        return decorate(function)

    async def _post_serve(self):
        await self.session.join()

        for callback in self._post_join_callbacks:
            coroutine = callback()
            self.session.task_pool.schedule(coroutine)

        await self._share_self_schema()

    def serve(self):
        """
        Runs an event loop to serve the microservice.
        """
        loop = asyncio.new_event_loop()
        loop.create_task(
            self._post_serve()
        )
        loop.run_forever()
