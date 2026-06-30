import logging

import structlog
from opentelemetry import trace


def extract_otel_trace_id(logger, log_method, event_dict):
    """
    Extracts trace_id and span_id from OpenTelemetry context
    and injects them into the structlog event dictionary.
    """
    span = trace.get_current_span()
    if span and span.is_recording():
        ctx = span.get_span_context()
        event_dict["trace_id"] = trace.format_trace_id(ctx.trace_id)
        event_dict["span_id"] = trace.format_span_id(ctx.span_id)
    return event_dict


def setup_logging(log_level: str = "INFO"):
    """
    Configures structlog to output JSON.
    Automatically merges contextvars and OpenTelemetry Trace IDs.
    """
    # Clear existing handlers
    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.handlers.clear()

    logging.basicConfig(level=log_level, format="%(message)s")

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            extract_otel_trace_id,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
