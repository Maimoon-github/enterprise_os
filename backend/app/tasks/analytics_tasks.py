from app.tasks.celery_app import celery_app

@celery_app.task(name="app.tasks.analytics_tasks.ingest_cross_platform_metrics")
def ingest_cross_platform_metrics():
    return {"status": "ingested", "records": 48}
