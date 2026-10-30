class MCPTasksExtension:
    """Manages asynchronous durable task handles for media generation jobs."""
    @staticmethod
    def create_task_handle(task_id: str, job_type: str) -> dict:
        return {"task_id": task_id, "job_type": job_type, "status": "processing"}
