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
