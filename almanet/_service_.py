import asyncio
import typing

from . import _almanet_
from . import _shared_

__all__ = [
    "service",
]


class service:

    class _kwargs(typing.TypedDict):
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
        topic = kwargs.get('label', procedure.__name__)

        if isinstance(self.pre, str):
            topic = f'{self.pre}.{topic}'

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
        self._post_join_callbacks.append(
            lambda: self._register_procedure(procedure, **kwargs)
        )

    def procedure(
        self,
        **kwargs: typing.Unpack[_register_procedure_kwargs],
    ):
        def decorate(function):
            self.add_procedure(function, **kwargs)
            return function
        return decorate

    async def _post_serve(self):
        await self.session.join()

        for callback in self._post_join_callbacks:
            coroutine = callback()
            self.session.task_pool.schedule(coroutine)

        await self._share_self_schema()

    def serve(self):
        loop = asyncio.new_event_loop()
        loop.create_task(
            self._post_serve()
        )
        loop.run_forever()
