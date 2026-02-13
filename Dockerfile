# Beta Graph MCP Server - for Cloud Run
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ src/

RUN pip install uv && uv pip install --system .

ENV CHROMA_PERSIST_DIR=/data

# Chroma data persistence - use volume
VOLUME ["/data"]

EXPOSE 8000

CMD ["python", "-m", "beta_graph.servers.wta.server", "--http"]
