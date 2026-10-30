from app.orchestrator.state import CampaignBlueprint


def validate_campaign_blueprint(blueprint_data: dict) -> CampaignBlueprint:
    """Validates raw agent output against CampaignBlueprint Pydantic model."""
    return CampaignBlueprint.model_validate(blueprint_data)
