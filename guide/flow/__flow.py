import almanet

from . import flow as public

__all__ = ["state_any", "public"]

state_any = almanet.observable_state(public.service, "ANY")
