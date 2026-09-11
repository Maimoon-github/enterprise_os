"""Verifies external writes require signed HITL clearance."""
import pytest

from app.integrations.ads.meta import MetaAdsAdapter


def test_paid_media_write_requires_signed_dispatch() -> None:
    with pytest.raises(PermissionError):
        MetaAdsAdapter(credentials={}).push_campaign({})
