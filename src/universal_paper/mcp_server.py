"""A read-only MCP server for Universal Paper:  up-mcp  (or  python -m universal_paper.mcp_server).

It lets an agent check agreements the same way every other party does: validate a bundle,
derive statuses and obligations, dry-run one event, simulate hypothetical events under a
Mandate, ask what-if questions (an amendment, rate conformity, a termination, a member's eligibility),
render the agreement text, hash an object, and look up Terms.

Every tool is read-only. Nothing is signed, written to disk, or sent anywhere, and the server
holds no keys. Results come from the reference interpreter, so each one can be reproduced by
hand from the specification. Requires the optional dependency:  pip install 'universal-paper[mcp]'
(or run the published package:  uvx universal-paper-mcp).

The same server is hosted at https://mcp.universalpaper.org/mcp (see mcp_http.py). In hosted mode a
bundle can only be passed as an object or as JSON text, never as a file path.
"""
from __future__ import annotations

import functools
import json
import os
import time
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from . import SPEC, __version__, whatif
from .__main__ import InputError, _latest, loads
from .build import load_terms
from .canon import content_hash
from .engine import Bundle, Evaluator, agreement_issues
from .render import render_agreement
from .report import snapshot
from .simulate import simulate

EXAMPLES = ("conventional", "generative", "confidential", "overlay", "mandate-cap", "what-if")
EXAMPLES_DIR = Path(os.environ.get("UP_EXAMPLES_DIR") or Path(__file__).resolve().parents[2] / "examples")
EXAMPLES_URL = "https://universalpaper.org/examples/{name}/bundle.json"

INSTRUCTIONS = (
    f"Universal Paper ({SPEC}) is an open language for agreements between group purchasing "
    "organizations (aggregators), suppliers and members. An agreement is signed, content-addressed "
    "JSON; a bundle holds Terms, Mandates and chains of signed events. These tools are read-only: "
    "use them to check what an agreement says and whether an action is allowed before anyone signs. "
    "Start with get_example or list_terms if you have no bundle yet. Spec: https://universalpaper.org/spec/"
)


# Set to False by the hosted server: a public endpoint must never read files on the machine it runs on.
ALLOW_PATHS = True


def _data(bundle: dict | str) -> dict:
    """A bundle given as an object, as JSON text, as "example:<name>", or (local servers only) as a path to a JSON file."""
    if isinstance(bundle, dict):
        return bundle
    if not isinstance(bundle, str):
        raise InputError("bundle must be a JSON object, JSON text, \"example:<name>\", or a file path")
    text = bundle.strip()
    if text.startswith("example:"):
        return get_example(text.removeprefix("example:"))
    if not text.startswith("{"):
        if not ALLOW_PATHS:
            raise InputError("pass the bundle as a JSON object or JSON text; the hosted server does not read file paths")
        try:
            text = Path(text).expanduser().read_text(encoding="utf-8")
        except OSError as e:
            raise InputError(f"cannot read {bundle}: {e.strerror or e}") from None
    try:
        data = loads(text)
    except json.JSONDecodeError as e:
        raise InputError(f"the bundle is not valid JSON: {e}") from None
    if not isinstance(data, dict):
        raise InputError("a bundle is a JSON object")
    return data


def _label(chain: list[dict], pos: int) -> str:
    body = chain[0].get("body") if chain and isinstance(chain[0], dict) else None
    ag = body.get("agreement") if isinstance(body, dict) else None
    return ag.get("label", f"chain {pos}") if isinstance(ag, dict) else f"chain {pos}"


# ---------------------------------------------------------------------------
# Tool implementations (plain functions, so they can be tested without MCP)
# ---------------------------------------------------------------------------

def validate_bundle(bundle: dict | str) -> dict:
    """Check every agreement and event in a bundle against the axioms."""
    b = Bundle(_data(bundle))
    ev = Evaluator(b)
    chains, rejected = [], 0
    for pos, ch in enumerate(b.chain_list):
        if not ch:
            continue
        cid = content_hash(ch[0])
        events = []
        for st in ev.run(cid):
            events.append({"index": st.index, "kind": st.event.get("kind"), "at": st.event.get("at"),
                           "event_hash": st.event_hash, "accepted": st.accepted, "reason": st.reason or None})
            rejected += not st.accepted
        S = ev.state_at(cid)
        chains.append({"chain": pos, "chain_id": cid, "label": _label(ch, pos), "events": events,
                       "state_hash": content_hash(S) if S else None})
    issues = [{"agreement": h, "rule": rule, "reason": why}
              for h, ag in sorted(b.agreements.items()) for rule, why in agreement_issues(b, ag)]
    forks = sorted(set(b.forks))
    return {"spec": SPEC, "valid": not rejected and not forks and not issues, "rejected_events": rejected,
            "agreement_issues": issues, "forked_chains": forks, "chains": chains}


def derive_state(bundle: dict | str, at: str | None = None) -> dict:
    """Statuses, tiers, contract prices and obligations of every agreement at a time."""
    b = Bundle(_data(bundle))
    return snapshot(Evaluator(b), at or _latest(b))


def check_event(bundle: dict | str, event: dict) -> dict:
    """Dry-run one signed event against its chain's current state. Nothing is written."""
    b = Bundle(_data(bundle))
    ev = Evaluator(b)
    if not isinstance(event, dict):
        raise InputError("event must be a JSON object")
    if "chain" in event:
        if event["chain"] not in b.chains:
            raise InputError("the event names a chain that is not in the bundle")
        S = ev.state_at(event["chain"])
    else:
        if content_hash(event) in b.chains:
            raise InputError("this genesis event already starts a chain in the bundle")
        S = None
    S2, checks, reason = ev.apply(S, event)
    return {"accepted": S2 is not None, "reason": reason or None, "checks": [c.to_json() for c in checks],
            "state_hash": content_hash(S2) if S2 else None}


def simulate_events(bundle: dict | str, events: list[dict], at: str | None = None) -> dict:
    """Run hypothetical, unsigned events forward. Mandate limits still apply."""
    if not isinstance(events, list):
        raise InputError("events must be a list")
    return simulate(_data(bundle), events, at)


def simulate_amendment(bundle: dict | str, clause: str, param: str, value: Any, chain: int = 0,
                       mandate: str | None = None, at: str | None = None) -> dict:
    """Try changing one clause parameter by amendment, proposed by an agent under its Mandate. Unsigned and hypothetical."""
    data = _data(bundle)
    b = Bundle(data)
    if not 0 <= chain < len(b.chain_list) or not b.chain_list[chain]:
        raise InputError(f"no chain {chain} in the bundle (it has {len(b.chain_list)})")
    ev = Evaluator(b)
    cid = content_hash(b.chain_list[chain][0])
    current = ev.agreement(ev.state_at(cid))
    if not current:
        raise InputError(f"chain {chain} has no agreement in force to amend")
    mandates = {content_hash(mm): mm for mm in data.get("mandates", []) if isinstance(mm, dict)}
    keys = {(p.get("party") or {}).get("key") for p in current.get("parties", []) if isinstance(p, dict)}
    if mandate is None:
        fits = [h for h, mm in mandates.items() if mm.get("principal") in keys]
        if len(fits) != 1:
            raise InputError(f"name the Mandate by its hash; {len(fits)} Mandates in the bundle have a principal on chain {chain}")
        mandate = fits[0]
    if mandate not in mandates:
        raise InputError(f"no Mandate {mandate} in the bundle; known: {', '.join(sorted(mandates)) or 'none'}")
    M = mandates[mandate]
    proposed = json.loads(json.dumps(current))
    target = next((c for c in proposed.get("clauses", []) if c.get("n") == clause), None)
    if target is None:
        raise InputError(f"no clause {clause!r}; clauses: {', '.join(c.get('n', '?') for c in proposed.get('clauses', []))}")
    if param not in target.get("params", {}):
        raise InputError(f"clause {clause!r} has no parameter {param!r}; parameters: {', '.join(sorted(target.get('params', {})))}")
    before = target["params"][param]
    if isinstance(before, str) and isinstance(value, int | float) and not isinstance(value, bool):
        value = str(value)  # Decimals and Rates are strings; agents often send numbers
    target["params"][param] = value
    if at is None:
        latest = datetime.fromisoformat(_latest(b).replace("Z", "+00:00")) + timedelta(days=1)
        at = latest.strftime("%Y-%m-%dT%H:%M:%SZ")
    event = {"chain": chain, "kind": "propose", "by": M["principal"], "at": at,
             "body": {"agreement": proposed, "supersedes": content_hash(current)},
             "agent": {"key": M["agent"], "mandate": mandate}}
    step = simulate(data, [event])["steps"][0]
    return {"hypothetical": True, "change": {"clause": clause, "param": param, "from": before, "to": value},
            "agent": M["agent"], "principal": M["principal"], "mandate": mandate, "at": at,
            "accepted": step["accepted"], "reason": step.get("reason") or None,
            "failed_checks": [c for c in step.get("checks", []) if not c.get("passed", True)]}


def simulate_rate_conformity(bundle: dict | str, chain: int, rates: list[dict], at: str | None = None,
                             tier: str | None = None) -> dict:
    """Do the rates given for items equal the member's contract prices at `at`? Optionally as if it moved to `tier`."""
    try:
        return whatif.simulate_rate_conformity(_data(bundle), chain, rates, at, tier)
    except whatif.WhatIfError as e:
        raise InputError(str(e)) from None


def simulate_termination(bundle: dict | str, chain: int, by: str, at: str | None = None, clause: str | None = None) -> dict:
    """If a party gave notice of termination at `at`: is it allowed, when does it take effect, and what is still owed."""
    try:
        return whatif.simulate_termination(_data(bundle), chain, by, at, clause)
    except whatif.WhatIfError as e:
        raise InputError(str(e)) from None


def simulate_eligibility(bundle: dict | str, member: str, at: str | None = None, parent: int | None = None) -> dict:
    """Is a member a real, active participant at `at`, so the aggregator agreement's terms and contract prices apply to it?"""
    try:
        return whatif.simulate_eligibility(_data(bundle), member, at, parent)
    except whatif.WhatIfError as e:
        raise InputError(str(e)) from None


def render_text(bundle: dict | str, chain: int | None = None, hashes_only: bool = False) -> str:
    """The human-readable agreement text, fixed by the agreement's hash."""
    b = Bundle(_data(bundle))
    if hashes_only:
        b.disclosures = {}
    ev = Evaluator(b)
    if chain is not None and not 0 <= chain < len(b.chain_list):
        raise InputError(f"no chain {chain} in the bundle (it has {len(b.chain_list)})")
    out = []
    for pos in [chain] if chain is not None else range(len(b.chain_list)):
        first = b.chain_list[pos][0]
        ag = ev.agreement(ev.state_at(content_hash(first))) or first["body"]["agreement"]
        out.append(render_agreement(b, ag))
    return "\n\n".join(out)


def hash_object(obj: Any) -> str:
    """The content hash (JCS + SHA-256, signatures stripped) of any JSON value."""
    return content_hash(obj)


def list_terms() -> list[dict]:
    """The standard Term library: id, title and parameter names."""
    return [{"id": t["id"], "title": t["title"], "params": sorted(t.get("params", {}))}
            for t in load_terms().values()]


def explain_term(term_id: str) -> dict:
    """One Term's parameters, claims, rendering template, provenance and content hash."""
    terms = load_terms()
    key = term_id if term_id in terms else f"UP:{term_id.removeprefix('UP-')}"
    if key not in terms:
        raise InputError(f"unknown Term {term_id!r}; known Terms: {', '.join(sorted(terms))}")
    t = terms[key]
    return {"id": t["id"], "title": t["title"], "hash": content_hash(t), "params": t.get("params", {}),
            "claims": t.get("claims", {}), "render": t.get("render"), "provenance": t.get("provenance"),
            "url": f"https://universalpaper.org/spec/terms/{t['id'].replace(':', '-')}/"}


def get_example(name: str) -> dict:
    """A worked example bundle (hypothetical parties and values, CC0)."""
    if name not in EXAMPLES:
        raise InputError(f"unknown example {name!r}; choose one of {', '.join(EXAMPLES)}")
    local = EXAMPLES_DIR / name / "bundle.json"
    if local.is_file():
        return loads(local.read_text(encoding="utf-8"))
    with urllib.request.urlopen(EXAMPLES_URL.format(name=name), timeout=20) as r:  # noqa: S310 (fixed https URL)
        return loads(r.read().decode("utf-8"))


# ---------------------------------------------------------------------------
# MCP wiring
# ---------------------------------------------------------------------------

def build_server(hosted: bool = False, on_call: Callable[[str, bool, float], None] | None = None):
    """The MCP server. `hosted` refuses file paths; `on_call(tool, ok, seconds)` sees only the tool name and outcome."""
    global ALLOW_PATHS
    ALLOW_PATHS = not hosted
    # Loaded by name so the module works, and type-checks, with either major version of the MCP SDK.
    import importlib

    Server: Any = None
    ToolError: Any = None
    for pkg, cls in (("mcp.server.mcpserver", "MCPServer"), ("mcp.server.fastmcp", "FastMCP")):  # SDK 2.x, then 1.x
        try:
            Server = getattr(importlib.import_module(pkg), cls)
            ToolError = importlib.import_module(f"{pkg}.exceptions").ToolError
            break
        except (ImportError, AttributeError):
            continue
    if Server is None:
        raise SystemExit("up-mcp needs the MCP SDK:  pip install 'universal-paper[mcp]'")

    try:
        server = Server("universal-paper", title="Universal Paper", instructions=INSTRUCTIONS,
                        website_url="https://universalpaper.org", version=__version__)
    except TypeError:  # 1.x
        server = Server("universal-paper", instructions=INSTRUCTIONS)
    where = "a bundle object or JSON text" if hosted else "a bundle object, JSON text, or a local file path"
    read_only: Any = {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}

    def tool(impl, description: str):
        @functools.wraps(impl)
        def fn(*args, **kwargs):
            t0, ok = time.monotonic(), False
            try:
                out = impl(*args, **kwargs)
                ok = True
                return out
            except InputError as e:
                raise ToolError(str(e)) from None
            except Exception as e:  # malformed input is reported, never a crash
                raise ToolError(f"the input could not be processed ({type(e).__name__}: {e})") from None
            finally:
                if on_call:
                    on_call(impl.__name__, ok, time.monotonic() - t0)

        try:
            server.tool(name=fn.__name__, description=description, annotations=read_only)(fn)
        except TypeError:  # older SDKs without annotations
            server.tool(name=fn.__name__, description=description)(fn)

    tool(validate_bundle,
         "Check every agreement and event in a Universal Paper bundle against the axioms (signatures, hashes, "
         f"Mandates, Term typing). `bundle` is {where}, or \"example:<name>\". "
         "Returns per-event accept/reject with the rule that rejected it.")
    tool(derive_state,
         "Derive each agreement's status, tiers, contract prices and open obligations at time `at` "
         "(RFC 3339 UTC, default: the latest event).")
    tool(check_event,
         "Dry-run one signed Event against its chain's current state, without writing anything. "
         "Returns whether it would be accepted and every check performed.")
    tool(simulate_events,
         "Run hypothetical events forward. Each event is {chain, kind, by, at, body, cosigners?, agent?: {key, mandate}}. "
         "Signatures are not required, but Mandate limits still apply, so an agent can test whether an action is "
         "within its authority before anyone signs.")
    tool(simulate_amendment,
         "Try one change to an agreement in force, as an amendment proposed by an agent under its Mandate: set parameter "
         "`param` of clause `clause` to `value` (e.g. clause 'price', param 'factor', value '1.05'). The Mandate defaults to "
         "the only one whose principal is a party. Nothing is signed or written; the result says whether every evaluator "
         "would accept it, and if not, which bound it breaks. Try it on bundle 'example:mandate-cap'.")
    tool(simulate_rate_conformity,
         "Check whether rates conform to a member's pricing agreement: for the member's participation (`chain`, its position "
         "in the bundle) at time `at`, compare each rate in `rates` ([{item, price}], item a GTIN string or {scheme, id}, price "
         "e.g. '9.40' or {value, currency}) with the contract price in the member's tier. The tier in effect is the one the "
         "member attested and the supplier acknowledged (UP:Tier-Selection); it is never derived from volume. `tier` (e.g. 'A') "
         "checks as if the member moved to that tier. Returns conforms true/false with the reason, and per item the contract "
         "price, the difference and the price in every tier. Try bundle 'example:what-if', chain 1.")
    tool(simulate_termination,
         "What happens if party `by` (a role such as 'supplier', or a name, key or identifier) gives notice of termination on "
         "chain `chain` at time `at`: allowed true/false with the reason, which clause (UP:Termination-Convenience or "
         "UP:Termination-Cause, including cure periods), the effective date, duties and fees (such as admin fees) still owed for periods up to then, "
         "and participations that stop with it. `clause` picks one termination clause. Try bundle 'example:what-if', chain 0.")
    tool(simulate_eligibility,
         "Is `member` (a name, key, or identifier such as an HIN or GLN) eligible at time `at`: a real, active participant "
         "under an aggregator agreement (UP:Participation: executed by every party, within its term, parent agreement in "
         "force), so the agreement's terms and contract prices apply to it? Returns eligible true/false with the reason for each participation. "
         "`parent` limits it to one aggregator agreement (chain position). Try bundle 'example:what-if'.")
    tool(render_text,
         "Render agreements as the human-readable text fixed by their hash. `chain` picks one chain by position; "
         "`hashes_only` ignores disclosures, showing what an outsider sees of sealed values.")
    tool(hash_object, "Content hash (RFC 8785 JCS + SHA-256, signatures stripped) of any JSON value.")
    tool(list_terms, "List the standard Universal Paper Term library.")
    tool(explain_term, "Explain one Term, e.g. 'UP:Admin-Fee': parameters, claims, rendering template, provenance and hash.")
    tool(get_example, f"Load a worked example bundle: one of {', '.join(EXAMPLES)}. All parties and values are hypothetical.")
    return server


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(prog="up-mcp", description=f"Read-only Universal Paper MCP server ({SPEC}, v{__version__})")
    p.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    p.add_argument("--hosted", action="store_true",
                   help="run the public, stateless HTTP endpoint (no file paths, no access logs, request counts only)")
    p.add_argument("--host", default=None, help="with --hosted: interface to bind (default 0.0.0.0)")
    p.add_argument("--port", type=int, default=None, help="with --hosted: port (default $PORT or 8080)")
    a = p.parse_args()
    if a.hosted:
        from .mcp_http import serve
        serve(host=a.host, port=a.port)
        return
    build_server().run(transport=a.transport)


if __name__ == "__main__":
    main()
