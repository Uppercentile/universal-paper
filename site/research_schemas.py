"""JSON Schemas (draft 2020-12) for the Research section (ported from schemas.rb): one entry, the index, and the two
research formats used by Note 001. The lists of kinds, topics and statuses come from research_library, so the schemas
cannot drift from the pages. Each schema is served at its $id, under /research/schema/0/, apart from the language's
own schemas at /schema/.
"""
from __future__ import annotations

import research_library as L

DRAFT = "https://json-schema.org/draft/2020-12/schema"
NOTE = "Research is not part of the Universal Paper language. These formats may change or be withdrawn, and no agreement depends on them."
HASH = {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}
URI = {"type": "string", "format": "uri"}
TEXT = {"type": "string", "minLength": 1}
# The evaluation calls of the reference engine. A manifest may name one of these and nothing else.
CALLS = ["validate_bundle", "derive_state", "check_event", "simulate_events", "simulate_amendment", "simulate_price_conformity",
         "simulate_termination", "simulate_eligibility"]


def strict(required, props):
    return {"type": "object", "required": required, "additionalProperties": False, "properties": props}


def lst(of, **extra):
    return {"type": "array", "items": of, **extra}


def numbers(what):
    return lst({"type": "integer", "minimum": 1}, uniqueItems=True, description=what)


def m(base, **extra):
    return {**base, **extra}


def all_schemas(base):
    kinds = [k[0] for k in L.KINDS]
    topics = [t[0] for t in L.TOPICS]
    work = [k for k, v in L.STATUS.items() if "note" in v[3]]
    asked = [k for k, v in L.STATUS.items() if "question" in v[3]]
    file = strict(["name", "url", "media_type"], {
        "name": TEXT, "url": URI, "media_type": TEXT, "describes": TEXT,
        "format": {"type": "string", "description": "The research format the file is written in, such as up-research/query-trace/0."},
        "schema": m(URI, description="The JSON Schema the file validates against."),
        "fingerprint": m(HASH, description="Content hash of the JSON value: RFC 8785 canonical JSON, then SHA-256, with any top-level sigs member left out. It is not a hash of the file as stored."),
        "bytes": {"type": "integer", "minimum": 0}, "license": TEXT, "simulated": {"type": "boolean"},
    })
    ref = strict(["number", "kind", "title", "url"], {"number": {"type": "integer", "minimum": 1}, "kind": {"enum": kinds}, "title": TEXT,
                                                      "status": {"enum": list(L.STATUS)}, "relation": {"enum": ["parent", "part", "related"]}, "url": URI, "json": URI})
    details = {
        "note": strict(["claim"], {
            "claim": TEXT,
            "adds_to_language": strict(["terms", "event_kinds", "required_fields"], {"terms": {"type": "integer"}, "event_kinds": {"type": "integer"}, "required_fields": {"type": "integer"}}),
            "sections": lst(strict(["id", "title"], {"id": TEXT, "title": TEXT, "url": URI})),
            "summary_json": URI,
        }),
        "experiment": strict(["claim", "method", "result", "limits"], {
            "claim": m(TEXT, description="The statement the experiment tests."),
            "method": lst(TEXT, minItems=1),
            "result": strict(["outcome", "summary"], {"outcome": {"enum": list(L.OUTCOME)}, "summary": TEXT}),
            "checks": lst(strict(["what", "by", "result"], {"what": TEXT, "by": m(TEXT, description="The implementations that computed the value."),
                                                            "result": {"enum": ["equal", "different", "not_compared"]}})),
            "limits": lst(TEXT, description="What the experiment does not show."),
            "run": lst(strict(["label", "command"], {"label": TEXT, "command": TEXT})),
            "files": lst({"$ref": "#/$defs/file"}),
        }),
        "reusable": strict(["files"], {
            "files": lst({"$ref": "#/$defs/file"}, minItems=1),
            "schemas": lst(URI),
            "use": lst(strict(["title", "text"], {"title": TEXT, "text": TEXT})),
            "source": {"type": "object"},
        }),
        "question": strict(["question", "why", "settle"], {
            "question": TEXT, "why": m(TEXT, description="Why the answer matters."),
            "known": lst(TEXT, description="What is established so far."),
            "options": lst(strict(["label", "text"], {"label": TEXT, "text": TEXT}), description="Candidate answers. None is a decision."),
            "settle": m(TEXT, description="The evidence or decision that would close the question."),
        }),
    }
    entry = {
        "$schema": DRAFT, "$id": f"{base}entry.schema.json",
        "title": "Universal Paper Research entry (up-research/entry/0)",
        "description": f"One entry in Universal Paper Research: a note, an experiment, a reusable or a question. The same shape is used in the index and in each entry's entry.json, which adds detail and refs. {NOTE}",
        "type": "object",
        "required": ["format", "number", "kind", "slug", "title", "summary", "status", "topics", "language_change", "built_on", "published", "url"],
        "additionalProperties": False,
        "properties": {
            "$schema": URI, "format": {"const": "up-research/entry/0"}, "notice": TEXT,
            "number": {"type": "integer", "minimum": 1, "description": "Permanent. An entry keeps its number and its address after it is withdrawn."},
            "kind": {"enum": kinds, "description": " ".join(f"{k}: {d}" for k, _, _, d in L.KINDS)},
            "slug": {"type": "string", "pattern": "^[a-z0-9]+(-[a-z0-9]+)*$", "description": "The last part of the address: /research/<slug>/."},
            "title": TEXT, "summary": m(TEXT, description="One or two sentences. Backticks mark code."),
            "status": {"enum": list(L.STATUS), "description": " ".join(f"{k}: {v[1]}" for k, v in L.STATUS.items())},
            "topics": lst({"enum": topics}, minItems=1, maxItems=3, uniqueItems=True, description="From a fixed list. The first is the primary topic."),
            "language_change": {"enum": list(L.IMPACT), "description": "none: needs no change to the language. proposes: would change it."},
            "built_on": lst(TEXT, uniqueItems=True, description="The Terms, rules and engine calls the entry uses, by their real names, such as UP:Admin-Fee, A9 or simulate_amendment."),
            "published": {"type": "string", "format": "date"}, "updated": {"type": "string", "format": "date"},
            "parent": {"type": "integer", "minimum": 1, "description": "The number of the entry this one came out of. A note has none."},
            "parts": numbers("The numbers of the entries that came out of this one. The inverse of parent."),
            "related": numbers("Other entries worth reading with this one."),
            "answered_by": {"type": "integer", "minimum": 1, "description": "For a question: the number of the entry that settles it. Required when status is answered."},
            "simulated": {"type": "boolean", "description": "True when the data is an example with hypothetical parties."},
            "license": m(TEXT, description="An SPDX identifier."),
            "reading_minutes": {"type": "integer", "minimum": 1},
            "url": m(URI, description="The page."), "markdown": m(URI, description="The same content as Markdown."),
            "json": m(URI, description="The full record: this shape plus detail and refs."),
            "detail": {"type": "object", "description": "Fields that depend on the kind. Present in entry.json, left out of the index."},
            "refs": lst({"$ref": "#/$defs/ref"}, description="Every entry named in parent, parts and related, resolved to a title and an address."),
        },
        "allOf": [
            {"if": {"properties": {"kind": {"const": "question"}}},
             "then": {"properties": {"status": {"enum": asked}}}, "else": {"properties": {"status": {"enum": work}}}},
            {"if": {"properties": {"kind": {"const": "note"}}}, "then": {"not": {"required": ["parent"]}}},
            {"if": {"properties": {"status": {"const": "answered"}}}, "then": {"required": ["answered_by"]}},
        ] + [{"if": {"properties": {"kind": {"const": k}}}, "then": {"properties": {"detail": {"$ref": f"#/$defs/{k}"}}}} for k in kinds],
        "$defs": {**details, "file": file, "ref": ref},
    }

    def term(extra):
        return strict(["id", "name", "definition", "url", "count"], {"id": TEXT, "name": TEXT, "definition": TEXT, "url": URI,
                                                                     "count": {"type": "integer", "minimum": 0}, **extra})
    index = {
        "$schema": DRAFT, "$id": f"{base}index.schema.json",
        "title": "Universal Paper Research index (up-research/index/0)",
        "description": f"Every entry in Universal Paper Research, with the fixed lists they are filed under. {NOTE}",
        "type": "object",
        "required": ["format", "title", "url", "updated", "notice", "kinds", "topics", "statuses", "language_change", "entries"],
        "additionalProperties": False,
        "properties": {
            "$schema": URI, "format": {"const": "up-research/index/0"}, "title": TEXT, "url": URI,
            "updated": {"type": "string", "format": "date"}, "notice": TEXT,
            "kinds": lst(term({"plural": TEXT})), "topics": lst(term({})),
            "statuses": lst(strict(["id", "name", "meaning", "kinds"], {"id": {"enum": list(L.STATUS)}, "name": TEXT, "meaning": TEXT, "kinds": lst({"enum": kinds})})),
            "language_change": {"type": "object", "additionalProperties": TEXT},
            "outcomes": {"type": "object", "additionalProperties": TEXT, "description": "The results an experiment may report."},
            "rules": lst(TEXT), "feed": URI,
            "schemas": {"type": "object", "additionalProperties": URI},
            "entries": lst({"$ref": "entry.schema.json"}, description="Newest first. No entry carries detail or refs here; fetch its json address for those."),
        },
    }
    question = strict(["id", "asks", "call", "fixed", "open"], {
        "id": {"type": "string", "pattern": "^[a-z0-9]+(-[a-z0-9]+)*$"}, "asks": m(TEXT, description="The question in plain words."),
        "call": {"enum": CALLS, "description": "An engine call that already exists. A manifest cannot define a new one."},
        "fixed": {"type": "object", "description": "Arguments the manifest pins. Agreements are named by ChainId."},
        "open": lst(TEXT, uniqueItems=True, description="Arguments the asker supplies, such as the member and the time."),
        "reads": {"type": "object", "description": "For a call that returns a whole state, the part that answers the question."},
    })
    manifest = {
        "$schema": DRAFT, "$id": f"{base}query-manifest.schema.json",
        "title": "Query manifest (up-research/query-manifest/0)",
        "description": "An optional file beside an agreement that names the questions the agreement will answer. It adds no Term, Event kind or required field, "
                       f"and an agreement without one is exactly as valid. See https://universalpaper.org/research/query-surfaces/. {NOTE}",
        "type": "object", "required": ["format", "spec", "agreement", "questions"], "additionalProperties": False,
        "properties": {
            "format": {"const": "up-research/query-manifest/0"}, "spec": m(TEXT, description="The version of the language the agreement is written in."),
            "status": {"const": "research"}, "simulated": {"type": "boolean"}, "note": TEXT,
            "agreement": strict(["chain", "fingerprint"], {"chain": m(HASH, description="The ChainId."), "fingerprint": m(HASH, description="The content hash of the agreement in force."), "label": TEXT}),
            "source": {"type": "object"},
            "named_by": strict(["role", "key"], {"role": TEXT, "key": {"type": "string", "pattern": "^ed25519:[0-9a-f]{64}$"}, "name": TEXT}),
            "questions": lst(question, minItems=1),
            "sigs": {"type": "array", "description": "Signatures, in the form the language already uses. Left out of the fingerprint, as everywhere else."},
        },
    }
    trace = {
        "$schema": DRAFT, "$id": f"{base}query-trace.schema.json",
        "title": "Query trace (up-research/query-trace/0)",
        "description": "One answer to a named question: the inputs, the state fingerprint of every agreement read, and the verdict. Two parties who compute "
                       f"the same content hash for a trace hold the same question, inputs, state and verdict. {NOTE}",
        "type": "object", "required": ["format", "spec", "manifest", "question", "call", "inputs", "state", "verdict"], "additionalProperties": False,
        "properties": {
            "format": {"const": "up-research/query-trace/0"}, "spec": TEXT, "simulated": {"type": "boolean"},
            "manifest": m(HASH, description="The fingerprint of the manifest the question came from."),
            "question": m(TEXT, description="The id of the question in that manifest."), "call": {"enum": CALLS},
            "inputs": {"type": "object", "required": ["at"], "properties": {"at": {"type": "string", "format": "date-time"}},
                       "description": "Every argument the call was given, including the time. Chains are named by ChainId, never by position."},
            "state": lst(strict(["chain", "fingerprint"], {"chain": HASH, "fingerprint": m(HASH, description="The state_hash that derive_state returns for the chain.")}), minItems=1),
            "verdict": {"type": "object", "description": "The values the call returned that the specification determines."},
        },
    }
    return {"entry.schema.json": entry, "index.schema.json": index, "query-manifest.schema.json": manifest, "query-trace.schema.json": trace}
