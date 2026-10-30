from app.tasks.celery_app import celery_app

@celery_app.task(name="app.tasks.publishing_tasks.dispatch_platform_post", bind=True, max_retries=1)
def dispatch_platform_post(self, platform: str, payload: dict, idempotency_key: str):
    return {"platform": platform, "status": "dispatched", "idempotency_key": idempotency_key}
