import re
from typing import Any

PLATFORM_CHAR_LIMITS: dict[str, int] = {
    "linkedin": 3000,
    "youtube_title": 100,
    "youtube_description": 5000,
    "youtube": 5000,
    "instagram": 2200,
    "threads": 500,
    "facebook": 63206,
    "x": 280,
    "pinterest_title": 100,
    "pinterest_description": 500,
    "pinterest": 500,
    "google_business_profile": 1500,
}

PLATFORM_MEDIA_RULES: dict[str, dict[str, Any]] = {
    "linkedin": {
        "max_media": 9,
        "allowed_media_types": ["image", "video", "document"],
        "disallow_organic_carousels": True,
        "aspect_ratios": ["1:1", "4:5", "16:9"],
    },
    "youtube": {
        "min_media": 1,
        "max_media": 1,
        "allowed_media_types": ["video"],
        "aspect_ratios": ["16:9", "9:16"],
    },
    "instagram": {
        "max_media": 20,
        "allowed_media_types": ["image", "video"],
        "allowed_image_formats": ["JPEG", "JPG"],
        "aspect_ratios": ["1:1", "4:5", "9:16"],
    },
    "threads": {
        "max_media": 20,
        "allowed_media_types": ["image", "video"],
        "aspect_ratios": ["1:1", "4:5", "16:9", "9:16"],
    },
    "facebook": {
        "max_media": 10,
        "allowed_media_types": ["image", "video"],
        "aspect_ratios": ["1:1", "4:5", "16:9", "9:16"],
    },
    "x": {
        "max_media": 4,
        "max_images": 4,
        "max_videos": 1,
        "max_gifs": 1,
        "allowed_media_types": ["image", "video", "gif"],
        "aspect_ratios": ["16:9", "1:1"],
    },
    "pinterest": {
        "min_media": 1,
        "max_media": 1,
        "allowed_media_types": ["image", "video"],
        "aspect_ratios": ["2:3", "1:1"],
    },
    "google_business_profile": {
        "max_media": 1,
        "allowed_media_types": ["image"],
        "disallowed_types": ["video", "product"],
        "aspect_ratios": ["1:1", "4:3", "16:9"],
    },
}

# Regex to strip raw phone numbers and emails to prevent GBP REJECTED policy state
PHONE_REGEX = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")


def sanitize_gbp_summary(text: str) -> str:
    """Strip raw phone numbers and email addresses from summary to prevent GBP REJECTED policy state."""
    no_phones = PHONE_REGEX.sub("[Contact via Profile]", text)
    sanitized = EMAIL_REGEX.sub("[Contact via Website]", no_phones)
    return sanitized.strip()


def validate_text_limit(platform: str, text: str) -> bool:
    """Validate text length against platform ceiling."""
    limit = PLATFORM_CHAR_LIMITS.get(platform, 5000)
    return len(text) <= limit


def validate_platform_asset_compliance(
    platform: str,
    copy_text: str,
    media_urls: list[str] | None = None,
    aspect_ratio: str = "1:1",
    media_type: str = "image",
    is_carousel: bool = False,
) -> tuple[bool, list[str]]:
    """Validate post parameters against platform limits and compliance rules."""
    errors: list[str] = []
    p_norm = platform.lower()
    media_urls = media_urls or []

    # 1. Text limit
    char_limit = PLATFORM_CHAR_LIMITS.get(p_norm, 5000)
    if len(copy_text) > char_limit:
        errors.append(f"{platform} copy exceeds maximum character limit ({len(copy_text)} > {char_limit})")

    rules = PLATFORM_MEDIA_RULES.get(p_norm, {})
    if not rules:
        return (len(errors) == 0, errors)

    # 2. Media count checks
    max_media = rules.get("max_media")
    if max_media is not None and len(media_urls) > max_media:
        errors.append(f"{platform} allows at most {max_media} media items, found {len(media_urls)}")

    min_media = rules.get("min_media", 0)
    if min_media > 0 and len(media_urls) < min_media:
        errors.append(f"{platform} requires at least {min_media} media item(s), found {len(media_urls)}")

    # 3. Disallowed types & organic carousels
    if rules.get("disallow_organic_carousels") and is_carousel:
        errors.append("LinkedIn: Organic carousels are unsupported. Use MultiImage or Document instead.")

    disallowed_types = rules.get("disallowed_types", [])
    if media_type.lower() in disallowed_types:
        errors.append(f"{platform} rejects {media_type} posts (disallowed types: {disallowed_types})")

    # 4. Aspect ratio validation
    allowed_ratios = rules.get("aspect_ratios", [])
    if allowed_ratios and aspect_ratio not in allowed_ratios:
        errors.append(
            f"{platform} aspect ratio '{aspect_ratio}' is not supported. Allowed ratios: {allowed_ratios}"
        )

    # 5. X Twitter specific constraints
    if p_norm == "x" and media_type.lower() == "video" and len(media_urls) > 1:
        errors.append("X (Twitter) supports only 1 video per tweet.")

    return (len(errors) == 0, errors)
