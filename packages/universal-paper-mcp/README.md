# Universal Paper MCP server

<!-- mcp-name: io.github.Uppercentile/universal-paper -->

[![Add to Cursor](https://img.shields.io/badge/Add_to-Cursor-15171b?logo=cursor&logoColor=white)](https://cursor.com/install-mcp?name=universal-paper&config=eyJ1cmwiOiJodHRwczovL21jcC51bml2ZXJzYWxwYXBlci5vcmcvbWNwIn0%3D) [![Install in VS Code](https://img.shields.io/badge/Install_in-VS_Code-2f45c6?logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=universal-paper&config=%7B%22type%22%3A%22http%22%2C%22url%22%3A%22https%3A%2F%2Fmcp.universalpaper.org%2Fmcp%22%7D)

The official [Model Context Protocol](https://modelcontextprotocol.io) server for [Universal Paper](https://universalpaper.org), an open language for agreements between group purchasing organizations (GPOs), suppliers and members.

It lets an AI agent check an agreement the same way every other party does: validate a bundle, derive statuses and obligations, dry-run a signed event, simulate hypothetical events under a Mandate, render the agreement text, hash an object and look up Terms. Every tool is read-only. The server holds no keys, signs nothing, writes nothing and reports nothing.

## Use it

Hosted, nothing to install (Streamable HTTP, no sign-in):

```
https://mcp.universalpaper.org/mcp
```

Or run it locally with [uv](https://docs.astral.sh/uv/):

```
uvx universal-paper-mcp
```

Claude Code: `claude mcp add universal-paper -- uvx universal-paper-mcp`, or for the hosted one `claude mcp add --transport http universal-paper https://mcp.universalpaper.org/mcp`.

Other clients:

```json
{"mcpServers": {"universal-paper": {"command": "uvx", "args": ["universal-paper-mcp"]}}}
```

## Tools

| Tool | What it does |
| --- | --- |
| `validate_bundle` | Check every agreement and event against the axioms; per-event accept or reject with the rule |
| `derive_state` | Statuses, tiers, contract prices and open obligations at a time |
| `check_event` | Dry-run one signed event against its chain, writing nothing |
| `simulate_events` | Run hypothetical unsigned events forward; Mandate limits still apply |
| `simulate_amendment` | Try one parameter change as an agent's amendment; see which Mandate bound it breaks |
| `simulate_rate_conformity` | Do rates conform to the member's contract prices in its tier (or another tier)? |
| `simulate_termination` | If a party gave notice: allowed or not, effective date, what is still owed |
| `simulate_eligibility` | Is a member an active participant, so the agreement's terms and contract prices apply to it? |
| `render_text` | The human-readable agreement text fixed by its hash; optionally as an outsider sees sealed values |
| `hash_object` | Content hash (RFC 8785 JCS + SHA-256) of any JSON value |
| `list_terms`, `explain_term` | The standard 16-Term library |
| `get_example` | Worked example bundles (hypothetical parties and values) |

## Privacy

The local server runs entirely on your machine. The hosted server is stateless: no sessions, storage, access logs or telemetry. It counts calls per tool name, in memory, and shows the totals at [/stats](https://mcp.universalpaper.org/stats). Universal Paper never sets or suggests prices.

## Links

Docs: <https://universalpaper.org/developers/#mcp> · Spec: <https://universalpaper.org/spec/> · Source: <https://github.com/Uppercentile/universal-paper>

Created and offered free by [Uppercentile](https://uppercentile.com). Code Apache-2.0.
