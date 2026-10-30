from app.core.config import settings
from celery import Celery

celery_app = Celery(
    "marketing_os_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_routes={
        "app.tasks.orchestrator_tasks.*": {"queue": "orchestrator_queue"},
        "app.tasks.publishing_tasks.*": {"queue": "publishing_queue"},
        "app.tasks.media_tasks.*": {"queue": "media_queue"},
        "app.tasks.analytics_tasks.*": {"queue": "analytics_queue"},
    },
)
