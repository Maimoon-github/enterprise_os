# Observability Infrastructure

## Architecture & Configuration

OpenTelemetry collector pipelines and Langfuse configuration for Agentic Brand Marketing OS.

### Canonical Collector Configuration
The canonical OpenTelemetry Collector configuration is located at:
- `observability/otel-collector/config.yaml`

A synchronized mirror is maintained at:
- `infra/observability/otel-collector/config.yaml`

### Pipelines
- **Receivers**: OTLP receiver accepting gRPC (`0.0.0.0:4317`) and HTTP (`0.0.0.0:4318`) traces.
- **Processors**: Batch processor (`timeout: 1s`, `send_batch_size: 256`).
- **Exporters**: 
  - `otlphttp/langfuse`: Dispatches trace spans directly to the Langfuse OTLP ingest endpoint (`http://langfuse:3000/api/public/otel`).
  - `debug`: Detailed logging for local debugging.
