"""PostgreSQL 16 + pgvector long-term persistence engine with multi-tenant Row-Level Security (RLS)."""

import json
import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union
import asyncpg

logger = logging.getLogger(__name__)


class LongTermMemory:
    """Persistent storage engine for baselines, client audits, competitor footprints, and historical knowledge."""

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
        # In-memory storage fallback for local/test execution without active PostgreSQL
        self._fallback_baselines: List[Dict[str, Any]] = []
        self._fallback_audit_logs: List[Dict[str, Any]] = []
        self._fallback_sessions: List[Dict[str, Any]] = []
        self._fallback_brand_profiles: List[Dict[str, Any]] = []
        self._fallback_competitors: List[Dict[str, Any]] = []

    @staticmethod
    def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Calculates cosine similarity between two dense embedding vectors."""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a)) or 1.0
        norm_b = math.sqrt(sum(b * b for b in vec_b)) or 1.0
        return dot / (norm_a * norm_b)

    async def connect(self) -> bool:
        """Initializes database connection pool or enables fallback mode if database is unavailable."""
        try:
            self.pool = await asyncpg.create_pool(dsn=self.dsn, min_size=1, max_size=10, timeout=2.0)
            await self.initialize_schema()
            return True
        except Exception as e:
            logger.info("PostgreSQL unavailable (%s), operating in in-memory persistence mode", e)
            self.pool = None
            return False

    async def initialize_schema(self) -> None:
        """Creates tenant-isolated schemas, tables, pgvector HNSW indices, and RLS policies."""
        if not self.pool:
            return
        async with self.pool.acquire() as conn:
            # 1. Enable pgvector extension
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")

            # 2. Tenants and Clients entity tables
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tenants (
                    tenant_id VARCHAR(64) PRIMARY KEY,
                    tenant_name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS clients (
                    client_id VARCHAR(64) PRIMARY KEY,
                    tenant_id VARCHAR(64) NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
                    client_name VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_clients_tenant ON clients(tenant_id);
                """
            )

            # 3. Client Brand Profiles with RLS
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS client_brand_profiles (
                    id SERIAL PRIMARY KEY,
                    tenant_id VARCHAR(64) NOT NULL,
                    client_id VARCHAR(64) NOT NULL,
                    brand_name VARCHAR(255) NOT NULL,
                    website_url TEXT NOT NULL,
                    industry VARCHAR(128) DEFAULT '',
                    business_goals JSONB DEFAULT '[]'::jsonb,
                    target_market TEXT DEFAULT '',
                    brand_positioning JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_profiles_tenant_client ON client_brand_profiles(tenant_id, client_id);
                ALTER TABLE client_brand_profiles ENABLE ROW LEVEL SECURITY;
                DO $$ BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'tenant_isolation_brand_profiles') THEN
                        CREATE POLICY tenant_isolation_brand_profiles ON client_brand_profiles
                            USING (tenant_id = current_setting('app.current_tenant', true));
                    END IF;
                END $$;
                """
            )

            # 4. Verified Competitor Footprints with 768-dim vector & HNSW index
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS verified_competitor_footprints (
                    id SERIAL PRIMARY KEY,
                    tenant_id VARCHAR(64) NOT NULL,
                    client_id VARCHAR(64) NOT NULL,
                    competitor_name VARCHAR(255) NOT NULL,
                    domain TEXT NOT NULL,
                    positioning_summary TEXT DEFAULT '',
                    digital_footprint JSONB DEFAULT '{}'::jsonb,
                    embedding vector(768),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_competitors_tenant_client ON verified_competitor_footprints(tenant_id, client_id);
                CREATE INDEX IF NOT EXISTS idx_competitor_embedding ON verified_competitor_footprints
                    USING hnsw (embedding vector_cosine_ops);
                ALTER TABLE verified_competitor_footprints ENABLE ROW LEVEL SECURITY;
                DO $$ BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'tenant_isolation_competitors') THEN
                        CREATE POLICY tenant_isolation_competitors ON verified_competitor_footprints
                            USING (tenant_id = current_setting('app.current_tenant', true));
                    END IF;
                END $$;
                """
            )

            # 5. Client Baselines with RLS
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS client_baselines (
                    id SERIAL PRIMARY KEY,
                    tenant_id VARCHAR(64) NOT NULL,
                    client_id VARCHAR(64) NOT NULL DEFAULT 'default_client',
                    brand_name VARCHAR(255) NOT NULL,
                    website_url TEXT NOT NULL,
                    kpi VARCHAR(128) NOT NULL,
                    baseline TEXT NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_baselines_tenant_client ON client_baselines(tenant_id, client_id);
                ALTER TABLE client_baselines ENABLE ROW LEVEL SECURITY;
                DO $$ BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'tenant_isolation_baselines') THEN
                        CREATE POLICY tenant_isolation_baselines ON client_baselines
                            USING (tenant_id = current_setting('app.current_tenant', true));
                    END IF;
                END $$;
                """
            )

            # 6. Strategy Audit Logs with RLS
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_audit_logs (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(64) NOT NULL,
                    tenant_id VARCHAR(64) NOT NULL,
                    client_id VARCHAR(64) NOT NULL DEFAULT 'default_client',
                    recommendation_id VARCHAR(64) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    audit_data JSONB NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_audit_tenant_client ON strategy_audit_logs(tenant_id, client_id);
                ALTER TABLE strategy_audit_logs ENABLE ROW LEVEL SECURITY;
                DO $$ BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'tenant_isolation_audit_logs') THEN
                        CREATE POLICY tenant_isolation_audit_logs ON strategy_audit_logs
                            USING (tenant_id = current_setting('app.current_tenant', true));
                    END IF;
                END $$;
                """
            )

            # 7. Engine Sessions with RLS
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS engine_sessions (
                    session_id VARCHAR(64) PRIMARY KEY,
                    tenant_id VARCHAR(64) NOT NULL,
                    client_id VARCHAR(64) NOT NULL DEFAULT 'default_client',
                    state_data JSONB NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_tenant_client ON engine_sessions(tenant_id, client_id);
                ALTER TABLE engine_sessions ENABLE ROW LEVEL SECURITY;
                DO $$ BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'tenant_isolation_sessions') THEN
                        CREATE POLICY tenant_isolation_sessions ON engine_sessions
                            USING (tenant_id = current_setting('app.current_tenant', true));
                    END IF;
                END $$;
                """
            )

    async def save_brand_profile(
        self,
        tenant_id: str,
        client_id: str,
        brand_name: str,
        website_url: str,
        industry: str = "",
        business_goals: Optional[List[str]] = None,
        target_market: Union[str, List[str]] = "",
        brand_positioning: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Stores or updates brand profile isolated by tenant_id and client_id."""
        market_str = ", ".join(target_market) if isinstance(target_market, list) else target_market
        record = {
            "tenant_id": tenant_id,
            "client_id": client_id,
            "brand_name": brand_name,
            "website_url": website_url,
            "industry": industry,
            "business_goals": business_goals or [],
            "target_market": market_str,
            "brand_positioning": brand_positioning or {},
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO client_brand_profiles (
                            tenant_id, client_id, brand_name, website_url,
                            industry, business_goals, target_market, brand_positioning, updated_at
                        )
                        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8::jsonb, CURRENT_TIMESTAMP);
                        """,
                        tenant_id,
                        client_id,
                        brand_name,
                        website_url,
                        industry,
                        json.dumps(business_goals or []),
                        market_str,
                        json.dumps(brand_positioning or {}),
                    )
                return
            except Exception as e:
                logger.warning("Error saving brand profile to DB: %s", e)
        # In-memory fallback
        for idx, item in enumerate(self._fallback_brand_profiles):
            if item["tenant_id"] == tenant_id and item["client_id"] == client_id:
                self._fallback_brand_profiles[idx] = record
                return
        self._fallback_brand_profiles.append(record)

    async def get_brand_profile(
        self,
        tenant_id: str,
        client_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Retrieves tenant- and client-isolated brand profile."""
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """
                        SELECT * FROM client_brand_profiles
                        WHERE tenant_id = $1 AND client_id = $2
                        ORDER BY updated_at DESC LIMIT 1;
                        """,
                        tenant_id,
                        client_id,
                    )
                    if row:
                        return dict(row)
            except Exception as e:
                logger.warning("Error reading brand profile from DB: %s", e)
        for item in reversed(self._fallback_brand_profiles):
            if item["tenant_id"] == tenant_id and item["client_id"] == client_id:
                return item
        return None

    async def save_competitor_footprint(
        self,
        tenant_id: str,
        client_id: str,
        competitor_name: str,
        domain: str,
        positioning_summary: str = "",
        digital_footprint: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None,
    ) -> None:
        """Saves verified competitor footprint with 768-dim vector embedding."""
        record = {
            "tenant_id": tenant_id,
            "client_id": client_id,
            "competitor_name": competitor_name,
            "domain": domain,
            "positioning_summary": positioning_summary,
            "digital_footprint": digital_footprint or {},
            "embedding": embedding,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    emb_str = f"[{','.join(str(x) for x in embedding)}]" if embedding else None
                    await conn.execute(
                        """
                        INSERT INTO verified_competitor_footprints (
                            tenant_id, client_id, competitor_name, domain,
                            positioning_summary, digital_footprint, embedding
                        )
                        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::vector);
                        """,
                        tenant_id,
                        client_id,
                        competitor_name,
                        domain,
                        positioning_summary,
                        json.dumps(digital_footprint or {}),
                        emb_str,
                    )
                return
            except Exception as e:
                logger.warning("Error saving competitor footprint to DB: %s", e)
        self._fallback_competitors.append(record)

    async def query_competitor_footprints(
        self,
        tenant_id: str,
        client_id: str,
        query_embedding: Optional[List[float]] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Queries competitor footprints isolated by tenant and client, optionally ranked by embedding similarity."""
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    if query_embedding:
                        emb_str = f"[{','.join(str(x) for x in query_embedding)}]"
                        rows = await conn.fetch(
                            """
                            SELECT id, tenant_id, client_id, competitor_name, domain,
                                   positioning_summary, digital_footprint,
                                   1 - (embedding <=> $3::vector) AS similarity_score
                            FROM verified_competitor_footprints
                            WHERE tenant_id = $1 AND client_id = $2
                            ORDER BY embedding <=> $3::vector
                            LIMIT $4;
                            """,
                            tenant_id,
                            client_id,
                            emb_str,
                            top_k,
                        )
                    else:
                        rows = await conn.fetch(
                            """
                            SELECT id, tenant_id, client_id, competitor_name, domain,
                                   positioning_summary, digital_footprint
                            FROM verified_competitor_footprints
                            WHERE tenant_id = $1 AND client_id = $2
                            ORDER BY created_at DESC
                            LIMIT $3;
                            """,
                            tenant_id,
                            client_id,
                            top_k,
                        )
                    return [dict(r) for r in rows]
            except Exception as e:
                logger.warning("Error querying competitor footprints from DB: %s", e)

        # In-memory fallback
        matching = [
            c for c in self._fallback_competitors
            if c["tenant_id"] == tenant_id and c["client_id"] == client_id
        ]
        if query_embedding:
            scored = []
            for comp in matching:
                comp_emb = comp.get("embedding")
                if comp_emb:
                    sim = self._cosine_similarity(query_embedding, comp_emb)
                else:
                    sim = 0.0
                comp_copy = dict(comp)
                comp_copy["similarity_score"] = round(sim, 4)
                scored.append((sim, comp_copy))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [x[1] for x in scored[:top_k]]
        return matching[:top_k]

    async def save_baseline(
        self,
        tenant_id: str,
        brand_name: str,
        website_url: str,
        kpi: str,
        baseline: str,
        client_id: str = "default_client",
    ) -> None:
        """Stores historical baseline metrics isolated by tenant and client."""
        record = {
            "tenant_id": tenant_id,
            "client_id": client_id,
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
                        INSERT INTO client_baselines (tenant_id, client_id, brand_name, website_url, kpi, baseline)
                        VALUES ($1, $2, $3, $4, $5, $6);
                        """,
                        tenant_id,
                        client_id,
                        brand_name,
                        website_url,
                        kpi,
                        baseline,
                    )
                return
            except Exception as e:
                logger.warning("Error saving baseline to DB, falling back to local: %s", e)
        self._fallback_baselines.append(record)

    async def get_baselines(
        self,
        tenant_id: str,
        client_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieves tenant baselines with strict client and tenant isolation."""
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    if client_id:
                        rows = await conn.fetch(
                            "SELECT * FROM client_baselines WHERE tenant_id = $1 AND client_id = $2 ORDER BY created_at DESC;",
                            tenant_id,
                            client_id,
                        )
                    else:
                        rows = await conn.fetch(
                            "SELECT * FROM client_baselines WHERE tenant_id = $1 ORDER BY created_at DESC;",
                            tenant_id,
                        )
                    return [dict(r) for r in rows]
            except Exception as e:
                logger.warning("Error reading baselines from DB: %s", e)
        return [
            b for b in self._fallback_baselines
            if b["tenant_id"] == tenant_id and (client_id is None or b.get("client_id") == client_id)
        ]

    async def save_audit_log(
        self,
        session_id: str,
        tenant_id: str,
        recommendation_id: str,
        status: str,
        audit_data: Dict[str, Any],
        client_id: str = "default_client",
    ) -> None:
        """Records immutable strategy audit entry isolated by tenant and client."""
        entry = {
            "session_id": session_id,
            "tenant_id": tenant_id,
            "client_id": client_id,
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
                        INSERT INTO strategy_audit_logs (session_id, tenant_id, client_id, recommendation_id, status, audit_data)
                        VALUES ($1, $2, $3, $4, $5, $6::jsonb);
                        """,
                        session_id,
                        tenant_id,
                        client_id,
                        recommendation_id,
                        status,
                        json.dumps(audit_data),
                    )
                return
            except Exception as e:
                logger.warning("Error writing audit log to DB: %s", e)
        self._fallback_audit_logs.append(entry)

    async def get_audit_history(
        self,
        tenant_id: str,
        client_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Fetches audit history isolated by tenant and client."""
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    if client_id:
                        rows = await conn.fetch(
                            "SELECT * FROM strategy_audit_logs WHERE tenant_id = $1 AND client_id = $2 ORDER BY created_at DESC;",
                            tenant_id,
                            client_id,
                        )
                    else:
                        rows = await conn.fetch(
                            "SELECT * FROM strategy_audit_logs WHERE tenant_id = $1 ORDER BY created_at DESC;",
                            tenant_id,
                        )
                    return [dict(r) for r in rows]
            except Exception as e:
                logger.warning("Error querying audit logs: %s", e)
        return [
            a for a in self._fallback_audit_logs
            if a["tenant_id"] == tenant_id and (client_id is None or a.get("client_id") == client_id)
        ]

    async def save_session_state(
        self,
        session_id: str,
        tenant_id: str,
        state_data: Dict[str, Any],
        client_id: str = "default_client",
    ) -> None:
        """Persists entire MasterEngineState snapshot for session recovery."""
        record = {
            "session_id": session_id,
            "tenant_id": tenant_id,
            "client_id": client_id,
            "state_data": state_data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO engine_sessions (session_id, tenant_id, client_id, state_data, updated_at)
                        VALUES ($1, $2, $3, $4::jsonb, CURRENT_TIMESTAMP)
                        ON CONFLICT (session_id) DO UPDATE
                        SET state_data = EXCLUDED.state_data,
                            client_id = EXCLUDED.client_id,
                            updated_at = CURRENT_TIMESTAMP;
                        """,
                        session_id,
                        tenant_id,
                        client_id,
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
        client_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Retrieves persisted MasterEngineState snapshot."""
        if self.pool:
            try:
                async with self.pool.acquire() as conn:
                    if tenant_id and client_id:
                        row = await conn.fetchrow(
                            "SELECT state_data FROM engine_sessions WHERE session_id = $1 AND tenant_id = $2 AND client_id = $3;",
                            session_id,
                            tenant_id,
                            client_id,
                        )
                    elif tenant_id:
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
                if (tenant_id is None or s["tenant_id"] == tenant_id) and (client_id is None or s.get("client_id") == client_id):
                    return s["state_data"]
        return None

    async def close(self) -> None:
        """Closes active database connections."""
        if self.pool:
            await self.pool.close()
