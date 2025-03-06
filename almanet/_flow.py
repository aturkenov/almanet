import logging
import re
import typing

from . import _shared

if typing.TYPE_CHECKING:
    from . import _session
    from . import _service

__all__ = [
    "transition",
    "observable_state",
    "new_observable_state",
    "next_observer",
]


_logger = logging.getLogger(__name__)
_logger.setLevel(logging.INFO)


@_shared.dataclass
class transition:
    label: str
    sources: set["observable_state"]
    target: "observable_state"
    procedure: typing.Callable
    description: str | None = None
    priority: int = -1
    is_observer: bool = False

    def __post_init__(self):
        self.__name__ = self.label
        self.__doc__ = self.description
        self.is_observer = self.priority > -1

    async def __call__(
        self,
        payload: typing.Any = None,
        *,
        session: "_session.Almanet",
    ):
        result = await self.procedure(payload, session=session, transition=self)
        session.call(self.target._next_procedure.uri, result)
        return result


_state_label_re = re.compile("[A-Za-z0-9_]+")


@_shared.dataclass(slots=True)
class _state:
    service: "_service.remote_service"
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

        if label is None:
            label = procedure.__name__

        if description is None:
            description = procedure.__doc__

        if not all(isinstance(i, observable_state) for i in sources):
            raise ValueError(f"{label}: `target` must be `observable_state` instance")

        instance = transition(
            label=label,
            description=description,
            sources=set(sources),
            target=self,  # type: ignore
            procedure=procedure,
            **extra,
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
    _next_procedure: "_service.remote_procedure_model" = ...

    @property
    def observers(self) -> list[transition]:
        return [i for i in self._transitions if i.is_observer]

    async def next(
        self,
        payload: typing.Any = None,
        *,
        session: "_session.Almanet",
    ) -> typing.Any:
        _logger.debug(f"{self.label} begin")

        for observer in self.observers:
            _logger.debug(f"trying to call {observer.label} observer")
            try:
                result = await observer(payload=payload, session=session)
                _logger.debug(f"{observer.label} observer end")
                return result
            except Exception as e:
                _logger.error(f"during execution of {observer.label}: {repr(e)}")

        if len(self.observers) > 0:
            raise flow_execution_error(self.label)

    def __post_init__(self):
        super(observable_state, self).__post_init__()
        self._next_procedure = self.service.add_procedure(
            self.next,
            name=self.label,
            include_to_api=False,
            validate=False,
        )

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
            return self._add_observer(
                sources=sources,
                procedure=function,
                **extra,
            )

        return wrap

    def __hash__(self) -> int:
        return hash(self.label)


new_observable_state = observable_state


class next_observer(Exception):
    def __init__(self, reason: str, *args):
        if not isinstance(reason, str):
            raise ValueError("`reason` must be `string`")
        self.reason = reason
        self.args = args
