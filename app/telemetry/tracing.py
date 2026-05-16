from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.trace import Span

from app.config import Settings

_configured = False


def configure_tracing(settings: Settings) -> None:
    global _configured
    if _configured or not settings.tracing_enabled:
        return

    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": settings.app_name,
                "service.version": settings.app_version,
                "deployment.environment": settings.environment,
            }
        )
    )
    if settings.tracing_console_exporter:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _configured = True


def instrument_fastapi(app: FastAPI, settings: Settings) -> None:
    if not settings.tracing_enabled:
        return
    FastAPIInstrumentor.instrument_app(app)


def get_tracer() -> trace.Tracer:
    return trace.get_tracer("agentops-rag")


@contextmanager
def traced_span(name: str, **attributes: Any) -> Iterator[Span]:
    with get_tracer().start_as_current_span(name) as span:
        set_span_attributes(span, attributes)
        yield span


def set_span_attributes(span: Span, attributes: dict[str, Any]) -> None:
    for key, value in attributes.items():
        if value is None:
            continue
        span.set_attribute(key, value)


def current_trace_id() -> str | None:
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return None
    return f"{span_context.trace_id:032x}"
