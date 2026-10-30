from fastapi import APIRouter

router = APIRouter()

@router.get("")
async def list_mcp_servers():
    return [
        {
            "name": "brand_rag_server",
            "transport": "Streamable HTTP",
            "endpoint": "http://localhost:8081",
            "capabilities": ["resources", "tools"],
            "status": "connected",
        },
        {
            "name": "social_gateway_server",
            "transport": "Streamable HTTP",
            "endpoint": "http://localhost:8082",
            "capabilities": ["tools", "notifications"],
            "status": "connected",
        },
        {
            "name": "media_studio_server",
            "transport": "Streamable HTTP",
            "endpoint": "http://localhost:8083",
            "capabilities": ["tools", "tasks"],
            "status": "connected",
        },
        {
            "name": "analytics_server",
            "transport": "Streamable HTTP",
            "endpoint": "http://localhost:8084",
            "capabilities": ["tools", "resources"],
            "status": "connected",
        },
    ]
