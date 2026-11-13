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

A PDF's cost is its pages, not its bytes: each page is embedded, and a
scanned one OCR'd. Past the page limit it is refused before any is read.
"""

import io
from unittest.mock import patch

import pytest
from pypdf import PdfWriter

from app.core.config import settings
from app.knowledge.pdf_download import PdfTooLargeError
from app.knowledge.pdf_limits import PdfRefused, PdfTooManyPages, check_page_count, count_pages


def pdf_with_pages(n: int) -> bytes:
    writer = PdfWriter()
    for _ in range(n):
        writer.add_blank_page(width=200, height=200)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def test_the_pages_are_counted():
    assert count_pages(io.BytesIO(pdf_with_pages(7))) == 7


def test_a_file_path_is_counted_too(tmp_path):
    path = tmp_path / "manual.pdf"
    path.write_bytes(pdf_with_pages(4))
    assert count_pages(str(path)) == 4


def test_a_pdf_at_the_limit_is_accepted():
    check_page_count(io.BytesIO(pdf_with_pages(3)), max_pages=3)


def test_a_pdf_over_the_limit_is_refused_and_told_why():
    with pytest.raises(PdfTooManyPages) as refused:
        check_page_count(io.BytesIO(pdf_with_pages(4)), max_pages=3)
    assert str(refused.value) == ("This PDF has 4 pages; the limit is 3. Upload the part you need, "
                                  "or split it into smaller files.")


def test_the_limit_comes_from_settings():
    with patch.object(settings, "KB_PDF_MAX_PAGES", 2), pytest.raises(PdfTooManyPages):
        check_page_count(io.BytesIO(pdf_with_pages(3)))


@pytest.mark.parametrize("damaged", [b"%PDF-1.4 test pdf content", b"", b"not a pdf"])
def test_one_that_cannot_be_counted_is_left_to_the_reader(damaged):
    assert count_pages(io.BytesIO(damaged)) is None
    check_page_count(io.BytesIO(damaged), max_pages=1)  # no refusal: the reader decides


def test_both_limits_are_refusals_with_a_message_for_the_user():
    too_big = PdfTooLargeError(25 * 1024 * 1024)
    assert isinstance(too_big, PdfRefused)
    assert str(too_big) == "This PDF is larger than 25 MB. Upload a smaller file, or split it into parts."
