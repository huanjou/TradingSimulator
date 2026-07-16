from app.core.logging import extract_otel_trace_id
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider


def test_extract_otel_trace_id_without_span():
    """
    Test that the function returns the original event_dict if no span is active.
    """
    event_dict = {"event": "test"}
    result = extract_otel_trace_id(None, None, event_dict)

    assert "trace_id" not in result
    assert "span_id" not in result
    assert result["event"] == "test"


def test_extract_otel_trace_id_with_span():
    """
    Test that the function injects trace_id and span_id when a span is active.
    """
    provider = TracerProvider()
    tracer = provider.get_tracer(__name__)

    event_dict = {"event": "test"}

    with tracer.start_as_current_span("test_span") as span:
        result = extract_otel_trace_id(None, None, event_dict)

        ctx = span.get_span_context()
        assert "trace_id" in result
        assert "span_id" in result

        assert result["trace_id"] == trace.format_trace_id(ctx.trace_id)
        assert result["span_id"] == trace.format_span_id(ctx.span_id)
