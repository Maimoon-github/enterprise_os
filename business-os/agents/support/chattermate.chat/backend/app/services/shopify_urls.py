"""
Copyright 2024-2026 ChatterMate

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

# Shop-scoped Shopify URLs. Every Admin API and OAuth call goes to the merchant's
# own host (`{shop}.myshopify.com`), so there is no single base to swap. When
# SHOPIFY_ADMIN_BASE is set (only the e2e suite does) the shop domain becomes a
# path segment under it instead: `{base}/{shop_domain}/admin/...`.

from app.core.external_urls import external_base

SHOPIFY_API_VERSION = "2025-10"
SHOPIFY_ADMIN_BASE = external_base("SHOPIFY_ADMIN_BASE", "")


def shopify_shop_url(shop_domain: str, path: str) -> str:
    """URL of `path` (no leading slash) on the shop's own host."""
    if SHOPIFY_ADMIN_BASE:
        return f"{SHOPIFY_ADMIN_BASE}/{shop_domain}/{path}"
    return f"https://{shop_domain}/{path}"


def shopify_admin_url(shop_domain: str, path: str) -> str:
    """Admin API URL, e.g. `shopify_admin_url(shop, "graphql.json")`."""
    return shopify_shop_url(shop_domain, f"admin/api/{SHOPIFY_API_VERSION}/{path}")


def shopify_oauth_token_url(shop_domain: str) -> str:
    """The shop's OAuth access-token endpoint (code and token exchange)."""
    return shopify_shop_url(shop_domain, "admin/oauth/access_token")
