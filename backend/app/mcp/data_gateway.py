"""Governed CRUD facade between Agentic RAG and systems of record.

The data gateway is the governed path (MCP_DATA) by which the Agentic RAG
service, Intelligence Engine, and orchestration layers read from or write to
the systems of record:
- Central Enterprise Database (CDB: relational/operational & vector)
- Headless CMS & Content Store (CMS: content models & staging)
- Institutional Memory Store (MEM: brand books & learned heuristics)
- Artifact & Evidence Registry (ART: content-addressable deliverables)

Enforces tenant authorization on every call before delegating to a repository.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.core.exceptions import AuthorizationError, PolicyViolationError
from app.integrations.artifact_store.client import ArtifactStoreClient
from app.integrations.cms.client import CmsClient
from app.persistence.repositories.artifact import ArtifactReference, ArtifactRepository
from app.persistence.repositories.memory import MemoryRecord, MemoryRepository
from app.persistence.repositories.operational import OperationalRepository
from app.persistence.repositories.telemetry import TelemetryRepository
from app.persistence.repositories.vector import VectorRepository
from app.schemas.governance import Directive, RiskLevel, TenantScope
from app.schemas.telemetry import TelemetryEvent
from app.security.authorization_boundary import AuthorizationBoundary, CallerIdentity
from app.services.provenance import ProvenanceRecorder


class DataGateway:
    """Authorizes and executes reads/writes against CDB, CMS, MEM, and ART systems of record."""

    def __init__(
        self,
        vector_repository: VectorRepository,
        authorization_boundary: AuthorizationBoundary | None = None,
        *,
        operational_repository: OperationalRepository | None = None,
        memory_repository: MemoryRepository | None = None,
        artifact_repository: ArtifactRepository | None = None,
        artifact_store: ArtifactStoreClient | None = None,
        cms_client: CmsClient | None = None,
        telemetry_repository: TelemetryRepository | None = None,
        provenance_recorder: ProvenanceRecorder | None = None,
    ) -> None:
        self._vector_repository = vector_repository
        self._authorization_boundary = authorization_boundary or AuthorizationBoundary()
        self._operational_repository = operational_repository
        self._memory_repository = memory_repository
        self._artifact_repository = artifact_repository
        self._artifact_store = artifact_store
        self._cms_client = cms_client
        self._telemetry_repository = telemetry_repository
        self._provenance_recorder = provenance_recorder

    def _authorize_tenant(
        self,
        caller: CallerIdentity,
        tenant_id: str,
        risk: RiskLevel = RiskLevel.LOW,
        requested_capability: str | None = None,
        delegation_parent: str | None = None,
    ) -> None:
        if not tenant_id or not tenant_id.strip():
            raise AuthorizationError("Tenant ID is required for Layer-4 access.")
        self._authorization_boundary.authorize(
            caller,
            requested_scope=TenantScope(tenant_id=tenant_id),
            requested_risk=risk,
            requested_capability=requested_capability,
            delegation_parent=delegation_parent,
        )

    async def _record_audit(
        self,
        tenant_id: str,
        entity_id: str,
        activity: str,
        agent: str,
        metadata: dict[str, Any] | None = None,
        session: Any = None,
    ) -> None:
        if self._provenance_recorder is not None:
            try:
                await self._provenance_recorder.record(
                    tenant_id=tenant_id,
                    entity_id=entity_id,
                    activity=activity,
                    agent=agent,
                    metadata=metadata,
                    session=session,
                )
            except Exception:
                pass

    def _assert_no_worker_access(self, caller: CallerIdentity) -> None:
        subj_lower = caller.subject.lower()
        if (
            caller.subject.startswith(("W_", "S_"))
            or "worker" in subj_lower
            or "specialist" in subj_lower
            or "subagent" in subj_lower
            or "sub_agent" in subj_lower
            or "sandbox" in subj_lower
        ):
            raise PolicyViolationError(
                f"Direct worker enterprise-store access forbidden for '{caller.subject}'; data access must be mediated through Intelligence Engine (Model A)"
            )
        self._authorization_boundary.authorize_sandbox_action(caller, target_resource="persistence")

    # -- Vector / Knowledge Retrieval & Ingestion --
    async def query(
        self,
        caller: CallerIdentity,
        *,
        tenant_id: str,
        query: str,
        top_k: int = 10,
        namespace: str | None = None,
        search_type: str = "exact",
        metric: str = "cosine",
        filter_metadata: dict[str, Any] | None = None,
        session: Any = None,
    ) -> list[dict[str, Any]]:
        """Authorize and execute a similarity-search read."""
        self._authorize_tenant(caller, tenant_id, requested_capability="mcp_data_read")
        self._assert_no_worker_access(caller)
        kwargs: dict[str, Any] = {"tenant_id": tenant_id, "query": query, "top_k": top_k}
        if namespace is not None:
            kwargs["namespace"] = namespace
        if search_type != "exact":
            kwargs["search_type"] = search_type
        if metric != "cosine":
            kwargs["metric"] = metric
        if filter_metadata is not None:
            kwargs["filter_metadata"] = filter_metadata
        if session is not None:
            kwargs["session"] = session

        try:
            results = await self._vector_repository.similarity_search(**kwargs)
        except TypeError:
            # Fall back safely on stand-ins with legacy 3-parameter signature
            results = await self._vector_repository.similarity_search(
                tenant_id=tenant_id, query=query, top_k=top_k
            )

        await self._record_audit(
            tenant_id=tenant_id,
            entity_id=f"query:{query[:32]}",
            activity="mcp_data_vector_read",
            agent=caller.subject,
            session=session,
        )
        return results

    async def ingest(
        self,
        caller: CallerIdentity,
        *,
        tenant_id: str,
        doc_id: str,
        text: str,
        source: str,
        namespace: str = "default",
        session: Any = None,
    ) -> None:
        """Authorize and execute a document ingestion write."""
        self._authorize_tenant(caller, tenant_id, risk=RiskLevel.MEDIUM, requested_capability="mcp_data_write")
        self._assert_no_worker_access(caller)
        kwargs: dict[str, Any] = {
            "doc_id": doc_id,
            "tenant_id": tenant_id,
            "text": text,
            "source": source,
            "namespace": namespace,
        }
        if session is not None:
            kwargs["session"] = session
        try:
            await self._vector_repository.index_document(**kwargs)
        except TypeError:
            try:
                await self._vector_repository.index_document(
                    doc_id=doc_id, tenant_id=tenant_id, text=text, source=source, namespace=namespace
                )
            except TypeError:
                await self._vector_repository.index_document(
                    doc_id=doc_id, tenant_id=tenant_id, text=text, source=source
                )
        await self._record_audit(
            tenant_id=tenant_id,
            entity_id=doc_id,
            activity="mcp_data_vector_write",
            agent=caller.subject,
            session=session,
        )

    # -- Institutional Memory Store (MEM) --
    async def query_memory(
        self,
        caller: CallerIdentity,
        *,
        tenant_id: str,
        category: str | None = None,
        namespace: str | None = None,
    ) -> list[MemoryRecord]:
        """Authorize and query institutional memory records."""
        self._authorize_tenant(caller, tenant_id)
        self._assert_no_worker_access(caller)
        recs: list[MemoryRecord] = []
        if self._memory_repository is not None and hasattr(self._memory_repository, "list_by_tenant"):
            recs = await self._memory_repository.list_by_tenant(
                tenant_id, category=category, namespace=namespace
            )
        await self._record_audit(
            tenant_id=tenant_id,
            entity_id=f"mem_query:{namespace or category or 'all'}",
            activity="mcp_data_memory_read",
            agent=caller.subject,
        )
        return recs

    async def promote_memory(
        self,
        caller: CallerIdentity,
        *,
        tenant_id: str,
        record: MemoryRecord,
        session: Any = None,
    ) -> None:
        """Authorize and promote a validated learning delta into institutional memory."""
        subj_lower = caller.subject.lower()
        if (
            caller.subject.startswith("W_")
            or caller.subject.startswith("S_")
            or "worker" in subj_lower
            or "specialist" in subj_lower
        ):
            raise PolicyViolationError(
                "Direct worker memory mutation forbidden; mutations must route through Intelligence Engine"
            )
        self._authorize_tenant(caller, tenant_id, risk=RiskLevel.MEDIUM)
        if self._memory_repository is not None:
            if session is not None:
                try:
                    await self._memory_repository.promote(record, session=session)
                except TypeError:
                    await self._memory_repository.promote(record)
            else:
                await self._memory_repository.promote(record)
            await self._record_audit(
                tenant_id=tenant_id,
                entity_id=record.memory_id,
                activity="mcp_data_memory_promote",
                agent=caller.subject,
            )

    # -- Artifact & Evidence Registry (ART) --
    async def resolve_artifact(
        self, caller: CallerIdentity, *, tenant_id: str, artifact_id: str
    ) -> ArtifactReference | None:
        """Authorize and resolve a deliverable/evidence artifact by UUID/hash."""
        self._authorize_tenant(caller, tenant_id)
        self._assert_no_worker_access(caller)
        if self._artifact_repository is None:
            return None
        try:
            art = await self._artifact_repository.resolve(artifact_id, tenant_id=tenant_id)
        except TypeError:
            art = await self._artifact_repository.resolve(artifact_id)
        await self._record_audit(
            tenant_id=tenant_id,
            entity_id=artifact_id,
            activity="mcp_data_artifact_read",
            agent=caller.subject,
        )
        return art

    async def resolve_artifact_by_hash(
        self, caller: CallerIdentity, *, tenant_id: str, content_hash: str
    ) -> ArtifactReference | None:
        """Authorize and resolve an artifact by cryptographic content hash."""
        self._authorize_tenant(caller, tenant_id)
        self._assert_no_worker_access(caller)
        if self._artifact_repository is None or not hasattr(self._artifact_repository, "resolve_by_hash"):
            return None
        art = await self._artifact_repository.resolve_by_hash(content_hash, tenant_id=tenant_id)
        if art:
            await self._record_audit(
                tenant_id=tenant_id,
                entity_id=art.artifact_id,
                activity="mcp_data_artifact_hash_read",
                agent=caller.subject,
            )
        return art

    async def register_artifact(
        self,
        caller: CallerIdentity,
        *,
        tenant_id: str,
        artifact: ArtifactReference,
        session: Any = None,
    ) -> None:
        """Authorize and register an immutable deliverable in the artifact registry."""
        self._authorize_tenant(caller, tenant_id)
        self._assert_no_worker_access(caller)
        if self._artifact_repository is not None:
            if session is not None:
                try:
                    await self._artifact_repository.register(tenant_id, artifact, session=session)
                except TypeError:
                    await self._artifact_repository.register(tenant_id, artifact)
            else:
                await self._artifact_repository.register(tenant_id, artifact)
            await self._record_audit(
                tenant_id=tenant_id,
                entity_id=artifact.artifact_id,
                activity="mcp_data_artifact_write",
                agent=caller.subject,
            )

    async def store_and_register_artifact(
        self,
        caller: CallerIdentity,
        *,
        tenant_id: str,
        content: bytes | str,
        deliverable_type: str = "generic",
        media_type: str = "application/octet-stream",
        name: str = "",
        artifact_id: str | None = None,
        metadata: dict[str, str] | None = None,
        session: Any = None,
    ) -> ArtifactReference:
        """Store content-addressed payload in artifact store and register metadata in repository."""
        self._authorize_tenant(caller, tenant_id)
        self._assert_no_worker_access(caller)

        if self._artifact_store is None:
            self._artifact_store = ArtifactStoreClient()

        content_hash, length, uri = await self._artifact_store.put_if_absent(content)
        art_id = artifact_id or str(uuid.uuid4())
        meta = dict(metadata or {})
        meta["byte_length"] = str(length)

        art_ref = ArtifactReference(
            artifact_id=art_id,
            content_hash=content_hash,
            uri=uri,
            media_type=media_type,
            deliverable_type=deliverable_type,
            tenant_id=tenant_id,
            name=name,
            creator_agent=caller.subject,
            metadata=meta,
        )

        if self._artifact_repository is not None:
            await self._artifact_repository.register(tenant_id, art_ref, session=session)

        await self._record_audit(
            tenant_id=tenant_id,
            entity_id=art_id,
            activity="mcp_data_artifact_payload_write",
            agent=caller.subject,
        )
        return art_ref

    async def get_artifact_payload(
        self, caller: CallerIdentity, *, tenant_id: str, artifact_id: str
    ) -> bytes:
        """Authorize and retrieve the payload of an artifact, verifying integrity."""
        self._authorize_tenant(caller, tenant_id)
        self._assert_no_worker_access(caller)
        if self._artifact_repository is None or self._artifact_store is None:
            raise ValueError("Artifact repository or artifact store not configured.")
        art = await self._artifact_repository.resolve(artifact_id, tenant_id=tenant_id)
        payload = await self._artifact_store.get(art.content_hash)
        if not art.verify_integrity(payload):
            raise ValueError(f"Integrity verification failed for artifact '{artifact_id}'.")
        await self._record_audit(
            tenant_id=tenant_id,
            entity_id=artifact_id,
            activity="mcp_data_artifact_payload_read",
            agent=caller.subject,
        )
        return payload

    # -- Headless CMS Staging & Publishing (CMS) --
    async def read_cms_staged(
        self, caller: CallerIdentity, *, tenant_id: str, content_type: str
    ) -> list[dict[str, Any]]:
        """Authorize and read staged CMS models."""
        self._authorize_tenant(caller, tenant_id, requested_capability="mcp_data_read")
        self._assert_no_worker_access(caller)
        if self._cms_client is None:
            return []
        items = await self._cms_client.read_staged(content_type, tenant_id=tenant_id)
        await self._record_audit(
            tenant_id=tenant_id,
            entity_id=f"cms:{content_type}",
            activity="mcp_data_cms_read",
            agent=caller.subject,
        )
        return items

    async def stage_cms_entry(
        self,
        caller: CallerIdentity,
        *,
        tenant_id: str,
        content_type: str,
        entry_id: str,
        data: dict[str, Any],
        idempotency_key: str | None = None,
        provenance_context: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Authorize and register a staged CMS entry."""
        self._authorize_tenant(caller, tenant_id, risk=RiskLevel.MEDIUM, requested_capability="mcp_data_write")
        self._assert_no_worker_access(caller)
        if self._cms_client is None:
            return None
        res = None
        if hasattr(self._cms_client, "stage_entry"):
            try:
                res = await self._cms_client.stage_entry(
                    content_type, entry_id, data, tenant_id=tenant_id, idempotency_key=idempotency_key
                )
            except TypeError:
                res = await self._cms_client.stage_entry(content_type, entry_id, data, tenant_id=tenant_id)
        meta = dict(provenance_context or {})
        if idempotency_key:
            meta["idempotency_key"] = idempotency_key
        await self._record_audit(
            tenant_id=tenant_id,
            entity_id=f"cms:{content_type}:{entry_id}",
            activity="mcp_data_cms_stage",
            agent=caller.subject,
            metadata=meta,
        )
        return res

    async def apply_cms_changes(
        self,
        caller: CallerIdentity,
        *,
        tenant_id: str,
        content_type: str,
        entry_id: str,
        diff: dict[str, Any],
        idempotency_key: str | None = None,
        provenance_context: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Authorize and apply schema/content diffs to staged CMS entries."""
        self._authorize_tenant(caller, tenant_id, risk=RiskLevel.MEDIUM, requested_capability="mcp_data_write")
        self._assert_no_worker_access(caller)
        if self._cms_client is None:
            return {"status": "cms_unconfigured"}
        try:
            res = await self._cms_client.apply_changes(
                content_type, entry_id, diff, tenant_id=tenant_id, idempotency_key=idempotency_key
            )
        except TypeError:
            res = await self._cms_client.apply_changes(content_type, entry_id, diff, tenant_id=tenant_id)
        meta = dict(provenance_context or {})
        if idempotency_key:
            meta["idempotency_key"] = idempotency_key
        await self._record_audit(
            tenant_id=tenant_id,
            entity_id=f"cms:{content_type}:{entry_id}",
            activity="mcp_data_cms_write",
            agent=caller.subject,
            metadata=meta,
        )
        return res

    async def publish_cms_entry(
        self,
        caller: CallerIdentity,
        *,
        tenant_id: str,
        content_type: str,
        entry_id: str,
        version: str = "v1.0",
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
        provenance_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Authorize and promote an approved staged entry to the live published state with version tracking."""
        self._authorize_tenant(caller, tenant_id, risk=RiskLevel.MEDIUM, requested_capability="mcp_data_write")
        self._assert_no_worker_access(caller)
        if self._cms_client is None:
            return {"status": "cms_unconfigured"}
        try:
            res = await self._cms_client.publish_entry(
                content_type,
                entry_id,
                tenant_id=tenant_id,
                version=version,
                payload=payload,
                idempotency_key=idempotency_key,
            )
        except TypeError:
            res = await self._cms_client.publish_entry(
                content_type, entry_id, tenant_id=tenant_id, version=version, payload=payload
            )
        meta = dict(provenance_context or {})
        meta.update({"version": version, "idempotency_key": idempotency_key or ""})
        await self._record_audit(
            tenant_id=tenant_id,
            entity_id=f"cms:{content_type}:{entry_id}:{version}",
            activity="mcp_data_cms_publish",
            agent=caller.subject,
            metadata=meta,
        )
        return res

    async def rollback_cms_entry(
        self,
        caller: CallerIdentity,
        *,
        tenant_id: str,
        content_type: str,
        entry_id: str,
        provenance_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Authorize and roll back a published entry to its previous version."""
        self._authorize_tenant(caller, tenant_id, risk=RiskLevel.MEDIUM, requested_capability="mcp_data_write")
        self._assert_no_worker_access(caller)
        if self._cms_client is None:
            return {"status": "cms_unconfigured"}
        res = await self._cms_client.rollback_entry(content_type, entry_id, tenant_id=tenant_id)
        await self._record_audit(
            tenant_id=tenant_id,
            entity_id=f"cms:{content_type}:{entry_id}:rollback",
            activity="mcp_data_cms_rollback",
            agent=caller.subject,
            metadata=provenance_context,
        )
        return res

    async def read_cms_published(
        self,
        caller: CallerIdentity,
        *,
        tenant_id: str,
        content_type: str,
        entry_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Authorize and read published CMS models."""
        self._authorize_tenant(caller, tenant_id, requested_capability="mcp_data_read")
        self._assert_no_worker_access(caller)
        if self._cms_client is None:
            return []
        items = await self._cms_client.read_published(content_type, tenant_id=tenant_id, entry_id=entry_id)
        await self._record_audit(
            tenant_id=tenant_id,
            entity_id=f"cms_published:{content_type}:{entry_id or 'all'}",
            activity="mcp_data_cms_published_read",
            agent=caller.subject,
        )
        return items

    async def deploy_cms_payload(
        self,
        caller: CallerIdentity,
        *,
        tenant_id: str,
        payload: dict[str, Any],
        version: str = "v1.0",
        idempotency_key: str | None = None,
        provenance_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Authorize and deploy a structured bundle of approved CMS models."""
        self._authorize_tenant(caller, tenant_id, risk=RiskLevel.HIGH, requested_capability="mcp_data_write")
        self._assert_no_worker_access(caller)
        if self._cms_client is None:
            return {"status": "cms_unconfigured"}
        payload_with_version = dict(payload)
        payload_with_version.setdefault("version", version)
        res = await self._cms_client.deploy_payload(payload_with_version, tenant_id=tenant_id)
        meta = dict(provenance_context or {})
        meta.update({"version": version, "idempotency_key": idempotency_key or ""})
        await self._record_audit(
            tenant_id=tenant_id,
            entity_id=f"cms_deploy:{version}",
            activity="mcp_data_cms_deploy",
            agent=caller.subject,
            metadata=meta,
        )
        return res

    # -- Central Operational & Telemetry DB (CDB) --
    async def save_directive(
        self,
        caller: CallerIdentity,
        *,
        tenant_id: str,
        directive: Directive,
        session: Any = None,
    ) -> None:
        """Authorize and persist an operational directive."""
        self._authorize_tenant(caller, tenant_id, risk=RiskLevel.MEDIUM, requested_capability="mcp_data_write")
        self._assert_no_worker_access(caller)
        if self._operational_repository is not None:
            if session is not None:
                try:
                    await self._operational_repository.save_directive(directive, session=session)
                except TypeError:
                    await self._operational_repository.save_directive(directive)
            else:
                await self._operational_repository.save_directive(directive)
            await self._record_audit(
                tenant_id=tenant_id,
                entity_id=directive.directive_id,
                activity="mcp_data_directive_write",
                agent=caller.subject,
                session=session,
            )

    async def get_directive(
        self,
        caller: CallerIdentity,
        *,
        tenant_id: str,
        directive_id: str,
        session: Any = None,
    ) -> Directive | None:
        """Authorize and load an operational directive."""
        self._authorize_tenant(caller, tenant_id, requested_capability="mcp_data_read")
        self._assert_no_worker_access(caller)
        if self._operational_repository is not None:
            if session is not None:
                try:
                    d = await self._operational_repository.require(directive_id, session=session)
                except TypeError:
                    d = await self._operational_repository.require(directive_id)
            else:
                d = await self._operational_repository.require(directive_id)
            await self._record_audit(
                tenant_id=tenant_id,
                entity_id=directive_id,
                activity="mcp_data_directive_read",
                agent=caller.subject,
                session=session,
            )
            return d
        return None

    async def record_telemetry(
        self,
        caller: CallerIdentity,
        *,
        tenant_id: str,
        event: TelemetryEvent,
        session: Any = None,
    ) -> None:
        """Authorize and persist an omnichannel telemetry event."""
        self._authorize_tenant(caller, tenant_id, requested_capability="mcp_data_write")
        self._assert_no_worker_access(caller)
        if self._telemetry_repository is not None:
            if session is not None:
                try:
                    await self._telemetry_repository.record(event, session=session)
                except TypeError:
                    await self._telemetry_repository.record(event)
            else:
                await self._telemetry_repository.record(event)
            await self._record_audit(
                tenant_id=tenant_id,
                entity_id=event.event_id,
                activity="mcp_data_telemetry_write",
                agent=caller.subject,
                session=session,
            )

    async def list_telemetry(
        self,
        caller: CallerIdentity,
        *,
        tenant_id: str,
        event_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        session: Any = None,
    ) -> list[TelemetryEvent]:
        """Authorize and query omnichannel performance telemetry through the governed gateway."""
        self._authorize_tenant(caller, tenant_id, requested_capability="mcp_data_read")
        self._assert_no_worker_access(caller)
        if self._telemetry_repository is None:
            return []
        kwargs: dict[str, Any] = {}
        if session is not None:
            kwargs["session"] = session
        if (start_time is not None or end_time is not None) and hasattr(self._telemetry_repository, "query_range"):
            try:
                events = await self._telemetry_repository.query_range(
                    tenant_id,
                    start_time=start_time,
                    end_time=end_time,
                    event_type=event_type,
                    limit=limit,
                    **kwargs,
                )
            except TypeError:
                events = await self._telemetry_repository.query_range(
                    tenant_id,
                    start_time=start_time,
                    end_time=end_time,
                    event_type=event_type,
                    limit=limit,
                )
        elif event_type:
            try:
                events = await self._telemetry_repository.list_by_type(tenant_id, event_type, **kwargs)
            except TypeError:
                events = await self._telemetry_repository.list_by_type(tenant_id, event_type)
        else:
            try:
                events = await self._telemetry_repository.list_all(tenant_id, **kwargs)
            except TypeError:
                events = await self._telemetry_repository.list_all(tenant_id)
        await self._record_audit(
            tenant_id=tenant_id,
            entity_id=f"telemetry:{event_type or 'all'}",
            activity="mcp_data_telemetry_read",
            agent=caller.subject,
            session=session,
        )
        return events