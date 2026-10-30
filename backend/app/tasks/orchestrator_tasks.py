from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.orchestrator_tasks.resume_graph_run")
def resume_graph_run(thread_id: str, payload: dict):
    # Asynchronously resumes an interrupted LangGraph execution thread
    return {"status": "dispatched", "thread_id": thread_id}
