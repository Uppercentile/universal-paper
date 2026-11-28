"""/research/: notes, experiments, reusable files and open questions built on the language (ported from build.rb).

Research is not part of the Universal Paper language. Every page under /research/ carries that notice, and nothing here
adds a Term, an Event kind, a required field, or anything under spec/ or schema/. The research schemas are served under
/research/schema/0/, apart from the language's own at /schema/.

Inputs (read only):
  research_library.py                  the kinds, topics, statuses and entries, as data
  research_schemas.py                  the four JSON Schemas, generated from the same lists
  theme/research/content/              hand-written text for the index, the note and the experiment
  theme/research/example/              the example manifest, three traces and the note's summary.json (served byte for byte)
  theme/research/*.css, *.js           styles for every Research page; the index, experiment and reading scripts

One function, build_entry, builds the page, entry.json and Markdown for an entry of any kind. build() then writes the
index, index.json, feed.xml, the schemas and the example files, and checks that every /research/ link it wrote points at
something it serves. --research-sample N (build_site.py) adds sample rows to the index for checking the layout at scale;
that build is marked "Preview only" and noindex, and must never be published.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import research_library as L
import research_schemas

HERE = Path(__file__).resolve().parent
SRC = HERE / "theme" / "research"
EX = SRC / "example"
NOTICE = "Research is not part of the Universal Paper language. It may grow, change, or be withdrawn. Agreements do not depend on it."
UPDATED = "November 27, 2026"
ISO = "2026-11-27"
FULL_AT = 6  # the search and filters appear once there are this many entries
BUNDLE_URL = "/examples/generative/bundle.json"
LICENSES = {"CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/", "CC0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/"}
ORG = {"@type": "Organization", "@id": "https://uppercentile.com/#org", "name": "Uppercentile", "url": "https://uppercentile.com"}
INDEX = {
    "title": "Research | Universal Paper",
    "desc": "Universal Paper Research: notes, experiments, reusable files and open questions built on the language. Research is not part of the language.",
    "lede": "Ideas we are testing on top of the language. Each one is built from what Universal Paper already has, and each can be checked by running an engine yourself.",
}
RUN = [("Local server", "uvx universal-paper-mcp"),
       ("Reference interpreter", "python -m universal_paper derive examples/generative/bundle.json --at 2027-03-01T00:00:00Z")]
CTA = {"note": "Read the note", "experiment": "Open the experiment", "reusable": "Get the files", "question": "Read the question"}
LD_TYPE = {"note": "TechArticle", "experiment": "TechArticle", "reusable": "Dataset", "question": "WebPage"}
NOTICE_HTML = ('<div class="announce rs-notice" role="note" aria-label="Research notice"><div class="wrap"><span class="pill">Research</span>'
               f"<span>{NOTICE}</span></div></div>")

esc, rich, bare, ico = L.esc, L.rich, L.bare, L.ico


def plain(s):
    return re.sub(r"&[a-z]+;", " ", re.sub(r"<[^>]+>", " ", s).replace("&rsquo;", "'"))


def slugify(s):
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", plain(s).lower()))


def short(h):
    x = h.split(":", 1)[1]
    return f"sha256:{x[:8]}…{x[-8:]}"


def compact(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def pretty(o):
    return json.dumps(o, ensure_ascii=False, indent=2) + "\n"


def read(name):
    return (SRC / name).read_text(encoding="utf-8")


def js(*names):
    return "\n".join(f"<script>\n{read(n)}</script>" for n in names)


def path_of(e):
    return f"/research/{e['slug']}/"


def md_of(e):
    return f"/research/{e['slug']}.md"


def kind_link(k):
    return f"/research/?kind={k}#library"


def topic_link(k):
    return f'<a href="/research/?topic={k}#library">{L.topic_name(k)}</a>'


def page_title(e):
    t = e.get("short") or e["title"]
    for s in (" | Universal Paper Research", " | UP Research"):
        if len(t + s) <= 60:
            return t + s
    raise SystemExit(f"research entry {e['n']}: the title is too long for a page title. Add short= to the entry.")


def page_desc(e):
    if e.get("desc"):
        if len(e["desc"]) > 155:
            raise SystemExit(f"research entry {e['n']}: desc is over 155 characters")
        return e["desc"]
    out = f"Research {e['kind']}:"
    for s in re.split(r"(?<=\.)\s+", bare(e["summary"])):
        if len(out + " " + s) > 155:
            break
        out += " " + s
    if out.endswith(":"):
        raise SystemExit(f"research entry {e['n']}: the first sentence of the summary is too long for a description. Add desc= to the entry.")
    return out


_TOKEN = re.compile(r'"(?:[^"\\\n]|\\.)*"|[{}\[\],]|-?\b\d+\b|\btrue\b|\bfalse\b')


def highlight_json(code):
    """The token classes the site's Markdown pipeline gives a JSON block (k, s, p, num), as research.js does."""
    out, pos = [], 0
    for mt in _TOKEN.finditer(code):
        out.append(esc(code[pos:mt.start()]))
        t = mt.group(0)
        if t[0] == '"':
            cls = "k" if re.match(r"\s*:", code[mt.end():]) else "s"
        else:
            cls = "p" if t in "{}[]," else "num"
        out.append(f'<span class="{cls}">{esc(t)}</span>')
        pos = mt.end()
    out.append(esc(code[pos:]))
    return "".join(out)


def prose(h):
    """Numbers the h2s, builds the section list, and labels table cells for narrow screens."""
    toc = []

    def h2(mt):
        t = mt.group(1)
        i = slugify(t)
        toc.append((i, t, len(toc) + 1))
        return (f'<h2 id="{i}" class="sec"><span class="sn">{len(toc):02d}</span><span>{t}</span>'
                f'<a class="anchor" href="#{i}" aria-label="Link to this section: {esc(plain(t).strip())}">#</a></h2>')
    body = re.sub(r"<h2>(.*?)</h2>", h2, h, flags=re.S)

    def table(mt):
        t = mt.group(1)
        heads = re.findall(r"<th>(.*?)</th>", t, re.S)

        def tr(r):
            cells = iter(heads)
            return f"<tr{r.group(1)}>" + re.sub(r"<td>", lambda _: f'<td data-th="{esc(plain(next(cells, "")).strip())}">', r.group(2)) + "</tr>"
        return "<table>" + re.sub(r"<tr([^>]*)>(.*?)</tr>", tr, t, flags=re.S) + "</table>"
    return re.sub(r"<table>(.*?)</table>", table, body, flags=re.S), toc


class Research:
    """One build of /research/: the entries, the example files and everything generated from them."""

    def __init__(self, site, *, style, sample=0):
        self.site, self.style = site, style
        self.base = site.base
        self.schema = f"{self.base}/research/schema/0/"
        self.repo_url = site.a.repo_url or "https://github.com/Uppercentile/universal-paper"
        self.real = L.ENTRIES
        self.all = self.real + L.sample(sample) if sample > len(self.real) else self.real
        self.preview = len(self.all) > len(self.real)
        L.check(self.all)
        self.by = {e["n"]: e for e in self.real}
        self.minutes, self.out = {}, {}  # out: published path under /research/ -> text (or bytes, served as is)
        self._example()

    # ---- the example: one manifest and three traces, published as files by the Reusable entry
    def _example(self):
        self.manifest_text = (EX / "manifest.json").read_text(encoding="utf-8")
        self.manifest = json.loads(self.manifest_text)
        self.summary = json.loads((EX / "summary.json").read_text(encoding="utf-8"))
        self.traces = self.summary["example"]["traces"]
        self.vec = next(e for e in self.real if e["kind"] == "reusable")
        rows = [("manifest.json", "The example manifest: three named questions about one agreement, Master X.", "up-research/query-manifest/0",
                 "query-manifest.schema.json", self.summary["manifest"]["fingerprint"])]
        for t in self.traces:
            q = next(x for x in self.manifest["questions"] if x["id"] == t["trace"]["question"])
            rows.append((f"trace-{q['id']}.json", f"One answer to: {q['asks']}", "up-research/query-trace/0", "query-trace.schema.json", t["fingerprint"]))
        self.vec_files = []
        for name, what, fmt, schema, fp in rows:
            data = json.loads((EX / name).read_text(encoding="utf-8"))
            want = self.manifest if name == "manifest.json" else next(t for t in self.traces if t["fingerprint"] == fp)["trace"]
            if data != want:
                raise SystemExit(f"theme/research/example/{name} does not match its entry in summary.json")
            self.vec_files.append({"name": name, "url": f"{self.base}{path_of(self.vec)}{name}", "media_type": "application/json", "describes": what,
                                   "format": fmt, "schema": self.schema + schema, "fingerprint": fp, "bytes": (EX / name).stat().st_size,
                                   "license": "CC0-1.0", "simulated": True})
        x = self.manifest["agreement"]["chain"]
        state = {}
        for t in self.traces:
            for s in t["trace"]["state"]:
                state[s["chain"]] = s["fingerprint"]
        px = next(k for k in state if k != x)
        self.values = {
            "AGREEMENT": self.manifest["agreement"]["fingerprint"], "CHAIN_X": x, "STATE_X": state[x], "STATE_PX": state[px],
            "MANDATE": self.manifest["questions"][2]["fixed"]["mandate"], "MANIFEST_FP": self.summary["manifest"]["fingerprint"],
            "T0": self.traces[0]["fingerprint"], "T1": self.traces[1]["fingerprint"], "T2": self.traces[2]["fingerprint"],
            "BUNDLE_URL": BUNDLE_URL, "REPO": self.repo_url,
        }

    def check_block(self, t):
        return f"""<div class="rs-check">
  <p class="fp"><span>Trace fingerprint</span><code>{t['fingerprint']}</code></p>
  <p class="fp"><span>Recomputed here</span><code data-got>Needs JavaScript</code><span class="vd sm" data-chip hidden></span></p>
  <div class="rs-ctl"><button class="cbtn light" type="button" data-tamper aria-pressed="false">Change one value</button><span class="fine" data-msg aria-live="polite"></span></div>
  <details><summary>Show the trace</summary><pre data-lang="json"><code data-json>{highlight_json(json.dumps(t['trace'], ensure_ascii=False, indent=2))}</code></pre></details>
</div>"""

    # ---- pieces that link one entry to another
    def part_card(self, e):
        return (f'<a class="rs-part" href="{path_of(e)}"><span class="fn k-{e["kind"]}">{L.label(e)}</span><b>{esc(e["title"])}</b>'
                f'<span class="rs-part-s">{rich(e["summary"])}</span><span class="more">{CTA[e["kind"]]} {ico("arrow")}</span></a>')

    def entry_list(self, lst):
        return '<ol class="rs-qlist">' + "".join(
            f'<li><a href="{path_of(q)}"><span class="fn k-{q["kind"]}">{L.label(q)}</span><b>{esc(q["title"])}</b>'
            f'<span class="rs-part-s">{rich(q["summary"])}</span>{L.status_pill(q["status"])}</a></li>' for q in lst) + "</ol>"

    def fill(self, text, extra=None):
        extra = extra or {}
        t = re.sub(r"\{\{([A-Z0-9_]+)\}\}", lambda mt: extra.get(mt.group(1), mt.group(0)), text)
        t = re.sub(r"\{\{ICO:([a-z-]+)\}\}", lambda mt: ico(mt.group(1)), t)
        t = re.sub(r"\{\{SHORT:([A-Z0-9_]+)\}\}", lambda mt: short(self.values[mt.group(1)]), t)
        t = re.sub(r"\{\{CHECK:(\d)\}\}", lambda mt: self.check_block(self.traces[int(mt.group(1))]), t)
        t = re.sub(r"\{\{PART:(\d+)\}\}", lambda mt: self.part_card(self.by[int(mt.group(1))]), t)
        t = t.replace("{{MANIFEST_PRE}}", f'<pre data-lang="json"><code>{highlight_json(self.manifest_text.strip())}</code></pre>')
        t = t.replace("{{MANIFEST}}", self.manifest_text.strip())

        def value(mt):
            if mt.group(1) not in self.values:
                raise SystemExit(f"research: unknown placeholder {mt.group(0)}")
            return self.values[mt.group(1)]
        t = re.sub(r"\{\{([A-Z0-9_]+)\}\}", value, t)
        left = re.search(r"\{\{[A-Z0-9_:]+\}\}", t)
        if left:
            raise SystemExit(f"research: unfilled placeholder {left.group(0)}")
        return t

    # ---- a whole page, with this section's notice
    def page(self, path, title, desc, main, *, scripts="", ld=(), links=(), kind="website", crumbs):
        notice = NOTICE_HTML
        if self.preview:
            notice += (f'\n<div class="rs-sample" role="note">Preview only. Entries {L.no(len(self.real) + 1)} to {len(self.all)} are samples for '
                       f"checking the layout. Only entries 001 to {L.no(len(self.real))} are real.</div>")
        html_text = self.site.page(path, title, desc, main, style=self.style, scripts=scripts, kind=kind, ld=ld, links=links,
                                   robots="noindex,nofollow" if self.preview else "index,follow", announce=notice, crumbs=crumbs)
        if NOTICE not in html_text:
            raise SystemExit(f"{path}: the Research notice is missing")
        return html_text

    def media(self, u, typ, name):
        return {"@type": "MediaObject", "contentUrl": self.base + u, "encodingFormat": typ, "name": name}

    def collection(self):
        u = f"{self.base}/research/"
        return {"@type": "CollectionPage", "@id": u, "name": "Universal Paper Research", "url": u}

    # ---- the record: the same shape in index.json and in each entry.json
    def record(self, e):
        r = {"format": "up-research/entry/0", "number": e["n"], "kind": e["kind"], "slug": e["slug"], "title": e["title"], "summary": e["summary"],
             "status": e["status"], "topics": e["topics"], "language_change": e["impact"], "built_on": e["built_on"], "published": e["date"], "updated": e["date"]}
        if e.get("parent"):
            r["parent"] = e["parent"]
        parts = [p["n"] for p in L.parts_of(self.real, e["n"])]
        if parts:
            r["parts"] = parts
        if e.get("related"):
            r["related"] = e["related"]
        if e.get("answered_by"):
            r["answered_by"] = e["answered_by"]
        if e.get("simulated"):
            r["simulated"] = True
        r["license"] = e.get("license") or "CC-BY-4.0"
        if e["n"] in self.minutes:
            r["reading_minutes"] = self.minutes[e["n"]]
        return {**r, "url": self.base + path_of(e), "markdown": self.base + md_of(e), "json": f"{self.base}{path_of(e)}entry.json"}

    def ref(self, e, relation):
        return {"number": e["n"], "kind": e["kind"], "title": e["title"], "status": e["status"], "relation": relation,
                "url": self.base + path_of(e), "json": f"{self.base}{path_of(e)}entry.json"}

    def refs(self, e):
        return (([self.ref(self.by[e["parent"]], "parent")] if e.get("parent") else []) + [self.ref(p, "part") for p in L.parts_of(self.real, e["n"])]
                + [self.ref(self.by[n], "related") for n in e.get("related") or []])

    def detail(self, e, toc):
        k = e["kind"]
        if k == "note":
            return {"claim": self.summary["claim"], "adds_to_language": self.summary["adds_to_language"],
                    "sections": [{"id": i, "title": plain(t).strip(), "url": f"{self.base}{path_of(e)}#{i}"} for i, t, _ in toc],
                    "summary_json": f"{self.base}{path_of(e)}summary.json"}
        if k == "experiment":
            return {"claim": e["claim"], "method": e["method"], "result": {"outcome": e["outcome"], "summary": e["result"]},
                    "checks": [{"what": w, "by": by, "result": res} for w, by, res in e["checks"]], "limits": e["limits"],
                    "run": [{"label": lab, "command": c} for lab, c in RUN], "files": self.vec_files}
        if k == "reusable":
            return {"files": self.vec_files, "schemas": list(dict.fromkeys(f["schema"] for f in self.vec_files)),
                    "use": [{"title": t, "text": x} for t, x in e["use"]], "source": self.manifest["source"]}
        d = {"question": e["title"], "why": e["why"], "known": e["known"]}
        if e.get("options"):
            d["options"] = [{"label": lab, "text": t} for lab, t in e["options"]]
        return {**d, "settle": e["settle"]}

    # ---- structured data, by kind
    def ld_ref(self, e):
        return {"@type": LD_TYPE[e["kind"]], "@id": self.base + path_of(e), "name": e["title"], "url": self.base + path_of(e)}

    def entry_ld(self, e, words):
        b = self.base
        url = b + path_of(e)
        parent = self.by.get(e.get("parent"))
        parts = L.parts_of(self.real, e["n"])
        o = {"@context": "https://schema.org", "@type": LD_TYPE[e["kind"]], "@id": url, "url": url, "name": e["title"], "description": bare(e["summary"]),
             "inLanguage": "en", "datePublished": e["date"], "dateModified": e["date"],
             "identifier": {"@type": "PropertyValue", "propertyID": "Universal Paper Research number", "value": L.no(e["n"])},
             "additionalType": f"{b}/research/#kind-{e['kind']}", "creativeWorkStatus": L.STATUS[e["status"]][0], "disambiguatingDescription": NOTICE,
             "author": ORG, "publisher": ORG, "license": LICENSES[e.get("license") or "CC-BY-4.0"], "isAccessibleForFree": True,
             "isPartOf": [self.collection(), self.ld_ref(parent)] if parent else self.collection(),
             "about": [{"@type": "DefinedTerm", "@id": f"{b}/research/#topic-{k}", "name": L.topic_name(k), "inDefinedTermSet": f"{b}/research/#topics"} for k in e["topics"]],
             "keywords": ", ".join([L.kind_name(e["kind"])] + [L.topic_name(k) for k in e["topics"]] + e["built_on"]),
             "encoding": [self.media(md_of(e), "text/markdown", "This entry as Markdown"), self.media(f"{path_of(e)}entry.json", "application/json", "This entry as a JSON record")]}
        if parts:
            o["hasPart"] = [self.ld_ref(p) for p in parts]
        if e.get("related"):
            o["isBasedOn"] = [self.ld_ref(self.by[n]) for n in e["related"]]
        k = e["kind"]
        if k == "note":
            o.update({"headline": e["title"], "abstract": self.summary["claim"], "proficiencyLevel": "Expert", "wordCount": words})
            o["encoding"].append(self.media(f"{path_of(e)}summary.json", "application/json", "Machine-readable summary: the three questions, the trace shape and the example traces"))
        elif k == "experiment":
            o.update({"headline": e["title"], "abstract": f"Claim: {e['claim']} Result: {L.OUTCOME[e['outcome']]}. {bare(e['result'])}",
                      "proficiencyLevel": "Expert", "wordCount": words})
        elif k == "reusable":
            o.update({"creator": ORG, "distribution": [
                {"@type": "DataDownload", "name": f["name"], "description": f["describes"], "contentUrl": f["url"], "encodingFormat": f["media_type"],
                 "contentSize": f"{f['bytes']} B"} for f in self.vec_files]})
        else:
            o["mainEntity"] = {"@type": "Question", "name": e["title"], "text": bare(f"{e['summary']} {e['why']}"), "answerCount": 0,
                               "dateCreated": e["date"], "author": ORG}
        return o

    # ---- generated bodies for the short kinds
    def question_body(self, e):
        opts = ""
        if e.get("options"):
            items = "".join(f'<li><span class="fn">Option {chr(65 + i)}</span><b>{esc(lab)}</b><p>{rich(t)}</p></li>' for i, (lab, t) in enumerate(e["options"]))
            opts = f"""<h2>Possible answers</h2>
<ol class="rs-qs rs-opts">{items}</ol>
<p class="fine">These are candidates. None of them is a decision.</p>
"""
        known = "".join(f"<li>{rich(k)}</li>" for k in e["known"])
        return f"""<p class="intro">{rich(e['summary'])}</p>
<h2>Why it matters</h2>
<p>{rich(e['why'])}</p>
<h2>What we know</h2>
<ul>{known}</ul>
{opts}
<h2>What would settle it</h2>
<p class="rs-settle">{rich(e['settle'])}</p>
<p>If you have a view, or evidence either way, <a href="{self.repo_url}/issues">open an issue</a> and mention Question {L.no(e['n'])}.</p>
<div class="doc-foot"><p>Research question by <a href="https://uppercentile.com">Uppercentile</a>, licensed under <a href="/license/">CC BY 4.0</a>. Asked {UPDATED}.</p></div>
"""

    def reusable_body(self, e):
        p = path_of(e)
        files = "\n".join(
            f'<li><div><b><a href="{p}{f["name"]}">{f["name"]}</a></b><p>{esc(f["describes"])}</p><p class="rs-fpline"><span>Fingerprint</span><code>{f["fingerprint"]}</code></p></div>'
            f'<div class="rs-file-side"><span>{f["bytes"]:,} bytes</span><a class="cbtn light" href="{p}{f["name"]}">Open</a></div></li>' for f in self.vec_files)
        use = "".join(f'<li><span class="fn">Use {i + 1}</span><b>{esc(t)}</b><p>{rich(x)}</p></li>' for i, (t, x) in enumerate(e["use"]))
        return f"""<p class="intro">{rich(e['summary'])}</p>
<aside class="rs-brief" aria-label="Before you use these">
  <p class="rs-brief-h">Before you use these</p>
  <ul>
    <li><b>Simulated.</b> The parties are hypothetical, and no party signed the manifest.</li>
    <li><b>Research formats.</b> The two formats are not part of the Universal Paper language and may change.</li>
    <li><b>Free to reuse.</b> The files are CC0 1.0. No credit is required.</li>
  </ul>
</aside>
<h2>The files</h2>
<ul class="rs-files">
{files}
</ul>
<p class="fine">Each fingerprint is a content hash: canonical JSON (RFC 8785), then SHA-256, the rule in <a href="/spec/domain/#1-encoding-canonical-form-and-hashes">section 1 of the domain</a>. It is computed from the JSON value, so it does not change with spacing or line endings.</p>
<details class="rs-more-d">
  <summary>Show manifest.json</summary>
<figure class="rs-file">
  <figcaption><span class="who">manifest.json</span><span class="vd sm rs-sim">Simulated</span><a class="cbtn light" href="{p}manifest.json">Open the file</a></figcaption>
{{{{MANIFEST_PRE}}}}
</figure>
</details>
<h2>How to use them</h2>
<ol class="rs-qs">{use}</ol>
<h2>The formats</h2>
<div class="tablewrap"><table>
<thead><tr><th>Format</th><th>What it describes</th><th>JSON Schema</th></tr></thead>
<tbody>
<tr><td><code>up-research/query-manifest/0</code></td><td>The questions an agreement will answer, and the existing engine call behind each one</td><td><a href="/research/schema/0/query-manifest.schema.json">query-manifest.schema.json</a></td></tr>
<tr><td><code>up-research/query-trace/0</code></td><td>One answer: the inputs, the state fingerprint of each agreement read, and the verdict</td><td><a href="/research/schema/0/query-trace.schema.json">query-trace.schema.json</a></td></tr>
</tbody></table></div>
<p>Both formats belong to Research. The language&rsquo;s own schemas, at <a href="/schema/">/schema/</a>, do not include them.</p>
<h2>Source and license</h2>
<p>The manifest was derived from <a href="{BUNDLE_URL}">the generative example bundle</a> in the repository. The verdicts and state fingerprints in the traces are the values the hosted reference engine returned on {UPDATED}, asked about <code>2027-03-01T00:00:00Z</code>. <a href="/research/three-traces-recomputed/">Experiment 002</a> says how they were checked and what was not checked.</p>
<div class="doc-foot"><p>Research files by <a href="https://uppercentile.com">Uppercentile</a>, released under CC0 1.0. Published {UPDATED}.</p></div>
"""

    def experiment_extra(self, e):
        word = {"equal": f'<span class="vd ok">{ico("check")}Equal</span>', "different": f'<span class="vd bad">{ico("x")}Different</span>',
                "not_compared": '<span class="vd rs-open">Not compared</span>'}
        return {
            "CLAIM": rich(e["claim"]),
            "RESULT": (f'<aside class="rs-result" data-outcome="{e["outcome"]}" aria-label="Result"><p class="rs-brief-h">Result</p>'
                       f'<p class="rs-result-v">{L.OUTCOME[e["outcome"]]}</p><p>{rich(e["result"])}</p></aside>'),
            "METHOD": '<ol class="rs-steps">' + "".join(f"<li>{rich(x)}</li>" for x in e["method"]) + "</ol>",
            "CHECKS": ('<div class="tablewrap"><table><thead><tr><th>What was compared</th><th>Computed by</th><th>Result</th></tr></thead><tbody>'
                       + "".join(f"<tr><td>{esc(w)}</td><td>{rich(by)}</td><td>{word[r]}</td></tr>" for w, by, r in e["checks"]) + "</tbody></table></div>"),
            "LIMITS": "<ul>" + "".join(f"<li>{rich(x)}</li>" for x in e["limits"]) + "</ul>",
            "EXPLORER": read("content/_explorer.html"), "WAYS": read("content/_ways.html"),
        }

    # ---- Markdown copies
    def md_head(self, e):
        parent = self.by.get(e.get("parent"))
        verb = {"note": "Published", "experiment": "Run", "reusable": "Published", "question": "Asked"}[e["kind"]]
        lines = [f"# {e['title']}", "", f"> {NOTICE}", "",
                 f"Research {e['kind']} {L.no(e['n'])} · Status: {L.STATUS[e['status']][0].lower()} · {verb} {UPDATED} · {L.IMPACT[e['impact']]}"]
        if parent:
            lines.append(f"{'Raised by' if e['kind'] == 'question' else 'Part of'}: {L.label(parent)}, {parent['title']} ({self.base}{path_of(parent)})")
        lines += ["", f"HTML: {self.base}{path_of(e)}", f"Record (JSON): {self.base}{path_of(e)}entry.json", "", e["summary"], ""]
        return "\n".join(lines)

    def md_filed(self, e):
        built = f" Built on: {', '.join(f'`{b}`' for b in e['built_on'])}." if e["built_on"] else ""
        return f"Kind: {L.kind_name(e['kind'])}. Topics: {', '.join(L.topic_name(k) for k in e['topics'])}.{built}\n"

    def md_for(self, e):
        k = e["kind"]
        if k == "question":
            opts = ("## Possible answers\n\n" + "\n".join(f"- **{lab}.** {t}" for lab, t in e["options"]) + "\n\nThese are candidates. None of them is a decision.\n\n"
                    if e.get("options") else "")
            body = (f"## Why it matters\n\n{e['why']}\n\n## What we know\n\n" + "\n".join(f"- {x}" for x in e["known"]) + f"\n\n{opts}## What would settle it\n\n{e['settle']}\n\n"
                    f"If you have a view, or evidence either way, open an issue and mention Question {L.no(e['n'])}: {self.repo_url}/issues\n\n")
        elif k == "reusable":
            body = ("Simulated. The parties are hypothetical, and no party signed the manifest. The two formats are research formats, not part of the Universal Paper language. The files are CC0 1.0.\n\n"
                    "## The files\n\n| File | What it is | Fingerprint |\n|---|---|---|\n" + "\n".join(f"| [{f['name']}]({f['url']}) | {f['describes']} | `{f['fingerprint']}` |" for f in self.vec_files)
                    + "\n\nEach fingerprint is a content hash: canonical JSON (RFC 8785), then SHA-256. It is computed from the JSON value, so it does not change with spacing or line endings.\n\n"
                    "## How to use them\n\n" + "\n".join(f"{i + 1}. **{t}.** {x}" for i, (t, x) in enumerate(e["use"]))
                    + f"\n\n## The formats\n\n- `up-research/query-manifest/0`: {self.schema}query-manifest.schema.json\n- `up-research/query-trace/0`: {self.schema}query-trace.schema.json\n\n"
                    f"## Source and license\n\nDerived from the generative example bundle in the repository ({self.manifest['source']['url']}). The verdicts and state fingerprints are the values the hosted reference engine returned on {UPDATED}, asked about 2027-03-01T00:00:00Z.\n\n")
        else:  # experiment
            word = {"equal": "Equal", "different": "Different", "not_compared": "Not compared"}
            body = (f"## The claim\n\n{e['claim']}\n\n## Result: {L.OUTCOME[e['outcome']].lower()}\n\n{e['result']}\n\n## What was run\n\n" + "\n".join(f"{i + 1}. {x}" for i, x in enumerate(e["method"]))
                    + "\n\n## What matched\n\n| What was compared | Computed by | Result |\n|---|---|---|\n" + "\n".join(f"| {w} | {by} | {word[r]} |" for w, by, r in e["checks"])
                    + f"\n\nState fingerprint of Master X: `{self.values['STATE_X']}`\nManifest fingerprint: `{self.values['MANIFEST_FP']}`\n\n| Question | Trace fingerprint |\n|---|---|\n"
                    + "\n".join(f"| {t['trace']['question']} | `{t['fingerprint']}` |" for t in self.traces)
                    + "\n\n## What this does not show\n\n" + "\n".join(f"- {x}" for x in e["limits"])
                    + "\n\n## Run it yourself\n\nThe MCP server is a convenience, not the source. The answer comes from the bytes, and a local engine must be able to recompute every trace.\n\n"
                    + "\n".join(f"- {lab}: `{c}`" for lab, c in RUN) + f"\n- Files: {self.base}{path_of(self.vec)}\n\n")
        return self.md_head(e) + body + self.md_filed(e)

    # ---- one entry: page, record and Markdown
    def build_entry(self, e):
        b, path, k = self.base, path_of(e), e["kind"]
        parts = L.parts_of(self.real, e["n"])
        if k == "note":
            src = self.fill(read(f"content/{e['slug']}.html"), {"QUESTIONS": self.entry_list([p for p in parts if p["kind"] == "question"])})
        elif k == "experiment":
            src = self.fill(read(f"content/{e['slug']}.html"), self.experiment_extra(e))
        elif k == "reusable":
            src = self.fill(self.reusable_body(e))
        else:
            src = self.fill(self.question_body(e))
        top, body = src.split("<!-- body -->\n", 1) if "<!-- body -->\n" in src else ("", src)
        body, toc = prose(body.replace("data-field=", "data-rs-field="))
        parent = self.by.get(e.get("parent"))
        rel = ""
        if parent:
            rel += f'<div class="rs-rel"><p class="rs-rel-h">{"Raised by" if k == "question" else "Part of"}</p>{self.part_card(parent)}</div>'
        related = [self.by[n] for n in e.get("related") or []]
        if related:
            rel += f'<div class="rs-rel"><p class="rs-rel-h">Read with this</p>{self.entry_list(related)}</div>'
        if k == "question":
            others = [q for q in self.real if q["kind"] == "question" and q.get("parent") == e.get("parent") and q["n"] != e["n"]]
            if others:
                rel += f'<div class="rs-rel"><p class="rs-rel-h">Other questions from {L.label(parent)}</p>{self.entry_list(others)}</div>'
        built = (f'<div><span class="k">Built on</span>{" ".join(f"<code>{esc(x)}</code>" for x in e["built_on"])}</div>' if e["built_on"] else "")
        filed = f"""<div class="rs-filed" aria-label="How this entry is filed">
  <div><span class="k">Kind</span><a href="{kind_link(k)}">{L.kind_name(k)}</a></div>
  <div><span class="k">Topics</span>{"".join(topic_link(t) for t in e["topics"])}</div>
  {built}
  <div><span class="k">Language</span><span>{L.IMPACT[e["impact"]]}</span></div>
  <div><span class="k">Record</span><a href="{path}entry.json">entry.json</a><a href="{md_of(e)}">Markdown</a></div>
</div>
"""
        if '<div class="doc-foot">' not in body:
            raise SystemExit(f"research entry {e['n']}: no doc-foot")
        body = body.replace('<div class="doc-foot">', rel + filed + '<div class="doc-foot">', 1)
        ids = re.findall(r'\bid="([^"]+)"', top + body)
        dups = sorted({i for i in ids if ids.count(i) > 1})
        if dups:
            raise SystemExit(f"research entry {e['n']}: duplicate ids {dups}")
        for a in set(re.findall(r'<a\b[^>]*\bhref="#([^"]+)"', top + body)):
            if a not in ids:
                raise SystemExit(f"research entry {e['n']}: broken anchor #{a}")
        for a in set(re.findall(r'aria-controls="([^"]+)"', top + body)):
            if a not in ids:
                raise SystemExit(f"research entry {e['n']}: broken tab panel {a}")
        words = len(plain(re.sub(r"<pre\b.*?</pre>", " ", top + body, flags=re.S)).split())
        minutes = max(math.ceil(words / 220), 1)
        if k in ("note", "experiment"):
            self.minutes[e["n"]] = minutes

        with_toc = len(toc) >= 5
        withs = ""
        if parts:
            qs = sum(1 for p in parts if p["kind"] == "question")
            withs = ('<b class="rs-toc-h">With this note</b>' + "".join(f'<a class="rs-w" href="{path_of(p)}">{L.label(p)}</a>' for p in parts if p["kind"] != "question")
                     + (f'<a class="rs-w" href="#what-we-are-not-sure-about">{qs} open questions</a>' if qs else ""))
        toc_html = ('<aside class="toc" aria-label="On this page"><b>On this page</b>' + "".join(f'<a href="#{i}"><span class="tn">{n:02d}</span>{t}</a>' for i, t, n in toc)
                    + withs + "</aside>") if with_toc else ""
        meta = {"note": f"Published {UPDATED} · {minutes} min read · {L.IMPACT[e['impact']]}",
                "experiment": f"Run {UPDATED} · Result: {L.OUTCOME.get(e.get('outcome'), '').lower()} · {L.IMPACT[e['impact']]}",
                "reusable": f"Published {UPDATED} · {len(self.vec_files)} files · CC0 1.0 · Simulated",
                "question": f"Asked {UPDATED} · {L.IMPACT[e['impact']]}"}[k]
        acts = [(md_of(e), "doc", "View as Markdown"), (f"{path}entry.json", "hash", "Record (JSON)")] + {
            "note": [(f"{path}summary.json", "hash", "Summary (JSON)"), (f"{path_of(self.vec)}manifest.json", "link", "Example manifest"), (BUNDLE_URL, "ext", "Source bundle")],
            "experiment": [(path_of(self.vec), "link", "The files"), (BUNDLE_URL, "ext", "Source bundle")],
            "reusable": [(f"{path}manifest.json", "link", "manifest.json"), (BUNDLE_URL, "ext", "Source bundle")],
            "question": [(f"{self.repo_url}/issues", "ext", "Open an issue")]}[k]
        up = f'<a class="rs-up" href="{path_of(parent)}">{ico("left")}From {L.label(parent)}</a>' if parent else ""
        long_ = " rs-long" if len(e["title"]) > 30 else ""
        main = f"""<main id="main" data-research-kind="{k}" data-research-number="{e['n']}" data-research-status="{e['status']}">
  <div class="rs-progress" aria-hidden="true"></div>
  <div class="wrap phero cg-hero rs-hero{long_}">
    <nav class="crumbs" aria-label="Breadcrumb"><a href="/">Universal Paper</a><span aria-hidden="true">/</span><a href="/research/">Research</a><span aria-hidden="true">/</span><a href="{kind_link(k)}">{L.kind_name(k, True)}</a><span aria-hidden="true">/</span><span>{esc(e.get('nav') or e.get('short') or e['title'])}</span></nav>
    <p class="rs-kicker">{L.status_pill(e['status'])}<span>Research {k} {L.no(e['n'])}</span>{up}</p>
    <h1 class="display">{esc(e['title'])}</h1>
    <p class="lede">{rich(e.get('lede') or e['summary'])}</p>
    <p class="tmeta">{meta}</p>
    <p class="rs-htags">{"".join(topic_link(t) for t in e["topics"])}</p>
    <p class="rs-acts">{"".join(f'<a href="{h}">{ico(i)}{t}</a>' for h, i, t in acts)}</p>
  </div>
{top.rstrip()}
  <div class="wrap docs trust cg rs-read{'' if with_toc else ' rs-solo'}">
    <article class="prose">
{body.strip()}
    </article>
    {toc_html}
  </div>
  <div class="wrap rs-back"><a class="btn ghost" href="/research/">{ico('left')} All research</a></div>
</main>"""
        crumbs = [("Universal Paper", f"{b}/"), ("Research", f"{b}/research/"), (L.kind_name(k, True), f"{b}/research/?kind={k}"), (e["title"], b + path)]
        links = [("alternate", "application/json", f"{path}entry.json", f"{L.label(e)} as a JSON record"),
                 ("alternate", "text/markdown", md_of(e), f"{e['title']} (Markdown)"),
                 ("describedby", "application/schema+json", "/research/schema/0/entry.schema.json", "JSON Schema for a research entry"),
                 ("collection", None, "/research/", "Universal Paper Research")]
        if parent:
            links.append(("up", None, path_of(parent), f"{L.label(parent)}: {parent['title']}"))
        if k == "note":
            links.append(("alternate", "application/json", f"{path_of(self.vec)}manifest.json", "Example manifest (JSON, simulated)"))
            links.append(("describedby", "application/json", f"{path}summary.json", "Machine-readable summary (JSON)"))
        if k == "experiment":
            data = compact(self.traces).replace("</", "<\\/")
            scripts = f'<script type="application/json" id="rs-data">{data}</script>\n' + js("research.js", "research-read.js")
        else:
            scripts = js("research-read.js")
        self.out[f"{e['slug']}/index.html"] = self.page(path, page_title(e), page_desc(e), main, scripts=scripts, ld=[self.entry_ld(e, words)],
                                                         links=links, kind="article", crumbs=crumbs)
        record = {"$schema": f"{self.schema}entry.schema.json", **self.record(e), "notice": NOTICE, "detail": self.detail(e, toc), "refs": self.refs(e)}
        self.out[f"{e['slug']}/entry.json"] = pretty(record)
        if k == "note":
            qmd = "\n".join(f"- Question {L.no(q['n'])}: {q['title']} {b}{md_of(q)}" for q in parts if q["kind"] == "question")
            self.out[f"{e['slug']}.md"] = self.fill(read(f"content/{e['slug']}.md"), {"QUESTIONS_MD": qmd})
        else:
            self.out[f"{e['slug']}.md"] = self.md_for(e)
        self.site.add_page(path, "0.6" if k == "note" else "0.5", "monthly")
        self.site.add_search(path, e["title"], f"Research {L.kind_name(k).lower()} {L.no(e['n'])}: {bare(e['summary'])}", "research", main, rank=40)

    # ---- the index
    def index_json(self):
        b, s = self.base, self.schema

        def count(k, by):
            return sum(1 for e in self.real if (k in e["topics"] if by == "topic" else e["kind"] == k))
        return {
            "$schema": f"{s}index.schema.json", "format": "up-research/index/0", "title": "Universal Paper Research", "url": f"{b}/research/",
            "updated": ISO, "notice": NOTICE,
            "kinds": [{"id": k, "name": n, "plural": pl, "definition": d, "url": f"{b}/research/?kind={k}", "count": count(k, "kind")} for k, n, pl, d in L.KINDS],
            "topics": [{"id": k, "name": t, "definition": d, "url": f"{b}/research/?topic={k}", "count": count(k, "topic")} for k, t, d in L.TOPICS],
            "statuses": [{"id": k, "name": v[0], "meaning": v[1], "kinds": v[3]} for k, v in L.STATUS.items()],
            "language_change": L.IMPACT, "outcomes": L.OUTCOME,
            "rules": ["Every entry has one kind, from a fixed list of four.", "One primary topic per entry, listed first, and at most two more. Topics are a fixed list.",
                      "built_on names real Terms, rules and engine calls.", "An entry keeps its number and address after it is withdrawn.",
                      "parent names the entry another entry came out of. parts is the inverse. A note has no parent.",
                      "A question is open or answered. An answered question names the entry that settles it in answered_by."],
            "feed": f"{b}/research/feed.xml",
            "schemas": self.schemas_map(),
            "entries": [self.record(e) for e in L.newest(self.real)],
        }

    def schemas_map(self):
        s = self.schema
        return {"entry": f"{s}entry.schema.json", "index": f"{s}index.schema.json", "query_manifest": f"{s}query-manifest.schema.json", "query_trace": f"{s}query-trace.schema.json"}

    def feed(self):
        b = self.base
        items = []
        for e in self.real:
            cats = (f'<category scheme="{b}/research/#kinds" term="{e["kind"]}" label="{L.kind_name(e["kind"])}"/>'
                    + "".join(f'<category scheme="{b}/research/#topics" term="{k}" label="{esc(L.topic_name(k))}"/>' for k in e["topics"]))
            items.append(f'  <entry><title>{esc(e["title"])}</title><id>{b}{path_of(e)}</id><link href="{b}{path_of(e)}"/>'
                         f'<link rel="alternate" type="application/json" href="{b}{path_of(e)}entry.json"/>'
                         f'<published>{e["date"]}T00:00:00Z</published><updated>{e["date"]}T00:00:00Z</updated><summary>{esc(bare(e["summary"]))}</summary>{cats}</entry>')
        newest = max(e["date"] for e in self.real)
        nl = "\n"
        return f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Universal Paper Research</title>
  <subtitle>{esc(NOTICE)}</subtitle>
  <id>{b}/research/</id>
  <link href="{b}/research/"/>
  <link rel="self" href="{b}/research/feed.xml"/>
  <updated>{newest}T00:00:00Z</updated>
  <author><name>Uppercentile</name></author>
{nl.join(items)}
</feed>
"""

    def build_index(self):
        b = self.base
        full = len(self.all) >= FULL_AT
        feat = next((e for e in self.all if e.get("featured")), self.all[0])
        feat_parts = L.parts_of(self.all, feat["n"])
        rest = [e for e in self.all if e["n"] != feat["n"] and e.get("parent") != feat["n"]]
        labels = "\n".join(f'<div><dt><span class="rs-status{v[2]}">{v[0]}</span></dt><dd>{v[1]}</dd></div>' for v in L.STATUS.values())
        idx = self.fill(read("content/index.html"), {
            "FEATURED": L.featured({**feat, "minutes": self.minutes.get(feat["n"], feat.get("minutes"))}, feat_parts),
            "LATEST": L.latest(rest) if full and len(rest) >= 3 else "",
            "LIBRARY": L.library(self.all) if full else L.short_list(self.all),
            "KINDS": L.kind_cards(self.all, full), "TOPICS": L.topic_cards(self.all, full), "LABELS": labels})
        acts = (f'<p class="rs-acts"><a href="#library">{ico("search")}Search the library</a><a href="#kinds">{ico("doc")}Four kinds</a>'
                f'<a href="#topics">{ico("hash")}Topics</a><a href="#agents">{ico("bot")}For agents</a></p>') if full else ""
        n = len(self.all)
        main = f"""<main id="main">
  <div class="wrap phero cg-hero rs-hero rs-home">
    <nav class="crumbs" aria-label="Breadcrumb"><a href="/">Universal Paper</a><span aria-hidden="true">/</span><span>Research</span></nav>
    <h1 class="display">Research</h1>
    <p class="lede">{INDEX['lede']}</p>
    <p class="tmeta">{n} {'entry' if n == 1 else 'entries'} · {len(L.KINDS)} kinds · {len(L.TOPICS)} topics · Not part of the language</p>
    {acts}
  </div>
{idx.rstrip()}
</main>"""
        ids = re.findall(r'\bid="([^"]+)"', main)
        dups = sorted({i for i in ids if ids.count(i) > 1})
        if dups:
            raise SystemExit(f"/research/: duplicate ids {dups}")
        for a in set(re.findall(r'<a\b[^>]*\bhref="#([^"]+)"', main)):
            if a not in ids:
                raise SystemExit(f"/research/: broken anchor #{a}")

        def term_set(i, name, terms):
            return {"@context": "https://schema.org", "@type": "DefinedTermSet", "@id": f"{b}/research/#{i}", "name": name, "url": f"{b}/research/#{i}",
                    "hasDefinedTerm": [{"@type": "DefinedTerm", "@id": f"{b}/research/#{tid}", "termCode": tid.split("-", 1)[1], "name": tn, "description": d}
                                       for tid, tn, d in terms]}
        ld = [
            {"@context": "https://schema.org", **self.collection(),
             "description": INDEX["desc"], "disambiguatingDescription": NOTICE, "inLanguage": "en",
             "dateModified": ISO, "publisher": ORG, "license": LICENSES["CC-BY-4.0"],
             "encoding": [self.media("/research/index.json", "application/json", "Machine-readable list of research entries"),
                          self.media("/research/feed.xml", "application/atom+xml", "Feed of research entries")],
             "mainEntity": {"@type": "ItemList", "numberOfItems": len(self.real),
                            "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": {**self.ld_ref(e), "additionalType": f"{b}/research/#kind-{e['kind']}"}}
                                                for i, e in enumerate(self.real)]}},
            term_set("kinds", "Kinds of research entry", [(f"kind-{k}", nm, d) for k, nm, _, d in L.KINDS]),
            term_set("topics", "Research topics", [(f"topic-{k}", t, d) for k, t, d in L.TOPICS]),
        ]
        links = [("alternate", "application/json", "/research/index.json", "Research entries (JSON)"),
                 ("alternate", "application/atom+xml", "/research/feed.xml", "Universal Paper Research (feed)"),
                 ("describedby", "application/schema+json", "/research/schema/0/index.schema.json", "JSON Schema for the research index"),
                 ("describedby", "application/schema+json", "/research/schema/0/entry.schema.json", "JSON Schema for a research entry"),
                 ("describedby", "application/schema+json", "/research/schema/0/query-manifest.schema.json", "JSON Schema for a query manifest"),
                 ("describedby", "application/schema+json", "/research/schema/0/query-trace.schema.json", "JSON Schema for a query trace")]
        self.out["index.html"] = self.page("/research/", INDEX["title"], INDEX["desc"], main, scripts=js("research-library.js") if full else "", ld=ld,
                                           links=links, crumbs=[("Universal Paper", f"{b}/"), ("Research", f"{b}/research/")])
        self.out["index.json"] = pretty(self.index_json())
        self.out["feed.xml"] = self.feed()
        self.site.add_page("/research/", "0.7", "weekly")
        self.site.add_search("/research/", "Research", "Notes, experiments, reusable files and open questions. Not part of the language.", "research", main, rank=12)

    # ---- discovery text for the site's own llms.txt and agent.json
    def llms_section(self):
        b, s = self.base, self.schema
        lines = [f"- [{e['title']}]({b}{md_of(e)}): {L.kind_name(e['kind'])} {L.no(e['n'])}, {L.STATUS[e['status']][0].lower()}. {bare(e['summary'])}" for e in self.real]
        return f"""## Research (not part of the language)

{NOTICE} Entries are of four kinds: notes, experiments, reusables (files to build on) and questions. Each has a page, a Markdown copy and a JSON record.

- [Research index, as JSON]({b}/research/index.json): every entry with its kind, status, topics, what it is built on, and the entries it came from
- [Research feed]({b}/research/feed.xml): new and changed entries (Atom)
- [JSON Schemas for Research]({s}entry.schema.json): an entry, the index ({s}index.schema.json), a query manifest ({s}query-manifest.schema.json) and a query trace ({s}query-trace.schema.json)
""" + "\n".join(lines) + "\n"

    def agent_block(self):
        b = self.base
        return {"notice": NOTICE, "index": f"{b}/research/index.json", "feed": f"{b}/research/feed.xml", "page": f"{b}/research/",
                "schemas": list(self.schemas_map().values()), "kinds": [k[0] for k in L.KINDS],
                "entryRecord": f"{b}/research/{{slug}}/entry.json", "entryMarkdown": f"{b}/research/{{slug}}.md"}

    def sitemap_paths(self):
        return ["/research/"] + [path_of(e) for e in self.real]

    # ---- everything, checked, then written
    def build(self):
        for e in self.real:
            self.build_entry(e)
        self.out[f"{self.real[0]['slug']}/summary.json"] = pretty(self.summary)
        for f in self.vec_files:  # served byte for byte: their fingerprints are published
            self.out[f"{self.vec['slug']}/{f['name']}"] = (EX / f["name"]).read_bytes()
        for name, sch in research_schemas.all_schemas(self.schema).items():
            if not sch["$id"].startswith(f"{self.base}/research/schema/0/"):
                raise SystemExit(f"research schema {name}: $id {sch['$id']} must be served under /research/schema/0/")
            self.out[f"schema/0/{name}"] = pretty(sch)
        self.build_index()
        # Every link inside /research/ must point at something this build writes.
        served = {"/research/" + re.sub(r"index\.html$", "", k) for k in self.out}
        for name, text in self.out.items():
            if isinstance(text, bytes) or not name.endswith((".html", ".md", ".json", ".xml")):
                continue
            for h in set(re.findall(r'(?:href="|https://universalpaper\.org)(/research/[^"\s<>)#?]*)', text)):
                h = re.sub(r"[.,;:]+$", "", h)
                if h not in served:
                    raise SystemExit(f"research/{name} links to {h}, which this build does not write")
            if name.endswith(".json"):
                json.loads(text)
        for name, text in self.out.items():
            if isinstance(text, bytes):
                p = self.site.out / "research" / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(text)
            else:
                self.site.write(f"research/{name}", text)
        return self
