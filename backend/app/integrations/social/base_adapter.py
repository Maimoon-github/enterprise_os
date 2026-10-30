from abc import ABC, abstractmethod

class BaseSocialAdapter(ABC):
    @abstractmethod
    async def publish(self, payload: dict, credentials: dict) -> dict:
        pass

    @abstractmethod
    async def fetch_metrics(self, post_id: str, credentials: dict) -> dict:
        pass
