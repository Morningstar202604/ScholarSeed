# ScholarSeed MCP server (stdio, JSON-RPC 2.0) — pure Python stdlib, no dependencies.
# The server needs the repository root as its working directory (it reads plugin.json
# for its version and scripts/ for the pipeline tools).
FROM python:3.12-slim

WORKDIR /app

COPY scripts/ ./scripts/
COPY plugin.json mcp.json ./

ENTRYPOINT ["python", "scripts/paper_tools.py"]
