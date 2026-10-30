
from pydantic import BaseModel


class AgentWorkerFactory:
    """Factory creating ephemeral workers with Pydantic BaseModel output validation."""

    @staticmethod
    def create_worker(name: str, model_tag: str, output_type: type[BaseModel]):
        return {
            "worker_name": name,
            "model": model_tag,
            "output_contract": output_type.__name__,
        }
