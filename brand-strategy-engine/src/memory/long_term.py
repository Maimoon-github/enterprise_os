"""PostgreSQL + pgvector long-term persistence engine with tenant isolation."""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import asyncpg

logger = logging.getLogger(__name__)


class LongTermMemory:
    """Persistent storage engine for baselines, client audits, and historical knowledge."""

    def __init__(
        self,
        dsn: Optional[str] = None,
        host: str = "postgres-pgvector",
        port: int = 5432,
        database: str = "brand_strategy_db",
        user: str = "engine_user",
        password: str = "engine_secure_pass",
    ):
        self.dsn = dsn or f"postgresql://{user}:{password}@{host}:{port}/{database}"
        self.pool: Optional[asyncpg.Pool] = None
        # In-memory storage fallback for local/test execution without PostgreSQL
        self._fallback_baselines: List[Dict[str, Any]] = []
        self._fallback_audit_logs: List[Dict[str, Any]] = []
        self._fallback_sessions: List[Dict[str, Any]] = []

    async def connect(self) -> bool:
        """Initializes database pool or enables fallback mode if database is unavailable."""
        try:
            self.pool = await asyncpg.create_pool(dsn=self.dsn, min_size=1, max_size=10, timeout=2.0)
            await self.initialize_schema()
            return True
        except Exception as e:
            logger.info("PostgreSQL unavailable (%s), operating in in-memory persistence mode", e)
            self.pool = None
            return False

    async def initialize_schema(self) -> None:
        """Creates tenant-isolated schema, session persistence, and audit tables."""
        if not self.pool:
            return
        async with self.pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS client_baselines (
                    id SERIAL PRIMARY KEY,
                    tenant_id VARCHAR(64) NOT NULL,
                    brand_name VARCHAR(255) NOT NULL,
                    website_url TEXT NOT NULL,
                    kpi VARCHAR(128) NOT NULL,
                    baseline TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_baselines_tenant ON client_baselines(tenant_id);

                CREATE TABLE IF NOT EXISTS strategy_audit_logs (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(64) NOT NULL,
                    tenant_id VARCHAR(64) NOT NULL,
                    recommendation_id VARCHAR(64) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    audit_data JSONB NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_audit_tenant ON strategy_audit_logs(tenant_id);

                CREATE TABLE IF NOT EXISTS engine_sessions (
                    session_id VARCHAR(64) PRIMARY KEY,
                    tenant_id VARCHAR(64) NOT NULL,
                    state_data JSONB NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_tenant ON engine_sessions(tenant_id);
                """
            )

    async def save_baseline(
        self,
        tenant_id: str,
        brand_name: str,
        website_url: str,
        kpi: str,
        baseline: str,
    ) -> None:
        """Stores historical baseline metrics."""
        record = {
            "tenant_id": tenant_id,
            "brand_name": brand_name,
            "website_url": website_url,
            "kpi": kpi,
            "baseline": baseline,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO client_baselines (tenant_id, brand_name, website_url, kpi, baseline)
                        VALUES ($1, $2, $3, $4, $5);
                        """,
                        tenant_id,
                        brand_name,
                        website_url,
                        kpi,
                        baseline,
                    )
                return
            except Exception as e:
                logger.warning("Error saving baseline to DB, falling back to local: %s", e)
        self._fallback_baselines.append(record)

    async def get_baselines(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Retrieves tenant baselines with strict isolation."""
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT * FROM client_baselines WHERE tenant_id = $1 ORDER BY created_at DESC;",
                        tenant_id,
                    )
                    return [dict(r) for r in rows]
            except Exception as e:
                logger.warning("Error reading baselines from DB: %s", e)
        return [b for b in self._fallback_baselines if b["tenant_id"] == tenant_id]

    async def save_audit_log(
        self,
        session_id: str,
        tenant_id: str,
        recommendation_id: str,
        status: str,
        audit_data: Dict[str, Any],
    ) -> None:
        """Records immutable strategy audit entry."""
        entry = {
            "session_id": session_id,
            "tenant_id": tenant_id,
            "recommendation_id": recommendation_id,
            "status": status,
            "audit_data": audit_data,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO strategy_audit_logs (session_id, tenant_id, recommendation_id, status, audit_data)
                        VALUES ($1, $2, $3, $4, $5::jsonb);
                        """,
                        session_id,
                        tenant_id,
                        recommendation_id,
                        status,
                        json.dumps(audit_data),
                    )
                return
            except Exception as e:
                logger.warning("Error writing audit log to DB: %s", e)
        self._fallback_audit_logs.append(entry)

    async def get_audit_history(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Fetches audit history for a tenant."""
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    rows = await conn.fetch(
                        "SELECT * FROM strategy_audit_logs WHERE tenant_id = $1 ORDER BY created_at DESC;",
                        tenant_id,
                    )
                    return [dict(r) for r in rows]
            except Exception as e:
                logger.warning("Error querying audit logs: %s", e)
        return [a for a in self._fallback_audit_logs if a["tenant_id"] == tenant_id]

    async def save_session_state(
        self,
        session_id: str,
        tenant_id: str,
        state_data: Dict[str, Any],
    ) -> None:
        """Persists entire MasterEngineState snapshot for session recovery."""
        record = {
            "session_id": session_id,
            "tenant_id": tenant_id,
            "state_data": state_data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO engine_sessions (session_id, tenant_id, state_data, updated_at)
                        VALUES ($1, $2, $3::jsonb, CURRENT_TIMESTAMP)
                        ON CONFLICT (session_id) DO UPDATE
                        SET state_data = EXCLUDED.state_data, updated_at = CURRENT_TIMESTAMP;
                        """,
                        session_id,
                        tenant_id,
                        json.dumps(state_data),
                    )
                return
            except Exception as e:
                logger.warning("Error saving session state to DB: %s", e)
        # In-memory fallback
        for idx, s in enumerate(self._fallback_sessions):
            if s["session_id"] == session_id:
                self._fallback_sessions[idx] = record
                return
        self._fallback_sessions.append(record)

    async def get_session_state(
        self,
        session_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieves persisted MasterEngineState snapshot."""
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    if tenant_id:
                        row = await conn.fetchrow(
                            "SELECT state_data FROM engine_sessions WHERE session_id = $1 AND tenant_id = $2;",
                            session_id,
                            tenant_id,
                        )
                    else:
                        row = await conn.fetchrow(
                            "SELECT state_data FROM engine_sessions WHERE session_id = $1;",
                            session_id,
                        )
                    if row:
                        raw = row["state_data"]
                        return json.loads(raw) if isinstance(raw, str) else dict(raw)
            except Exception as e:
                logger.warning("Error reading session state from DB: %s", e)
        for s in self._fallback_sessions:
            if s["session_id"] == session_id:
                if tenant_id is None or s["tenant_id"] == tenant_id:
                    return s["state_data"]
        return None

    async def close(self) -> None:
        """Closes active database connections."""
        if self.pool:
            await self.pool.close()
