FROM python:3.12-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -u 10002 -s /bin/bash -m mcpuser
WORKDIR /app

COPY backend/pyproject.toml /app/
RUN pip install --no-cache-dir mcp fastmcp httpx pydantic qdrant-client

COPY backend/mcp_servers/ /app/mcp_servers/
RUN chown -R mcpuser:mcpuser /app

USER mcpuser
ENV PYTHONUNBUFFERED=1

EXPOSE 8080
CMD ["python3", "-m", "mcp_servers.social_gateway_server.main"]
