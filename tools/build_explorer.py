"""Build the single-file Explorer from explorer/src/.

Writes explorer/index.html (a complete document, opened from the repository so it can fetch
examples/traces/). With --artifact PATH, also writes the body-only form used for publishing,
which a host wraps in its own document skeleton.

    python3 tools/build_explorer.py [--run-tests] [--artifact PATH]

The Conformance section shows the test counts (collected at build time), the findings in AUDIT.md,
and the last recorded run in explorer/conformance-results.json. --run-tests runs the suite, the
JavaScript conformance check and 60 lab seeds first and records the outcome there. Without it the
build is deterministic, so CI can check that the committed page is up to date.
"""
from __future__ import annotations

import base64
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "explorer" / "src"


FILE_ABOUT = {
    "test_axioms.py": "Each axiom A1 to A13 holds, and breaking it is rejected",
    "test_rules.py": "Clause forms: windows, exits, selections, valuations, duties, links",
    "test_canon.py": "Canonical JSON, hashing and seals",
    "test_crypto.py": "Ed25519 test vectors and the strict verification rules",
    "test_differential.py": "Python and JavaScript on 30,000+ seeded random operations",
    "test_robustness.py": "Fuzzing signed events and the command line",
    "test_terms.py": "All 16 Terms, every parameter and claim type",
    "test_js_conformance.py": "The JavaScript engine reproduces every Python trace",
    "test_simulate_trace.py": "Traces and what-if simulations",
    "test_audit_regressions.py": "One regression test per audit finding",
    "test_mcp_server.py": "The read-only MCP server: its 13 tools agree with the CLI and engine",
    "test_integration_lcp.py": "Optional Legal Context Protocol integration, outside the language",
    "test_integration_vc.py": "Optional Verifiable Credentials convention, outside the language",
    "test_integrations_index.py": "The machine-readable index of optional integrations",
    "test_site_pages.py": "The website build: every page, link, search entry and stated fact",
}


RESULTS = ROOT / "explorer" / "conformance-results.json"


def run_suite() -> None:
    """Run the suite, the JavaScript conformance check and 60 lab seeds, and record the outcome in RESULTS."""
    out: dict = {"run": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d")}
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True, text=True)
    tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    passed = int((re.search(r"(\d+) passed", tail) or [0, 0])[1])
    failed = int((re.search(r"(\d+) failed", tail) or [0, 0])[1])
    out["pytest"] = {"passed": passed, "failed": failed}
    sys.path[:0] = [str(ROOT / "tests"), str(ROOT / "src"), str(ROOT / "examples")]
    import tempfile

    from test_js_conformance import _term_scenarios  # type: ignore
    with tempfile.TemporaryDirectory() as d:
        fx = Path(d) / "fixtures.json"
        subprocess.run([sys.executable, str(ROOT / "tools" / "dump_conformance.py"), str(fx)], check=True, capture_output=True)
        data = json.loads(fx.read_text())
        traces, renders, bundles = _term_scenarios()
        data["traces"] += traces
        data["renders"] += renders
        data["bundles"].update(bundles)
        fx.write_text(json.dumps(data, ensure_ascii=False))
        js = subprocess.run(["node", str(ROOT / "tests" / "js_conformance.mjs"), str(fx)], capture_output=True, text=True)
    m = re.search(r"(\d+)/(\d+) conformance checks passed \((\d+) traces", js.stdout)
    if m:
        out["js"] = {"passed": int(m.group(1)), "total": int(m.group(2)), "traces": int(m.group(3))}
    lab = subprocess.run(["node", str(ROOT / "tests" / "js_lab.mjs"), "60"], capture_output=True, text=True)
    m = re.search(r"(\d+) generated runs, (\d+) failures", lab.stdout)
    if m:
        out["lab"] = {"runs": int(m.group(1)), "failures": int(m.group(2))}
    RESULTS.write_text(json.dumps(out, indent=1) + "\n")
    print(f"wrote {RESULTS.relative_to(ROOT)}: {out}")


def conformance() -> dict:
    """Facts for the Conformance section: test counts, the last recorded run, and AUDIT.md. Deterministic."""
    out: dict = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    col = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
                         cwd=ROOT, capture_output=True, text=True)
    files: dict[str, int] = {}
    for line in col.stdout.splitlines():
        m = re.match(r"tests/(test_\w+\.py)::", line)
        if m:
            files[m.group(1)] = files.get(m.group(1), 0) + 1
    out["files"] = [{"file": f, "tests": n, "about": FILE_ABOUT.get(f, "")} for f, n in sorted(files.items(), key=lambda x: (-x[1], x[0]))]
    audit = (ROOT / "AUDIT.md").read_text()
    out["audit"] = [{"id": m.group(1), "sev": m.group(2), "title": m.group(3).rstrip(".")}
                    for m in re.finditer(r"^\| (F\d+) \| (\w+) \| \*\*(.+?)\*\*", audit, re.M)]
    opens = audit.split("## What remains open", 1)[1].split("\n## ", 1)[0]
    out["open"] = len(re.findall(r"^\d+\. ", opens, re.M))
    return out


def build() -> str:
    page = (SRC / "app.html").read_text()
    terms = [json.loads(p.read_text()) for p in sorted((ROOT / "spec" / "06-terms").glob("*.json"))]
    parts = {
        "/*@@TERMS@@*/": json.dumps(terms, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
        "/*@@TOKENS@@*/": (SRC / "tokens.css").read_text(),
        "/*@@UP_CRYPTO@@*/": (SRC / "up-crypto.js").read_text(),
        "/*@@UP_ENGINE@@*/": (SRC / "up-engine.js").read_text(),
        "/*@@UP_LAB@@*/": (SRC / "up-lab.js").read_text(),
        "/*@@UP_PLAY@@*/": (SRC / "up-play.js").read_text(),
        "/*@@CONFORMANCE@@*/": json.dumps(conformance(), ensure_ascii=False).replace("</", "<\\/"),
        "/*@@APP@@*/": (SRC / "app.js").read_text(),
    }
    for name in ("BLACK_96", "WHITE_96", "BLACK_64", "WHITE_64"):
        png = (SRC / f"logo-{name.lower().replace('_', '-')}.png").read_bytes()
        page = page.replace(f"@@LOGO_{name}@@", "data:image/png;base64," + base64.b64encode(png).decode())
    for k, v in parts.items():
        if "</script" in v.lower():
            raise SystemExit(f"{k} contains </script")
        page = page.replace(k, v)
    return page


def main(argv: list[str]) -> None:
    if "--run-tests" in argv:
        run_suite()
    body = build()
    head, _, rest = body.partition("<!--BODY-->")
    doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
           + head + "</head>\n<body>\n" + rest + "</body>\n</html>\n")
    out = ROOT / "explorer" / "index.html"
    out.write_text(doc)
    print(f"wrote {out.relative_to(ROOT)} ({len(doc) // 1024} KB)")
    if "--artifact" in argv:
        p = Path(argv[argv.index("--artifact") + 1])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(head + rest)
        print(f"wrote {p} ({len(head + rest) // 1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1:])
