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

from unittest.mock import patch

import httpx
import pytest

from app.knowledge import pdf_download, url_safety
from app.knowledge.pdf_download import PdfTooLargeError, download_pdf
from app.knowledge.url_safety import BlockedHostError

PDF = b"%PDF-1.4 test body"
PUBLIC_IP = [(2, 1, 6, "", ("93.184.216.34", 0))]


@pytest.fixture
def served(monkeypatch):
    """Route download_pdf's httpx client to an in-process handler and record
    every URL it was asked to open."""
    requested = []
    routes = {}

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        requested.append(url)
        return routes[url]()

    real_client = httpx.Client
    monkeypatch.setattr(
        pdf_download.httpx, "Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    return routes, requested


@pytest.fixture
def public_dns():
    with patch.object(url_safety.socket, "getaddrinfo", return_value=PUBLIC_IP):
        yield


@pytest.mark.parametrize("url", [
    "http://127.0.0.1/internal.pdf",
    "http://localhost:8000/api/v1/secret.pdf",
    "http://169.254.169.254/latest/meta-data/",
])
def test_internal_url_is_refused_before_any_request(served, tmp_path, url):
    _, requested = served
    with pytest.raises(BlockedHostError):
        download_pdf(url, str(tmp_path / "out.pdf"))
    assert requested == []


def test_hostname_resolving_to_internal_address_is_refused(served, tmp_path):
    _, requested = served
    with patch.object(url_safety.socket, "getaddrinfo",
                      return_value=[(2, 1, 6, "", ("10.0.0.7", 0))]):
        with pytest.raises(BlockedHostError):
            download_pdf("https://pdfs.attacker.example/a.pdf", str(tmp_path / "out.pdf"))
    assert requested == []


def test_public_url_redirecting_to_private_address_is_refused(served, public_dns, tmp_path):
    routes, requested = served
    routes["https://files.example.com/doc.pdf"] = lambda: httpx.Response(
        302, headers={"location": "http://169.254.169.254/latest/meta-data/"})
    with pytest.raises(BlockedHostError):
        download_pdf("https://files.example.com/doc.pdf", str(tmp_path / "out.pdf"))
    # The internal hop was never opened.
    assert requested == ["https://files.example.com/doc.pdf"]


def test_public_url_is_streamed_to_disk_following_safe_redirects(served, public_dns, tmp_path):
    routes, _ = served
    routes["https://files.example.com/doc.pdf"] = lambda: httpx.Response(
        301, headers={"location": "/v2/doc.pdf"})
    routes["https://files.example.com/v2/doc.pdf"] = lambda: httpx.Response(200, content=PDF)
    dest = tmp_path / "out.pdf"

    assert download_pdf("https://files.example.com/doc.pdf", str(dest)) == str(dest)
    assert dest.read_bytes() == PDF


def test_declared_oversize_is_refused(served, public_dns, tmp_path):
    routes, _ = served
    routes["https://files.example.com/big.pdf"] = lambda: httpx.Response(
        200, content=PDF, headers={"content-length": str(10 ** 9)})
    with pytest.raises(PdfTooLargeError):
        download_pdf("https://files.example.com/big.pdf", str(tmp_path / "out.pdf"))


def test_body_past_the_cap_is_refused_even_without_content_length(served, public_dns, tmp_path):
    routes, _ = served

    def chunked():
        return httpx.Response(200, content=iter([PDF] * 10))  # streamed: no length

    routes["https://files.example.com/big.pdf"] = chunked
    with pytest.raises(PdfTooLargeError):
        download_pdf("https://files.example.com/big.pdf", str(tmp_path / "out.pdf"),
                     max_bytes=len(PDF) * 2)


def test_http_error_is_raised(served, public_dns, tmp_path):
    routes, _ = served
    routes["https://files.example.com/gone.pdf"] = lambda: httpx.Response(404)
    with pytest.raises(httpx.HTTPStatusError):
        download_pdf("https://files.example.com/gone.pdf", str(tmp_path / "out.pdf"))
