# pyright: reportMissingImports=false
"""Persistence and vector-relational storage layers for Enterprise OS (TSK-02).
Checkpointers and pgvector storage backends for multi-turn execution and HitL gates.
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager, contextmanager
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional
import psycopg
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


def get_db_uri() -> str:
    """Retrieve PostgreSQL connection URI from environment variables."""
    return os.getenv(
        "DATABASE_URL",
        f"postgresql://{os.getenv('POSTGRES_USER', 'postgres')}:{os.getenv('POSTGRES_PASSWORD', 'postgres')}@"
        f"{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}/"
        f"{os.getenv('POSTGRES_DB', 'governed_backend')}",
    )


def get_memory_checkpointer() -> MemorySaver:
    """Return in-memory checkpointer for testing and lightweight sessions."""
    return MemorySaver()


@contextmanager
def get_postgres_checkpointer(db_uri: Optional[str] = None) -> Iterator[PostgresSaver]:
    """Yield a configured synchronous PostgreSQL checkpointer."""
    uri = db_uri or get_db_uri()
    with PostgresSaver.from_conn_string(uri) as checkpointer:
        checkpointer.setup()
        yield checkpointer


@asynccontextmanager
async def get_async_postgres_checkpointer(db_uri: Optional[str] = None) -> AsyncIterator[AsyncPostgresSaver]:
    """Yield a configured asynchronous PostgreSQL checkpointer."""
    uri = db_uri or get_db_uri()
    async with AsyncPostgresSaver.from_conn_string(uri) as checkpointer:
        await checkpointer.setup()
        yield checkpointer


class VectorRelationalClient:
    """PostgreSQL and pgvector storage client for episodic memory and brand state."""

    def __init__(self, db_uri: Optional[str] = None):
        self.db_uri = db_uri or get_db_uri()

    def _get_connection(self) -> psycopg.Connection:
        return psycopg.connect(self.db_uri)

    def save_brand_state(
        self,
        brand_id: str,
        profile_data: Dict[str, Any],
        embedding: List[float],
        version: int = 1,
    ) -> str:
        """Insert or update semantic brand profile state."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO brand_state (brand_id, version, profile_data, embedding)
                    VALUES (%s, %s, %s, %s::vector)
                    RETURNING id;
                    """,
                    (brand_id, version, json.dumps(profile_data), str(embedding)),
                )
                row_id = cur.fetchone()[0]
                conn.commit()
                return str(row_id)

    def search_brand_state(
        self,
        embedding: List[float],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Perform vector cosine similarity search on brand state snapshots."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, brand_id, version, profile_data, 1 - (embedding <=> %s::vector) AS similarity
                    FROM brand_state
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s;
                    """,
                    (str(embedding), str(embedding), limit),
                )
                rows = cur.fetchall()
                return [
                    {
                        "id": str(r[0]),
                        "brand_id": r[1],
                        "version": r[2],
                        "profile_data": r[3],
                        "similarity": float(r[4]),
                    }
                    for r in rows
                ]

    def save_episodic_post_mortem(
        self,
        task_id: str,
        phase: str,
        outcome: str,
        reflection: str,
        metrics: Dict[str, Any],
        embedding: List[float],
    ) -> str:
        """Record task reflection, metrics, and semantic embedding into episodic memory."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO episodic_post_mortems (task_id, phase, outcome, reflection, metrics, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s::vector)
                    RETURNING id;
                    """,
                    (task_id, phase, outcome, reflection, json.dumps(metrics), str(embedding)),
                )
                row_id = cur.fetchone()[0]
                conn.commit()
                return str(row_id)

    def search_episodic_post_mortems(
        self,
        embedding: List[float],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Perform vector cosine similarity search on episodic post-mortems."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, task_id, phase, outcome, reflection, metrics, 1 - (embedding <=> %s::vector) AS similarity
                    FROM episodic_post_mortems
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s;
                    """,
                    (str(embedding), str(embedding), limit),
                )
                rows = cur.fetchall()
                return [
                    {
                        "id": str(r[0]),
                        "task_id": r[1],
                        "phase": r[2],
                        "outcome": r[3],
                        "reflection": r[4],
                        "metrics": r[5],
                        "similarity": float(r[6]),
                    }
                    for r in rows
                ]
