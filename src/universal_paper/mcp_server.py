"""A read-only MCP server for Universal Paper:  up-mcp  (or  python -m universal_paper.mcp_server).

It lets an agent check agreements the same way every other party does: validate a bundle,
derive statuses and obligations, dry-run one event, simulate hypothetical events under a
Mandate, ask what-if questions (an amendment, price conformity, a termination, a member's eligibility),
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
import inspect
import json
import os
import time
import typing
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

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


def simulate_price_conformity(bundle: dict | str, chain: int, prices: list[dict], at: str | None = None,
                             tier: str | None = None) -> dict:
    """Do the prices given for items equal the member's contract prices at `at`? Optionally as if it moved to `tier`."""
    try:
        return whatif.simulate_price_conformity(_data(bundle), chain, prices, at, tier)
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
# What an agent reads: one description per tool and one per parameter
# ---------------------------------------------------------------------------
# Each tool says what it answers, when to use it rather than a named sibling, and what it needs first.
# A test checks that every parameter of every tool has a description here.

_BUNDLE = (
    "The bundle to read: a JSON object {\"type\": \"Bundle\", \"spec\", \"terms\", \"mandates\", \"chains\"}; the same "
    "object as JSON text; or the string \"example:<name>\" for a worked example (" + ", ".join(EXAMPLES) + "). "
    "A local server also accepts a path to a .json file; the hosted server does not. Get one with get_example."
)
_AT = ("The time to evaluate at, as a UP Time: RFC 3339 UTC with seconds and a Z, e.g. \"2027-03-01T00:00:00Z\". "
       "Omit it to use the bundle's latest event.")
_CHAIN = ("A chain's position in the bundle's `chains` list, counting from 0 (each chain is one agreement's history). "
          "derive_state and validate_bundle list every chain with its position and label.")

TOOL_DOCS: dict[str, str] = {
    "validate_bundle": (
        "Check a whole bundle against the axioms: signatures, hashes, chain linkage, Mandate bounds and Term typing, for "
        "every agreement and every recorded event. Use it first on any bundle you receive, before trusting what other tools "
        "derive from it. Use check_event instead to test one new signed event, simulate_events for unsigned hypothetical "
        "events, and derive_state to read what the agreements say. Returns valid true/false, each event as accepted or "
        "rejected with the rule and reason, agreement-level issues and forked chains."),
    "derive_state": (
        "Read what every agreement in a bundle means at one time: each chain's status (e.g. proposed, active, expired, terminated), "
        "term window, the tier each member attested, contract prices per item, and obligations with due dates and status (e.g. "
        "overdue). Use it to answer \"what is in force on date X, and what is owed\". Rejected events are skipped, not "
        "reported, so run validate_bundle first on a bundle you did not build. Use render_text instead for the agreement's "
        "wording, simulate_events for the state after hypothetical events, and the simulate_* what-if tools for one "
        "specific question (price conformity, termination, eligibility, an amendment)."),
    "check_event": (
        "Dry-run one signed Event, exactly as it would be appended, against the current state of the chain it names, and "
        "return whether every evaluator would accept it, with each check (rule, passed, reason) and the resulting state "
        "hash. Nothing is written. Use it when you hold a real, signed event (from a party or your own signer) and want to "
        "know before publishing whether it is valid. Use simulate_events instead for unsigned or several events, "
        "simulate_amendment to try one parameter change, and validate_bundle for events already in the bundle. Needs the "
        "bundle holding that chain; the event's `prev` must be the chain's current state hash."),
    "simulate_events": (
        "Apply a list of hypothetical, unsigned events in order to a copy of the bundle and return each step (accepted, "
        "reason, checks) plus the derived state afterwards. Signatures are not required, but Mandate limits, unanimity and "
        "every other rule still apply, so an agent can test a multi-step plan (propose, accept, attest) within its "
        "authority before anyone signs. Use check_event instead for one already-signed event, simulate_amendment for a "
        "single parameter change under a Mandate, and the simulate_* what-if tools for price conformity, termination or "
        "eligibility. Nothing is signed or written."),
    "simulate_amendment": (
        "Try one change to an agreement in force: set parameter `param` of clause `clause` to `value`, proposed by an agent "
        "under its Mandate, and return whether every evaluator would accept it and, if not, which Mandate bound or rule it "
        "breaks. Use it instead of simulate_events when the question is one parameter change, because it builds the "
        "proposal for you. Clause and parameter names come from render_text or derive_state on the same bundle; the bundle "
        "must contain the Mandate. Hypothetical: nothing is signed or written. Try bundle \"example:mandate-cap\", clause "
        "\"price\", param \"factor\", value \"1.05\"."),
    "simulate_price_conformity": (
        "Check whether given prices conform to a member's contract prices: for one participation chain at time `at`, "
        "compare each price with the contract price in the tier in effect, and return conforms true/false with the "
        "reason, and per item the contract price, the difference and the price in every tier. The tier in effect is the "
        "one the member attested and the supplier acknowledged (UP:Tier-Selection); it is never derived from volume. Use "
        "it instead of derive_state when you have prices to check (an invoice, a quote) rather than just reading the "
        "contract prices. Needs a participation chain (find it with derive_state). Try bundle \"example:what-if\", chain 1."),
    "simulate_termination": (
        "Ask what happens if a party gives notice of termination on a chain at time `at`: allowed true/false with the "
        "reason, which clause permits it (UP:Termination-Convenience or UP:Termination-Cause, with any cure period), the "
        "effective date, duties and fees (such as admin fees) still owed for periods up to then, and participations that "
        "stop with it. Use it instead of simulate_events, which would only say whether a notice event is accepted, not "
        "its consequences. The chain must hold an executed agreement with a termination clause. Hypothetical: nothing is signed. Try bundle "
        "\"example:what-if\", chain 0."),
    "simulate_eligibility": (
        "Ask whether a member is eligible at time `at`: a real, active participant under an aggregator agreement "
        "(UP:Participation executed by every party, within its term, parent agreement in force), so that agreement's "
        "terms and contract prices apply to it. Returns eligible true/false with the reason for each participation found. "
        "Use it instead of derive_state when the question is about one member, and before simulate_price_conformity when "
        "you are not sure the member is covered. Try bundle \"example:what-if\"."),
    "render_text": (
        "Render agreements as the human-readable text fixed by their hash: parties and roles, every clause in words, and "
        "the agreement hash. Use it to read or quote what an agreement says, or to find clause and parameter names for "
        "simulate_amendment. It does not check anything: use validate_bundle to check validity, derive_state for status, "
        "tiers, prices and obligations at a time, and hash_object to compute a hash. With `hashes_only`, it shows what an "
        "outsider sees of sealed (confidential) values."),
    "hash_object": (
        "Compute the content hash of any JSON value: RFC 8785 canonical JSON (JCS), then SHA-256, with signatures "
        "(`sigs`) stripped, returned as \"sha256:<hex>\". Use it to get the hash that identifies an agreement, Term, "
        "Mandate or event, e.g. to fill an event's `prev`, `chain`, `target` or `supersedes`, or to check that two "
        "parties hold the same text. It does not validate: use validate_bundle or check_event for that."),
    "list_terms": (
        "List the standard Universal Paper Term library: each Term's id (e.g. \"UP:Admin-Fee\"), title and parameter "
        "names. Use it to discover which clauses an agreement can contain; then call explain_term for one Term's full "
        "definition. Needs no bundle. To see the Terms a given agreement actually uses, call render_text on its bundle."),
    "explain_term": (
        "Explain one standard Term: its parameters with types, the claims it allows, its rendering template, provenance, "
        "content hash and spec page URL. Use it after list_terms, or when a clause in render_text or a Mandate scope names "
        "a Term you need to understand before proposing values. Needs no bundle."),
    "get_example": (
        "Load a worked example bundle (hypothetical parties and values, CC0) to try the other tools on. Use it when you "
        "have no bundle yet (use list_terms instead to browse Terms without one). Instead of passing the returned object on, you can pass the string \"example:<name>\" as "
        "`bundle` to any tool. conventional: a signed GPO agreement; generative: agent actions, two rejected by their "
        "Mandate; confidential: sealed prices; overlay: an existing paper contract referenced by hash; mandate-cap: an "
        "agent's price factor bounded by its Mandate; what-if: participations for the simulate_* what-if tools."),
}

# What a person sees: a short name for each tool, shown by clients in place of the function name.
TOOL_TITLES: dict[str, str] = {
    "validate_bundle": "Validate a bundle",
    "derive_state": "Read agreement state",
    "check_event": "Check a signed event",
    "simulate_events": "Simulate events",
    "simulate_amendment": "Simulate an amendment",
    "simulate_price_conformity": "Check price conformity",
    "simulate_termination": "Simulate a termination",
    "simulate_eligibility": "Check member eligibility",
    "render_text": "Render agreement text",
    "hash_object": "Hash a JSON value",
    "list_terms": "List standard Terms",
    "explain_term": "Explain a Term",
    "get_example": "Get an example bundle",
}

PARAM_DOCS: dict[str, dict[str, str]] = {
    "validate_bundle": {"bundle": _BUNDLE},
    "derive_state": {"bundle": _BUNDLE, "at": _AT},
    "check_event": {
        "bundle": _BUNDLE + " It must contain the chain the event names.",
        "event": (
            "One complete, signed Event object: {\"type\": \"Event\", \"spec\": \"UP/0.1-draft\", \"kind\": \"propose\" | "
            "\"accept\" | \"attest\", \"chain\": ChainId (\"sha256:...\"; omit for a genesis proposal that starts a new "
            "chain), \"prev\": the chain's current state hash, \"at\": UP Time, \"by\": \"ed25519:<hex>\" public key, "
            "\"body\": {\"agreement\", \"supersedes\"?} | {\"target\"} | {\"claim\"}, \"sigs\": [{\"key\", \"sig\"}]}. "
            "Unlike simulate_events, `chain` here is the ChainId hash, not a position, and signatures are checked."),
    },
    "simulate_events": {
        "bundle": _BUNDLE,
        "events": (
            "Hypothetical events (a JSON array), applied in order, each {\"chain\": position (0-based) or ChainId, or null to start a "
            "new chain, \"kind\": \"propose\" | \"accept\" | \"attest\", \"by\": party public key \"ed25519:<hex>\", "
            "\"at\": UP Time, \"body\": {\"agreement\", \"supersedes\"?} | {\"target\"} | {\"claim\"}, \"cosigners\"?: "
            "[public keys of other parties signing the same event], \"agent\"?: {\"key\", \"mandate\": Mandate hash}}. No `sigs` or `prev`: they are filled in. "
            "An empty list just derives the state."),
        "at": "Time for the final derived state, as a UP Time (e.g. \"2027-03-01T00:00:00Z\"). Omit it to use the last event's time.",
    },
    "simulate_amendment": {
        "bundle": _BUNDLE + " It must contain the Mandate.",
        "clause": "The clause to change, by its name `n` in the agreement (e.g. \"price\", \"fee\"); render_text shows the names.",
        "param": "The parameter of that clause to change, e.g. \"factor\". The error lists the valid names if it does not exist.",
        "value": ("The new value, typed as the Term defines it: Decimals and Rates as strings (\"1.05\", \"0.03\"), "
                  "Times as UP Time strings, Durations as {\"count\", \"unit\"}. A number is converted to a string where the "
                  "old value is a string."),
        "chain": _CHAIN + " Default 0.",
        "mandate": "The Mandate's content hash (\"sha256:...\"). Omit it when exactly one Mandate in the bundle has a principal who is a party to the chain.",
        "at": "When the amendment is proposed, as a UP Time. Omit it to use one day after the bundle's latest event.",
    },
    "simulate_price_conformity": {
        "bundle": _BUNDLE,
        "chain": _CHAIN + " It must be a member's participation (UP:Participation), not the aggregator agreement itself.",
        "prices": (
            "The prices to check, one per item: [{\"item\": GTIN string or {\"scheme\", \"id\"}, \"price\": decimal "
            "string (\"9.40\") or {\"value\", \"currency\"}}]. An item the agreement does not price makes the result conforms false, with that reason."),
        "at": _AT,
        "tier": "A tier name defined by the agreement (e.g. \"A\", \"B\") to check as if the member had attested that tier instead. Omit it to use the tier in effect.",
    },
    "simulate_termination": {
        "bundle": _BUNDLE,
        "chain": _CHAIN + " The agreement to terminate: an aggregator agreement or a participation.",
        "by": ("The party giving notice: a role (\"aggregator\", \"supplier\", \"member\") when one party holds it, or "
               "the party's name, public key or identifier (e.g. HIN, GLN)."),
        "at": "When notice is given, as a UP Time (e.g. \"2027-03-01T00:00:00Z\"). Omit it to use the bundle's latest event.",
        "clause": "The termination clause to use, by its name `n` in the agreement. Omit it to get every termination clause this party may use.",
    },
    "simulate_eligibility": {
        "bundle": _BUNDLE,
        "member": "The member to check: its name, public key (\"ed25519:<hex>\") or identifier such as an HIN or GLN.",
        "at": _AT,
        "parent": _CHAIN + " Limits the check to participations under this aggregator agreement. Omit it to check all.",
    },
    "render_text": {
        "bundle": _BUNDLE,
        "chain": _CHAIN + " Omit it to render every chain's agreement in force (or its first proposal).",
        "hashes_only": ("true to ignore the bundle's disclosures and show sealed values as hashes only, as an outsider sees "
                        "them. Default false."),
    },
    "hash_object": {"obj": "Any JSON value (object, array, string, number, boolean or null). A `sigs` member is ignored."},
    "list_terms": {},
    "explain_term": {"term_id": "The Term id from list_terms, e.g. \"UP:Admin-Fee\" (the \"UP-Admin-Fee\" spelling also works)."},
    "get_example": {"name": "The example's name, one of: " + ", ".join(EXAMPLES) + "."},
}


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
    from pydantic import Field  # installed with the MCP SDK

    try:
        server = Server("universal-paper", title="Universal Paper", instructions=INSTRUCTIONS,
                        website_url="https://universalpaper.org", version=__version__)
    except TypeError:  # 1.x
        server = Server("universal-paper", instructions=INSTRUCTIONS)
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

        # Every parameter carries its description into the tool's input schema (Annotated + pydantic Field;
        # pydantic comes with the MCP SDK, so the plain functions above do not need it).
        hints = typing.get_type_hints(impl)
        sig = inspect.signature(impl)
        fn.__signature__ = sig.replace(parameters=[  # type: ignore[attr-defined]
            p.replace(annotation=Annotated[hints[p.name], Field(description=PARAM_DOCS[impl.__name__][p.name])])
            for p in sig.parameters.values()])
        fn.__annotations__ = {p.name: p.annotation for p in fn.__signature__.parameters.values()}  # type: ignore[attr-defined]
        if "return" in hints:
            fn.__annotations__["return"] = hints["return"]

        # The title goes on the tool and in its annotations, so a client finds it in either place.
        title = TOOL_TITLES[fn.__name__]
        ann = {**read_only, "title": title}
        attempts: list[dict[str, Any]] = [
            {"title": title, "annotations": ann},
            {"annotations": ann},  # SDKs without tool titles
            {},  # older SDKs without annotations
        ]
        for extra in attempts:
            try:
                server.tool(name=fn.__name__, description=description, **extra)(fn)
                break
            except TypeError:
                continue
        else:
            raise SystemExit(f"up-mcp could not register {fn.__name__} with this version of the MCP SDK")

    for name in TOOL_DOCS:
        tool(globals()[name], TOOL_DOCS[name])
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
