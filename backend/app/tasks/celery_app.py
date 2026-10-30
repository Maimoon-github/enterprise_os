import logging
from typing import Any

from app.core.config import settings
from app.tasks.beat_schedule import CELERY_BEAT_SCHEDULE
from celery import Celery
from celery.signals import before_task_publish, task_prerun
from kombu import Exchange, Queue
from opentelemetry import context
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

logger = logging.getLogger("tasks.celery_app")

# Initialize Celery app with Redis broker and result backend
celery_app = Celery(
    "marketing_os_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.orchestrator_tasks",
        "app.tasks.publishing_tasks",
        "app.tasks.media_tasks",
        "app.tasks.analytics_tasks",
    ],
)

# Kombu Exchange & Partitioned Queues
marketing_os_exchange = Exchange("marketing_os", type="direct")

task_queues = [
    Queue("orchestrator_queue", marketing_os_exchange, routing_key="orchestrator"),
    Queue("publishing_queue", marketing_os_exchange, routing_key="publishing"),
    Queue("media_queue", marketing_os_exchange, routing_key="media"),
    Queue("analytics_queue", marketing_os_exchange, routing_key="analytics"),
]

# Task routing map
task_routes = {
    "app.tasks.orchestrator_tasks.*": {
        "queue": "orchestrator_queue",
        "routing_key": "orchestrator",
    },
    "app.tasks.publishing_tasks.*": {
        "queue": "publishing_queue",
        "routing_key": "publishing",
    },
    "app.tasks.media_tasks.*": {
        "queue": "media_queue",
        "routing_key": "media",
    },
    "app.tasks.analytics_tasks.*": {
        "queue": "analytics_queue",
        "routing_key": "analytics",
    },
}

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_queues=task_queues,
    task_routes=task_routes,
    task_default_queue="orchestrator_queue",
    task_default_exchange="marketing_os",
    task_default_routing_key="orchestrator",
    beat_schedule=CELERY_BEAT_SCHEDULE,
)


@before_task_publish.connect
def inject_traceparent_header(sender: str | None = None, headers: dict[str, Any] | None = None, **kwargs: Any) -> None:
    """Inject W3C traceparent headers into outbound Celery message envelope for distributed tracing."""
    if headers is not None:
        TraceContextTextMapPropagator().inject(headers)


@task_prerun.connect
def extract_traceparent_header(
    sender: Any = None,
    task_id: str | None = None,
    task: Any = None,
    args: tuple | None = None,
    kwargs: dict[str, Any] | None = None,
    **extra: Any,
) -> None:
    """Extract W3C traceparent headers from incoming Celery task request headers."""
    if task and hasattr(task, "request") and getattr(task.request, "headers", None):
        carrier = task.request.headers
        extracted_context = TraceContextTextMapPropagator().extract(carrier)
        token = context.attach(extracted_context)
        # Store token for cleanup if needed
        task.__trace_context_token = token
