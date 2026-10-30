from app.core.config import settings


def route_model_for_task(task_type: str) -> str:
    """Selects appropriate local Ollama model based on task complexity."""
    if task_type in ["supervisor_routing", "creative_synthesis", "rubric_evaluation"]:
        return settings.OLLAMA_MODEL_SUPERVISOR  # llama3.3:70b
    return settings.OLLAMA_MODEL_WORKER          # qwen2.5:14b
