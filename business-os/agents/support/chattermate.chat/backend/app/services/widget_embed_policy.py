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

Where a widget may be embedded.

A widget's `allowed_domains` list is enforced by the browser through the
`frame-ancestors` directive on the widget document. An empty list means the
widget can be embedded anywhere, localhost included. Our own surfaces (the
dashboard, help centers, Shopify admin) are always allowed, so a list never
locks the org out of its own previews.
"""

import re
from typing import Iterable, List, Optional
from urllib.parse import urlparse
from uuid import UUID

import idna
import tldextract
from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.help_center import HelpCenterRepository

MAX_ALLOWED_DOMAINS = 20
# Each entry becomes up to four sources; this keeps the whole header well inside
# a proxy's default response-header buffer
MAX_ALLOWED_DOMAINS_LENGTH = 800

# The dashboard runs embedded in Shopify admin. frame-ancestors checks every
# ancestor, so a storefront previewed in the theme editor still needs the shop's
# own domain in the list.
SHOPIFY_ADMIN_ORIGIN = "https://admin.shopify.com"

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1"})
_LABEL = r"(?!-)[a-z0-9-]{1,63}(?<!-)"
_HOST_RE = re.compile(rf"^(?:\*\.)?{_LABEL}(?:\.{_LABEL})*$")
# Anything that could end a CSP source list or start a new directive
_UNSAFE_IN_HEADER = re.compile(r"[\s;,'\"]")
_PORT_RE = re.compile(r"^[0-9]{1,5}$")  # ASCII only: str.isdigit() also takes "８０" and "²"
_MAX_DOMAIN_LENGTH = 253


class InvalidAllowedDomain(ValueError):
    """An allowed-domains entry that isn't a host name we can put in a header."""


# The bundled public suffix list (private section included, so github.io and
# myshopify.com count): no network fetch, no cache directory
_suffixes = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None, include_psl_private_domains=True)


def _shown(entry: object) -> str:
    """An entry as quoted back in an error: short, whatever was pasted."""
    text = str(entry)
    return repr(text if len(text) <= 60 else text[:57] + "...")


def _is_public_suffix(host: str) -> bool:
    """co.uk, com, github.io: names under which anyone can register a site."""
    return not _suffixes(host).domain


def _to_ascii(host: str) -> str:
    """Punycode an internationalised name the way browsers do (UTS #46, so
    `ß` stays `ß` rather than becoming `ss`); leave a leading `*.` alone."""
    prefix, name = ("*.", host[2:]) if host.startswith("*.") else ("", host)
    if name.isascii():
        return prefix + name
    try:
        return prefix + idna.encode(name, uts46=True, transitional=False).decode("ascii")
    except idna.IDNAError as exc:
        raise InvalidAllowedDomain(f"{_shown(host)} isn't a valid domain") from exc


def normalize_allowed_domain(entry: object) -> str:
    """`host[:port]` for one entry, accepting a pasted URL (scheme and path dropped)."""
    if not isinstance(entry, str):
        raise InvalidAllowedDomain(f"{_shown(entry)} isn't a valid domain")
    if len(entry) > _MAX_DOMAIN_LENGTH + 64:
        raise InvalidAllowedDomain(f"{_shown(entry)} is too long for a domain")
    raw = entry.strip().lower()
    if "://" in raw:
        raw = raw.split("://", 1)[1]
    raw = re.split(r"[/?#]", raw, 1)[0]
    if not raw or _UNSAFE_IN_HEADER.search(raw):
        raise InvalidAllowedDomain(f"{_shown(entry)} isn't a valid domain")

    host, _, port = raw.partition(":")
    host = _to_ascii(host)
    if len(host) > _MAX_DOMAIN_LENGTH or not _HOST_RE.match(host):
        raise InvalidAllowedDomain(f"{_shown(entry)} isn't a valid domain")
    if "." not in host and host not in _LOCAL_HOSTS:
        raise InvalidAllowedDomain(f"{_shown(entry)} needs a full domain, like example.com")
    if host.startswith("*.") and (host[2:] in _LOCAL_HOSTS or _is_public_suffix(host[2:])):
        # *.com or *.co.uk would allow every site there, which is what an empty list is for
        raise InvalidAllowedDomain(f"{_shown(entry)} is too broad for a wildcard")
    if port and not (_PORT_RE.match(port) and 0 < int(port) < 65536):
        raise InvalidAllowedDomain(f"{_shown(entry)} has an invalid port")

    return f"{host}:{port}" if port else host


def normalize_allowed_domains(entries: Iterable[object]) -> List[str]:
    """Validated, de-duplicated list, in the order given."""
    entries = list(entries or [])
    if len(entries) > MAX_ALLOWED_DOMAINS:
        raise InvalidAllowedDomain(f"At most {MAX_ALLOWED_DOMAINS} domains")
    seen: List[str] = []
    for entry in entries:
        domain = normalize_allowed_domain(entry)
        if domain not in seen:
            seen.append(domain)
    if len(seen) > MAX_ALLOWED_DOMAINS:
        raise InvalidAllowedDomain(f"At most {MAX_ALLOWED_DOMAINS} domains")
    if sum(len(d) for d in seen) > MAX_ALLOWED_DOMAINS_LENGTH:
        raise InvalidAllowedDomain("That's too many long domains; try a wildcard like *.example.com")
    return seen


def _entry_sources(entry: str) -> List[str]:
    """CSP sources for one stored entry, for both http and https embedders.

    A scheme-less source would only match https pages from an https frame, so
    each host gets both schemes. A plain domain also covers its www. twin, as
    CORS always has. Localhost without a port means any port.
    """
    host, _, port = entry.partition(":")
    if host.startswith("*.") or host in _LOCAL_HOSTS:
        hosts = [host]
    else:
        apex = host[len("www."):] if host.startswith("www.") else host
        hosts = [apex, f"www.{apex}"]
    suffix = f":{port}" if port else (":*" if host in _LOCAL_HOSTS else "")
    return [f"{scheme}://{h}{suffix}" for h in hosts for scheme in ("https", "http")]


def origin_of(url: str) -> Optional[str]:
    """`scheme://host[:port]` of a URL, or None unless it's an http(s) origin
    with a real host name (it may end up in a header, or an email)."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc or "@" in parsed.netloc:
        return None
    try:
        host = (parsed.hostname or "").lower()
        port = parsed.port
    except ValueError:
        return None
    if not _HOST_RE.match(host):
        return None
    origin = f"{parsed.scheme}://{host}" + (f":{port}" if port else "")
    return None if _UNSAFE_IN_HEADER.search(origin) else origin


def _always_allowed(db: Session, organization_id: Optional[UUID]) -> List[str]:
    """Our own surfaces that embed the widget, whatever the org's list says."""
    # CORS_ORIGINS is deliberately not here: self-hosters list customer sites
    # there too, and those must still obey a widget's own list. Nor is 'self':
    # the frame host serves other orgs' widget pages, which must not frame this
    # one (path-mode help centres live on BACKEND_URL, listed below).
    sources = [SHOPIFY_ADMIN_ORIGIN]
    for url in [settings.FRONTEND_URL, settings.BACKEND_URL]:
        origin = origin_of(url)
        if origin:
            sources.append(origin)

    base = settings.HELP_CENTER_BASE_DOMAIN
    if base and not _UNSAFE_IN_HEADER.search(base):
        dev_port = urlparse(settings.BACKEND_URL).port
        for scheme in ("https", "http"):
            sources.append(f"{scheme}://*.{base}")
            if dev_port:
                sources.append(f"{scheme}://*.{base}:{dev_port}")

    if organization_id:
        help_center = HelpCenterRepository(db).get_by_org(organization_id)
        domain = (help_center.custom_domain or "").lower() if help_center and help_center.domain_verified else ""
        if domain and not domain.startswith("*.") and _HOST_RE.match(domain):
            sources += [f"https://{domain}", f"http://{domain}"]
    return sources


def frame_ancestors(db: Session, allowed_domains: Optional[List[str]], organization_id: Optional[UUID]) -> Optional[str]:
    """The `frame-ancestors` directive for a widget, or None when it may be embedded anywhere.

    No directive (rather than `*`) for an empty list: `*` would still refuse
    file: and other opaque ancestors such as mobile webviews.
    """
    if not allowed_domains:
        return None
    sources = _always_allowed(db, organization_id)
    for entry in allowed_domains:
        # Re-checked on the way out: a row edited by hand must neither reach
        # the header nor take the widget down for every embed
        try:
            sources += _entry_sources(normalize_allowed_domain(entry))
        except Exception:
            continue
    return "frame-ancestors " + " ".join(dict.fromkeys(sources))


def _source_matches(source: str, scheme: str, host: str, port: Optional[int]) -> bool:
    """Whether a `scheme://host[:port]` source (as built above) covers an origin."""
    src_scheme, _, rest = source.partition("://")
    src_host, _, src_port = rest.partition(":")
    if src_scheme != scheme:
        return False
    if src_host.startswith("*."):
        if not host.endswith(src_host[1:]):
            return False
    elif src_host != host:
        return False
    if src_port == "*":
        return True
    default = 443 if scheme == "https" else 80
    return (int(src_port) if src_port else default) == (port or default)


def allows_embedder(db: Session, allowed_domains: Optional[List[str]], organization_id: Optional[UUID],
                    embedder_origin: str) -> bool:
    """Whether the browser would let `embedder_origin` frame the widget.

    For telling the org where its widget was refused; the header itself is the
    enforcement. Mirrors frame_ancestors().
    """
    return directive_allows(frame_ancestors(db, allowed_domains, organization_id), embedder_origin)


def directive_allows(directive: Optional[str], embedder_origin: str) -> bool:
    """Whether a frame_ancestors() directive (None: anywhere) lets `embedder_origin` frame the widget."""
    if directive is None:
        return True
    try:
        parsed = urlparse(embedder_origin)
        scheme, host, port = parsed.scheme, (parsed.hostname or "").lower(), parsed.port
    except ValueError:
        return False
    sources = directive.split()[1:]
    return any(_source_matches(s, scheme, host, port) for s in sources if "://" in s)


def frame_document_csp(nonce: str, connect_origins: Iterable[str], ancestors: Optional[str],
                       assets_url: Optional[str] = None) -> str:
    """Content-Security-Policy for the framed widget document.

    The widget only talks to its own API and socket, loads its bundle from
    `assets_url` (its /assets/ folder) and fonts from Google; everything else a
    script could reach for is closed. Scripts are held to that folder rather
    than the whole origin: without a separate frame host it is the API's own,
    and nothing else served there may run as the widget. Styles stay
    inline-able for the theme and font loader.
    """
    connect = " ".join(dict.fromkeys(o for o in connect_origins if o and not _UNSAFE_IN_HEADER.search(o)))
    assets = assets_url if assets_url and not _UNSAFE_IN_HEADER.search(assets_url) else "'self'"
    directives = [
        "default-src 'self'",
        f"script-src {assets} 'nonce-{nonce}'",
        f"style-src {assets} 'unsafe-inline' https://fonts.googleapis.com",
        "font-src 'self' data: https://fonts.gstatic.com",
        "img-src * data: blob:",
        "media-src * data: blob:",
        f"connect-src 'self' {connect}".rstrip(),
        "frame-src https:",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'self'",
    ]
    if ancestors:
        directives.append(ancestors)
    return "; ".join(directives)
