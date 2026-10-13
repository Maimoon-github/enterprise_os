from typing import Any, Dict
from src.memory.summarizer import StateSummarizer
from src.schemas.state import (
    AnalystSlice,
    AudienceSlice,
    BrandSlice,
    GrowthSlice,
    MasterEngineState,
    SEOSlice,
    ValidatorSlice,
)


class ContextIsolator:
    """Extracts strictly bounded, typed state slices for each domain specialist."""

    @classmethod
    def get_analyst_slice_model(cls, state: MasterEngineState) -> AnalystSlice:
        """Returns strongly-typed AnalystSlice contract."""
        return AnalystSlice(
            website_url=str(state.brand_profile.website_url),
            mode=state.mode.value,
            business_goals=state.brand_profile.business_goals,
            industry=state.brand_profile.industry,
        )

    @classmethod
    def get_analyst_slice(cls, state: MasterEngineState) -> Dict[str, Any]:
        """Provides minimal parameters needed for visual and DOM exploration, token-bounded."""
        model = cls.get_analyst_slice_model(state)
        return StateSummarizer.compress_scratchpad(model.model_dump())

    @classmethod
    def get_audience_slice_model(cls, state: MasterEngineState) -> AudienceSlice:
        """Returns strongly-typed AudienceSlice contract."""
        visual_notes = [
            ev.observation_notes for ev in state.research_repository.visual_evidence_vnc
        ]
        return AudienceSlice(
            mode=state.mode.value,
            industry=state.brand_profile.industry,
            target_market=state.brand_profile.target_market,
            observation_notes=" | ".join(visual_notes) if visual_notes else "Standard digital touchpoint",
            business_goals=state.brand_profile.business_goals,
            competitors=state.research_repository.competitor_profiles,
        )

    @classmethod
    def get_audience_slice(cls, state: MasterEngineState) -> Dict[str, Any]:
        """Provides audience parameters omitting heavy DOM trees, token-bounded."""
        model = cls.get_audience_slice_model(state)
        return StateSummarizer.compress_scratchpad(model.model_dump())

    @classmethod
    def get_brand_slice_model(cls, state: MasterEngineState) -> BrandSlice:
        """Returns strongly-typed BrandSlice contract."""
        headline = "Full-Stack Developer & Passionate Problem Solver"
        for snap in state.research_repository.dom_snapshots.values():
            meta = snap.get("metadata", {})
            if meta.get("title"):
                headline = meta["title"]
                break

        return BrandSlice(
            mode=state.mode.value,
            headline=headline,
            brand_name=state.brand_profile.brand_name,
            audience_icp=state.strategic_artifacts.audience_analysis.get("icp_profile", {}),
            competitors=state.research_repository.competitor_profiles,
        )

    @classmethod
    def get_brand_slice(cls, state: MasterEngineState) -> Dict[str, Any]:
        """Provides messaging and positioning context, token-bounded."""
        model = cls.get_brand_slice_model(state)
        return StateSummarizer.compress_scratchpad(model.model_dump())

    @classmethod
    def get_seo_slice_model(cls, state: MasterEngineState) -> SEOSlice:
        """Returns strongly-typed SEOSlice contract."""
        first_url = str(state.brand_profile.website_url)
        snapshot = state.research_repository.dom_snapshots.get(first_url, {})
        return SEOSlice(
            mode=state.mode.value,
            website_url=first_url,
            dom_snapshot=snapshot,
            brand_positioning=state.strategic_artifacts.brand_positioning,
        )

    @classmethod
    def get_seo_slice(cls, state: MasterEngineState) -> Dict[str, Any]:
        """Provides semantic headings, schema blocks, and competitor keywords, token-bounded."""
        model = cls.get_seo_slice_model(state)
        return StateSummarizer.compress_scratchpad(model.model_dump())

    @classmethod
    def get_growth_slice_model(cls, state: MasterEngineState) -> GrowthSlice:
        """Returns strongly-typed GrowthSlice contract."""
        return GrowthSlice(
            mode=state.mode.value,
            website_url=str(state.brand_profile.website_url),
            audience_analysis=state.strategic_artifacts.audience_analysis,
            brand_positioning=state.strategic_artifacts.brand_positioning,
            seo_and_content_plan=state.strategic_artifacts.seo_and_content_plan,
            visual_evidence_vnc=state.research_repository.visual_evidence_vnc,
            business_goals=state.brand_profile.business_goals,
        )

    @classmethod
    def get_growth_slice(cls, state: MasterEngineState) -> Dict[str, Any]:
        """Provides upstream synthesized findings for initiative drafting, token-bounded."""
        model = cls.get_growth_slice_model(state)
        return StateSummarizer.compress_scratchpad(model.model_dump())

    @classmethod
    def get_validator_slice_model(cls, state: MasterEngineState) -> ValidatorSlice:
        """Returns strongly-typed ValidatorSlice contract."""
        return ValidatorSlice(
            growth_initiatives=state.strategic_artifacts.growth_initiatives,
            research_repository=state.research_repository.model_dump(),
            brand_profile=state.brand_profile.model_dump(),
        )

    @classmethod
    def get_validator_slice(cls, state: MasterEngineState) -> Dict[str, Any]:
        """Provides proposed initiatives and raw evidence repository for adversarial check, token-bounded."""
        model = cls.get_validator_slice_model(state)
        return StateSummarizer.compress_scratchpad(model.model_dump())

