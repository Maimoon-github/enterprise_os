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

Pages that ask for a password are not knowledge: a store's admin, a site's
sign-in page, or a Shopify store that isn't open to visitors yet (its "Opening
soon" page). Storing one teaches the agent a login form, and following links
into them only reaches more of the same.
"""

from typing import Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

# Paths that are sign-in or admin areas, with everything under them
AUTH_PATHS = (
    "account/login",
    "account/register",
    "log-in",
    "login",
    "password",
    "sign-in",
    "signin",
    "user/login",
    "wp-admin",
    "wp-login.php",
)
# Sign-in or admin only as the whole path: docs.x.com/admin/configure-sso is a
# public page. On a Shopify store everything under /admin is the admin.
EXACT_AUTH_PATHS = ("admin", "auth")
SHOPIFY_STORE_SUFFIX = ".myshopify.com"

# Shopify's "store isn't open yet" page, in any theme: its password form carries
# this hidden field (current themes put the password box itself in a dialog,
# which would otherwise read as a site's login modal)
SHOPIFY_STOREFRONT_PASSWORD = {"name": "form_type", "value": "storefront_password"}

# Where sites keep a login box on every page; one there says nothing about the
# page's own content
SITE_CHROME = ("header", "nav", "footer", "dialog", "aside")

# Said when someone adds one, so they can fix it right away
AUTH_URL_MESSAGE = (
    "That's a sign-in or admin page, which needs a login. Enter your site's "
    "public address instead, like yourstore.com."
)

# A sign-in page has a password box and little else. A real page with a login
# box in its header still has plenty to read, and stays.
MAX_TEXT_ON_A_LOGIN_PAGE = 1000


def is_auth_path(url: str) -> bool:
    """Whether the URL is a sign-in or admin area (by its path)."""
    parsed = urlparse(url)
    path = parsed.path.strip("/").lower()
    if any(path == auth or path.startswith(f"{auth}/") for auth in AUTH_PATHS):
        return True
    if (parsed.hostname or "").endswith(SHOPIFY_STORE_SUFFIX):
        return any(path == auth or path.startswith(f"{auth}/") for auth in EXACT_AUTH_PATHS)
    return path in EXACT_AUTH_PATHS


def _in_site_chrome(tag: Tag) -> bool:
    """Inside the header/nav/footer/a dialog, or hidden: a login box every page has."""
    return any(
        parent.name in SITE_CHROME or parent.has_attr("hidden") or parent.get("aria-hidden") == "true"
        for parent in [tag, *tag.parents] if isinstance(parent, Tag)
    )


def asks_for_a_password(soup: BeautifulSoup) -> bool:
    """Whether the page's own content (not its header login box) has a password field."""
    boxes = soup.find_all("input", attrs={"type": lambda kind: (kind or "").lower() == "password"})
    return any(not _in_site_chrome(box) for box in boxes)


def is_shopify_password_page(soup: BeautifulSoup) -> bool:
    """Whether this is a Shopify store's "isn't open yet" password page."""
    return soup.find("input", attrs=SHOPIFY_STOREFRONT_PASSWORD) is not None


def looks_like_login_wall(url: str, text: Optional[str], *pages: BeautifulSoup) -> bool:
    """Whether the page asks for a password instead of showing content. The
    URL alone can't tell when a site redirects there (a Shopify store that
    isn't open sends its homepage to /password), so the page is checked too:
    every version of it given, since a browser-rendered copy comes back
    cleaned of its forms."""
    if is_auth_path(url):
        return True
    if any(is_shopify_password_page(page) for page in pages):
        return True
    return any(asks_for_a_password(page) for page in pages) and len(text or "") < MAX_TEXT_ON_A_LOGIN_PAGE
