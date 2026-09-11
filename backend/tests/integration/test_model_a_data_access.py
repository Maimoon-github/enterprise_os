"""Verifies workers cannot directly access RAG or persistence."""
import inspect

from app.agents import development, learning_performance, strategy

FORBIDDEN = ("app.services.rag", "app.persistence")


def test_workers_do_not_access_rag_or_persistence() -> None:
    for module in (development, strategy, learning_performance):
        source = inspect.getsource(module)
        for token in FORBIDDEN:
            assert token not in source
