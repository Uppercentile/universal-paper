"""Optional LCP integration example, agent side: discover, fetch, verify, evaluate, check the Mandate.

THIS IS AN OPTIONAL EXTERNAL INTEGRATION. Universal Paper does not need it.
See docs/integrations/legal-context-protocol.md.

Run from the repository root:
  python3 examples/integrations/lcp/agent.py            # uses the files next to this script, no network
  python3 examples/integrations/lcp/agent.py --online   # fetches the same files from universalpaper.org

All parties and values are HYPOTHETICAL.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT / "integrations" / "lcp"), str(ROOT / "src")]

import up_lcp  # noqa: E402

from universal_paper.canon import content_hash  # noqa: E402


def load(name: str, online: bool) -> tuple[dict, bytes]:
    """Step 1 and 2: discover the LCP file and fetch the terms it points at."""
    if online:
        lcp = json.loads(up_lcp.fetch(f"https://universalpaper.org/examples/integrations/lcp/{name}/legal-context.json"))
        return lcp, up_lcp.fetch(lcp["terms"])
    lcp = json.loads((HERE / name / "legal-context.json").read_text(encoding="utf-8"))
    return lcp, (HERE / name / Path(lcp["terms"]).name).read_bytes()


def verify_and_evaluate(name: str, online: bool) -> dict:
    lcp, raw = load(name, online)
    print(f"\n== {name}\n1. discovered  terms={lcp['terms']}\n               atrHash={lcp['atrHash']}")
    print(f"2. fetched     {len(raw)} bytes")
    v = up_lcp.verify(lcp, raw)  # step 3
    print(f"3. verified    atrHash matches: {v.atr_hash_matches} · canonical UP JSON: {v.canonical} · fingerprint {v.fingerprint}")
    if not v.ok:
        raise SystemExit("   NOT the pinned terms: " + "; ".join(v.problems))
    assert v.artifact is not None
    for cid in v.chain_ids:
        print(f"               agreement ChainId {cid}")
    r = up_lcp.evaluate(v.artifact)  # step 4: any Universal Paper engine gives the same answer
    print(f"4. evaluated   valid: {r['valid']} · rejected events: {len(r['rejected_events'])} · at {r['state']['at']}")
    for c in r["state"]["chains"]:
        print(f"               {c.get('label') or c['chain_id']}: {c['status']}")
    return v.artifact


def mandate_check(bundle: dict) -> None:
    """Step 5 (optional): before proposing, the agent asks whether its own action is inside its Mandate."""
    m = bundle["mandates"][0]
    mid = content_hash(m)
    cid = content_hash(bundle["chains"][0][0])
    from universal_paper.engine import Bundle, Evaluator
    ev = Evaluator(Bundle(bundle))
    current = ev.agreement(ev.state_at(cid))
    last = max(e["at"] for e in bundle["chains"][0])
    at = (datetime.fromisoformat(last.replace("Z", "+00:00")) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for factor in ("1.01", "1.05"):
        proposed = json.loads(json.dumps(current))
        next(c for c in proposed["clauses"] if c["n"] == "price")["params"]["factor"] = factor
        event = {"chain": 0, "kind": "propose", "by": m["principal"], "at": at,
                 "body": {"agreement": proposed, "supersedes": content_hash(current)},
                 "agent": {"key": m["agent"], "mandate": mid}}
        r = up_lcp.check_mandate(bundle, event)
        verdict = "inside the Mandate" if r["accepted"] else f"outside the Mandate ({r['reason']})"
        print(f"5. mandate     price factor {factor}: {verdict}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--online", action="store_true", help="fetch from universalpaper.org instead of the local files")
    a = ap.parse_args()
    verify_and_evaluate("conventional", a.online)
    mandate_check(verify_and_evaluate("mandate-cap", a.online))


if __name__ == "__main__":
    main()
