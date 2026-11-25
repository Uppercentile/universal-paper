"""Rebuild the Fingerprint Coordination worked examples from the public example bundles, so they cannot drift.

    python3 examples/integrations/fingerprint-coordination/regenerate.py           # write the files
    python3 examples/integrations/fingerprint-coordination/regenerate.py --check   # exit 1 if any file is stale

Writes demo-profile.json, contribution.json, structural-diff.json and demo/scenario.json (the predictive-redline
playthrough of seed-1, derived only from the profile), and embeds the profile, the scenario, the static step list
and the HowTo JSON-LD in demo/index.html (so the demo opens from disk with no network calls). Inputs are only the hypothetical,
public bundles under examples/. OPTIONAL: nothing in Universal Paper reads these files.
"""
from __future__ import annotations

import html
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


SCENARIO_SEED = "seed-1"
AGENT_SENTENCE = ("An agent can read scenario.json, verify both agreement fingerprints, and reproduce this simulation with any "
                  "Universal Paper engine. The picture is not the source.")


def _pct(d: str) -> str:
    return f"{abs(float(d)) * 100:g}%"


def build_scenario(profile: dict) -> dict:
    """The predictive-redline playthrough of one seed. Every value is copied from the profile; nothing is typed by hand."""
    seed = next(s for s in profile["seeds"] if s["id"] == SCENARIO_SEED)
    ch, sim, basis, t = seed["change"], seed["simulation"], seed["basis"], seed["target"]
    deltas = sim["obligationsChanged"]
    pretty = f"{ch['term'].removeprefix('UP:')} · {ch['param']}"
    delta_text = "; ".join(f"the {d['after']['period']['start'][:7]} {d['after']['clause']} obligation from "
                           f"{d['before']['amount']['value']} {d['before']['amount']['currency']} to "
                           f"{d['after']['amount']['value']} {d['after']['amount']['currency']}" for d in deltas)
    verdict = "accepted" if sim["accepted"] else "rejected"
    steps = [
        {"id": "variance", "reveals": ["parameter", "before", "median", "cohort"],
         "text": f"{pretty} on {t['label']} is {ch['from']}, {_pct(basis['deviation'])} {'below' if basis['deviation'].startswith('-') else 'above'} "
                 f"the median of {basis['median']} across {basis['observations']} comparable agreements from {basis['inputs']} inputs."},
        {"id": "seed", "reveals": ["rule", "change"],
         "text": f"The {seed['rule']} rule moves the largest numeric outlier in the cohort to the cohort median, "
                 f"giving the seed {ch['clause']}.{ch['param']} {ch['from']} → {ch['to']}."},
        {"id": "engine", "reveals": ["engine", "result", "delta"],
         "text": f"The Universal Paper engine {verdict} the hypothetical amendment, producing agreement {sim['newAgreement']} "
                 f"and recomputing {delta_text}."},
        {"id": "median", "reveals": ["after"],
         "text": f"{pretty} on {t['label']} now sits at the cohort median of {basis['median']}; no other parameter is changed."},
    ]
    engine: dict = {"verdict": verdict, "assumes": sim["assumes"], "proposedAt": sim["at"], "comparedAt": sim["comparedAt"]}
    if "reason" in sim:
        engine["reason"] = sim["reason"]
    return up_fpc.with_fingerprint({
        "type": "PredictiveRedlineScenario", "convention": up_fpc.CONVENTION, "simulated": True,
        "notice": "SIMULATED FROM PUBLIC EXAMPLES",
        "disclaimer": seed["note"],
        "source": {"profile": "../demo-profile.json", "profileFingerprint": profile["fingerprint"], "seed": seed["id"]},
        "target": {"label": t["label"], "row": t["row"], "input": t["input"], "chain": t["chain"], "agreement": t["agreement"]},
        "parameter": {"key": basis["parameter"], "term": ch["term"], "param": ch["param"], "clause": ch["clause"]},
        "before": ch["from"], "after": ch["to"], "median": basis["median"], "deviation": basis["deviation"],
        "cohort": {"roles": basis["cohort"], "agreements": basis["observations"], "inputs": basis["inputs"]},
        "rule": {"id": seed["rule"], "text": steps[1]["text"]},
        "engine": engine,
        "result": {"supersedes": sim["supersedes"], "newAgreement": sim["newAgreement"], "stateHash": sim["stateHash"]},
        "delta": {"obligationsChanged": deltas, "obligationsAdded": sim["obligationsAdded"], "obligationsRemoved": sim["obligationsRemoved"]},
        "agents": AGENT_SENTENCE,
        "steps": steps,
    })


def howto(scenario: dict) -> dict:
    """schema.org HowTo for the playthrough: the same sentences, in the same order, as scenario.json."""
    base = "https://universalpaper.org/integrations/fingerprint-coordination/demo/"
    return {"@context": "https://schema.org", "@type": "HowTo", "@id": base + "#predictive-redline",
            "name": "Predictive redline from a Universal Paper fingerprint profile (simulated)",
            "description": f"{scenario['notice']}. {scenario['agents']}", "isAccessibleForFree": True,
            "subjectOf": {"@type": "Dataset", "name": "scenario.json", "url": base + "scenario.json", "encodingFormat": "application/json"},
            "step": [{"@type": "HowToStep", "position": i, "name": s["id"], "text": s["text"], "url": f"{base}#step-{s['id']}"}
                     for i, s in enumerate(scenario["steps"], 1)]}


def static_playthrough(scenario: dict) -> str:
    """The no-JavaScript / reduced-motion rendering of the whole cycle, generated from scenario.json."""
    e = html.escape
    steps = "\n".join(f'      <li id="step-{e(s["id"])}" data-step="{i}">{e(s["text"])}</li>' for i, s in enumerate(scenario["steps"]))
    rows = "\n".join(
        f'          <tr><td>{e(d["after"]["clause"])} · {e(d["after"]["duty"])} · {e(d["after"]["period"]["start"][:7])}</td>'
        f'<td><del>{e(d["before"]["amount"]["value"])} {e(d["before"]["amount"]["currency"])}</del></td>'
        f'<td><ins>{e(d["after"]["amount"]["value"])} {e(d["after"]["amount"]["currency"])}</ins></td></tr>'
        for d in scenario["delta"]["obligationsChanged"])
    r = scenario["result"]
    return f"""<ol class="pt-steps" id="pt-steps">
{steps}
    </ol>
    <div class="pt-outcome" id="pt-outcome" aria-live="polite">
      <div class="pt-res">
        <p><span class="pill {'ok' if scenario['engine']['verdict'] == 'accepted' else 'bad'}">engine: {e(scenario['engine']['verdict'])}</span> <span class="pill">hypothetical, unsigned</span></p>
        <dl class="kv">
          <dt>before</dt><dd class="fp" id="pt-fp-old">{e(r['supersedes'])}</dd>
          <dt>after</dt><dd class="fp" id="pt-fp-new">{e(r['newAgreement'])}</dd>
        </dl>
        <table class="ob"><thead><tr><th>obligation</th><th>before</th><th>after</th></tr></thead><tbody>
{rows}
        </tbody></table>
        <p class="sub" style="margin:8px 0 0">{e(scenario['engine']['assumes'].capitalize())}. Compared at {e(scenario['engine']['comparedAt'])}.</p>
      </div>
    </div>"""


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
    scenario = build_scenario(profile)
    page = (HERE / "demo/index.html").read_text(encoding="utf-8")

    def js(obj: dict) -> str:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    for pattern, text in ((r'(<script type="application/json" id="profile">).*?(</script>)', js(profile)),
                          (r'(<script type="application/json" id="scenario">).*?(</script>)', js(scenario)),
                          (r'(<script type="application/ld\+json" id="howto">).*?(</script>)', js(howto(scenario))),
                          (r'(<!-- scenario:begin -->).*?(<!-- scenario:end -->)', "\n    " + static_playthrough(scenario) + "\n    ")):
        page, n = re.subn(pattern, lambda m, text=text: m.group(1) + text + m.group(2), page, count=1, flags=re.S)
        if n != 1:
            raise SystemExit(f"demo/index.html has no block matching {pattern}")
    return {HERE / "demo-profile.json": dumps(profile), HERE / "contribution.json": dumps(contrib),
            HERE / "structural-diff.json": dumps(diff), HERE / "demo/scenario.json": dumps(scenario), HERE / "demo/index.html": page}


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
