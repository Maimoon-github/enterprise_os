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

Only our own surfaces may use the dashboard's sign-in cookies cross-origin.

An org's domain is whatever was typed at signup, unverified, and every org
domain is in the CORS list. If those origins were also allowed credentials, a
page on any signed-up domain could read a signed-in dashboard user's account.
"""

import logging

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import app.main  # noqa: F401 - the CORS middleware is added on import
from app.core import auth_utils, cors
from app.core.application import app as api

DASHBOARD = "https://app.example.com"
OPERATOR_LISTED = "https://admin.example.com"
ORG_SITE = "https://signed-up-domain.example"
HELP_CENTER = "https://acme.help.example.com"
API_HOST = "api.example.com"


def configure(monkeypatch, frontend_url=DASHBOARD, cors_origins=(OPERATOR_LISTED, DASHBOARD + "/")):
    monkeypatch.setattr(cors.settings, "FRONTEND_URL", frontend_url)
    monkeypatch.setattr(cors, "BASE_CORS_ORIGINS", list(cors_origins))
    cors.first_party_origins.cache_clear()


@pytest.fixture(autouse=True)
def first_party(monkeypatch):
    configure(monkeypatch)
    yield
    # Don't leave this module's origins cached for other tests
    cors.first_party_origins.cache_clear()


def cors_app(allow_origins=(DASHBOARD, OPERATOR_LISTED, ORG_SITE)):
    app = FastAPI()
    app.add_middleware(
        cors.FirstPartyCredentialsCORSMiddleware,
        credentialed_origins=cors.first_party_origins(),
        allow_origins=list(allow_origins),
        allow_origin_regex=r"^https://[a-z0-9-]+\.help\.example\.com$",
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/me")
    def me():
        return {"who": "a signed-in user"}

    @app.get("/refused")
    def refused():
        raise HTTPException(status_code=401, detail="Not signed in")

    return app


@pytest.fixture
def client():
    return TestClient(cors_app())


def preflight(client, origin):
    return client.options("/me", headers={"Origin": origin, "Access-Control-Request-Method": "GET"})


def cors_layers(app):
    return [m for m in app.user_middleware if isinstance(m.cls, type) and issubclass(m.cls, cors.CORSMiddleware)]


class TestFirstPartyOrigins:
    def test_the_dashboard_and_operator_listed_origins(self):
        assert cors.first_party_origins() == {DASHBOARD, OPERATOR_LISTED}

    @pytest.mark.parametrize("frontend_url, expected", [
        ("https://App.Example.com:443/dashboard/", "https://app.example.com"),
        ("http://localhost:5173/", "http://localhost:5173"),
        ("http://localhost:80", "http://localhost"),
        ("https://app.example.com:8443", "https://app.example.com:8443"),
    ])
    def test_frontend_url_is_read_the_way_browsers_send_origin(self, monkeypatch, frontend_url, expected):
        configure(monkeypatch, frontend_url=frontend_url)
        assert expected in cors.first_party_origins()

    def test_a_frontend_url_without_a_scheme_is_reported(self, monkeypatch, caplog):
        configure(monkeypatch, frontend_url="app.example.com")
        with caplog.at_level(logging.ERROR):
            assert cors.first_party_origins() == {OPERATOR_LISTED, DASHBOARD}
        assert "FRONTEND_URL" in caplog.text

    def test_the_widget_frame_host_is_never_first_party(self, monkeypatch):
        # Even listed in CORS_ORIGINS: the widget's host stays cookieless
        monkeypatch.setattr(cors.settings, "WIDGET_FRAME_URL", "https://widget.example.com")
        configure(monkeypatch, cors_origins=[OPERATOR_LISTED, "https://widget.example.com"])
        assert cors.first_party_origins() == {DASHBOARD, OPERATOR_LISTED}
        assert not cors.is_first_party_origin("https://widget.example.com")

    def test_a_wildcard_in_cors_origins_trusts_no_one(self, monkeypatch):
        configure(monkeypatch, cors_origins=["*"])
        assert cors.first_party_origins() == {DASHBOARD}
        assert not cors.is_first_party_origin(ORG_SITE)

    @pytest.mark.parametrize("origin, expected", [
        (DASHBOARD, True),
        (DASHBOARD.upper(), True),
        (DASHBOARD + "/", True),
        (DASHBOARD + ":443", True),
        (OPERATOR_LISTED, True),
        ("http://app.example.com", False),
        ("https://app.example.com:8443", False),
        (ORG_SITE, False),
        (HELP_CENTER, False),
        ("null", False),
        ("", False),
        (None, False),
    ])
    def test_is_first_party(self, origin, expected):
        assert cors.is_first_party_origin(origin) is expected


class TestCredentials:
    @pytest.mark.parametrize("origin", [DASHBOARD, OPERATOR_LISTED])
    def test_our_own_origins_may_send_credentials(self, client, origin):
        for response in (client.get("/me", headers={"Origin": origin}), preflight(client, origin)):
            assert response.headers["access-control-allow-origin"] == origin
            assert response.headers["access-control-allow-credentials"] == "true"

    @pytest.mark.parametrize("origin", [ORG_SITE, HELP_CENTER])
    def test_an_org_site_may_call_the_api_but_never_with_cookies(self, client, origin):
        for response in (client.get("/me", headers={"Origin": origin}), preflight(client, origin)):
            assert response.headers["access-control-allow-origin"] == origin
            assert "access-control-allow-credentials" not in response.headers

    def test_even_when_it_sends_cookies(self, client):
        response = client.get("/me", headers={"Origin": ORG_SITE, "Cookie": "access_token=x"})
        assert "access-control-allow-credentials" not in response.headers

    def test_error_responses_too(self, client):
        org = client.get("/refused", headers={"Origin": ORG_SITE})
        assert org.status_code == 401
        assert org.headers["access-control-allow-origin"] == ORG_SITE
        assert "access-control-allow-credentials" not in org.headers
        assert client.get("/refused", headers={"Origin": DASHBOARD}).headers["access-control-allow-credentials"] == "true"

    def test_a_wildcard_allow_list_still_keeps_cookies_first_party(self):
        client = TestClient(cors_app(allow_origins=["*"]))
        org = client.get("/me", headers={"Origin": ORG_SITE, "Cookie": "access_token=x"})
        assert "access-control-allow-credentials" not in org.headers
        dashboard = client.get("/me", headers={"Origin": DASHBOARD, "Cookie": "access_token=x"})
        assert dashboard.headers["access-control-allow-origin"] == DASHBOARD
        assert dashboard.headers["access-control-allow-credentials"] == "true"

    def test_an_unknown_site_gets_nothing(self, client):
        response = client.get("/me", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in response.headers
        assert "access-control-allow-credentials" not in response.headers
        assert preflight(client, "https://evil.example").status_code == 400


class TestRefreshKeepsTheSplit:
    def test_update_local_cors_keeps_first_party_credentials(self, client):
        app = client.app
        cors.update_local_cors(app, [DASHBOARD, ORG_SITE])

        layers = cors_layers(app)
        assert len(layers) == 1
        assert layers[0].cls is cors.FirstPartyCredentialsCORSMiddleware
        assert "access-control-allow-credentials" not in client.get("/me", headers={"Origin": ORG_SITE}).headers
        assert client.get("/me", headers={"Origin": DASHBOARD}).headers["access-control-allow-credentials"] == "true"

    def test_the_apis_own_origin_is_always_allowed(self, monkeypatch):
        # The iframe snippet and path-mode help centres are pages on the API
        monkeypatch.setattr(cors.settings, "BACKEND_URL", "https://api.example.com/")
        assert {"https://api.example.com", ORG_SITE} <= set(cors.with_configured_origins([ORG_SITE]))
        assert not cors.is_first_party_origin("https://api.example.com")

    def test_a_cached_list_from_an_older_config_never_drops_the_dashboard(self, client):
        # Redis keeps the list across restarts; it may predate the current env
        cors.update_local_cors(client.app, [ORG_SITE])

        response = client.get("/me", headers={"Origin": DASHBOARD})
        assert response.headers["access-control-allow-origin"] == DASHBOARD
        assert response.headers["access-control-allow-credentials"] == "true"

    def test_the_same_origins_in_another_order_do_not_rebuild(self, client):
        origins = cors.with_configured_origins([ORG_SITE, "https://other.example"])
        cors.update_local_cors(client.app, origins)
        client.get("/me")
        built = client.app.middleware_stack

        cors.update_local_cors(client.app, list(reversed(origins)))

        assert client.app.middleware_stack is built

    def test_a_rebuilt_middleware_is_the_first_party_one(self):
        bare = FastAPI()
        cors.update_local_cors(bare, [ORG_SITE])
        assert bare.user_middleware[0].cls is cors.FirstPartyCredentialsCORSMiddleware


def test_the_app_is_wired_with_the_first_party_middleware():
    layers = cors_layers(api)
    assert len(layers) == 1
    assert layers[0].cls is cors.FirstPartyCredentialsCORSMiddleware
    assert layers[0].kwargs["credentialed_origins"]


def handshake(origin=None, query="EIO=4&transport=polling", host=API_HOST, fetch_site=None, cookie="access_token=tok"):
    environ = {"QUERY_STRING": query, "HTTP_HOST": host, "HTTP_COOKIE": cookie}
    if origin:
        environ["HTTP_ORIGIN"] = origin
    if fetch_site:
        environ["HTTP_SEC_FETCH_SITE"] = fetch_site
    return environ


class TestCookieSockets:
    """Sockets get no CORS check, and socket.io signs a namespace in with the
    headers of the first handshake request, so the handshake itself must have
    come from our own pages."""

    @pytest.mark.parametrize("environ", [
        handshake(origin=DASHBOARD),
        handshake(origin=DASHBOARD + ":443"),
        handshake(origin=OPERATOR_LISTED),
        handshake(origin=f"https://{API_HOST}"),
        handshake(origin=f"https://{API_HOST}:443"),
        handshake(origin="http://127.0.0.1:8000", host="127.0.0.1:8000"),
        handshake(fetch_site="same-origin"),
    ], ids=["dashboard", "dashboard-default-port", "operator-listed", "the-api-itself", "the-api-default-port",
            "the-api-on-a-port", "same-origin-no-origin"])
    def test_our_own_pages_may_use_the_cookies(self, environ):
        assert auth_utils.cookie_socket_allowed(environ)

    @pytest.mark.parametrize("environ", [
        handshake(origin=ORG_SITE),
        handshake(origin=HELP_CENTER),
        handshake(origin="null"),
        handshake(),
        handshake(fetch_site="cross-site"),
        handshake(fetch_site="same-site"),
        handshake(query="EIO=4&transport=polling&j=0"),
        handshake(query="EIO=4&transport=polling&j=0", fetch_site="same-origin"),
        handshake(origin=DASHBOARD, query="EIO=4&transport=polling&j=0"),
        handshake(origin=ORG_SITE, host="signed-up-domain.example:8443"),
        handshake(origin=f"https://{API_HOST}", host=""),
    ], ids=["org-site", "help-centre", "opaque", "no-origin", "cross-site-no-origin", "same-site-no-origin",
            "jsonp", "jsonp-same-origin", "jsonp-from-dashboard", "org-site-other-port", "no-host"])
    def test_anything_else_may_not(self, environ):
        assert not auth_utils.cookie_socket_allowed(environ)

    @pytest.fixture
    def auth_calls(self, monkeypatch):
        calls = []

        async def refresh(token, db):
            calls.append(("refresh", token))
            return "fresh-access-token"

        monkeypatch.setattr(auth_utils, "refresh_access_token", refresh)
        monkeypatch.setattr(auth_utils, "live_payload", lambda db, token, kind: calls.append(("verify", token)) or None)
        return calls

    @pytest.mark.asyncio
    @pytest.mark.parametrize("environ", [
        handshake(origin=ORG_SITE, cookie="refresh_token=r; access_token=a"),
        handshake(cookie="refresh_token=r", query="EIO=4&transport=polling&j=0"),
    ], ids=["org-site", "jsonp"])
    async def test_a_refused_handshake_never_reads_or_refreshes_the_cookies(self, auth_calls, environ):
        assert await auth_utils.authenticate_socket("sid-1", environ) == (None, None, None)
        assert auth_calls == []

    @pytest.mark.asyncio
    async def test_our_dashboard_is_still_authenticated_from_its_cookies(self, auth_calls):
        await auth_utils.authenticate_socket("sid-1", handshake(origin=DASHBOARD))
        assert auth_calls == [("verify", "tok")]

    @pytest.mark.asyncio
    async def test_a_refreshed_token_stays_on_the_server(self, auth_calls):
        await auth_utils.authenticate_socket("sid-1", handshake(origin=DASHBOARD, cookie="refresh_token=r"))
        assert auth_calls == [("refresh", "r"), ("verify", "fresh-access-token")]
