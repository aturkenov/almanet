import opentelemetry.trace as _tracing

__all__ = [
    "new_span",
    "use_span",
]

tracer = _tracing.get_tracer("almanet")

new_span = tracer.start_as_current_span

use_span = _tracing.use_span
