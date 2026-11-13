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

Minting, rotating and classifying widget conversation tokens.

One module decides how long a conversation token lives, which claims survive a
rotation, and what a dead token means. Three call sites used to answer that last
question differently, which is how an identified visitor could silently become a
fresh anonymous customer just by leaving the page open past the token's TTL.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
import uuid

from jose import JWTError, jwt

from app.core.logger import get_logger
from app.core.security import (
    ALGORITHM,
    CONVERSATION_SECRET_KEY,
    _is_token_in_redis,
    _store_token_in_redis,
)

logger = get_logger(__name__)

TOKEN_TYPE = "conversation"

# Lifetime bounds for an identified (POST /generate-token) conversation token.
DEFAULT_TTL_SECONDS = 3600
MIN_TTL_SECONDS = 60
MAX_TTL_SECONDS = 86400

# A token may be rotated for as long as the visitor keeps the page open, but not
# forever: past this the embedding app has to identify the visitor again, so an
# abandoned tab can't carry an identity indefinitely.
MAX_CHAIN_SECONDS = 30 * 24 * 3600

# Claims that say WHO the visitor is. A rotation that dropped these would keep the
# conversation and lose the person - the whole bug this module exists for.
IDENTITY_CLAIMS = (
    "sub",
    "customer_id",
    "customer_email",
    "customer_name",
    "custom_data",
    "email",
    "source",
)

# Unix seconds of the FIRST token in this rotation chain. MAX_CHAIN_SECONDS is
# measured from it, so rotating does not reset the ceiling.
CHAIN_START_CLAIM = "cst"

# Random key the widget mints into every token it issues for itself. An
# unverified token may name an existing customer (the visitor only typed an
# email), so it must not reach that customer's other conversations: the key
# scopes it to the sessions started from this browser. Tabs share the token, so
# they share the key.
CONVERSATION_KEY_CLAIM = "ckey"

# Scope of a token the embedding app vouched for. It reaches the sessions that
# carry no conversation key - every session created before keys existed, and
# every session a verified token has created since.
VERIFIED_SCOPE = "verified"

# Scope prefix for widget tokens issued before conversation keys existed. Their
# jti never changes (they carry no `iat`, so the widget never rotates them), so
# it scopes them to sessions they create from now on and to nothing older.
LEGACY_SCOPE_PREFIX = "jti:"

# Conversation-key prefix for a token our own backend vouched for on behalf of
# one dashboard account (the in-app support chat). As trusted as VERIFIED_SCOPE,
# but confined to the conversations that account started: the email the token
# names is only what the account currently has set.
ACCOUNT_SCOPE_PREFIX = "user:"

# Codes the widget and the embed loader branch on. `identity_expired` means the
# request carried a real token for a real customer that has since lapsed - the
# client must ask its host for a fresh one rather than start over anonymously.
IDENTITY_EXPIRED_CODE = "identity_expired"
INVALID_TOKEN_CODE = "invalid_token"


@dataclass(frozen=True)
class TokenState:
    """What a request's conversation token is worth.

    `payload` set     - the token is live; use its claims.
    `identity_lost`   - our signature, and it names a customer, but it has expired
                        or been revoked. Never quietly swap this for a new
                        anonymous identity: the visitor is signed in.
    neither           - unusable; treat the request as having no token at all.
    """

    payload: Optional[Dict[str, Any]] = None
    identity_lost: bool = False

    @property
    def is_live(self) -> bool:
        return self.payload is not None


def clamp_ttl(ttl_seconds: Optional[int]) -> int:
    """Bring any requested lifetime inside the supported range."""
    if not ttl_seconds:
        return DEFAULT_TTL_SECONDS
    return max(MIN_TTL_SECONDS, min(MAX_TTL_SECONDS, int(ttl_seconds)))


def is_ttl_supported(ttl_seconds: Optional[int]) -> bool:
    """True when the caller's requested lifetime needs no clamping.

    Nothing at all (None, 0) asks for the default rather than for a bad lifetime.
    """
    if not ttl_seconds:
        return True
    return MIN_TTL_SECONDS <= ttl_seconds <= MAX_TTL_SECONDS


def is_identified(payload: Dict[str, Any]) -> bool:
    """True when the EMBEDDING APP vouched for this visitor.

    Deliberately narrower than "has a customer id": every widget visitor gets a
    customer row, including the anonymous `…@noemail.com` ones the widget
    mints for itself. Only a token from POST /generate-token carries the email the
    app asserted, and only that identity is worth refusing a request over - an
    anonymous token that lapses can simply be replaced, exactly as before.
    """
    return bool(payload.get("customer_email") or payload.get("email"))


def new_conversation_key() -> str:
    return uuid.uuid4().hex


def account_conversation_key(user_id) -> str:
    """The conversation key of a token minted for one dashboard account."""
    return f"{ACCOUNT_SCOPE_PREFIX}{user_id}"


def is_account_key(key: Optional[str]) -> bool:
    return bool(key) and str(key).startswith(ACCOUNT_SCOPE_PREFIX)


def is_verified_scope(scope: Optional[str]) -> bool:
    """True for a scope our side vouched for: the embedding app's, or an account's."""
    return scope == VERIFIED_SCOPE or is_account_key(scope)


def conversation_scope(payload: Dict[str, Any]) -> str:
    """Which of a customer's conversations this token may reach.

    The conversation key wins even on an identified token, so a caller that adds
    one narrows itself further. Without a key, an identified token reaches the
    keyless sessions (VERIFIED_SCOPE) and an anonymous one only what its own jti
    created. Never returns a value that means "every session of the customer".
    Raises ValueError for a token that can't be scoped, or claims a verified scope
    it was never given.
    """
    key = payload.get(CONVERSATION_KEY_CLAIM)
    if key:
        key = str(key)
        if key == VERIFIED_SCOPE or (is_account_key(key) and not is_identified(payload)):
            raise ValueError("Conversation token claims a scope it was not given")
        return key
    if is_identified(payload):
        return VERIFIED_SCOPE
    jti = payload.get("jti")
    if not jti:
        raise ValueError("Conversation token has no jti to scope it by")
    return f"{LEGACY_SCOPE_PREFIX}{jti}"


def session_key_for_scope(scope: str) -> Optional[str]:
    """The conversation_key a session created under `scope` is stored with.

    No scope is an error, never "keyless": that would read as VERIFIED_SCOPE.
    """
    if not scope:
        raise ValueError("A conversation scope is required")
    return None if scope == VERIFIED_SCOPE else scope


def scope_for_session_key(conversation_key: Optional[str]) -> str:
    """The scope that created a session stored with `conversation_key`."""
    return conversation_key or VERIFIED_SCOPE


def mint(
    claims: Dict[str, Any],
    ttl_seconds: Optional[int] = None,
    jti: Optional[str] = None,
) -> Tuple[str, datetime, int]:
    """Sign a conversation token for `claims` and register it for revocation.

    Args:
        claims: identity claims plus `widget_id`. `None` values are dropped so an
            anonymous token carries no null `sub` (python-jose refuses to decode one).
        ttl_seconds: lifetime, clamped to the supported range.
        jti: reuse an existing JWT ID instead of minting a new one - how
            /generate-token avoids multiplying tokens across page refreshes.

    Returns:
        (token, expires_at, ttl_seconds)
    """
    ttl = clamp_ttl(ttl_seconds)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl)
    issued_at = int(now.timestamp())

    payload = {key: value for key, value in claims.items() if value is not None}
    payload.update({
        "type": TOKEN_TYPE,
        "jti": jti or str(uuid.uuid4()),
        "iat": issued_at,
        "exp": int(expires_at.timestamp()),
    })
    payload.setdefault(CHAIN_START_CLAIM, issued_at)

    token = jwt.encode(payload, CONVERSATION_SECRET_KEY, algorithm=ALGORITHM)

    # Registering the email mapping too keeps revoke_user_sessions() effective on
    # rotated tokens - without it a refresh would escape a bulk revocation.
    _store_token_in_redis(
        payload["jti"],
        ttl,
        email=payload.get("customer_email") or payload.get("email"),
        widget_id=payload.get("widget_id"),
    )
    return token, expires_at, ttl


def rotate(payload: Dict[str, Any]) -> Optional[Tuple[str, datetime, int]]:
    """Issue the successor of a still-live token, same identity, fresh lifetime.

    Returns None once the chain has run past MAX_CHAIN_SECONDS. The predecessor is
    left alone rather than revoked: other tabs on the same page share the token and
    would otherwise be logged out by whichever tab refreshed first.
    """
    now = int(datetime.now(timezone.utc).timestamp())
    chain_start = payload.get(CHAIN_START_CLAIM) or payload.get("iat") or now
    if now - int(chain_start) > MAX_CHAIN_SECONDS:
        logger.info("Conversation token chain expired; re-identification required")
        return None

    issued_at, expires_at = payload.get("iat"), payload.get("exp")
    ttl = int(expires_at) - int(issued_at) if issued_at and expires_at else DEFAULT_TTL_SECONDS

    claims: Dict[str, Any] = {claim: payload.get(claim) for claim in IDENTITY_CLAIMS}
    claims["widget_id"] = payload.get("widget_id")
    # Carry the scope, not just the claim: a legacy token's scope is its jti,
    # which the successor would otherwise lose along with its conversations.
    try:
        claims[CONVERSATION_KEY_CLAIM] = session_key_for_scope(conversation_scope(payload))
    except ValueError:
        logger.info("Conversation token cannot be scoped; re-identification required")
        return None
    claims[CHAIN_START_CLAIM] = int(chain_start)
    return mint(claims, ttl)


def inspect(token: Optional[str], widget_id: Optional[str] = None) -> TokenState:
    """Classify the conversation token a widget request arrived with."""
    if not token:
        return TokenState()

    try:
        # verify_sub=False tolerates tokens already in browsers' localStorage that
        # were issued with `sub: null` (see verify_conversation_token).
        payload = jwt.decode(
            token,
            CONVERSATION_SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_sub": False},
        )
    except JWTError:
        return _inspect_lapsed(token, widget_id)

    if payload.get("type") != TOKEN_TYPE:
        return TokenState()
    if widget_id and payload.get("widget_id") != widget_id:
        return TokenState()

    jti = payload.get("jti")
    if jti and not _is_token_in_redis(jti):
        # Revoked, or its Redis TTL ran out before the JWT's exp did.
        return TokenState(identity_lost=is_identified(payload))

    return TokenState(payload=payload)


def claims_ignoring_expiry(token: str) -> Optional[Dict[str, Any]]:
    """Verified claims of a token whose lifetime may already be over.

    The signature is still enforced - only `exp` is ignored - so this is safe for
    revoking or classifying a lapsed token, and never for authenticating one.
    """
    try:
        return jwt.decode(
            token,
            CONVERSATION_SECRET_KEY,
            algorithms=[ALGORITHM],
            options={"verify_sub": False, "verify_exp": False},
        )
    except JWTError:
        return None


def _inspect_lapsed(token: str, widget_id: Optional[str]) -> TokenState:
    """Tell an expired token of ours apart from a corrupt or foreign one."""
    payload = claims_ignoring_expiry(token)
    if payload is None:
        return TokenState()

    if payload.get("type") != TOKEN_TYPE:
        return TokenState()
    if widget_id and payload.get("widget_id") != widget_id:
        return TokenState()

    return TokenState(identity_lost=is_identified(payload))
