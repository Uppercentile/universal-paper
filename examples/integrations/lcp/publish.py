"""Optional LCP integration example, publisher side: pin a Universal Paper bundle in a legal-context.json.

THIS IS AN OPTIONAL EXTERNAL INTEGRATION. Universal Paper does not need it.
See docs/integrations/legal-context-protocol.md.

Run from the repository root:  python3 examples/integrations/lcp/publish.py

For each example it writes two files next to this script:
  <name>/terms.up.json        the bundle's canonical bytes (serve these exactly, byte for byte)
  <name>/legal-context.json   the LCP discovery file (a publisher serves it at /.well-known/legal-context.json)

The terms files are snapshots of examples/<name>/bundle.json, pinned by hash on purpose: that is
the point of atrHash. Re-running this script after the examples change makes new snapshots with new
hashes. All parties and values are HYPOTHETICAL.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / "integrations" / "lcp"), str(ROOT / "src")]

import up_lcp  # noqa: E402

BASE_URL = "https://universalpaper.org/examples/integrations/lcp"

# (example, LCP options). mandate-cap asks for explicit acceptance (LCP Level 3) because an agent
# acts for the aggregator there; conventional stops at Level 2 (provable terms).
EXAMPLES = {
    "conventional": {},
    "mandate-cap": {"acceptance_required": True},
}


def main() -> None:
    for name, opts in EXAMPLES.items():
        bundle = json.loads((ROOT / "examples" / name / "bundle.json").read_text(encoding="utf-8"))
        out = HERE / name
        out.mkdir(exist_ok=True)
        (out / "terms.up.json").write_bytes(up_lcp.canonical_bytes(bundle))
        doc = up_lcp.legal_context(f"{BASE_URL}/{name}/terms.up.json", bundle, **opts)
        (out / "legal-context.json").write_text(up_lcp.dumps_legal_context(doc), encoding="utf-8")
        print(f"{name}: {up_lcp.fingerprint(bundle)}  ->  atrHash {doc['atrHash']}")


if __name__ == "__main__":
    main()
