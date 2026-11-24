# The hosted Universal Paper MCP endpoint (https://mcp.universalpaper.org/mcp).
# Stateless and read-only: no volumes, no secrets, no outbound calls. Build: docker build -t up-mcp .
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8080 UP_EXAMPLES_DIR=/srv/examples

WORKDIR /src
COPY pyproject.toml README.md LICENSE NOTICE ./
COPY spec/LICENSE spec/LICENSE
COPY src src
COPY deploy/requirements-hosted.txt /tmp/requirements-hosted.txt
RUN pip install -c /tmp/requirements-hosted.txt '.[hosted]' && rm -rf /src

# The four worked examples, so get_example never reaches out to the network.
COPY examples/conventional/bundle.json /srv/examples/conventional/bundle.json
COPY examples/generative/bundle.json   /srv/examples/generative/bundle.json
COPY examples/confidential/bundle.json /srv/examples/confidential/bundle.json
COPY examples/overlay/bundle.json      /srv/examples/overlay/bundle.json

RUN useradd --system --uid 10001 --no-create-home up
USER up
WORKDIR /srv
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/healthz',timeout=2)"
CMD ["up-mcp", "--hosted"]
