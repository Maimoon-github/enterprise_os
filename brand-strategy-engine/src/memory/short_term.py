"""Asynchronous in-memory scratchpad with TTL-based state storage, Redis replication, and typed Session Graph."""

import asyncio
from datetime import datetime, timezone
from enum import Enum
import json
import logging
import time
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SessionNodeType(str, Enum):
    """Categorical classification of session graph artifacts."""

    INITIALIZATION = "initialization"
    REACT_STEP = "react_step"
    STAGE_HANDOFF = "stage_handoff"
    DOM_TREE = "dom_tree"
    VISUAL_BUFFER = "visual_buffer"
    ARTIFACT = "artifact"


class SessionGraphNode(BaseModel):
    """Immutable vertex in the intra-agent execution session graph."""

    node_id: str = Field(default_factory=lambda: f"node_{uuid.uuid4().hex[:10]}")
    session_id: str
    agent_id: str
    stage: str
    node_type: SessionNodeType
    payload: Dict[str, Any]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionGraphEdge(BaseModel):
    """Directed handoff between execution graph nodes."""

    source_node_id: str
    target_node_id: str
    relationship: str = "sequential_handoff"


class TaskSessionGraph(BaseModel):
    """Complete typed session graph container."""

    session_id: str
    nodes: List[SessionGraphNode] = Field(default_factory=list)
    edges: List[SessionGraphEdge] = Field(default_factory=list)


class ShortTermMemory:
    """Intra-session working memory, transient buffer manager, and typed Session Graph."""

    def __init__(
        self,
        default_ttl: int = 3600,
        redis_client: Optional[Any] = None,
    ):
        self.default_ttl = default_ttl
        self.redis_client = redis_client
        self._store: Dict[str, Any] = {}
        self._expiry: Dict[str, float] = {}
        self._stage_buffers: Dict[str, Dict[str, Any]] = {}
        self._session_graphs: Dict[str, TaskSessionGraph] = {}
        self._lock = asyncio.Lock()

    async def add_graph_node(
        self,
        session_id: str,
        agent_id: str,
        stage: str,
        node_type: SessionNodeType,
        payload: Dict[str, Any],
    ) -> SessionGraphNode:
        """Appends a strongly typed node to the active session graph."""
        async with self._lock:
            if session_id not in self._session_graphs:
                self._session_graphs[session_id] = TaskSessionGraph(session_id=session_id)

            graph = self._session_graphs[session_id]
            node = SessionGraphNode(
                session_id=session_id,
                agent_id=agent_id,
                stage=stage,
                node_type=node_type,
                payload=payload,
            )

            # Link sequentially to previous node if available
            if graph.nodes:
                prev = graph.nodes[-1]
                edge = SessionGraphEdge(source_node_id=prev.node_id, target_node_id=node.node_id)
                graph.edges.append(edge)

            graph.nodes.append(node)

            # Replicate to Redis if active
            if self.redis_client:
                try:
                    await self.redis_client.set(
                        f"graph:{session_id}",
                        json.dumps(graph.model_dump(mode="json")),
                    )
                except Exception as e:
                    logger.debug("Redis graph replication fallback: %s", e)

            return node

    async def get_session_graph(self, session_id: str) -> TaskSessionGraph:
        """Retrieves complete typed session graph."""
        async with self._lock:
            if session_id in self._session_graphs:
                return self._session_graphs[session_id]
            # Try Redis retrieval
            if self.redis_client:
                try:
                    raw = await self.redis_client.get(f"graph:{session_id}")
                    if raw:
                        data = json.loads(raw)
                        graph = TaskSessionGraph(**data)
                        self._session_graphs[session_id] = graph
                        return graph
                except Exception as e:
                    logger.debug("Redis graph read fallback: %s", e)
            return TaskSessionGraph(session_id=session_id)

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Stores a value with optional TTL in seconds and replicates to Redis if available."""
        async with self._lock:
            self._store[key] = value
            expiry_time = time.time() + (ttl if ttl is not None else self.default_ttl)
            self._expiry[key] = expiry_time

            if self.redis_client:
                try:
                    val_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                    await self.redis_client.set(key, val_str, ex=ttl or self.default_ttl)
                except Exception as e:
                    logger.debug("Redis replication error: %s", e)

    async def get(self, key: str) -> Optional[Any]:
        """Retrieves an unexpired value, purging if expired."""
        async with self._lock:
            if key not in self._store:
                if self.redis_client:
                    try:
                        raw = await self.redis_client.get(key)
                        if raw:
                            try:
                                return json.loads(raw)
                            except Exception:
                                return raw
                    except Exception as e:
                        logger.debug("Redis read error: %s", e)
                return None
            if time.time() > self._expiry.get(key, 0):
                self._store.pop(key, None)
                self._expiry.pop(key, None)
                return None
            return self._store[key]

    async def delete(self, key: str) -> bool:
        """Deletes a key from storage."""
        async with self._lock:
            removed = self._store.pop(key, None) is not None
            self._expiry.pop(key, None)
            if self.redis_client:
                try:
                    await self.redis_client.delete(key)
                except Exception as e:
                    logger.debug("Redis delete error: %s", e)
            return removed

    async def save_stage_buffer(self, session_id: str, stage: str, data: Any) -> None:
        """Buffers intermediate stage execution artifacts."""
        async with self._lock:
            if session_id not in self._stage_buffers:
                self._stage_buffers[session_id] = {}
            self._stage_buffers[session_id][stage] = data

            if self.redis_client:
                try:
                    payload = data if isinstance(data, (dict, list)) else {"data": str(data)}
                    await self.redis_client.set(
                        f"stage:{session_id}:{stage}",
                        json.dumps(payload),
                        ex=self.default_ttl,
                    )
                except Exception as e:
                    logger.debug("Redis buffer error: %s", e)

    async def get_stage_buffer(self, session_id: str, stage: str) -> Optional[Any]:
        """Retrieves execution artifacts from a completed stage."""
        async with self._lock:
            if session_id in self._stage_buffers and stage in self._stage_buffers[session_id]:
                return self._stage_buffers[session_id][stage]
            if self.redis_client:
                try:
                    raw = await self.redis_client.get(f"stage:{session_id}:{stage}")
                    if raw:
                        return json.loads(raw)
                except Exception as e:
                    logger.debug("Redis buffer read error: %s", e)
            return None

    async def clear_session(self, session_id: str) -> None:
        """Purges transient buffers and session graphs."""
        async with self._lock:
            self._stage_buffers.pop(session_id, None)
            self._session_graphs.pop(session_id, None)
            if self.redis_client:
                try:
                    await self.redis_client.delete(f"graph:{session_id}")
                except Exception as e:
                    logger.debug("Redis clear session error: %s", e)

