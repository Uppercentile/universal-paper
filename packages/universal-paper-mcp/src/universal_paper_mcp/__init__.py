"""The official Universal Paper MCP server, as its own package:  uvx universal-paper-mcp

A thin entry point over universal_paper.mcp_server, so MCP clients and registries can start the
server by package name. All the code lives in the universal-paper package.
"""
from __future__ import annotations


def main() -> None:
    from universal_paper.mcp_server import main as run

    run()
