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

PDFs we will not index, and why.

Bytes don't bound the work: a small file can hold thousands of pages, and a
PDF is read page by page - every page's text embedded, and a scanned one
OCR'd at a second or more a page. So the page count is limited too, checked
before any of it is read.
"""

from typing import BinaryIO, Optional, Union

from pypdf import PdfReader

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class PdfRefused(ValueError):
    """A PDF over one of our limits. The message is for the user, as it is
    shown on the failed source."""


class PdfTooManyPages(PdfRefused):
    pass


def count_pages(pdf: Union[str, BinaryIO]) -> Optional[int]:
    """Pages in `pdf` (a path or a file object), or None when it cannot be
    counted (encrypted, damaged): the reader then fails it its own way."""
    try:
        return len(PdfReader(pdf).pages)
    except Exception as e:
        logger.warning(f"Could not count the pages of a PDF: {e}")
        return None


def check_page_count(pdf: Union[str, BinaryIO], max_pages: Optional[int] = None) -> None:
    """Raise PdfTooManyPages when `pdf` has more pages than we index."""
    limit = max_pages if max_pages is not None else settings.KB_PDF_MAX_PAGES
    pages = count_pages(pdf)
    if pages is not None and pages > limit:
        raise PdfTooManyPages(
            f"This PDF has {pages} pages; the limit is {limit}. Upload the part "
            "you need, or split it into smaller files."
        )
