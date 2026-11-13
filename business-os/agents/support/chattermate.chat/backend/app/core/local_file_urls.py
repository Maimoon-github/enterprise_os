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

"""Short-lived signed URLs for private files in local (non-S3) storage.

The local counterpart of an S3 presigned URL: an HMAC binds the storage key to
an expiry, so a link works for whoever holds it until it expires, and for no
other file. Bearer links rather than session auth because the widget renders
attachments with plain <img>/<a> tags, which cannot send a token header.
"""

import hashlib
import hmac
import time
from typing import Optional
from urllib.parse import quote, urlencode

from app.core.config import settings

LOCAL_FILE_ROUTE = f"{settings.API_V1_STR}/files/local"

# SECRET_KEY also signs JWTs; the purpose prefix keeps the two from ever
# validating each other.
_PURPOSE = b"chattermate:local-file-url:v1\n"


def _signature(key: str, expires: int) -> str:
    message = _PURPOSE + f"{key}\n{expires}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), message, hashlib.sha256).hexdigest()


def sign_local_key(key: str, expires_in: Optional[int] = None) -> str:
    """Relative URL serving ``key`` (a path under uploads/) until it expires.
    Lifetime follows S3_PRESIGN_EXPIRY_SECONDS, so both backends behave alike."""
    lifetime = settings.S3_PRESIGN_EXPIRY_SECONDS if expires_in is None else expires_in
    expires = int(time.time()) + lifetime
    query = urlencode({"exp": expires, "sig": _signature(key, expires)})
    return f"{LOCAL_FILE_ROUTE}/{quote(key)}?{query}"


def verify_local_signature(key: str, expires: Optional[int], signature: Optional[str]) -> bool:
    """True when ``signature`` was issued for ``key`` and has not expired."""
    if expires is None or not signature or expires < time.time():
        return False
    return hmac.compare_digest(_signature(key, expires), signature)
