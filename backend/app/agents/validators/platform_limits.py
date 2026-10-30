PLATFORM_CHAR_LIMITS = {
    "linkedin": 3000,
    "youtube_title": 100,
    "youtube_description": 5000,
    "instagram": 2200,
    "threads": 500,
    "facebook": 63206,
    "x": 280,
    "pinterest_title": 100,
    "pinterest_description": 500,
    "google_business_profile": 1500,
}

def validate_text_limit(platform: str, text: str) -> bool:
    limit = PLATFORM_CHAR_LIMITS.get(platform, 5000)
    return len(text) <= limit
