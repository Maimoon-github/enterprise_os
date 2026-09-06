import asyncio
import json

from social_agent.mcp_tools.web_search import mcp

async def run_tests():
    print("=== Testing FastMCP web_search endpoints ===")
    
    tools = mcp._tools
    print(f"Registered tools: {list(tools.keys())}")
    
    print("\n1. Testing health_check()...")
    res1 = await tools['health_check']()
    print(json.dumps(res1, indent=2))
    
    print("\n2. Testing search_trends()...")
    res2 = await tools['search_trends'](query="AI Agents 2026", timeframe="7d")
    print(json.dumps(res2, indent=2))
    
    print("\n3. Testing search_social_content()...")
    res3 = await tools['search_social_content'](keywords="OpenAI O1 reasoning")
    print(json.dumps(res3, indent=2))
    
    print("\n4. Testing fetch_profile_and_posts()...")
    res4 = await tools['fetch_profile_and_posts'](account_handle="tech_lead")
    print(json.dumps(res4, indent=2))
    
    print("\n5. Testing search_local_places()...")
    res5 = await tools['search_local_places'](query="coffee", location="Karachi")
    print(json.dumps(res5, indent=2))
    
    print("\n6. Testing search_web_and_browse()...")
    res6 = await tools['search_web_and_browse'](query="LangGraph python documentation", max_results=1)
    
    # Trim the long page_content if present
    if "results" in res6:
        for r in res6["results"]:
            if "page_content" in r:
                r["page_content"] = r["page_content"][:100] + "... [TRUNCATED]"
    print(json.dumps(res6, indent=2))
    print("\nAll endpoints executed successfully without internal crashes!")

if __name__ == "__main__":
    asyncio.run(run_tests())
