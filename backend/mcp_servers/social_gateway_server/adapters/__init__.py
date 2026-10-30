from app.integrations.social.base_adapter import BaseSocialAdapter
from app.integrations.social.facebook import FacebookAdapter
from app.integrations.social.google_business_profile import GoogleBusinessProfileAdapter
from app.integrations.social.instagram import InstagramAdapter
from app.integrations.social.linkedin import LinkedInAdapter
from app.integrations.social.pinterest import PinterestAdapter
from app.integrations.social.threads import ThreadsAdapter
from app.integrations.social.x_twitter import XTwitterAdapter
from app.integrations.social.youtube import YouTubeAdapter

ADAPTERS_MAP: dict[str, BaseSocialAdapter] = {
    "linkedin": LinkedInAdapter(),
    "youtube": YouTubeAdapter(),
    "instagram": InstagramAdapter(),
    "threads": ThreadsAdapter(),
    "facebook": FacebookAdapter(),
    "x": XTwitterAdapter(),
    "pinterest": PinterestAdapter(),
    "google_business_profile": GoogleBusinessProfileAdapter(),
}


def get_social_adapter(platform: str) -> BaseSocialAdapter:
    """Return the designated social adapter for platform."""
    adapter = ADAPTERS_MAP.get(platform.strip().lower())
    if not adapter:
        raise ValueError(f"Unsupported social platform: {platform}")
    return adapter
