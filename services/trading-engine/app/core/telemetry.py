import os

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.prometheus import PrometheusMetricReader
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import start_http_server


def setup_opentelemetry():
    """
    Configures OpenTelemetry Tracing to OTel Collector,
    and Metrics to expose a Prometheus /metrics endpoint.
    """
    if os.getenv("TESTING") == "1":
        return

    resource = Resource(attributes={SERVICE_NAME: "trading-engine"})

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")

    # Trace setup (Push to Jaeger/Tempo via OTLP)
    trace_provider = TracerProvider(resource=resource)
    trace_exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
    trace_processor = BatchSpanProcessor(trace_exporter)
    trace_provider.add_span_processor(trace_processor)
    trace.set_tracer_provider(trace_provider)

    # Metrics setup (Pull via Prometheus HTTP Server)
    # Start the prometheus server on port 8000
    try:
        start_http_server(port=8000, addr="0.0.0.0")
    except Exception:
        # Ignore if already started (e.g. in tests)
        pass

    metric_reader = PrometheusMetricReader()
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
