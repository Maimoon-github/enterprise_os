"""CMS content models, schemas, and staging contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class CmsContentType(StrEnum):
    PAGE = "pages"
    POST = "posts"
    PRODUCT = "products"
    LAYOUT = "layouts"
    COMPONENT = "components"
    ASSET = "assets"


class CmsPublishState(StrEnum):
    DRAFT = "draft"
    STAGED = "staged"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class CmsComponent(BaseModel):
    """Reusable UI/content component model."""

    component_id: str
    name: str
    component_type: str
    props: dict[str, Any] = Field(default_factory=dict)


class CmsPageModel(BaseModel):
    """Structured page model containing layouts, metadata, and components."""

    page_id: str
    tenant_id: str
    slug: str
    title: str
    layout_id: str = "default"
    components: list[CmsComponent] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
    publish_state: CmsPublishState = CmsPublishState.STAGED
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CmsProductModel(BaseModel):
    """Catalog product object with pricing, assets, and staging status."""

    product_id: str
    tenant_id: str
    sku: str
    title: str
    description: str = ""
    price: float = Field(ge=0.0)
    currency: str = "USD"
    categories: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)
    publish_state: CmsPublishState = CmsPublishState.STAGED
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CmsAssetModel(BaseModel):
    """Digital asset reference with content hash and storage pointer."""

    asset_id: str
    tenant_id: str
    filename: str
    mime_type: str
    storage_uri: str
    content_hash: str
    size_bytes: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ===========================================================================
# DE-07 CMS Schema, Contract, Migration & Deliverable Specifications
# ===========================================================================

import hashlib
import json
from typing import Literal
import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CmsFieldType(StrEnum):
    """Supported CMS content model primitive and composite field types."""

    STRING = "string"
    TEXT = "text"
    RICHTEXT = "richtext"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    JSON = "json"
    REFERENCE = "reference"
    MEDIA = "media"
    ARRAY = "array"
    OBJECT = "object"


class CmsFieldDefinition(BaseModel):
    """Detailed definition of an individual field within a CMS content model."""

    name: str
    field_type: str = CmsFieldType.STRING.value
    required: bool = False
    default_value: Any = None
    description: str = ""
    label: str = ""
    max_length: int | None = None
    min_length: int | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    relation_target: str | None = None
    localized: bool = False
    is_indexed: bool = False

    def to_json_schema_property(self) -> dict[str, Any]:
        """Convert this field definition into a JSON Schema Draft 2020-12 property snippet."""
        type_mapping = {
            "string": "string",
            "text": "string",
            "richtext": "string",
            "integer": "integer",
            "number": "number",
            "boolean": "boolean",
            "date": "string",
            "datetime": "string",
            "json": "object",
            "reference": "string",
            "media": "string",
            "array": "array",
            "object": "object",
        }
        json_type = type_mapping.get(self.field_type.lower(), "string")
        prop: dict[str, Any] = {"type": json_type}
        if self.description:
            prop["description"] = self.description
        elif self.label:
            prop["description"] = self.label
        if self.default_value is not None:
            prop["default"] = self.default_value
        if self.field_type.lower() == "date":
            prop["format"] = "date"
        elif self.field_type.lower() == "datetime":
            prop["format"] = "date-time"
        elif self.field_type.lower() == "reference":
            prop["format"] = "uri"
            if self.relation_target:
                prop["x-relation-target"] = self.relation_target

        if self.max_length is not None:
            prop["maxLength"] = self.max_length
        if self.min_length is not None:
            prop["minLength"] = self.min_length

        for k, v in self.constraints.items():
            if k in ("minLength", "maxLength", "pattern", "minimum", "maximum", "enum", "minItems", "maxItems"):
                prop[k] = v
            elif k == "min_length":
                prop["minLength"] = v
            elif k == "max_length":
                prop["maxLength"] = v

        return prop


class CmsContentModelSchema(BaseModel):
    """Provider-agnostic CMS Content Model Schema specification."""

    model_name: str = "ContentModel"
    content_type: str = "pages"
    version: str = "1.0.0"
    description: str = ""
    tenant_id: str = ""
    fields: list[CmsFieldDefinition] = Field(default_factory=list)
    primary_key: str = "id"
    indexes: list[str] = Field(default_factory=list)
    relationships: list[dict[str, Any]] = Field(default_factory=list)

    @property
    def schema_id(self) -> str:
        return self.model_name

    @property
    def name(self) -> str:
        return self.model_name

    @model_validator(mode="before")
    @classmethod
    def _normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            d = dict(data)
            if "model_name" not in d:
                d["model_name"] = d.get("schema_id") or d.get("name") or "ContentModel"
            return d
        return data


    def to_json_schema_draft_2020_12(self) -> dict[str, Any]:
        """Export this content model to authoritative JSON Schema Draft 2020-12 representation."""
        properties: dict[str, Any] = {
            self.primary_key: {"type": "string", "description": "Primary unique identifier"}
        }
        required_fields: list[str] = [self.primary_key]

        for f in self.fields:
            properties[f.name] = f.to_json_schema_property()
            if f.required:
                required_fields.append(f.name)

        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"https://schemas.enterprise-os.internal/cms/{self.model_name.lower()}.json",
            "title": self.model_name,
            "description": self.description or f"CMS content model schema for {self.model_name}",
            "type": "object",
            "properties": properties,
            "required": sorted(list(set(required_fields))),
            "additionalProperties": False,
        }

    def to_typescript_interface(self) -> str:
        """Generate TypeScript interface definition for the schema."""
        ts_types = {
            "string": "string",
            "text": "string",
            "integer": "number",
            "number": "number",
            "boolean": "boolean",
            "date": "string",
            "datetime": "string",
            "json": "Record<string, unknown>",
            "reference": "string",
            "media": "string",
            "array": "Array<unknown>",
            "object": "Record<string, unknown>",
        }
        interface_name = "".join(part.capitalize() for part in self.model_name.replace("-", "_").split("_")) if ("_" in self.model_name or "-" in self.model_name) else self.model_name
        lines = [f"export interface {interface_name} {{"]
        lines.append(f"  {self.primary_key}: string;")
        for f in self.fields:
            opt = "" if f.required else "?"
            t = ts_types.get(f.field_type.lower(), "string")
            lines.append(f"  {f.name}{opt}: {t};")
        lines.append("}")
        return "\n".join(lines)

    def to_openapi_3_1_schema(self) -> dict[str, Any]:
        """Export this content model to OpenAPI 3.1.0 schema specification."""
        json_schema = self.to_json_schema_draft_2020_12()
        return {
            "openapi": "3.1.0",
            "info": {
                "title": f"{self.model_name} CMS API",
                "version": self.version,
                "description": self.description or f"OpenAPI 3.1 specification for CMS model {self.model_name}",
            },
            "components": {
                "schemas": {
                    self.model_name: {
                        "type": "object",
                        "description": json_schema.get("description", ""),
                        "properties": json_schema.get("properties", {}),
                        "required": json_schema.get("required", []),
                    }
                }
            },
        }

    def to_graphql_sdl(self) -> str:
        """Export this content model to standard GraphQL Schema Definition Language (SDL)."""
        gql_types = {
            "string": "String",
            "text": "String",
            "richtext": "String",
            "integer": "Int",
            "number": "Float",
            "boolean": "Boolean",
            "date": "String",
            "datetime": "String",
            "json": "JSON",
            "reference": "ID",
            "media": "String",
            "array": "[String]",
            "object": "JSON",
        }
        type_name = "".join(part.capitalize() for part in self.model_name.replace("-", "_").split("_")) if ("_" in self.model_name or "-" in self.model_name) else self.model_name
        lines = [f"\"\"\"{self.description or f'GraphQL type for {type_name}'}\"\"\""]
        lines.append(f"type {type_name} {{")
        lines.append(f"  {self.primary_key}: ID!")
        for f in self.fields:
            t = gql_types.get(f.field_type.lower(), "String")
            bang = "!" if f.required else ""
            lines.append(f"  {f.name}: {t}{bang}")
        lines.append("}")
        return "\n".join(lines)


class CmsChangeClassification(StrEnum):
    """Backward compatibility risk classification for CMS schema changes."""

    ADDITIVE = "ADDITIVE"
    COMPATIBLE = "COMPATIBLE"
    POTENTIALLY_BREAKING = "POTENTIALLY_BREAKING"
    BREAKING = "BREAKING"


class CmsFieldDiff(BaseModel):
    """Detailed diff for an individual schema field."""

    field_name: str
    change_type: Literal["added", "removed", "modified", "unchanged"]
    old_definition: CmsFieldDefinition | None = None
    new_definition: CmsFieldDefinition | None = None
    classification: CmsChangeClassification = CmsChangeClassification.COMPATIBLE
    reason: str = ""


class CmsDetailedSchemaDiff(BaseModel):
    """Comprehensive, structured schema diff between base and candidate schemas."""

    model_name: str = ""
    base_version: str = "1.0.0"
    target_version: str = "1.1.0"
    field_diffs: list[CmsFieldDiff] = Field(default_factory=list)
    overall_classification: CmsChangeClassification = CmsChangeClassification.ADDITIVE
    breaking_changes: list[str] = Field(default_factory=list)
    data_loss_risks: list[str] = Field(default_factory=list)
    is_backward_compatible: bool = True
    unified_diff: str = ""

    @property
    def added_fields(self) -> list[CmsFieldDefinition]:
        return [d.new_definition for d in self.field_diffs if d.change_type == "added" and d.new_definition is not None]

    @property
    def removed_fields(self) -> list[CmsFieldDefinition]:
        return [d.old_definition for d in self.field_diffs if d.change_type == "removed" and d.old_definition is not None]

    @property
    def modified_fields(self) -> list[CmsFieldDiff]:
        return [d for d in self.field_diffs if d.change_type == "modified"]


    def to_deliverable_diff(self) -> dict[str, Any]:
        """Map to standard DevelopmentDeliverable CmsSchemaDiff format."""
        added = [
            {"name": d.field_name, "type": d.new_definition.field_type if d.new_definition else "string"}
            for d in self.field_diffs if d.change_type == "added"
        ]
        modified = [
            {"name": d.field_name, "change": d.reason}
            for d in self.field_diffs if d.change_type in ("modified", "removed")
        ]
        return {
            "schema_name": self.model_name,
            "target_content_type": "pages",
            "operation": "schema_evolution",
            "added_fields": added,
            "modified_fields": modified,
            "validation_rules": [f"Classification: {self.overall_classification}"],
            "is_backward_compatible": self.is_backward_compatible,
        }


class CmsMigrationPhase(StrEnum):
    """Ordered phases for safe, zero-downtime expand-contract schema evolution."""

    DIRECT_APPLY = "direct_apply"
    EXPAND = "expand"
    MIGRATE_BACKFILL = "migrate_backfill"
    VALIDATE = "validate"
    CONTRACT = "contract"


class CmsMigrationStep(BaseModel):
    """An individual migration step with forward (up) and rollback (down) directives."""

    step_number: int = 1
    phase: CmsMigrationPhase = CmsMigrationPhase.EXPAND
    description: str = ""
    operation: str = ""
    up_script: str = ""
    down_script: str = ""
    is_reversible: bool = True
    data_loss_risk: bool = False


class CmsMigrationPlan(BaseModel):
    """Ordered, phased migration plan with safety and rollback guarantees."""

    migration_id: str = Field(default_factory=lambda: f"mig-{uuid.uuid4().hex[:8]}")
    model_name: str = ""
    from_version: str = "1.0.0"
    to_version: str = "1.1.0"
    strategy: Literal["DIRECT_APPLY", "EXPAND_CONTRACT", "MANUAL_INTERVENTION_REQUIRED"] = "DIRECT_APPLY"
    steps: list[CmsMigrationStep] = Field(default_factory=list)
    rollback_steps: list[CmsMigrationStep] = Field(default_factory=list)
    is_reversible: bool = True
    safety_precautions: list[str] = Field(default_factory=list)
    estimated_impact: str = "low"

    @property
    def is_expand_contract(self) -> bool:
        return self.strategy == "EXPAND_CONTRACT" or any(
            s.phase in (CmsMigrationPhase.EXPAND, CmsMigrationPhase.CONTRACT) for s in self.steps
        )


class CmsCompatibilityReport(BaseModel):
    """Detailed backward-compatibility analysis report."""

    is_compatible: bool = True
    classification: CmsChangeClassification = CmsChangeClassification.ADDITIVE
    breaking_changes: list[str] = Field(default_factory=list)
    field_conflicts: list[str] = Field(default_factory=list)
    data_loss_warnings: list[str] = Field(default_factory=list)
    remediation_suggestions: list[str] = Field(default_factory=list)

    @property
    def is_breaking(self) -> bool:
        return (
            not self.is_compatible
            or len(self.breaking_changes) > 0
            or self.classification in (CmsChangeClassification.BREAKING, CmsChangeClassification.POTENTIALLY_BREAKING)
        )

    @property
    def dropped_fields(self) -> list[str]:
        return [b for b in self.breaking_changes if "dropped" in b.lower() or "removed" in b.lower()]


class CmsValidationEvidence(BaseModel):
    """Validation findings from AST, JSON Schema, constraint, and simulated run."""

    syntax_valid: bool = True
    json_schema_valid: bool = True
    references_resolved: bool = True
    constraints_valid: bool = True
    migration_reversible: bool = True
    simulated_success: bool = True
    confidence: float = 0.95
    findings: list[str] = Field(default_factory=list)

    @property
    def ast_valid(self) -> bool:
        return self.syntax_valid

    @property
    def migration_simulated(self) -> bool:
        return self.simulated_success

    @property
    def rollback_simulated(self) -> bool:
        return self.migration_reversible and self.simulated_success


class CmsCandidateDeliverable(BaseModel):
    """Complete sealed deliverable produced by DEV-CMS for DE-04 HITL review."""

    candidate_id: str
    task_id: str
    workflow_id: str
    attempt_id: str = "att-1"
    schemas: list[CmsContentModelSchema] = Field(default_factory=list)
    schema_diffs: list[CmsDetailedSchemaDiff] = Field(default_factory=list)
    contracts: dict[str, dict[str, Any]] = Field(default_factory=dict)
    generated_types: dict[str, str] = Field(default_factory=dict)
    migration_plan: CmsMigrationPlan | None = None
    compatibility_report: CmsCompatibilityReport
    validation_evidence: CmsValidationEvidence
    candidate_hash: str = ""
    rejection_feedback: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)

    @property
    def schema_definition(self) -> CmsContentModelSchema:
        return self.schemas[0] if self.schemas else CmsContentModelSchema(model_name="", fields=[])

    @property
    def detailed_diff(self) -> CmsDetailedSchemaDiff:
        return self.schema_diffs[0] if self.schema_diffs else CmsDetailedSchemaDiff(model_name="")

    @property
    def change_classification(self) -> CmsChangeClassification:
        return self.compatibility_report.classification

    @property
    def json_schema_draft_2020_12(self) -> dict[str, Any]:
        return self.contracts.get("json_schema_draft_2020_12") or {}

    @property
    def typescript_interfaces(self) -> str:
        return self.generated_types.get("typescript", "")

    @property
    def openapi_schema(self) -> dict[str, Any]:
        return self.contracts.get("openapi_3_1") or {}

    @property
    def graphql_sdl(self) -> str:
        return self.generated_types.get("graphql_sdl") or ""

    def canonical_bytes(self) -> bytes:
        """Return deterministic JSON-serialized byte representation of candidate deliverable."""
        canonical_schemas = [
            {
                "model_name": s.model_name,
                "content_type": s.content_type,
                "version": s.version,
                "fields": [
                    {
                        "name": f.name,
                        "type": f.field_type,
                        "required": f.required,
                        "default": str(f.default_value),
                        "constraints": f.constraints,
                    }
                    for f in s.fields
                ],
            }
            for s in sorted(self.schemas, key=lambda x: x.model_name)
        ]
        canonical_diffs = [
            {
                "model_name": d.model_name,
                "classification": d.overall_classification.value,
                "is_backward_compatible": d.is_backward_compatible,
                "breaking_changes": sorted(d.breaking_changes),
                "data_loss_risks": sorted(d.data_loss_risks),
                "field_diffs_count": len(d.field_diffs),
            }
            for d in sorted(self.schema_diffs, key=lambda x: x.model_name)
        ]
        payload = {
            "attempt_id": self.attempt_id,
            "candidate_id": self.candidate_id,
            "compatibility": {
                "classification": self.compatibility_report.classification.value,
                "is_compatible": self.compatibility_report.is_compatible,
                "breaking_changes": sorted(self.compatibility_report.breaking_changes),
            },
            "contracts_keys": sorted(list(self.contracts.keys())),
            "schema_diffs": canonical_diffs,
            "schemas": canonical_schemas,
            "task_id": self.task_id,
            "validation": {
                "syntax_valid": self.validation_evidence.syntax_valid,
                "json_schema_valid": self.validation_evidence.json_schema_valid,
                "simulated_success": self.validation_evidence.simulated_success,
            },
            "workflow_id": self.workflow_id,
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def compute_candidate_hash(self) -> str:
        """Compute tamper-evident SHA-256 digest over canonical deliverable bytes."""
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


