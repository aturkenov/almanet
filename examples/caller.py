import asyncio

import almanet
import examples.microservice.greeting

import opentelemetry.trace as _tracing
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter


resource = Resource(attributes={
    SERVICE_NAME: "almanet.caller"
})

traceProvider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(
    OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")
)
traceProvider.add_span_processor(processor)
_tracing.set_tracer_provider(traceProvider)

tracer = _tracing.get_tracer("caller")


async def main():
    # join to your network.
    async with almanet.new_session("localhost:4150") as session:
        with tracer.start_as_current_span("caller") as span:
            payload = "Aidar"
            # catching rpc exceptions with `try` and `except almanet.rpc_error` statement
            try:
                # calling the procedure by URI (Uniform Resource Identifier)
                result = await session.call(examples.microservice.greeting.greeting, payload)
                print(result)
                span.add_event("result", attributes={"result": result})
            except almanet.rpc_error as e:
                print(f"during call net.example.greeting({payload}): {e}")
                raise e


asyncio.run(main())
