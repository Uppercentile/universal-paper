# Hosted, read-only Universal Paper MCP server (streamable HTTP at /mcp).
# Build from the repository root:  docker build -f deploy/mcp/Dockerfile -t up-mcp .
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UP_MCP_PUBLIC=1 PORT=8080 UP_EXAMPLES_DIR=/app/examples
WORKDIR /app
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY spec ./spec
COPY src ./src
COPY examples ./examples
RUN pip install --no-cache-dir '.[mcp]' && useradd --system --no-create-home up
USER up
EXPOSE 8080
CMD ["sh", "-c", "up-mcp --transport streamable-http --public --host 0.0.0.0 --port ${PORT}"]
