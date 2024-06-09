import asyncio
import logging
import re
import typing

from . import _service_
from . import _shared_

if typing.TYPE_CHECKING:
    from . import _almanet_

__all__ = [
    "observable_state",
    "transition",
    "next_observer",
]


_logger = logging.getLogger(__name__)


@_shared_.dataclass(slots=True)
class transition:
    label: str
    source: "observable_state"
    target: "observable_state"
    procedure: typing.Callable
    description: str | None = None
    priority: int = -1
    is_async: bool = False

    def __post_init__(self):
        if asyncio.iscoroutinefunction(self.procedure):
            self.is_async = True

    def __call__(
        self,
        session: "_almanet_.Almanet",
        *args,
        **kwargs,
    ):
        if self.is_async:
            coroutine = self.procedure(*args, **kwargs, transition=self)
            task = asyncio.create_task(coroutine)
            task.add_done_callback(
                lambda task: self.target.notify(session, task.result())
            )
            return task

        result = self.procedure(*args, **kwargs, transition=self)
        self.target.notify(session, result)
        return result

    def __str__(self) -> str:
        return f"{self.label}: {self.source.label} > {self.target.label}"

    def __hash__(self) -> int:
        return hash(self.__str__())


_state_label_re = re.compile("[A-Za-z_]+")


@_shared_.dataclass(slots=True)
class _state:

    entity: str
    label: str
    service: _service_.service
    description: str | None = None
    transitions: typing.List[transition] = ...

    def __post_init__(self):
        if not (isinstance(self.label, str) and len(self.label) > 0 and _state_label_re.match(self.label)):
            raise ValueError("`label` must contain uppercase words separated by underscore")
        self.transitions = []

    def _add_transition(
        self,
        label: str | None,
        description: str | None,
        target: "observable_state",
        procedure: typing.Callable,
        **extra,
    ) -> transition:
        if not callable(procedure):
            raise ValueError("decorated function must be callable")

        if label is None:
            label = f"{procedure.__module__}.{procedure.__name__}"

        if description is None:
            description = procedure.__doc__

        if not isinstance(target, observable_state):
            raise ValueError(f"{label}: `target` must be `observable_state` instance")

        instance = transition(
            label=label,
            description=description,
            source=self, # type: ignore
            target=target,
            procedure=procedure,
            **extra,
        )
        self.transitions.append(instance)
        return instance

    def transition(
        self,
        target: "observable_state",
        label: str | None = None,
        description: str | None = None,
        **extra,
    ):
        def wrap(function):
            return self._add_transition(
                label=label,
                description=description,
                target=target,
                procedure=function,
                **extra,
            )
        return wrap


LOWEST_PRIORITY = 100
LOW_PRIORITY = 75
MEDIUM_PRIORITY = 50
HIGH_PRIORITY = 25
HIGHEST_PRIORITY = 0

DEFAULT_PRIORITY = MEDIUM_PRIORITY


@_shared_.dataclass(slots=True)
class observable_state(_state):

    _observers: typing.List[transition] = ...

    @property
    def route(self) -> str:
        return f'{self.entity}.{self.label}.next'

    @property
    def full_route(self) -> str:
        if isinstance(self.service.pre, str):
            return f'{self.service.pre}.{self.route}'
        return self.route

    async def next(
        self,
        payload: typing.Any,
        session: "_almanet_.Almanet",
        **kwargs,
    ) -> typing.Any:
        _logger.debug(f"{self.label} begin")

        if payload is None:
            payload = []
        if isinstance(payload, typing.Iterable):
            payload = [payload]

        for observer in self._observers:
            _logger.debug(f"trying to call {observer.label} observer")
            try:
                if observer.is_async:
                    result = await observer(session, *payload, **kwargs)
                else:
                    result = await asyncio.to_thread(observer, session, *payload, **kwargs)
                _logger.debug(f"{observer.label} observer end")
                return result
            except Exception as e:
                _logger.error(f"during execution of {observer.label}: {repr(e)}")

    def __post_init__(self):
        super(observable_state, self).__post_init__()
        self._observers = []
        self.service.add_procedure(self.next, label=self.route, include_to_api=False, validate=False)

    def notify(
        self,
        session: "_almanet_.Almanet",
        previous_result: typing.Any,
    ):
        return session.call(
            self.full_route,
            previous_result,
        )

    def _add_observer(
        self,
        priority: int,
        **kwargs,
    ) -> transition:
        if not (isinstance(priority, int) and priority > -1):
            raise ValueError("`priority` must be `integer` and greater than -1")

        instance = self._add_transition(**kwargs, priority=priority)

        existing_priorities = {i.priority for i in self._observers}
        if priority in existing_priorities:
            raise ValueError(f"invalid observer `{instance.label}`: priority {priority} already exists")

        self._observers.append(instance)
        self._observers = sorted(self._observers, key=lambda x: -x.priority)

        return instance

    def observer(
        self,
        target: "observable_state",
        label: str | None = None,
        description: str | None = None,
        priority: int = DEFAULT_PRIORITY,
        **extra,
    ):
        def wrap(function):
            return self._add_observer(
                label=label,
                description=description,
                target=target,
                procedure=function,
                priority=priority,
                **extra,
            )
        return wrap


class next_observer(Exception):

    def __init__(self, reason: str, *args):
        if not isinstance(reason, str):
            raise ValueError("`reason` must be `string`")
        self.reason = reason
        self.args = args
