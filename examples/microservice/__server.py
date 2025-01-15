import almanet

from . import _greeting

import opentelemetry.trace as _tracing
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter


resource = Resource(attributes={
    SERVICE_NAME: "almanet.server"
})

traceProvider = TracerProvider(resource=resource)
processor = BatchSpanProcessor(
    OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces")
)
traceProvider.add_span_processor(processor)
_tracing.set_tracer_provider(traceProvider)


microservice = almanet.new_service_group("localhost:4150")
microservice.include(_greeting.public.example_service)
microservice.serve()
