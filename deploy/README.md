# Hosting and releasing the MCP server

The official Universal Paper MCP server ships three ways from this repository:

| What | Where | Built from |
|---|---|---|
| Hosted endpoint | `https://mcp.universalpaper.org/mcp` | `Dockerfile`, `up-mcp --hosted` |
| PyPI packages | `universal-paper` (interpreter, CLI, `up-mcp`) and `universal-paper-mcp` (the server by name, for `uvx`) | `pyproject.toml`, `packages/universal-paper-mcp/` |
| MCP Registry entry | `io.github.Uppercentile/universal-paper` | `server.json` |

## What the hosted endpoint does and doesn't do

- Read-only tools only, the same nine as the local server. No keys, no signing, no writes.
- Stateless Streamable HTTP with JSON responses. No sessions, no database, no volume.
- Never reads file paths. Never makes outbound calls (the example bundles are baked into the image).
- No access logs: uvicorn's access log is off, so client addresses and request lines are never written.
- Usage signal: per-tool call counts in memory, at `/stats`, plus one log line per call with the tool name, outcome and duration. Nothing else. A restart resets `/stats`.
- Request bodies are capped at 2 MiB.

Routes: `/mcp` (MCP), `/` (what this is, JSON), `/healthz`, `/stats`.

Run it yourself: `docker build -t up-mcp . && docker run -p 8080:8080 up-mcp`, or `pip install -e '.[hosted]' && up-mcp --hosted`.

## Hosting options

The image runs anywhere that runs a container. Two configs are included.

**Fly.io (`fly.toml`, recommended).** One 256 MB machine that stops when idle and wakes on the next request in about a second, so MCP clients and directory checks don't time out. Fly has no free allowance for new accounts; a machine that is mostly stopped costs cents to about $2 a month, and a card is required. Fly's GitHub integration deploys it; `.github/workflows/deploy-mcp.yml` is an alternative that runs only once a `FLY_API_TOKEN` repository secret exists.

**Render (`render.yaml`, $0).** The free plan needs no card, but it sleeps after 15 idle minutes and can take up to a minute to wake, which can make the first call from an agent time out. Render deploys from GitHub itself; no secret needed.

## One-time setup (owner accounts)

1. **Host.** Fly.io: in the dashboard, Apps > Deploy from GitHub > Choose a repository > this repository, branch `main`, root folder. Fly reads `fly.toml` and the `Dockerfile` and then redeploys on every push to `main`. Name `universal-paper-mcp`, region `iad`, smallest machine; no Postgres, Redis, Tigris or secrets. (Alternative: deploy with the "Deploy MCP endpoint" workflow by adding a `FLY_API_TOKEN` deploy token as a repository secret. Use one or the other, not both.) Render instead: New > Blueprint, pick this repository.
2. **Domain.** Add `mcp.universalpaper.org` as a custom domain on the host (`fly certs add mcp.universalpaper.org -a universal-paper-mcp`). At the DNS provider for universalpaper.org, add the record the host shows: a `CNAME` from `mcp` to `universal-paper-mcp.fly.dev` (or the Render hostname).
3. **PyPI trusted publishing.** On pypi.org, under Publishing, add a pending publisher for `universal-paper` (owner `Uppercentile`, repository `universal-paper`, workflow `release.yml`, environment `pypi`) and one for `universal-paper-mcp` (the same, but environment `pypi-mcp`). PyPI refuses two pending publishers with identical settings. In the repository settings, create the environments `pypi` and `pypi-mcp` (optionally requiring approval).
4. **Release.** Create a GitHub Release with the tag `v0.1.0` (it must match the versions in `pyproject.toml`, `packages/universal-paper-mcp/pyproject.toml` and `server.json`). `release.yml` tests, builds and publishes both packages to PyPI, then publishes `server.json` to the MCP Registry with GitHub OIDC. No tokens are stored anywhere.

## Releasing a new version

Bump the version in `pyproject.toml`, `src/universal_paper/__init__.py`, `packages/universal-paper-mcp/pyproject.toml` (also its `universal-paper[mcp]==` pin) and both places in `server.json`; `tests/test_mcp_server.py` fails if they disagree. Then tag.
