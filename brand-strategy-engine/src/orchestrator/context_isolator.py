"""Context isolation engine providing bounded state slices to prevent context dilution."""

from typing import Any, Dict
from src.schemas.state import MasterEngineState


class ContextIsolator:
    """Extracts strictly bounded, typed state slices for each domain specialist."""

    @staticmethod
    def get_analyst_slice(state: MasterEngineState) -> Dict[str, Any]:
        """Provides minimal parameters needed for visual and DOM exploration."""
        return {
            "website_url": str(state.brand_profile.website_url),
            "mode": state.mode.value,
            "business_goals": state.brand_profile.business_goals,
            "industry": state.brand_profile.industry,
        }

    @staticmethod
    def get_audience_slice(state: MasterEngineState) -> Dict[str, Any]:
        """Provides audience parameters omitting heavy DOM trees and terminal logs."""
        visual_notes = [
            ev.observation_notes for ev in state.research_repository.visual_evidence_vnc
        ]
        return {
            "mode": state.mode.value,
            "industry": state.brand_profile.industry,
            "target_market": state.brand_profile.target_market,
            "observation_notes": " | ".join(visual_notes) if visual_notes else "Standard digital touchpoint",
            "business_goals": state.brand_profile.business_goals,
            "competitors": state.research_repository.competitor_profiles,
        }

    @staticmethod
    def get_brand_slice(state: MasterEngineState) -> Dict[str, Any]:
        """Provides messaging and positioning context."""
        headline = "Full-Stack Developer & Passionate Problem Solver"
        # Extract title or h1 from DOM snapshot if available
        for snap in state.research_repository.dom_snapshots.values():
            meta = snap.get("metadata", {})
            if meta.get("title"):
                headline = meta["title"]
                break

        return {
            "mode": state.mode.value,
            "headline": headline,
            "brand_name": state.brand_profile.brand_name,
            "audience_icp": state.strategic_artifacts.audience_analysis.get("icp_profile", {}),
            "competitors": state.research_repository.competitor_profiles,
        }

    @staticmethod
    def get_seo_slice(state: MasterEngineState) -> Dict[str, Any]:
        """Provides semantic headings, schema blocks, and competitor keywords."""
        first_url = str(state.brand_profile.website_url)
        snapshot = state.research_repository.dom_snapshots.get(first_url, {})

        return {
            "mode": state.mode.value,
            "website_url": first_url,
            "dom_snapshot": snapshot,
            "brand_positioning": state.strategic_artifacts.brand_positioning,
        }

    @staticmethod
    def get_growth_slice(state: MasterEngineState) -> Dict[str, Any]:
        """Provides upstream synthesized findings for initiative drafting."""
        return {
            "mode": state.mode.value,
            "website_url": str(state.brand_profile.website_url),
            "audience_analysis": state.strategic_artifacts.audience_analysis,
            "brand_positioning": state.strategic_artifacts.brand_positioning,
            "seo_and_content_plan": state.strategic_artifacts.seo_and_content_plan,
            "visual_evidence_vnc": state.research_repository.visual_evidence_vnc,
            "business_goals": state.brand_profile.business_goals,
        }

    @staticmethod
    def get_validator_slice(state: MasterEngineState) -> Dict[str, Any]:
        """Provides proposed initiatives and raw evidence repository for adversarial check."""
        return {
            "growth_initiatives": state.strategic_artifacts.growth_initiatives,
            "research_repository": state.research_repository.model_dump(),
            "brand_profile": state.brand_profile.model_dump(),
        }
