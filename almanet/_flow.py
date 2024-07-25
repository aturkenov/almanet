import asyncio
import logging
import re
import typing

from . import _microservice
from . import _shared

if typing.TYPE_CHECKING:
    from . import _almanet

__all__ = [
    "observable_state",
    "transition",
    "next_observer",
]


_logger = logging.getLogger(__name__)
_logger.setLevel(logging.INFO)


@_shared.dataclass(slots=True)
class transition:
    label: str
    sources: set["observable_state"]
    target: "observable_state"
    procedure: typing.Callable
    description: str | None = None
    priority: int = -1
    registration: typing.Optional["_almanet.registration_model"] = None
    _is_async = False

    @property
    def __name__(self) -> str:
        return self.label

    @property
    def __doc__(self) -> str | None:
        return self.description

    @property
    def is_observer(self) -> bool:
        return self.priority > -1

    @property
    def uri(self) -> str | None:
        if self.registration is None:
            raise AttributeError("`observer` has no attribute `uri`")
        return self.registration.uri

    def __call__(
        self,
        *args,
        context: typing.MutableMapping | None = None,
        **kwargs,
    ):
        if context is None:
            context = {}
        result = self.procedure(*args, **kwargs, context=context, transition=self)
        self.target.notify(context)
        return result


@_shared.dataclass(slots=True)
class async_transition(transition):
    _is_async = True

    async def __call__(
        self,
        *args,
        context: typing.MutableMapping | None = None,
        **kwargs,
    ):
        if context is None:
            context = {}
        result = await self.procedure(*args, **kwargs, context=context, transition=self)
        self.target.notify(context)
        return result


_state_label_re = re.compile("[A-Za-z_]+")


@_shared.dataclass(slots=True)
class _state:
    service: _microservice.microservice
    label: str
    description: str | None = None
    _transitions: typing.List[transition] = ...

    def __post_init__(self):
        if not (isinstance(self.label, str) and len(self.label) > 0 and _state_label_re.match(self.label)):
            raise ValueError("`label` must contain uppercase words separated by underscore")
        self._transitions = []

    def _add_transition(
        self,
        sources: typing.Iterable["observable_state"],
        procedure: typing.Callable,
        label: str | None = None,
        description: str | None = None,
        **extra,
    ):
        if not callable(procedure):
            raise ValueError("decorated function must be callable")

        transition_class = async_transition if asyncio.iscoroutinefunction(procedure) else transition

        if label is None:
            label = procedure.__name__

        if description is None:
            description = procedure.__doc__

        if not all(isinstance(i, observable_state) for i in sources):
            raise ValueError(f"{label}: `target` must be `observable_state` instance")

        instance = transition_class(
            label=label,
            description=description,
            sources=set(sources),
            target=self,  # type: ignore
            procedure=procedure,
            **extra,
        )

        if not instance.is_observer:
            payload_model, return_model = _shared.extract_annotations(procedure)
            instance.registration = self.service.register_procedure(
                instance.__call__,
                label=label,
                description=description,
                payload_model=payload_model,
                return_model=return_model,
            )

        for i in sources:
            i._transitions.append(instance)
            i._transitions = sorted(i._transitions, key=lambda o: -o.priority)

        return instance

    def transition_from(
        self,
        *sources: "observable_state",
        **extra,
    ):
        def wrap(function):
            return self._add_transition(sources, procedure=function, **extra)

        return wrap


class priorities:
    unset = -1
    lowest = 0
    low = 25
    medium = 50
    high = 75
    highest = 100


class flow_execution_error(Exception): ...


@_shared.dataclass(slots=True)
class observable_state(_state):
    @property
    def observers(self) -> list[transition]:
        return [i for i in self._transitions if i.is_observer]

    async def next(
        self,
        context,
    ) -> typing.Any:
        _logger.debug(f"{self.label} begin")

        for observer in self.observers:
            _logger.debug(f"trying to call {observer.label} observer")
            try:
                if observer._is_async:
                    result = await observer(context=context)
                else:
                    result = await asyncio.to_thread(observer, context=context)
                _logger.debug(f"{observer.label} observer end")
                return result
            except Exception as e:
                _logger.error(f"during execution of {observer.label}: {repr(e)}")

        if len(self.observers) > 0:
            raise flow_execution_error(self.label)

    def __post_init__(self):
        super(observable_state, self).__post_init__()
        # TODO: better to consume
        self.service.register_procedure(
            self.next,
            label=self.label,
            include_to_api=False,
            validate=False,
        )

    def notify(
        self,
        context,
    ):
        self.service.session.call(self.service._make_uri(self.label), context)

    def _add_observer(
        self,
        priority: int = priorities.medium,
        **kwargs,
    ):
        if not (isinstance(priority, int) and priority > -1):
            raise ValueError("`priority` must be `integer` and greater than -1")

        existing_priorities = {i.priority for i in self.observers}
        if priority in existing_priorities:
            raise ValueError(f"invalid observer `{self.label}` (priority {priority} already exists)")

        return self._add_transition(**kwargs, priority=priority)

    def observe(
        self,
        *sources: "observable_state",
        **extra,
    ):
        def wrap(function):
            return self._add_observer(sources=sources, procedure=function, **extra)

        return wrap

    def __hash__(self) -> int:
        return hash(self.label)


class next_observer(Exception):
    def __init__(self, reason: str, *args):
        if not isinstance(reason, str):
            raise ValueError("`reason` must be `string`")
        self.reason = reason
        self.args = args
