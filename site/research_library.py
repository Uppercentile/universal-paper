"""The Research library: the kinds, the topics, the statuses and every entry, as data (ported from library.rb).

Research is not part of the Universal Paper language. Nothing here is a Term, an Event kind or a rule.

Entries are data. Add one by adding a dict to ENTRIES; the index, the JSON records, the feed, the schemas and the
structured data all follow from it (site/research.py). A note or an experiment also needs a content file in
site/theme/research/content/<slug>.html; a reusable or a question is generated from its fields.
In text fields, `backticks` mark code. They are kept in JSON and Markdown and become <code> in HTML.
"""
from __future__ import annotations

import datetime
import html

# Four kinds of entry. Fixed, like the topics: (id, name, plural, definition)
KINDS = [
    ("note", "Note", "Notes", "An idea argued in full, with a worked example."),
    ("experiment", "Experiment", "Experiments", "Something that was run: a claim, a method, a result, and what it did not show."),
    ("reusable", "Reusable", "Reusables", "Files published to build on: manifests, traces, test vectors and schemas."),
    ("question", "Question", "Questions", "An open problem, stated so that someone can settle it."),
]
# Topics are a fixed list. An entry has one primary topic (the first) and at most two more: (id, name, definition)
TOPICS = [
    ("queries", "Queries and discovery", "Asking an agreement a question, and finding agreements to ask."),
    ("fingerprints", "Fingerprints and state", "Content hashes, state fingerprints, and what two parties can prove they share."),
    ("mandates", "Mandates and agents", "What an agent may do for a party, and how others check it."),
    ("fees", "Fees and reporting", "Administrative fees, sales reports, and the duties they create."),
    ("pricing", "Pricing and tiers", "Contract prices, tier selection, and price conformity."),
    ("membership", "Membership and eligibility", "Participations, rosters, and who an agreement covers."),
    ("sealing", "Sealed values", "Keeping values private while every party checks the same paper."),
    ("lifecycle", "Amendments and lifecycle", "Proposals, amendments, renewal and termination."),
    ("engines", "Engines and conformance", "Independent engines, traces, and showing that two of them agree."),
]
WORK = ["note", "experiment", "reusable"]
# id: (label, meaning, CSS modifier, the kinds that may carry it)
STATUS = {
    "open": ("Open", "A question with no answer yet.", " open", ["question"]),
    "answered": ("Answered", "A question that another entry settles. It links to the answer.", " done", ["question"]),
    "exploring": ("Exploring", "Early work with an example you can check.", "", WORK),
    "prototype": ("Prototype", "Running code you can try.", " proto", WORK),
    "withdrawn": ("Withdrawn", "No longer pursued. The entry says why.", " gone", WORK + ["question"]),
}
IMPACT = {"none": "No change to the language", "proposes": "Would change the language"}
OUTCOME = {"held": "Held", "held_in_part": "Held in part", "did_not_hold": "Did not hold", "inconclusive": "Inconclusive"}
DAY = "2026-11-27"

ENTRIES: list[dict] = [
    dict(n=1, kind="note", slug="query-surfaces", title="Agreements as query surfaces",
         nav="Query surfaces",
         lede="The signed agreement is the interface. A party names the questions it will answer, and anyone holding the bytes can compute the answer and show it is the same one.",
         desc="Research note: a signed agreement names the questions it will answer. Anyone with the bytes runs an engine and gets a trace a second engine can recompute.",
         summary="A signed agreement names the questions it will answer. Anyone with the bytes runs an engine and gets a trace that a second engine can recompute.",
         topics=["queries", "fingerprints", "mandates"], status="exploring", impact="none", date=DAY,
         built_on=["simulate_eligibility", "derive_state", "simulate_amendment", "UP:Admin-Fee", "A9"], featured=True),

    dict(n=2, kind="experiment", slug="three-traces-recomputed", parent=1, related=[3, 6], title="Three traces, recomputed",
         desc="Research experiment: three answers from one agreement, each fingerprinted by separate implementations. The fingerprints matched. One part is untested.",
         summary="Three answers from one agreement, each fingerprinted by separate implementations of the fingerprint rule. The fingerprints matched. The verdicts came from one engine.",
         lede="Three questions were put to one example agreement. Every fingerprint that was computed more than once came out the same. One part of the claim is still untested.",
         topics=["engines", "fingerprints", "queries"], status="exploring", impact="none", date=DAY,
         built_on=["simulate_eligibility", "derive_state", "simulate_amendment", "hash_object", "validate_bundle"],
         claim="Given the same bytes, separate implementations compute the same fingerprints for a manifest, a state and a trace.",
         method=["Took the public generative example bundle and named three questions about one agreement in it, Master X.",
                 "Ran each question on the hosted reference engine at `2027-03-01T00:00:00Z` and recorded the verdict and the state fingerprints it returned.",
                 "Built a trace for each answer and fingerprinted it with a script written for this experiment.",
                 "Fingerprinted the manifest three ways: with the engine's `hash_object`, with the script, and with code that runs in the page.",
                 "Compared the state fingerprint of Master X with the one in the trace file committed to the repository."],
         outcome="held_in_part",
         result="Every fingerprint that was computed more than once came out the same. The verdicts were computed once, by one engine, so this does not yet show a second engine reaching the same answers.",
         checks=[("Manifest fingerprint", "Hosted engine (`hash_object`), a separate script, code in the page", "equal"),
                 ("Three trace fingerprints", "A separate script, code in the page", "equal"),
                 ("State fingerprint of Master X", "Hosted engine, trace file in the repository", "equal"),
                 ("Three verdicts", "Hosted reference engine only", "not_compared")],
         limits=["One engine derived the verdicts. The repository's JavaScript engine was not run for this experiment.",
                 "The hosted engine and the trace file in the repository both come from the Python reference interpreter. Their agreement shows a stable result, not an independent one.",
                 "One bundle, one moment in time, three questions.",
                 "The command line shown for the reference interpreter is taken from its source. It was not run for this experiment."]),

    dict(n=3, kind="reusable", slug="query-test-vectors", parent=1, related=[2], title="A query manifest and three traces",
         nav="Query test vectors", desc="Reusable research files: an example query manifest and three traces, each with its fingerprint, for testing an engine or a fingerprint routine.",
         summary="The example manifest and its three traces as separate files, each with its fingerprint, for testing an engine or a fingerprint routine.",
         lede="Four small files and two schemas. Use them to check that your code computes the same fingerprints, and that your engine reaches the same verdicts.",
         topics=["queries", "fingerprints", "engines"], status="exploring", impact="none", date=DAY,
         built_on=["simulate_eligibility", "derive_state", "simulate_amendment", "hash_object"],
         license="CC0-1.0", simulated=True,
         use=[("Check your fingerprint code", "Canonicalize each file (RFC 8785), hash it with SHA-256, and compare with the fingerprint listed beside it."),
              ("Check your engine", "Load the source bundle, run the call a trace names with the inputs it lists, and compare your verdict and state fingerprints with the trace."),
              ("Check a format", "Validate the manifest and the traces against the two schemas.")]),

    dict(n=4, kind="question", slug="who-may-name-questions", parent=1, title="Who may name the questions an agreement answers?",
         short="Who may name an agreement's questions?",
         summary="A manifest lists the questions an agreement will answer. It is not settled whether one party may publish one for an agreement that several parties share.",
         topics=["queries"], status="open", impact="none", date=DAY, built_on=[],
         why="A manifest cannot change what an agreement means, so a wrong one does no harm to the agreement. It can still mislead. A reader may take a list of questions as something every party stands behind, when only one of them wrote it.",
         known=["The example manifest is unsigned. Its `named_by` field names the aggregator, and nothing proves the aggregator wrote it.",
                "A signed manifest would use the same Ed25519 signature the language uses everywhere else, so signing one needs no new mechanism.",
                "Every call a manifest can name is one that any holder of the bytes can already run. A manifest grants no access."],
         options=[("Any one party", "Each party publishes its own manifest and signs it. A reader sees whose it is."),
                  ("All parties together", "A manifest counts only when every party to the agreement has signed it."),
                  ("Anyone", "A manifest is only a list. Readers decide which lists they trust.")],
         settle="A rule a reader can apply to decide which manifests to honor, tried on an agreement with three or more parties who want different questions answered."),

    dict(n=5, kind="question", slug="how-much-may-a-question-select", parent=1, title="How much may a named question select?",
         summary="The `reads` field picks one part of an engine result. If it grows filters and conditions, the manifest turns into a query language.",
         topics=["queries", "engines"], status="open", impact="none", date=DAY, built_on=["derive_state"],
         why="Note 001 promises to add nothing to the language. A manifest that can filter, join and compare would be a second language beside the first, with its own bugs and its own disagreements between engines.",
         known=["One of the three example questions uses `reads`. It selects the obligations of one clause, `fee`, from the state that `derive_state` returns.",
                "The other two questions need no selection, because `simulate_eligibility` and `simulate_amendment` return only the answer.",
                "Two engines have to apply a selection the same way. If they do not, their trace fingerprints differ even when they agree on the state."],
         options=[("A fixed short list", "A manifest may select by chain and by clause, and nothing else."),
                  ("No selection", "Drop `reads`. A question that needs part of a state waits for an engine call that returns only that part.")],
         settle="Ten more realistic questions written against the public example bundles, counted by how many need a selection that `reads` cannot express today."),

    dict(n=6, kind="question", slug="wording-in-the-fingerprint", parent=1, related=[2], title="Should an engine's wording be inside a trace fingerprint?",
         short="Engine wording inside a trace fingerprint?",
         summary="The example verdicts leave out the engine's explanatory sentences so two engines can match. That may hide a real disagreement, and one phrase gets through anyway.",
         topics=["engines", "fingerprints"], status="open", impact="none", date=DAY, built_on=["derive_state", "simulate_amendment"],
         why="A trace fingerprint proves agreement only about what is inside the trace. Leave the reasons out, and two engines can report the same verdict for different reasons with nobody noticing. Put them in, and two correct engines fail to match because they phrase a sentence differently.",
         known=["The example traces keep structured values: eligible or not, amounts, dates, statuses, and the rule that failed.",
                "The engine's explanatory sentences are left out.",
                "One phrase is inside a fingerprint anyway. For February 2027 the fee trace carries the amount as the text `no base reported yet`, which is what the reference engine returns in place of a number. A second engine has to return the same words to match.",
                "The amendment trace names the failed rule as `A9` with the label `Bounded delegation`."],
         options=[("Values only", "Only values the specification determines go in a verdict. A missing value gets a fixed code, not a phrase."),
                  ("Reasons as codes", "A verdict carries the identifier of every rule that decided it, and no sentences.")],
         settle="The three example questions run on the repository's second engine, with the verdicts compared field by field. A field that differs only in wording marks where a code is needed."),

    dict(n=7, kind="question", slug="trace-freshness", parent=1, title="How does a reader know a trace is out of date?",
         summary="A trace is true for the state it names. When a new event lands, the old trace stays correct about the old state, and nothing tells its holder.",
         topics=["fingerprints", "lifecycle"], status="open", impact="none", date=DAY, built_on=["derive_state", "validate_bundle"],
         why="An agent that acts on a stale answer acts on an agreement that has moved. The trace is not wrong, so no check on the trace alone can catch it.",
         known=["Each trace names the state fingerprint of every agreement it read. Comparing it with the current one is a single string comparison.",
                "`derive_state` returns the current state fingerprint as `state_hash`.",
                "Rejected events are skipped and leave the state fingerprint unchanged. The example bundle contains two.",
                "A verdict also depends on the time asked about, `at`, which is part of the inputs."],
         settle="A convention for how the holder of a trace learns that the state has moved, tried on a chain that gains an event after the trace was made."),

    dict(n=8, kind="question", slug="what-a-manifest-reveals", parent=1, title="What does a manifest reveal by naming a question?",
         short="What does a manifest reveal?",
         summary="Naming a question shows that a clause exists and that someone expects to be asked about it. For an agreement with sealed values, that may be more than a party wants to show.",
         topics=["sealing", "queries"], status="open", impact="none", date=DAY, built_on=[],
         why="Sealing lets parties keep values private while every party checks the same paper. A manifest sits outside the agreement and is not sealed. Whatever it names is visible to anyone who reads it.",
         known=["The example manifest shows the clause name `fee`, the parameter name `rate`, and the fingerprint of the aggregator's Mandate.",
                "It shows no values. The rate, the Mandate's limit and the fee amounts appear only in traces, which a party computes for itself.",
                "The example agreement has no sealed values, so this has not been tried where it matters."],
         settle="A manifest written for the repository's confidential example bundle, reviewed for what a reader with no disclosed values learns from it."),

    dict(n=9, kind="question", slug="positions-and-chain-ids", parent=1, title="Should every engine call take a ChainId instead of a position?",
         short="ChainIds or positions in engine calls?",
         summary="Manifests name agreements by ChainId. Several engine calls take a position in the caller's file, so the caller has to look the position up first.",
         topics=["engines", "queries"], status="open", impact="none", date=DAY, built_on=["simulate_eligibility", "simulate_amendment"],
         why="Two parties rarely hold the same file. Each may hold the agreements in a different order, or hold only some of them. A position means something in one file. A ChainId means the same thing in all of them.",
         known=["Manifests and traces use ChainIds only.",
                "On the reference engine, `simulate_amendment`, `simulate_price_conformity` and `simulate_termination` take a `chain` position, and `simulate_eligibility` takes a `parent` position.",
                "To run a named question, a caller finds the position of the chain whose ChainId the manifest names.",
                "The language already identifies every chain by its ChainId. This concerns the engine's interface only."],
         settle="The engine calls accepting a ChainId wherever they accept a position. That would change the engine's interface, not the language."),
]

# Sample entries for checking the layout at scale (build_site.py --research-sample N). Never published: that build is
# marked "Preview only" and noindex.
SUBJECTS = {
    "queries": ["Named questions for price checks", "Finding agreements by fingerprint", "Standing offers an agent can read", "Question sets for auditors", "Asking across a roster", "Well-known manifests", "Answer caching by state"],
    "fingerprints": ["State fingerprints across forks", "Comparing two histories", "Fingerprints for partial bundles", "Pinning a version in a credential", "Hash chains for reports", "Structural diffs of agreements", "Fingerprint collisions in practice"],
    "mandates": ["Mandate bounds on price changes", "Delegating a renewal decision", "Revoking an agent", "Nested Mandates", "Mandates with time windows", "Agents that negotiate tiers", "Auditing an agent after the fact"],
    "fees": ["Fee derivation with late reports", "Rounding rules in fee amounts", "Disputed sales reports", "Fee disclosure to members", "Reconciling paid and owed", "Reporting periods that overlap", "Fees on returned goods"],
    "pricing": ["Tier selection under sealed prices", "Price conformity at invoice time", "Reference prices that move", "Tier changes mid-term", "Volume commitments and tiers", "Price files as attestations", "Conformity checks for agents"],
    "membership": ["Eligibility through a parent agreement", "Rosters as participations", "Members with two cooperatives", "Class of trade checks", "Onboarding a member by agent", "Leaving one agreement of many", "Eligibility at a past date"],
    "sealing": ["Sealed rates and open audits", "Disclosing one value to one party", "Range checks without the value", "Sealed values in a trace", "What a hashes-only holder can prove", "Re-sealing after an amendment", "Leaks through structure"],
    "lifecycle": ["Amendment proposals in sequence", "Termination with duties outstanding", "Renewal by silence", "Superseding a chain", "Notice periods computed", "Backdated events and how they fail", "Winding down a participation"],
    "engines": ["A third engine in Rust", "Differential tests at scale", "Trace size and replay time", "Conformance for partial engines", "Engines that explain themselves", "Deterministic wording", "Running an engine in the browser"],
}
ANGLES = ["a worked example", "with two engines", "for agents", "under sealed values", "at renewal", "without a registry", "in three steps", "and what breaks", "measured", "revisited"]
TERMS = {"queries": ["simulate_eligibility", "derive_state"], "fingerprints": ["hash_object", "A3"], "mandates": ["simulate_amendment", "A9"],
         "fees": ["UP:Admin-Fee", "UP:Sales-Reporting"], "pricing": ["UP:Tiers", "simulate_price_conformity"], "membership": ["UP:Participation", "simulate_eligibility"],
         "sealing": ["A10", "UP:Fee-Disclosure"], "lifecycle": ["simulate_termination", "UP:Renewing-Term"], "engines": ["validate_bundle", "simulate_events"]}


def sample(count):
    seed = 20_261_127

    def rnd(k):
        nonlocal seed
        seed = (seed * 1_103_515_245 + 12_345) % 2_147_483_648
        return (seed >> 8) % k
    start = datetime.date(2026, 12, 1)
    keys = [t[0] for t in TOPICS]
    first = len(ENTRIES) + 1
    notes = [1]
    out = []
    for n in range(first, count + 1):
        t = keys[rnd(len(keys))]
        second = keys[rnd(len(keys))]
        roll = rnd(100)
        k = rnd(100)
        kind = "note" if k < 16 else ("experiment" if k < 40 else ("reusable" if k < 58 else "question"))
        if kind == "question":
            status = "open" if roll < 70 else ("answered" if roll < 94 else "withdrawn")
        else:
            status = "exploring" if roll < 78 else ("prototype" if roll < 93 else "withdrawn")
        parent = None if kind == "note" else notes[rnd(len(notes))]
        if kind == "note":
            notes.append(n)
        title = f"{SUBJECTS[t][rnd(7)]}: {ANGLES[rnd(10)]}"
        impact = "none" if rnd(100) < 72 else "proposes"
        date = (start + datetime.timedelta(days=(n - first) * 3 + rnd(3))).isoformat()
        minutes = 4 + rnd(11)
        built = [TERMS[t][rnd(2)]]
        e = dict(n=n, kind=kind, slug=f"sample-{n}", href="#library", sample=True, title=title,
                 summary="Sample entry for checking the layout. It is not real.",
                 topics=list(dict.fromkeys([t, second])), status=status, impact=impact, date=date, minutes=minutes, built_on=built)
        if parent:
            e["parent"] = parent
        out.append(e)
    return out


# ----------------------------------------------------------------------------- small helpers
def esc(s):
    """HTML escaping, the same characters as Ruby's CGI.escapeHTML."""
    return html.escape(str(s), quote=True).replace("&#x27;", "&#39;")


def rich(s):
    import re
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", esc(s))


def bare(s):
    return str(s).replace("`", "")


def ico(n):
    return f'<svg class="ico" aria-hidden="true"><use href="#i-{n}"/></svg>'


def no(n):
    return f"{n:03d}"


def kind_name(k, plural=False):
    return next(x for x in KINDS if x[0] == k)[2 if plural else 1]


def topic_name(k):
    return next(t for t in TOPICS if t[0] == k)[1]


def _date(d):
    return datetime.date.fromisoformat(d)


def day(d):
    x = _date(d)
    return f"{x:%b} {x.day}, {x.year}"


def long_day(d):
    x = _date(d)
    return f"{x:%B} {x.day}, {x.year}"


def status_pill(s):
    return f'<span class="rs-status{STATUS[s][2]}">{STATUS[s][0]}</span>'


def href(e):
    return e.get("href") or f"/research/{e['slug']}/"


def label(e):
    return f"{kind_name(e['kind'])} {no(e['n'])}"


def parts_of(entries, n):
    return [x for x in entries if x.get("parent") == n]


def count_words(lst, kind):
    c = sum(1 for x in lst if x["kind"] == kind)
    return None if c == 0 else f"{c} {kind_name(kind, c != 1).lower()}"


class EntryError(SystemExit):
    pass


def check(entries):
    """Every entry is checked before anything is built, so a typo in a kind, topic or status stops the build."""
    seen = set()
    numbers = {x["n"] for x in entries}
    for e in entries:
        who = f"entry {e.get('n')}"
        if not any(k[0] == e.get("kind") for k in KINDS):
            raise EntryError(f"{who}: unknown kind {e.get('kind')}")
        if e.get("status") not in STATUS or e["kind"] not in STATUS[e["status"]][3]:
            raise EntryError(f"{who}: status {e.get('status')} is not allowed for a {e['kind']}")
        topics = e.get("topics") or []
        if not (1 <= len(topics) <= 3) or len(set(topics)) != len(topics):
            raise EntryError(f"{who}: needs one to three topics")
        for t in topics:
            if not any(x[0] == t for x in TOPICS):
                raise EntryError(f"{who}: unknown topic {t}")
        if e.get("impact") not in IMPACT:
            raise EntryError(f"{who}: unknown language impact")
        if ("n", e["n"]) in seen or ("s", e["slug"]) in seen:
            raise EntryError(f"{who}: number or address used twice")
        seen |= {("n", e["n"]), ("s", e["slug"])}
        for r in [e.get("parent"), *(e.get("related") or []), e.get("answered_by")]:
            if r is not None and r not in numbers:
                raise EntryError(f"{who}: points at entry {r}, which does not exist")
        if e["kind"] == "note" and e.get("parent"):
            raise EntryError(f"{who}: a note has no parent")
        if e["status"] == "answered" and not e.get("answered_by") and not e.get("sample"):  # the schema requires it too
            raise EntryError(f"{who}: an answered question names the entry that settles it in answered_by")
        if e["kind"] == "experiment" and not e.get("sample") and e.get("outcome") not in OUTCOME:
            raise EntryError(f"{who}: unknown experiment outcome {e.get('outcome')}")


def newest(entries):
    """Newest first. Entries published on the same day keep their number order, so a note comes before its parts."""
    return sorted(entries, key=lambda x: (-_date(x["date"]).toordinal(), x["n"]))


# ----------------------------------------------------------------------------- index markup
def featured(note, parts):
    inside = [w for w in (count_words(parts, k) for k in ("experiment", "reusable", "question")) if w]
    extra = f'<p class="rs-inside"><span>With it</span>{"".join(f"<b>{t}</b>" for t in inside)}</p>' if inside else ""
    tags = "".join(f"<li>{topic_name(t)}</li>" for t in note["topics"])
    return f"""<a class="rs-feat rv" href="{href(note)}">
  <div class="artcard"><canvas data-field="{note['slug']}" data-tone="lilac" aria-hidden="true"></canvas><span class="glyph">{label(note)}</span></div>
  <div class="rs-feat-body">
    <p class="rs-meta">{status_pill(note['status'])}<span>{long_day(note['date'])}</span><span>{note['minutes']} min read</span></p>
    <h2 class="h2">{esc(note['title'])}</h2>
    <p class="rs-dek">{rich(note['summary'])}</p>
    <ul class="rs-tags">{tags}<li>{IMPACT[note['impact']]}</li></ul>
    {extra}
    <span class="more">Read the note {ico('arrow')}</span>
  </div>
</a>
"""


def latest(entries):
    cards = "".join(
        f'<a class="rs-mini" href="{href(x)}"><span class="rs-meta"><span>{label(x)}</span><span>{day(x["date"])}</span></span>'
        f'<b>{esc(x["title"])}</b><span class="rs-mini-t">{topic_name(x["topics"][0])}</span></a>' for x in newest(entries)[:3])
    return f'<div class="rs-latest"><p class="eyebrow">Latest</p><div class="rs-minis">{cards}</div></div>'


def row(x):
    text = " ".join([x["title"], bare(x["summary"]), *[topic_name(t) for t in x["topics"]], *x["built_on"], STATUS[x["status"]][0],
                     kind_name(x["kind"]), f"{kind_name(x['kind'])} {no(x['n'])}", no(x["n"])]).lower()
    built = "".join(f"<code>{esc(b)}</code>" for b in x["built_on"][:3])
    more = "".join(f'<span class="rs-t2">{topic_name(t)}</span>' for t in x["topics"][1:])
    frm = f'<span class="rs-from">From {no(x["parent"])}</span>' if x.get("parent") else ""
    imp = '<span class="rs-imp">Would change the language</span>' if x["impact"] == "proposes" else ""
    return (f'<li class="rs-row" data-n="{x["n"]}" data-kind="{x["kind"]}" data-topics="{" ".join(x["topics"])}" data-status="{x["status"]}" '
            f'data-impact="{x["impact"]}" data-year="{x["date"][:4]}" data-date="{x["date"]}" data-title="{esc(x["title"].lower())}" data-text="{esc(text)}">'
            f'<a href="{href(x)}"><span class="rs-no"><i class="rs-k k-{x["kind"]}">{kind_name(x["kind"])}</i>{no(x["n"])}</span>'
            f'<span class="rs-main"><b>{esc(x["title"])}</b><span class="rs-sum">{rich(x["summary"])}</span>'
            f'<span class="rs-rowmeta"><span class="rs-t1">{topic_name(x["topics"][0])}</span>{more}{built}{frm}{imp}</span></span>'
            f'<span class="rs-side">{status_pill(x["status"])}<time datetime="{x["date"]}">{day(x["date"])}</time></span></a></li>')


def facet(name, lab, values):
    items = "".join(f'<li><button class="rs-f" type="button" data-facet="{name}" data-value="{v}" aria-pressed="false"><span>{t}</span><i>{c}</i></button></li>'
                    for v, t, c in values)
    return f'<div class="rs-facet"><b>{lab}</b><ul>{items}</ul></div>'


def sorted_rows(entries):
    return "\n".join(row(x) for x in newest(entries))


def library(entries):
    """The full library: kinds across the top, facets on the left, search, sort and rows on the right. Every row is in
    the HTML, so the list works without JavaScript; the script filters, sorts and counts."""
    def count(f):
        return sum(1 for x in entries if f(x))
    kinds = [(k, pl, c) for k, _, pl, _ in KINDS if (c := count(lambda x, k=k: x["kind"] == k))]
    topics = [(k, t, c) for k, t, _ in TOPICS if (c := count(lambda x, k=k: k in x["topics"]))]
    statuses = [(k, v[0], c) for k, v in STATUS.items() if (c := count(lambda x, k=k: x["status"] == k))]
    impacts = [(k, v, c) for k, v in IMPACT.items() if (c := count(lambda x, k=k: x["impact"] == k))]
    years = [(y, y, count(lambda x, y=y: x["date"][:4] == y)) for y in sorted({x["date"][:4] for x in entries}, reverse=True)]
    tabs = "".join(f'<button class="rs-f rs-kf" type="button" data-facet="kind" data-value="{v}" aria-pressed="{str(not v).lower()}"><span>{t}</span><i>{c}</i></button>'
                   for v, t, c in [("", "All", len(entries))] + kinds)
    return f"""<section class="band tight rs-lib" id="library" aria-labelledby="lib-h">
  <div class="wrap">
    <p class="eyebrow">Library</p>
    <h2 class="h2" id="lib-h">Every entry.</h2>
    <div class="rs-kinds" role="group" aria-label="Kind of entry">{tabs}</div>
    <div class="rs-lib-grid">
      <aside class="rs-facets" aria-label="Filter entries">
        <details class="rs-fd" open><summary>Filters {ico('down')}</summary>
          {facet('topic', 'Topic', topics)}
          {facet('status', 'Status', statuses)}
          {facet('impact', 'Language', impacts)}
          {facet('year', 'Year', years)}
        </details>
      </aside>
      <div class="rs-results">
        <div class="rs-bar">
          <label class="tsearch rs-search">{ico('search')}<span class="sr">Search research</span><input id="rs-q" type="search" placeholder="Search titles, topics, Terms and rules" autocomplete="off"><kbd>/</kbd></label>
          <label class="rs-sort"><span>Sort</span><select id="rs-sort"><option value="new">Newest</option><option value="old">Oldest</option><option value="az">Title, A to Z</option><option value="no">Number</option></select></label>
        </div>
        <div class="rs-active"><p class="tcount" id="rs-count" aria-live="polite">{len(entries)} entries</p><div id="rs-chips"></div><button class="rs-clear" id="rs-clear" type="button" hidden>Clear all</button></div>
        <ol class="rs-list" id="rs-list">
{sorted_rows(entries)}
        </ol>
        <p class="rs-empty" id="rs-empty" hidden>Nothing matches. Try a shorter search, or clear a filter.</p>
        <button class="btn ghost rs-more" id="rs-more" type="button" hidden>Show more</button>
      </div>
    </div>
  </div>
</section>
"""


def short_list(entries):
    return f"""<section class="band tight rs-lib" id="library" aria-labelledby="lib-h">
  <div class="wrap">
    <p class="eyebrow">Library</p>
    <h2 class="h2" id="lib-h">Every entry.</h2>
    <ol class="rs-list rs-list-solo">
{sorted_rows(entries)}
    </ol>
  </div>
</section>
"""


def kind_cards(entries, linked):
    out = []
    for k, one, many, d in KINDS:
        c = sum(1 for x in entries if x["kind"] == k)
        inner = f'<span class="fn k-{k}">{one}</span><b>{many}</b><p>{d}</p><span class="rs-tc">{c} {"entry" if c == 1 else "entries"}</span>'
        out.append(f'<a class="rs-topic rs-kind" id="kind-{k}" href="/research/?kind={k}#library" data-set="kind" data-value="{k}">{inner}</a>'
                   if linked and c > 0 else f'<div class="rs-topic rs-kind" id="kind-{k}">{inner}</div>')
    return "\n".join(out)


def topic_cards(entries, linked):
    out = []
    for k, t, d in TOPICS:
        c = sum(1 for x in entries if k in x["topics"])
        inner = f'<b>{t}</b><p>{d}</p><span class="rs-tc">{c} {"entry" if c == 1 else "entries"}</span>'
        out.append(f'<a class="rs-topic" id="topic-{k}" href="/research/?topic={k}#library" data-set="topic" data-value="{k}">{inner}</a>'
                   if linked and c > 0 else f'<div class="rs-topic" id="topic-{k}">{inner}</div>')
    return "\n".join(out)
