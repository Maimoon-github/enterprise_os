from celery.schedules import crontab
from app.tasks.celery_app import celery_app

celery_app.conf.beat_schedule = {
    "ingest-social-metrics-every-6-hours": {
        "task": "app.tasks.analytics_tasks.ingest_cross_platform_metrics",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "midnight-brand-compliance-audit": {
        "task": "app.tasks.orchestrator_tasks.audit_brand_compliance",
        "schedule": crontab(minute=0, hour=0),
    },
}
