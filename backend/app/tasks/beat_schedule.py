from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "ingest-social-metrics-every-6-hours": {
        "task": "app.tasks.analytics_tasks.ingest_cross_platform_metrics",
        "schedule": crontab(minute=0, hour="*/6"),
        "options": {"queue": "analytics_queue"},
    },
    "midnight-brand-compliance-audit": {
        "task": "app.tasks.orchestrator_tasks.audit_brand_compliance",
        "schedule": crontab(minute=0, hour=0),
        "options": {"queue": "orchestrator_queue"},
    },
    "poll-due-schedules-every-5-minutes": {
        "task": "app.tasks.publishing_tasks.poll_due_schedules_and_dispatch",
        "schedule": crontab(minute="*/5"),
        "options": {"queue": "publishing_queue"},
    },
    "weekly-analytics-backup-sunday": {
        "task": "app.tasks.analytics_tasks.export_weekly_analytics_backup",
        "schedule": crontab(minute=0, hour=2, day_of_week=0),  # Sunday at 02:00 UTC
        "options": {"queue": "analytics_queue"},
    },
}
