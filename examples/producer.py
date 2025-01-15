import asyncio

import almanet
import pydantic

import opentelemetry.trace as _tracing
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter


resource = Resource(attributes={
    SERVICE_NAME: "almanet.producer"
})

traceProvider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(
    OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")
)
traceProvider.add_span_processor(processor)
_tracing.set_tracer_provider(traceProvider)


class newcomer(pydantic.BaseModel):
    id: str


async def main():
    # create new session
    session = almanet.new_session("localhost:4150")

    # join to your nsq network.
    async with session:
        print(f"joined session.id={session.id}")

        # publishing message to `net.example.newcomers` topic with 'hello, world' argument.
        await session.produce("net.example.newcomers", newcomer(id="test"))


asyncio.run(main())
