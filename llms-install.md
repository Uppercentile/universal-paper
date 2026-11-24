# Installing the Universal Paper MCP server (for AI agents)

You are installing the official, read-only Universal Paper MCP server. It needs no API key, account or environment variables, and it never signs or writes anything.

## Preferred: the hosted server (nothing to install)

Add a remote MCP server with Streamable HTTP transport:

- Name: `universal-paper`
- URL: `https://mcp.universalpaper.org/mcp`

Config files that take a URL (Cline, Cursor, VS Code, Windsurf and others):

```json
{
  "mcpServers": {
    "universal-paper": {
      "url": "https://mcp.universalpaper.org/mcp"
    }
  }
}
```

For Cline, set `"type": "streamableHttp"` on the entry if your version asks for a type. For VS Code, use `"type": "http"`.

## Alternative: run locally (stdio)

This needs [uv](https://docs.astral.sh/uv/) (`pip install uv`, or see its docs):

```json
{
  "mcpServers": {
    "universal-paper": {
      "command": "uvx",
      "args": ["universal-paper-mcp"]
    }
  }
}
```

Without uv: `pip install universal-paper-mcp`, then use `"command": "universal-paper-mcp"` with no args.

## Check that it works

1. Call `list_terms`. It should return 16 Terms, such as `UP:Admin-Fee`.
2. Call `simulate_amendment` with `bundle: "example:mandate-cap"`, `clause: "price"`, `param: "factor"`, `value: "1.05"`. It should return `"accepted": false` with a reason saying 1.05 is above the maximum 1.02. That is the expected result: the agent's Mandate caps price changes at 2%.

Any tool accepts `"example:<name>"` as its bundle: `conventional`, `generative`, `confidential`, `overlay` or `mandate-cap`. The local server also accepts file paths; the hosted one does not.

Docs: https://universalpaper.org/developers/#mcp
