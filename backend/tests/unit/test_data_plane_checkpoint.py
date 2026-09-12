"""Unit tests for the Governed Data Plane & Central Storage Integration (Model A)."""

from __future__ import annotations

import pytest

from app.mcp.data_gateway import DataGateway
from app.orchestration.data_plane_checkpoint import (
    DataPlaneIntegrationValidator,
)
from app.orchestration.rag_query_dispatch import RagQueryDispatcher
from app.persistence.repositories.artifact import ArtifactReference, ArtifactRepository
from app.persistence.repositories.memory import MemoryRecord, MemoryRepository
from app.persistence.repositories.operational import OperationalRepository
from app.schemas.artifact import compute_content_hash
from app.schemas.cms import CmsPageModel
from app.schemas.governance import Directive, RiskLevel, TenantScope
from app.security.authorization_boundary import AuthorizationBoundary, CallerIdentity
from app.services.rag.controller import RagController
from app.services.rag.freshness import FreshnessPolicy
from app.services.rag.hybrid_retriever import HybridRetriever
from app.services.rag.schema_validator import SchemaValidator
from tests.conftest import FakeVectorRepository


class _InMemoryStore:
    def __init__(self) -> None:
        self.artifacts: dict[str, ArtifactReference] = {}
        self.memories: dict[str, list[MemoryRecord]] = {}
        self.directives: dict[str, Directive] = {}

    # Artifact repo mock
    async def register(self, tenant_id: str, artifact: ArtifactReference) -> None:
        self.artifacts[artifact.artifact_id] = artifact

    async def resolve(self, artifact_id: str) -> ArtifactReference:
        if artifact_id not in self.artifacts:
            raise KeyError(f"Artifact {artifact_id} not found")
        return self.artifacts[artifact_id]

    async def resolve_by_hash(self, content_hash: str, tenant_id: str | None = None) -> ArtifactReference | None:
        for art in self.artifacts.values():
            if art.content_hash == content_hash:
                if tenant_id is None or art.tenant_id == tenant_id:
                    return art
        return None

    # Memory repo mock
    async def promote(self, record: MemoryRecord) -> None:
        self.memories.setdefault(record.tenant_id, []).append(record)

    async def list_by_tenant(self, tenant_id: str, category: str | None = None, namespace: str | None = None) -> list[MemoryRecord]:
        recs = self.memories.get(tenant_id, [])
        if category:
            recs = [r for r in recs if r.category == category]
        if namespace:
            recs = [r for r in recs if r.namespace == namespace]
        return recs

    # Operational repo mock
    async def save_directive(self, directive: Directive) -> None:
        self.directives[directive.directive_id] = directive

    async def require(self, directive_id: str) -> Directive:
        if directive_id not in self.directives:
            raise KeyError(f"Directive {directive_id} not found")
        return self.directives[directive_id]


@pytest.fixture
def mock_data_plane():
    store = _InMemoryStore()
    vector_repo = FakeVectorRepository()
    from app.integrations.cms.client import CmsClient
    cms_client = CmsClient(base_url=None, api_key=None)

    gateway = DataGateway(
        vector_repository=vector_repo,
        authorization_boundary=AuthorizationBoundary(),
        operational_repository=store,  # type: ignore[arg-type]
        memory_repository=store,  # type: ignore[arg-type]
        artifact_repository=store,  # type: ignore[arg-type]
        cms_client=cms_client,
    )

    retriever = HybridRetriever(data_gateway=gateway)
    rag_controller = RagController(
        retriever=retriever,
        freshness_policy=FreshnessPolicy(),
        schema_validator=SchemaValidator(),
        data_gateway=gateway,
    )
    dispatcher = RagQueryDispatcher(rag_controller)

    return gateway, rag_controller, dispatcher, store


@pytest.mark.asyncio
async def test_data_plane_checkpoint_evaluates_all_15_conditions(mock_data_plane) -> None:
    gateway, rag_controller, dispatcher, store = mock_data_plane
    validator = DataPlaneIntegrationValidator(gateway, rag_controller, dispatcher)

    report = await validator.validate_checkpoint(tenant_id="tenant-cp-alpha", provenance_count=5)

    assert report.is_complete is True
    assert report.checkpoint_id == "M2_DATA_PLANE"
    assert len(report.results) == 15
    assert all(r.satisfied for r in report.results)


@pytest.mark.asyncio
async def test_artifact_hash_addressing_and_integrity_verification(mock_data_plane) -> None:
    gateway, _, _, _ = mock_data_plane
    tenant = "tenant-cp-alpha"
    caller = CallerIdentity(subject="ie", tenant_scope=TenantScope(tenant_id=tenant), risk_ceiling=RiskLevel.HIGH)

    content = "Final ad copy: Refresh your summer vibe."
    chash = compute_content_hash(content)

    art = ArtifactReference(
        artifact_id="art-copy-1",
        content_hash=chash,
        uri="enterprise://artifacts/art-copy-1",
        media_type="text/plain",
        deliverable_type="copy_pack",
        tenant_id=tenant,
    )

    await gateway.register_artifact(caller, tenant_id=tenant, artifact=art)
    assert art.verify_integrity(content) is True
    assert art.verify_integrity("Tampered copy text") is False

    resolved_by_hash = await gateway.resolve_artifact_by_hash(caller, tenant_id=tenant, content_hash=chash)
    assert resolved_by_hash is not None
    assert resolved_by_hash.artifact_id == "art-copy-1"


@pytest.mark.asyncio
async def test_cms_staging_and_diff_application(mock_data_plane) -> None:
    gateway, _, _, _ = mock_data_plane
    tenant = "tenant-cp-alpha"
    caller = CallerIdentity(subject="ie", tenant_scope=TenantScope(tenant_id=tenant), risk_ceiling=RiskLevel.HIGH)

    page_data = {"title": "Homepage", "slug": "home", "components": []}
    await gateway.stage_cms_entry(caller, tenant_id=tenant, content_type="pages", entry_id="page-1", data=page_data)

    staged = await gateway.read_cms_staged(caller, tenant_id=tenant, content_type="pages")
    assert len(staged) == 1
    assert staged[0]["title"] == "Homepage"

    diff_res = await gateway.apply_cms_changes(
        caller,
        tenant_id=tenant,
        content_type="pages",
        entry_id="page-1",
        diff={"title": "Updated Homepage Title"},
    )
    assert diff_res["status"] == "updated"

    staged_after = await gateway.read_cms_staged(caller, tenant_id=tenant, content_type="pages")
    assert staged_after[0]["title"] == "Updated Homepage Title"
