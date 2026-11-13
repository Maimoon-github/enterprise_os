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

A widget's allowed domains: what's accepted, and the frame-ancestors it becomes.
"""

import pytest

from app.models.help_center import HelpCenterSettings
from app.services import widget_embed_policy as policy
from app.services.widget_embed_policy import InvalidAllowedDomain


@pytest.fixture
def own_origins(monkeypatch):
    monkeypatch.setattr(policy.settings, "FRONTEND_URL", "https://app.example.com")
    monkeypatch.setattr(policy.settings, "BACKEND_URL", "https://api.example.com")
    monkeypatch.setattr(policy.settings, "CORS_ORIGINS", ["https://dashboard.selfhost.example"])
    monkeypatch.setattr(policy.settings, "HELP_CENTER_BASE_DOMAIN", "help.example")


class TestNormalize:
    @pytest.mark.parametrize("typed, stored", [
        ("acme.com", "acme.com"),
        ("  ACME.com  ", "acme.com"),
        ("https://www.acme.com/pricing?x=1#top", "www.acme.com"),
        ("shop.acme.co.uk:8443", "shop.acme.co.uk:8443"),
        ("*.acme.com", "*.acme.com"),
        ("*.acme.co.uk", "*.acme.co.uk"),
        ("*.acme.github.io", "*.acme.github.io"),
        ("localhost", "localhost"),
        ("http://localhost:3000/", "localhost:3000"),
        ("127.0.0.1:5173", "127.0.0.1:5173"),
        ("bücher.de", "xn--bcher-kva.de"),
        ("faße.de", "xn--fae-6ka.de"),  # UTS #46, as browsers encode it (not fasse.de)
    ])
    def test_accepts(self, typed, stored):
        assert policy.normalize_allowed_domain(typed) == stored

    @pytest.mark.parametrize("typed", [
        "",
        "   ",
        "acme.com; script-src *",
        "acme.com other.com",
        "acme.com,other.com",
        "'self'",
        '"acme.com"',
        "intranet",
        "*.localhost",
        "acme.com:0",
        "acme.com:99999",
        "acme.com:http",
        "-acme.com",
        "acme..com",
        "a" * 64 + ".com",
        "*",
        "*.*.acme.com",
        "*.com",
        "*.co.uk",       # public suffixes: every site registered under them
        "*.com.au",
        "*.github.io",
        "*.myshopify.com",
        "acme.com:\uff18\uff10",
        "acme.com:\u00b2",
        "a" * 300 + ".com",
    ])
    def test_refuses(self, typed):
        with pytest.raises(InvalidAllowedDomain):
            policy.normalize_allowed_domain(typed)

    @pytest.mark.parametrize("typed, message", [
        ("*.co.uk", "is too broad for a wildcard"),
        ("a" * 400 + ".com", "is too long for a domain"),
        ("x " * 100, "isn't a valid domain"),
    ])
    def test_errors_quote_the_entry_briefly(self, typed, message):
        with pytest.raises(InvalidAllowedDomain) as refused:
            policy.normalize_allowed_domain(typed)
        assert message in str(refused.value)
        assert len(str(refused.value)) < 120

    def test_list_is_deduplicated_in_order(self):
        assert policy.normalize_allowed_domains(["B.com", "a.com", "https://b.com/"]) == ["b.com", "a.com"]

    @pytest.mark.parametrize("not_text", [123, None, ["acme.com"]])
    def test_refuses_anything_but_text(self, not_text):
        with pytest.raises(InvalidAllowedDomain):
            policy.normalize_allowed_domain(not_text)

    def test_list_is_capped(self):
        too_many = [f"site{i}.com" for i in range(policy.MAX_ALLOWED_DOMAINS + 1)]
        with pytest.raises(InvalidAllowedDomain):
            policy.normalize_allowed_domains(too_many)

    def test_the_whole_list_has_a_size_budget(self):
        long_ones = [f"{'a' * 60}{i}.example.com" for i in range(15)]
        with pytest.raises(InvalidAllowedDomain):
            policy.normalize_allowed_domains(long_ones)

    def test_the_largest_list_allowed_fits_a_proxy_header_buffer(self, db, own_origins):
        domains, i = [], 0
        while sum(len(d) for d in domains) < policy.MAX_ALLOWED_DOMAINS_LENGTH - 60 and len(domains) < policy.MAX_ALLOWED_DOMAINS:
            domains.append(f"{'a' * 30}{i}.example.com")
            i += 1
        policy.normalize_allowed_domains(domains)
        assert len(policy.frame_ancestors(db, domains, None)) < 4096

    def test_one_bad_entry_refuses_the_list(self):
        with pytest.raises(InvalidAllowedDomain):
            policy.normalize_allowed_domains(["good.com", "bad domain"])


class TestFrameAncestors:
    def test_empty_list_means_anywhere(self, db):
        assert policy.frame_ancestors(db, [], None) is None
        assert policy.frame_ancestors(db, None, None) is None

    def test_plain_domain_covers_www_on_both_schemes(self, db, own_origins):
        directive = policy.frame_ancestors(db, ["acme.com"], None)
        for source in ("https://acme.com", "http://acme.com", "https://www.acme.com", "http://www.acme.com"):
            assert f" {source}" in directive

    def test_www_entry_also_covers_the_apex(self, db, own_origins):
        assert " https://acme.com" in policy.frame_ancestors(db, ["www.acme.com"], None)

    def test_wildcard_stays_a_wildcard(self, db, own_origins):
        directive = policy.frame_ancestors(db, ["*.acme.com"], None)
        assert " https://*.acme.com" in directive
        assert "www.*" not in directive

    def test_localhost_without_a_port_is_any_port(self, db, own_origins):
        directive = policy.frame_ancestors(db, ["localhost"], None)
        assert " http://localhost:*" in directive
        assert " https://localhost:*" in directive

    def test_a_typed_port_is_kept(self, db, own_origins):
        directive = policy.frame_ancestors(db, ["localhost:3000", "shop.acme.com:8443"], None)
        assert " http://localhost:3000" in directive
        assert " https://shop.acme.com:8443" in directive
        assert "localhost:*" not in directive

    def test_our_own_surfaces_are_always_allowed(self, db, own_origins):
        directive = policy.frame_ancestors(db, ["acme.com"], None)
        assert directive.startswith("frame-ancestors ")
        # not 'self': the frame host serves other orgs' widget pages
        assert "'self'" not in directive
        for source in (
            "https://admin.shopify.com",
            "https://app.example.com",
            "https://api.example.com",
            "https://*.help.example",
        ):
            assert f" {source}" in directive

    def test_sites_listed_for_cors_still_obey_the_list(self, db, own_origins):
        assert "dashboard.selfhost.example" not in policy.frame_ancestors(db, ["acme.com"], None)

    def test_the_orgs_verified_help_center_domain_is_allowed(self, db, own_origins, test_organization):
        db.add(HelpCenterSettings(
            organization_id=test_organization.id,
            custom_domain="support.acme.com",
            txt_record_verified=True,
            cname_record_verified=True,
        ))
        db.commit()
        assert " https://support.acme.com" in policy.frame_ancestors(db, ["acme.com"], test_organization.id)

    def test_an_unverified_help_center_domain_is_not(self, db, own_origins, test_organization):
        db.add(HelpCenterSettings(
            organization_id=test_organization.id,
            custom_domain="support.acme.com",
            txt_record_verified=True,
            cname_record_verified=False,
        ))
        db.commit()
        assert "support.acme.com" not in policy.frame_ancestors(db, ["acme.com"], test_organization.id)

    @pytest.mark.parametrize("domain", [None, "", "support.acme.com evil.com", "*.acme.com"])
    def test_a_verified_help_center_row_without_a_usable_domain_adds_nothing(self, db, own_origins,
                                                                           test_organization, domain):
        db.add(HelpCenterSettings(
            organization_id=test_organization.id,
            custom_domain=domain,
            txt_record_verified=True,
            cname_record_verified=True,
        ))
        db.commit()
        directive = policy.frame_ancestors(db, ["acme.com"], test_organization.id)
        assert "evil.com" not in directive and "*.acme.com" not in directive and "None" not in directive

    def test_a_hand_edited_bad_row_never_reaches_the_header(self, db, own_origins):
        directive = policy.frame_ancestors(db, ["acme.com; script-src *", "good.com"], None)
        assert ";" not in directive
        assert "script-src" not in directive
        assert " https://good.com" in directive

    def test_an_unsafe_configured_origin_is_skipped(self, db, own_origins, monkeypatch):
        monkeypatch.setattr(policy.settings, "FRONTEND_URL", "https://bad.example; x")
        directive = policy.frame_ancestors(db, ["acme.com"], None)
        assert " https://api.example.com" in directive
        assert "bad.example" not in directive

    def test_no_duplicate_sources(self, db, own_origins):
        sources = policy.frame_ancestors(db, ["acme.com", "www.acme.com"], None).split()
        assert len(sources) == len(set(sources))


class TestOriginOf:
    @pytest.mark.parametrize("url, origin", [
        ("https://Shop.Example.com/page?x=1", "https://shop.example.com"),
        ("http://localhost:3000/", "http://localhost:3000"),
        ("https://<svg>.example", None),
        ("https://a<b>c.com", None),
        ("https://user@evil.example", None),
        ("javascript:alert(1)", None),
        ("https://", None),
        ("", None),
    ])
    def test_only_real_origins(self, url, origin):
        assert policy.origin_of(url) == origin


class TestAllowsEmbedder:
    def test_an_open_widget_allows_anyone(self, db):
        assert policy.allows_embedder(db, [], None, "https://anywhere.example")

    @pytest.mark.parametrize("origin, allowed", [
        ("https://acme.com", True),
        ("http://www.acme.com", True),
        ("https://shop.acme.com", True),          # *.acme.com
        ("https://acme.com.evil.io", False),
        ("https://other.io", False),
        ("http://localhost:3000", True),
        ("http://localhost:3001", False),         # only the port listed
        ("https://staging.example:8443", True),
        ("https://staging.example", False),
        ("https://admin.shopify.com", True),      # always allowed
        ("not a url", False),
    ])
    def test_mirrors_the_header(self, db, own_origins, origin, allowed):
        domains = ["acme.com", "*.acme.com", "localhost:3000", "staging.example:8443"]
        assert policy.allows_embedder(db, domains, None, origin) is allowed


class TestFrameDocumentCsp:
    def test_scripts_need_the_nonce(self):
        csp = policy.frame_document_csp("abc123", ["https://api.example.com"], None)
        assert "script-src 'self' 'nonce-abc123'" in csp

    def test_scripts_and_styles_come_only_from_the_assets_folder(self):
        # Without a frame host the page shares the API's origin: nothing else
        # served there may run as the widget
        csp = policy.frame_document_csp("n", [], None, assets_url="https://api.example.com/assets/")
        assert "script-src https://api.example.com/assets/ 'nonce-n'" in csp
        assert "style-src https://api.example.com/assets/ 'unsafe-inline'" in csp
        assert "script-src 'self'" not in csp

    def test_an_unsafe_assets_url_falls_back_to_self(self):
        csp = policy.frame_document_csp("n", [], None, assets_url="https://api.example.com/assets/; script-src *")
        assert "script-src 'self' 'nonce-n'" in csp
        assert "script-src *" not in csp
        assert "object-src 'none'" in csp
        assert "base-uri 'none'" in csp
        assert "frame-ancestors" not in csp

    def test_connects_only_to_its_api(self):
        csp = policy.frame_document_csp("n", ["https://api.example.com", "wss://api.example.com"], None)
        assert "connect-src 'self' https://api.example.com wss://api.example.com" in csp

    def test_carries_the_ancestors(self):
        csp = policy.frame_document_csp("n", [], "frame-ancestors 'self' https://acme.com")
        assert csp.endswith("; frame-ancestors 'self' https://acme.com")

    def test_drops_an_unsafe_connect_origin(self):
        csp = policy.frame_document_csp("n", ["https://api.example.com; script-src *"], None)
        assert "script-src *" not in csp
