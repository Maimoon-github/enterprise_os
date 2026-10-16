from typing import Any, Dict
from src.memory.summarizer import StateSummarizer, TokenBudget
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

    STAGE_TOKEN_BUDGET = TokenBudget

    @classmethod
    def get_analyst_slice_model(cls, state: MasterEngineState) -> AnalystSlice:
        """Returns strongly-typed AnalystSlice contract."""
        return AnalystSlice(
            website_url=state.brand_profile.website_url,
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
        """Returns strongly-typed AudienceSlice contract omitting heavy unpruned DOM trees."""
        visual_notes = [
            f"[{ev.evidence_id}] {ev.observation_notes}" for ev in state.research_repository.visual_evidence_vnc
        ]
        ev_ids = [ev.evidence_id for ev in state.research_repository.visual_evidence_vnc]

        # Pruned DOM summary: title, headings, and opengraph only (omits heavy raw trees)
        dom_summary = {}
        for url, snap in state.research_repository.dom_snapshots.items():
            meta = snap.get("metadata", {})
            dom_summary[url] = {
                "title": meta.get("title", ""),
                "headings": meta.get("headings", []),
                "opengraph": meta.get("opengraph", {}),
            }

        return AudienceSlice(
            mode=state.mode.value,
            industry=state.brand_profile.industry,
            target_market=state.brand_profile.target_market,
            observation_notes=" | ".join(visual_notes) if visual_notes else "Standard digital touchpoint",
            business_goals=state.brand_profile.business_goals,
            competitors=state.research_repository.competitor_profiles,
            visual_evidence_ids=ev_ids,
            dom_summary=dom_summary,
            rag_citations=state.research_repository.rag_citations,
        )

    @classmethod
    def get_audience_slice(cls, state: MasterEngineState) -> Dict[str, Any]:
        """Provides audience parameters omitting heavy DOM trees, token-bounded."""
        model = cls.get_audience_slice_model(state)
        return StateSummarizer.compress_scratchpad(model.model_dump())

    @classmethod
    def get_brand_slice_model(cls, state: MasterEngineState) -> BrandSlice:
        """Returns strongly-typed BrandSlice contract omitting raw DOM trees, terminal logs, and technical SEO markups."""
        headline = ""
        subheadings = []
        for snap in state.research_repository.dom_snapshots.values():
            meta = snap.get("metadata", {})
            if not headline and meta.get("title"):
                headline = meta["title"]
            headings = meta.get("headings", [])
            for h in headings:
                if isinstance(h, dict):
                    text = h.get("text", "")
                    lvl = (h.get("level") or h.get("tag") or "").lower()
                    if lvl in ("h1", "hero") and not headline:
                        headline = text
                    elif text and text not in subheadings:
                        subheadings.append(text)
                elif isinstance(h, str) and h not in subheadings:
                    subheadings.append(h)
            if headline and subheadings:
                break

        if not headline:
            headline = "Full-Stack Developer & Passionate Problem Solver"

        visual_summaries = [
            f"[{ev.evidence_id}] {ev.observation_notes}"
            for ev in state.research_repository.visual_evidence_vnc
        ]
        visual_evidence_ids = [
            ev.evidence_id for ev in state.research_repository.visual_evidence_vnc
        ]

        return BrandSlice(
            mode=state.mode.value,
            headline=headline,
            brand_name=state.brand_profile.brand_name,
            audience_icp=state.strategic_artifacts.audience_analysis.get("icp_profile", {}),
            competitors=state.research_repository.competitor_profiles,
            visual_summaries=visual_summaries,
            visual_evidence_ids=visual_evidence_ids,
            subheadings=subheadings[:5],
            competitor_messaging=state.research_repository.competitor_profiles,
            audience_analysis=state.strategic_artifacts.audience_analysis,
            rag_citations=state.research_repository.rag_citations,
        )

    @classmethod
    def get_brand_slice(cls, state: MasterEngineState) -> Dict[str, Any]:
        """Provides messaging and positioning context, token-bounded."""
        model = cls.get_brand_slice_model(state)
        return StateSummarizer.compress_scratchpad(model.model_dump())

    @classmethod
    def get_seo_slice_model(cls, state: MasterEngineState) -> SEOSlice:
        """Returns strongly-typed SEOSlice contract omitting raw VNC screenshot frame buffers and unrelated agent scratchpads."""
        first_url = state.brand_profile.website_url
        snapshot = state.research_repository.dom_snapshots.get(first_url, {})
        return SEOSlice(
            mode=state.mode.value,
            website_url=first_url,
            dom_snapshot=snapshot,
            dom_snapshots=state.research_repository.dom_snapshots,
            competitor_profiles=state.research_repository.competitor_profiles,
            brand_positioning=state.strategic_artifacts.brand_positioning,
            rag_citations=state.research_repository.rag_citations,
        )

    @classmethod
    def get_seo_slice(cls, state: MasterEngineState) -> Dict[str, Any]:
        """Provides semantic headings, schema blocks, and competitor keywords, token-bounded."""
        model = cls.get_seo_slice_model(state)
        return StateSummarizer.compress_scratchpad(model.model_dump())

    @classmethod
    def get_growth_slice_model(cls, state: MasterEngineState) -> GrowthSlice:
        """Returns strongly-typed GrowthSlice contract omitting raw VNC frame buffers and transient scratchpads."""
        failed_entries = [e for e in state.validation_report.audit_trail if not e.passed]
        rejection_reasons = [e.failure_reason for e in failed_entries if e.failure_reason] or None

        return GrowthSlice(
            mode=state.mode.value,
            website_url=state.brand_profile.website_url,
            brand_profile=state.brand_profile.model_dump(),
            audience_analysis=state.strategic_artifacts.audience_analysis,
            brand_positioning=state.strategic_artifacts.brand_positioning,
            seo_and_content_plan=state.strategic_artifacts.seo_and_content_plan,
            visual_evidence_vnc=state.research_repository.visual_evidence_vnc,
            research_repository={
                "visual_evidence_ids": [ev.evidence_id for ev in state.research_repository.visual_evidence_vnc],
                "dom_snapshots_keys": list(state.research_repository.dom_snapshots.keys()),
                "competitor_profiles": state.research_repository.competitor_profiles,
                "rag_citations": state.research_repository.rag_citations,
            },
            rag_citations=state.research_repository.rag_citations,
            business_goals=state.brand_profile.business_goals,
            rejection_reasons=rejection_reasons,
            iteration_cycle=state.iteration_counter,
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
            iteration_counter=state.iteration_counter,
        )

    @classmethod
    def get_validator_slice(cls, state: MasterEngineState) -> Dict[str, Any]:
        """Provides proposed initiatives and raw evidence repository for adversarial check, token-bounded."""
        model = cls.get_validator_slice_model(state)
        return StateSummarizer.compress_scratchpad(model.model_dump())

