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

**Fly.io (`fly.toml`, recommended).** One 256 MB machine that stops when idle and wakes on the next request in about a second, so MCP clients and directory checks don't time out. Fly has no free allowance for new accounts; a machine that is mostly stopped costs cents to about $2 a month, and a card is required. `.github/workflows/deploy-mcp.yml` deploys on every relevant push to `main` once the `FLY_API_TOKEN` repository secret exists.

**Render (`render.yaml`, $0).** The free plan needs no card, but it sleeps after 15 idle minutes and can take up to a minute to wake, which can make the first call from an agent time out. Render deploys from GitHub itself; no secret needed.

## One-time setup (owner accounts)

1. **Host.** Fly.io: create an account, run `fly apps create universal-paper-mcp` (or create it in the dashboard), create a deploy token (`fly tokens create deploy -a universal-paper-mcp`), and add it as the repository secret `FLY_API_TOKEN`; then run the "Deploy MCP endpoint" workflow. Render instead: New > Blueprint, pick this repository.
2. **Domain.** Add `mcp.universalpaper.org` as a custom domain on the host (`fly certs add mcp.universalpaper.org -a universal-paper-mcp`). At the DNS provider for universalpaper.org, add the record the host shows: a `CNAME` from `mcp` to `universal-paper-mcp.fly.dev` (or the Render hostname).
3. **PyPI trusted publishing.** On pypi.org, under Publishing, add a pending publisher for each of `universal-paper` and `universal-paper-mcp`: owner `Uppercentile`, repository `universal-paper`, workflow `release.yml`, environment `pypi`. In the repository settings, create the environment `pypi` (optionally requiring approval).
4. **Release.** Create a GitHub Release with the tag `v0.1.0` (it must match the versions in `pyproject.toml`, `packages/universal-paper-mcp/pyproject.toml` and `server.json`). `release.yml` tests, builds and publishes both packages to PyPI, then publishes `server.json` to the MCP Registry with GitHub OIDC. No tokens are stored anywhere.

## Releasing a new version

Bump the version in `pyproject.toml`, `src/universal_paper/__init__.py`, `packages/universal-paper-mcp/pyproject.toml` (also its `universal-paper[mcp]==` pin) and both places in `server.json`; `tests/test_mcp_server.py` fails if they disagree. Then tag.
