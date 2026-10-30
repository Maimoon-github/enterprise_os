from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.media_tasks.process_video_transcode")
def process_video_transcode(input_key: str, output_key: str, target_ratio: str):
    return {"status": "transcoded", "output_key": output_key}
