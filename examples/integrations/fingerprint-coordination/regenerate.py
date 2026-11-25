"""Rebuild the Fingerprint Coordination worked examples from the public example bundles, so they cannot drift.

    python3 examples/integrations/fingerprint-coordination/regenerate.py           # write the files
    python3 examples/integrations/fingerprint-coordination/regenerate.py --check   # exit 1 if any file is stale

Writes demo-profile.json, contribution.json and structural-diff.json, and embeds the profile in
demo/index.html (so the demo opens from disk with no network calls). Inputs are only the hypothetical,
public bundles under examples/. OPTIONAL: nothing in Universal Paper reads these files.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))

import up_fpc  # noqa: E402

# (label, source, disclosure). The confidential example is shared as its hashes-only file: its sealed
# prices and fee rate stay sealed and are never counted, only its structure and open parameters are.
INPUTS = [
    ("conventional", "examples/conventional/bundle.json", "parameters"),
    ("confidential (hashes only)", "examples/confidential/bundle.hashes-only.json", "parameters"),
    ("generative", "examples/generative/bundle.json", "parameters"),
    ("mandate-cap", "examples/mandate-cap/bundle.json", "parameters"),
    ("overlay", "examples/overlay/bundle.json", "parameters"),
    ("what-if", "examples/what-if/bundle.json", "parameters"),
]
NOTICE = ("SIMULATED FROM PUBLIC EXAMPLES. Every input is a hypothetical example bundle already published in the "
          "Universal Paper repository (CC0 1.0). Parties, prices and fees are invented. This is not market data, a benchmark "
          "or a recommendation. Optional external convention: Universal Paper does not operate, require or depend on it.")


def load_inputs() -> list[dict]:
    return [{"label": label, "source": src, "disclosure": disc,
             "data": json.loads((ROOT / src).read_text(encoding="utf-8"))} for label, src, disc in INPUTS]


def dumps(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def build() -> dict[Path, str]:
    inputs = load_inputs()
    profile = up_fpc.derive_profile(inputs, minimum_cohort=3, max_seeds=2, notice=NOTICE)
    conventional = inputs[0]
    contrib = up_fpc.contribution(
        contributor="did:example:hypothetical-health-purchasing-alliance",
        artifacts=[{"fingerprint": up_fpc.fingerprint(conventional["data"]), "kind": "Bundle", "disclosure": "parameters"}],
        purposes=["parameter-ranges", "variance", "historical-deltas", "proposal-seeds"],
        minimum_cohort=3, created="2027-04-20T12:00:00Z", expires="2028-04-20T12:00:00Z")
    diff = up_fpc.diff_bundles(conventional["data"], inputs[5]["data"])
    page = (HERE / "demo/index.html").read_text(encoding="utf-8")
    embedded = json.dumps(profile, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    page, n = re.subn(r'(<script type="application/json" id="profile">).*?(</script>)',
                      lambda m: m.group(1) + embedded + m.group(2), page, count=1, flags=re.S)
    if n != 1:
        raise SystemExit("demo/index.html has no profile <script> block")
    return {HERE / "demo-profile.json": dumps(profile), HERE / "contribution.json": dumps(contrib),
            HERE / "structural-diff.json": dumps(diff), HERE / "demo/index.html": page}


def main(argv: list[str]) -> int:
    files = build()
    if "--check" in argv:
        stale = [p for p, text in files.items() if not p.is_file() or p.read_text(encoding="utf-8") != text]
        for p in stale:
            print(f"stale: {p.relative_to(ROOT)}  (run {Path(__file__).relative_to(ROOT)})")
        return 1 if stale else 0
    for p, text in files.items():
        p.write_text(text, encoding="utf-8")
        print(f"wrote {p.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
