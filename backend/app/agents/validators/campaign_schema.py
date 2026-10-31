from typing import Any

from app.agents.validators.platform_limits import (
    sanitize_gbp_summary,
    validate_platform_asset_compliance,
)
from app.orchestrator.state import CampaignBlueprint, PlatformAssetSpec


class CampaignValidationError(ValueError):
    """Raised when a CampaignBlueprint violates platform compliance rules."""


def validate_campaign_blueprint(blueprint_data: dict[str, Any], sanitize_gbp: bool = True) -> CampaignBlueprint:
    """Validates raw agent output against CampaignBlueprint and platform limits."""
    # Pre-process GBP text if sanitize_gbp is enabled
    if sanitize_gbp and "platform_assets" in blueprint_data:
        for asset in blueprint_data.get("platform_assets", []):
            if isinstance(asset, dict) and asset.get("platform") == "google_business_profile":
                if "copy_text" in asset:
                    asset["copy_text"] = sanitize_gbp_summary(asset["copy_text"])

    blueprint = CampaignBlueprint.model_validate(blueprint_data)

    errors: list[str] = []
    for asset in blueprint.platform_assets:
        # Check platform compliance rules
        passed, asset_errors = validate_platform_asset_compliance(
            platform=asset.platform,
            copy_text=asset.copy_text,
            media_urls=asset.media_urls,
            aspect_ratio=asset.aspect_ratio,
        )
        if not passed:
            errors.extend(asset_errors)
            asset.compliance_passed = False
        else:
            asset.compliance_passed = True

    if errors:
        raise CampaignValidationError(f"CampaignBlueprint compliance validation failed: {'; '.join(errors)}")

    return blueprint
