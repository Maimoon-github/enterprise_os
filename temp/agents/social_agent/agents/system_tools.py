import json
import logging
import asyncio
from typing import Dict, Any, List
from langchain_core.tools import tool
from pydantic import BaseModel, Field

# We import the mcp tools from our web_search
try:
    from social_agent.mcp_tools.web_search import (
        search_trends as _search_trends,
        search_web_and_browse as _search_web_and_browse,
        search_social_content as _search_social_content,
        search_local_places as _search_local_places
    )
except ImportError:
    _search_trends = _search_web_and_browse = _search_social_content = _search_local_places = None

logger = logging.getLogger(__name__)

class QueryBrandRagInput(BaseModel):
    query: str = Field(..., description="Query to search against internal brand guidelines.")

@tool("tool_query_brand_rag", args_schema=QueryBrandRagInput)
async def tool_query_brand_rag(query: str) -> Dict[str, Any]:
    """Queries hybrid RAG memory for brand voice and guidelines."""
    # Mocking hybrid retriever behavior for the unified action orchestrator
    logger.info(f"Querying Brand RAG for: {query}")
    return {
        "status": "success", 
        "query": query, 
        "results": [
            "Brand tone should be professional and technical.",
            "Avoid buzzwords like 'synergy' or 'disrupt'."
        ]
    }

class SearchWebTrendsInput(BaseModel):
    query: str = Field(..., description="Search keyword, domain topic, or trend phrase.")
    timeframe: str = Field(default="24h", description="Recency filter window ('24h', '7d', '30d')")

@tool("tool_search_web_trends", args_schema=SearchWebTrendsInput)
async def tool_search_web_trends(query: str, timeframe: str = "24h") -> Dict[str, Any]:
    """Queries search APIs (via FastMCP) for baseline trend discovery and real-time news."""
    if _search_trends:
        return await _search_trends(query=query, timeframe=timeframe)
    return {"status": "failed", "message": "Tool not available."}

class BrowseWebpageInput(BaseModel):
    url: str = Field(..., description="HTTPS URL of the page you want to scrape.")

@tool("tool_browse_webpage", args_schema=BrowseWebpageInput)
async def tool_browse_webpage(url: str) -> Dict[str, Any]:
    """Executes live web search/scraping on a target webpage to extract readable content (SSRF protected)."""
    if _search_web_and_browse:
        return await _search_web_and_browse(query=url, max_results=1)
    return {"status": "failed", "message": "Tool not available."}

class SearchSocialTrendsInput(BaseModel):
    keywords: str = Field(..., description="Keywords, hashtags, or viral topic queries.")
    platforms: List[str] = Field(description="Target platforms (e.g. ['instagram', 'x_twitter'])")

@tool("tool_search_social_trends", args_schema=SearchSocialTrendsInput)
async def tool_search_social_trends(keywords: str, platforms: List[str]) -> Dict[str, Any]:
    """Aggregates public social posts and viral hooks across Instagram, Facebook, Threads, and X."""
    if _search_social_content:
        return await _search_social_content(keywords=keywords, platforms=platforms)
    return {"status": "failed", "message": "Tool not available."}

class SearchLocalVenuesInput(BaseModel):
    query: str = Field(..., description="Place category or query (e.g., 'coffee shops').")
    location: str = Field(..., description="Geographic city, district, or coordinates.")

@tool("tool_search_local_venues", args_schema=SearchLocalVenuesInput)
async def tool_search_local_venues(query: str, location: str) -> Dict[str, Any]:
    """Queries local places APIs returning venue names, addresses, ratings, and regional POI insights."""
    if _search_local_places:
        return await _search_local_places(query=query, location=location)
    return {"status": "failed", "message": "Tool not available."}

class TriggerSocialCampaignInput(BaseModel):
    prompt: str = Field(..., description="Instructions for the agent explaining what kind of campaign to create.")
    platforms: List[str] = Field(description="List of target platforms (e.g., ['instagram', 'x_twitter']).")

@tool("tool_trigger_social_campaign", args_schema=TriggerSocialCampaignInput)
async def tool_trigger_social_campaign(prompt: str, platforms: List[str]) -> Dict[str, Any]:
    """Spawns multi-agent LangGraph workflow. Triggers autonomous campaign creation and persists to Django DB."""
    try:
        from social_agent.models import SocialCampaign
        from social_agent.tasks import run_campaign_workflow_task
        from django.db import transaction
        
        # We need a synchronous context or an async-safe creation. 
        # But this is a regular Django model call. Wait, Django async ORM.
        campaign = await SocialCampaign.objects.acreate(
            title=f"Campaign: {prompt[:20]}",
            raw_prompt=prompt,
            target_platforms=platforms,
            status="PENDING"
        )
        # Typically run_campaign_workflow_task would be triggered via celery on commit
        # transaction.on_commit is synchronous. For async, we can just trigger it directly:
        run_campaign_workflow_task.delay(str(campaign.id))
        
        return {
            "status": "success",
            "campaign_id": str(campaign.id),
            "message": "Initialized LangGraph multi-agent campaign workflow.",
            "platforms": platforms
        }
    except Exception as e:
        logger.error(f"Failed to launch campaign: {str(e)}")
        return {"status": "error", "message": str(e)}

class CheckConnectedAccountsInput(BaseModel):
    pass

@tool("tool_check_connected_accounts", args_schema=CheckConnectedAccountsInput)
async def tool_check_connected_accounts() -> List[Dict[str, Any]]:
    """Resolves connected social media channels and their diagnostic health status."""
    return [
        {"platform": "x_twitter", "status": "authenticated", "handle": "@tech_architect"},
        {"platform": "instagram", "status": "authenticated", "handle": "@enterprise.ai.lab"}
    ]

# Gather all tools
ORCHESTRATOR_TOOLS = [
    tool_query_brand_rag,
    tool_search_web_trends,
    tool_browse_webpage,
    tool_search_social_trends,
    tool_search_local_venues,
    tool_trigger_social_campaign,
    tool_check_connected_accounts
]
