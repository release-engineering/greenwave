# SPDX-License-Identifier: GPL-2.0+

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def init_tracing(app):
    endpoint = app.config.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    service_name = app.config.get("OTEL_EXPORTER_SERVICE_NAME")
    if not endpoint or not service_name:
        return
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))
    trace.set_tracer_provider(provider)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))

    FlaskInstrumentor().instrument_app(app, tracer_provider=provider)
