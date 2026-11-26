#!/usr/bin/env python3
"""Build the public website for Universal Paper (universalpaper.org).

Inputs (read only, never edited):
  site/theme/                        the v7 look: site.css, site.js, fonts, icons (served from /assets/), and
  site/theme/pages/*.html            hand-designed page bodies: home, developers, spec index, integrations, licenses
  site/layout.py                     shared header, footer, search, document layout and Markdown post-processing
  REPO/explorer/index.html           -> /playground/app.html, framed by /playground/ (the in-browser Playground)
  REPO/spec/**/*.md, DESIGN_NOTES.md -> /spec/...    (rendered pages plus the raw .md)
  REPO/schema/*.json, spec/06-terms/*.json, examples/*/bundle.json (copied as is)
  content/faq.py                     -> /faq/ and the FAQ parts of llms.txt
  REPO/docs/integrations/*.md        -> /integrations/... (optional integrations, linked only from the footer)
                                        plus /integrations/index.json, a machine-readable index for agents
  REPO/explorer/conformance-results.json, AUDIT.md -> the figures on the home page

Output: dist/ (a static site for GitHub Pages: CNAME, .nojekyll, sitemap.xml, robots.txt,
llms.txt, llms-full.txt, 404.html, search index, og image, favicons).

  python3 build_site.py [--repo PATH] [--out dist] [--domain universalpaper.org]
                        [--repo-url https://github.com/Uppercentile/universal-paper] [--og]
"""
import argparse
import ast
import datetime
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import markdown

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "content"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))  # the reference canonicalizer (standard library only), for hashes the pages show
import layout as L  # noqa: E402
from faq import SECTIONS as FAQ  # noqa: E402

from universal_paper.canon import content_hash, jcs  # noqa: E402

TODAY = datetime.date.today().isoformat()
CREATOR = {"@type": "Organization", "@id": "https://uppercentile.com/#org", "name": "Uppercentile", "url": "https://uppercentile.com"}
LIC = {
    "ccby": ("CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
    "apache": ("Apache-2.0", "https://www.apache.org/licenses/LICENSE-2.0"),
    "cc0": ("CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"),
}
TAGLINE = "The open language for agreements between GPOs, suppliers and members"
SITE_DESC = ("Universal Paper is a free, open language for group purchasing agreements between GPOs, suppliers and members. "
             "Every party holds the same agreement, every change is signed, and anyone can verify it offline. "
             "Created by Uppercentile, offered free under CC BY 4.0 and Apache-2.0.")

SPEC_FILES = [  # (source path in repo, slug, title, description)
    ("spec/00-overview.md", "overview", "Overview",
     "What Universal Paper is, why universality buys speed, its engineered properties, design principles and boundaries (antitrust, enforceability, regulation)."),
    ("spec/01-domain.md", "domain", "Domain",
     "The things that exist in Universal Paper: canonical JSON and hashes, Identifier, Seal, Party, Role, Term, Agreement, Event, State, Mandate, Commitment and Bundle."),
    ("spec/02-predicates-functions.md", "predicates-functions", "Predicates and functions",
     "What can be asked of a Universal Paper agreement: the predicates and functions every evaluator provides."),
    ("spec/03-axioms.md", "axioms", "Axioms",
     "The thirteen consensus rules (A1 to A13) that every valid Universal Paper agreement and event satisfies."),
    ("spec/04-inference.md", "inference", "Inference",
     "How a State and an Event yield the next State: clause forms, exceptions and precedence, rendering and simulation."),
    ("spec/05-lifecycle.md", "lifecycle", "Lifecycle",
     "The agreement status model and the transition rule for every Event kind: who must sign and what must be true."),
    ("spec/06-terms/README.md", "terms", "Term library",
     "The initial Universal Paper Term library: sixteen reusable, value-neutral clauses for GPO, supplier and member agreements."),
    ("spec/07-mapping-guide.md", "mapping-guide", "Mapping guide",
     "How rosters, eligibility files and ASC X12 845, 844, 849 and 867 EDI sets map onto Universal Paper events."),
    ("spec/08-neutrality-charter.md", "neutrality-charter", "Neutrality charter",
     "Who owns Universal Paper (no one), how the steward discloses affiliations, and how the specification changes."),
    ("DESIGN_NOTES.md", "design-notes", "Design notes",
     "What was cut, merged or added while drafting Universal Paper, and the open questions for the steward."),
]


# ----------------------------------------------------------------------------- helpers
def esc(s):
    return html.escape(s, quote=True)


def strip_tags(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def jsonld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + "</script>"


# Every page opens at its top. Browsers otherwise restore the last scroll position on reload,
# on back/forward and when a mobile browser reopens a tab, which lands people mid-page. A URL
# with a #fragment still goes straight to it, without the smooth scroll animating across the page.
SCROLL_TOP_JS = """<script id="up-scroll-top">(function(){var h=history,r=document.documentElement,moved=false;
try{if("scrollRestoration"in h)h.scrollRestoration="manual"}catch(e){}
r.style.scrollBehavior="auto";
["wheel","touchstart","keydown","mousedown"].forEach(function(t){addEventListener(t,function(){moved=true},{passive:true,once:true})});
function top(){if(!location.hash&&!moved)scrollTo(0,0)}
addEventListener("DOMContentLoaded",top);
addEventListener("load",function(){top();setTimeout(function(){r.style.scrollBehavior=""},50)});
addEventListener("pageshow",function(e){if(e.persisted&&!location.hash)scrollTo(0,0)})})();</script>"""


class Site:
    def __init__(self, a):
        self.a = a
        self.base = "https://" + a.domain
        self.out = Path(a.out)
        self.repo = Path(a.repo)
        self.pages = []  # (path, priority, changefreq)
        self.search = []  # entries for /assets/search-index.js, in the order an empty search lists them

    def url(self, path):
        return self.base + path

    def write(self, rel, text):
        if rel.endswith(".html") and "<head>" in text and "up-scroll-top" not in text:
            text = text.replace("<head>", "<head>\n" + SCROLL_TOP_JS, 1)
        p = self.out / rel.lstrip("/")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def add_page(self, path, prio="0.6", freq="monthly"):
        self.pages.append((path, prio, freq))

    def add_search(self, path, title, sub, kind, main_html="", rank=50):
        self.search.append({"t": title, "s": sub, "u": path, "k": kind, "h": L.headings(main_html), "rank": rank})

    def page(self, path, title, desc, main, *, style="", scripts="", kind="website", ld=(), links=(), robots="index,follow", announce=""):
        """A whole v7 page: shared header, footer, search and scripts around `main`."""
        return L.document(title=title, head=self.head_meta(path, title, desc, kind=kind, extra_ld=ld, robots=robots, links=links),
                          header_html=L.header(path, self.a.repo_url), footer_html=L.footer(self.legal_strip(), TAGLINE, self.a.repo_url),
                          main=main, style=style, scripts=scripts, announce=announce)

    # ---- <head> pieces shared by every page
    def head_meta(self, path, title, desc, kind="website", extra_ld=(), robots="index,follow", links=()):
        url = self.url(path)
        og = self.url("/assets/og-image.png")
        crumbs = None
        if path != "/":
            crumbs = {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Universal Paper", "item": self.url("/")},
                {"@type": "ListItem", "position": 2, "name": title.split(" | ")[0], "item": url}]}
        lines = [
            f'<meta name="description" content="{esc(desc)}">',
            f'<link rel="canonical" href="{url}">',
            f'<meta name="robots" content="{robots}">',
            '<meta name="author" content="Uppercentile">',
            '<meta name="creator" content="Uppercentile">',
            '<meta name="theme-color" content="#F5F2EC">',
            '<meta name="color-scheme" content="light">',
            f'<meta property="og:type" content="{kind}">',
            '<meta property="og:site_name" content="Universal Paper">',
            f'<meta property="og:title" content="{esc(title)}">',
            f'<meta property="og:description" content="{esc(desc)}">',
            f'<meta property="og:url" content="{url}">',
            f'<meta property="og:image" content="{og}">',
            '<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">',
            '<meta property="og:image:alt" content="Universal Paper: the open language for GPO, supplier and member agreements">',
            '<meta property="og:locale" content="en_US">',
            '<meta name="twitter:card" content="summary_large_image">',
            f'<meta name="twitter:title" content="{esc(title)}">',
            f'<meta name="twitter:description" content="{esc(desc)}">',
            f'<meta name="twitter:image" content="{og}">',
            f'<link rel="license" href="{self.url("/license/")}">',
            '<link rel="icon" href="/favicon.ico" sizes="32x32">',
            '<link rel="icon" type="image/png" sizes="64x64" href="/assets/icons/favicon-64-navy-transparent.png">',
            '<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">',
            '<link rel="manifest" href="/site.webmanifest">',
            '<link rel="alternate" type="text/plain" title="LLM summary" href="/llms.txt">',
            '<link rel="sitemap" type="application/xml" href="/sitemap.xml">',
        ]
        # extra <link>s, as (rel, type, href, title): e.g. a page's plain Markdown or a JSON descriptor
        lines += [f'<link rel="{rel}" type="{typ}" href="{esc(href)}"' + (f' title="{esc(t)}"' if t else "") + ">" for rel, typ, href, t in links]
        if crumbs:
            lines.append(jsonld(crumbs))
        for o in extra_ld:
            lines.append(jsonld(o))
        return "\n".join(lines)

    # ---- the legal row at the foot of every page
    def legal_strip(self):
        return (
            '<div class="legal"><span><b>Created by <a href="https://uppercentile.com">Uppercentile</a>, free for everyone.</b> '
            f'Specification and docs <a href="{LIC["ccby"][1]}" rel="license">CC BY 4.0</a> · '
            f'code <a href="{LIC["apache"][1]}" rel="license">Apache-2.0</a> · '
            f'example agreements and traces <a href="{LIC["cc0"][1]}" rel="license">CC0 1.0</a>. '
            'No account, fee or license key is ever required. <a href="/license/">How to use and credit it</a>.</span>'
            '<span class="up-badge">'
            # SubmitLLMs directory badge: its listing requires a live link to it (added at Joe's request, 2026-11-24)
            '<a href="https://submitllms.com/directory/universalpaper.org" target="_blank" rel="noopener noreferrer">'
            '<img src="https://submitllms.com/api/badge/universalpaper.org" alt="AI Ready on SubmitLLMs" height="20" loading="lazy" '
            'style="height:20px;width:auto;display:inline-block;vertical-align:middle;opacity:.9"></a></span></div>'
        )


# ----------------------------------------------------------------------------- hand-designed pages (site/theme/pages/)
def fill(text, values, name):
    """Replace {{NAME}} placeholders in a page fragment; every placeholder must be filled."""
    for k, v in values.items():
        text = text.replace("{{" + k + "}}", str(v))
    left = re.findall(r"\{\{\w+\}\}", text)
    if left:
        raise SystemExit(f"theme/pages/{name}.html: unfilled placeholders {sorted(set(left))}")
    return text


def require_links(name, html_text, hrefs):
    """A hand-designed page must keep linking to every page it lists, so a new spec file or tool cannot be forgotten."""
    missing = [h for h in hrefs if f'href="{h}"' not in html_text]
    if missing:
        raise SystemExit(f"theme/pages/{name}.html does not link {missing}")


def conformance_facts(site):
    """The figures the home page shows: the last recorded full test run (tools/build_explorer.py --run-tests) and AUDIT.md."""
    r = json.loads((site.repo / "explorer/conformance-results.json").read_text(encoding="utf-8"))
    audit = (site.repo / "AUDIT.md").read_text(encoding="utf-8")
    sev = re.findall(r"^\| F\d+ \| (\w+) \| \*\*", audit, re.M)
    return {"TESTS_PASSED": r["pytest"]["passed"], "TESTS_TOTAL": r["pytest"]["passed"] + r["pytest"]["failed"],
            "JS_PASSED": r["js"]["passed"], "JS_TOTAL": r["js"]["total"], "LAB_RUNS": r["lab"]["runs"], "LAB_FAILURES": r["lab"]["failures"],
            "AUDIT_FIXED": len(sev), "AUDIT_HIGH": sev.count("High"), "RUN_DATE": r["run"]}


def term_defs(site):
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((site.repo / "spec/06-terms").glob("UP-*.json"))]


PLAYGROUND_REDIRECT = """<script>/* The Playground moved from /#playground to /playground/: keep old links working. */
(function(){var h=location.hash;if(h==="#playground"||h.indexOf("#pg-")===0)location.replace("/playground/"+(h==="#playground"?"":h))})();</script>"""


def build_home(site):
    title = "Universal Paper | Open language for GPO, supplier and member agreements"
    desc = ("Universal Paper is a free, open language for group purchasing agreements. GPOs, suppliers and members share the same paper: "
            "every change is signed, every party computes the same state, fees and obligations. Try the Playground.")
    ld = [
        {"@context": "https://schema.org", "@type": "WebSite", "@id": site.url("/#website"), "name": "Universal Paper",
         "url": site.url("/"), "description": SITE_DESC, "inLanguage": "en", "publisher": CREATOR, "creator": CREATOR,
         "license": LIC["ccby"][1]},
        dict(CREATOR, **{"@context": "https://schema.org", "description": "Creator and current steward of Universal Paper."}),
        {"@context": "https://schema.org", "@type": "CreativeWork", "@id": site.url("/spec/#spec"), "name": "Universal Paper specification",
         "alternateName": "UP", "version": "UP/0.1-draft", "creativeWorkStatus": "Draft", "url": site.url("/spec/"),
         "about": ["group purchasing organizations", "contracts", "supply chain agreements", "administrative fees", "content-addressed data"],
         "creator": CREATOR, "copyrightHolder": CREATOR, "license": LIC["ccby"][1], "isAccessibleForFree": True,
         "description": SITE_DESC},
        playground_ld(site),
    ]
    style, main, scripts = L.fragment("home")
    facts = conformance_facts(site)
    terms = term_defs(site)
    if len(terms) != 16:  # the page says "Sixteen Terms" and "16 standard Terms" in prose
        raise SystemExit(f"theme/pages/home.html says 16 Terms; the library has {len(terms)}")
    rail = [[t["id"], t.get("title", ""), sorted(t.get("params", {}))] for t in terms]
    scripts = scripts.replace("/*@@TERMS@@*/[]", json.dumps(rail, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    # The Write / Agree / Build stage hashes the conventional example's master agreement in the browser (RFC 8785 +
    # SHA-256) and compares it with the hash both parties signed, so both come from the example, never from the design.
    agreement = json.loads((site.repo / "examples/conventional/bundle.json").read_text(encoding="utf-8"))["chains"][0][0]["body"]["agreement"]
    names = [c["n"] for c in agreement["clauses"]]
    stage = {"AGREEMENT_JSON": json.dumps(agreement, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
             "AGREEMENT_HEX": content_hash(agreement).split(":", 1)[1], "AGREEMENT_BYTES": f"{len(jcs(agreement)):,}",
             "FEE_POS": names.index("fee") + 1, "CLAUSE_COUNT": len(names)}
    main = fill(main, {**facts, **stage}, "home")
    scripts = fill(scripts, stage, "home")
    announce = ('<div class="announce" role="region" aria-label="Announcement"><div class="wrap"><span class="pill">UP/0.1</span>'
                f'<span>The draft specification is open for review. <b>{facts["TESTS_PASSED"]}/{facts["TESTS_TOTAL"]}</b> conformance tests passing.</span>'
                '<a href="/spec/">Read the draft</a></div></div>')
    page = site.page("/", title, desc, main, style=style, scripts=PLAYGROUND_REDIRECT + "\n" + scripts, ld=ld, announce=announce)
    site.write("index.html", page)
    site.add_page("/", "1.0", "weekly")
    site.add_search("/", "Home", "Universal Paper", "page", main, rank=0)


def playground_ld(site):
    return {"@context": "https://schema.org", "@type": "WebApplication", "name": "Universal Paper Playground", "url": site.url("/playground/"),
            "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "isAccessibleForFree": True,
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}, "creator": CREATOR, "license": LIC["apache"][1],
            "description": "Write a Universal Paper agreement in the browser and watch its fingerprint, signatures, rendering and obligations update live."}


def build_developers(site):
    title = "Universal Paper for Developers | Spec, reference engine and CLI"
    desc = ("Build on Universal Paper: canonical JSON (RFC 8785), SHA-256 content addresses, Ed25519 signatures, a 16-Term library, "
            "a Python reference interpreter and CLI, and a JavaScript engine that matches it byte for byte. Free and open source.")
    ld = [{"@context": "https://schema.org", "@type": "TechArticle", "headline": "Universal Paper for Developers",
           "url": site.url("/developers/"), "description": desc, "author": CREATOR, "publisher": CREATOR,
           "license": LIC["ccby"][1], "isAccessibleForFree": True, "dateModified": TODAY, "inLanguage": "en",
           "proficiencyLevel": "Expert", "about": {"@id": site.url("/spec/#spec")}},
          {"@context": "https://schema.org", "@type": "SoftwareSourceCode", "name": "universal_paper (reference interpreter)",
           "programmingLanguage": ["Python", "JavaScript"], "license": LIC["apache"][1], "author": CREATOR,
           **({"codeRepository": site.a.repo_url} if site.a.repo_url else {}),
           "description": "Reference interpreter and CLI (up) for Universal Paper, plus an independent JavaScript engine."}]
    style, main, scripts = L.fragment("developers")
    require_links("developers", main, ["/spec/", "/faq/"])
    site.write("developers/index.html", site.page("/developers/", title, desc, main, style=style, scripts=scripts, kind="article", ld=ld))
    site.add_page("/developers/", "0.9", "weekly")
    site.add_search("/developers/", "Developers", "Spec, reference engine, CLI and MCP server", "page", main, rank=1)


def build_playground(site):
    """/playground/: the in-browser Playground from explorer/index.html, framed in the site's own page.

    The explorer page is built by tools/build_explorer.py and is never edited here. Its copy at /playground/app.html
    shows only the Playground section (opened), in the site's fonts and colors; the frame grows to fit it.
    """
    src = (site.repo / "explorer/index.html").read_text(encoding="utf-8")
    app = src.replace('<html lang="en">', '<html lang="en" data-theme="light" data-embed="playground">', 1)
    app = re.sub(r'<link rel="stylesheet" href="https://fonts\.googleapis\.com[^>]*>\s*', "", app)
    app = re.sub(r'<link rel="preconnect"[^>]*>\s*', "", app)
    app = re.sub(r'<meta name="claude:[^"]*"[^>]*>\n?', "", app)
    app = app.replace("</head>", PLAYGROUND_EMBED_HEAD + "\n</head>", 1)
    app = app.replace("</body>", PLAYGROUND_EMBED_JS + "\n</body>", 1)
    site.write("playground/app.html", app)
    title = "Playground | Write a Universal Paper agreement in your browser"
    desc = ("Write a Universal Paper agreement in the browser: change the fee, the length or a party and watch the contract text, "
            "its fingerprint and its signatures update. Compare versions or play out a year of reports and payments. Runs locally.")
    main = f"""<main id="main">
  <div class="wrap phero" style="padding-bottom:8px">
    {L.crumbs([("/", "Universal Paper"), ("", "Playground")])}
    <h1 class="display">Write an agreement. Watch it fingerprint.</h1>
    <p class="lede">Change the fee, the length or a name and watch the contract and its fingerprint update. Sign it, then change it again to see the signatures stop covering it. Compare versions, or play out a year of reports and payments. Everything runs in your browser; the values are examples.</p>
  </div>
  <div class="wrap" style="padding-bottom:clamp(64px,8vw,120px)">
    <iframe id="pgframe" class="pgframe" src="/playground/app.html" title="Universal Paper Playground" loading="eager"></iframe>
    <noscript><p>The Playground needs JavaScript. The <a href="/developers/#quick-start">command line</a> does the same without a browser.</p></noscript>
  </div>
</main>"""
    style = """<style>.pgframe{display:block;width:100%;min-height:900px;border:1px solid var(--line);border-radius:var(--r-xl);background:var(--canvas)}</style>"""
    scripts = """<script>(function(){var f=document.getElementById("pgframe");function fit(){try{var d=f.contentDocument;if(!d||!d.body)return;f.style.height=Math.max(600,d.documentElement.scrollHeight)+"px"}catch(e){}}
f.addEventListener("load",function(){fit();try{new ResizeObserver(fit).observe(f.contentDocument.body)}catch(e){setInterval(fit,1000)}});addEventListener("resize",fit)})();</script>"""
    site.write("playground/index.html", site.page("/playground/", title, desc, main, style=style, scripts=scripts, ld=[playground_ld(site)]))
    site.add_page("/playground/", "0.9", "weekly")
    site.add_search("/playground/", "Playground", "Write an agreement in your browser", "page", main, rank=3)


# Shown inside /playground/app.html only: the Playground section, opened, in the site's fonts and colors (light only, like the site).
PLAYGROUND_EMBED_HEAD = """<meta name="robots" content="noindex,follow">
<link rel="canonical" href="/playground/">
<style id="up-embed">
@font-face{font-family:"Hedvig Serif";src:url("/assets/fonts/hedvig-brand-serif-variable-latin.woff2") format("woff2");font-weight:400;font-display:swap}
@font-face{font-family:"Funnel Sans";src:url("/assets/fonts/funnel-product-sans-roman-latin.woff2") format("woff2");font-weight:300 800;font-display:swap}
@font-face{font-family:"Recursive";src:url("/assets/fonts/recursive-interface-variable-latin.woff2") format("woff2");font-weight:300 1000;font-display:swap}
:root,:root[data-theme]{color-scheme:light;--bg:#F5F2EC;--bg-2:#ECE7DD;--surface:#FFFFFF;--ink:#16143A;--ink-2:#4B4968;--ink-3:#77758F;
--rule:rgba(22,20,58,.12);--rule-2:rgba(22,20,58,.2);--accent:#19173F;--accent-ink:#FFFFFF;--accent-soft:#EEE9FF;
--ok:#138A5A;--ok-soft:#DDF5E8;--bad:#D2401F;--bad-soft:#FFE1D8;--warn:#5C3D00;--warn-soft:#FFF1C7;--flip:#FFD873;
--f-display:"Hedvig Serif",Georgia,serif;--f-paper:"Hedvig Serif",Georgia,serif;--f-body:"Funnel Sans",system-ui,sans-serif;--f-mono:"Recursive",ui-monospace,monospace;
--r-2:14px;--r-3:20px}
html[data-embed] body{background:var(--bg)}
html[data-embed] .site-header,html[data-embed] .site-footer,html[data-embed] main>section:not(#playground),html[data-embed] .scrolly,
html[data-embed] #playground .sec-head,html[data-embed] #pg-bar,html[data-embed] #pg-peek,html[data-embed] .up-legal{display:none!important}
html[data-embed] #playground{padding:24px 0!important;margin:0!important}
html[data-embed] .fpbar{display:none!important} /* the frame never scrolls, so the sticky fingerprint bar would only repeat the fingerprint card below */
html[data-embed] .fpmini{position:static!important}
html[data-embed] [class*="mono"],html[data-embed] code,html[data-embed] .fp{font-variation-settings:"MONO" 1}
html[data-embed] .h2,html[data-embed] h2,html[data-embed] h3,html[data-embed] h4{font-weight:400}
</style>"""
PLAYGROUND_EMBED_JS = """<script>(function(){/* open the Playground and send links to other pages to the top window */
function open(){var b=document.getElementById("pg-body"),t=document.getElementById("pg-toggle");if(b&&b.hidden&&t)t.click();if(b)b.hidden=false}
document.addEventListener("click",function(e){var a=e.target.closest&&e.target.closest("a[href]");if(!a)return;var u=new URL(a.href,location.href);
if(u.origin!==location.origin||u.pathname!==location.pathname){e.preventDefault();(window.top||window).location.href=u.href}},true);
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",open);else open()})();</script>"""


def faq_main(site):
    groups, ld_q, side, cats = [], [], [], []
    for i, (gid, gtitle, qs) in enumerate(FAQ):
        side.append(f'<a href="#{gid}">{esc(gtitle)}</a>')
        tone = L.CARD_TONES[i % len(L.CARD_TONES)]
        cats.append(f'<a class="ccard c-{tone}" href="#{gid}" style="min-height:150px;padding:20px;border-radius:20px"><span class="fn">{len(qs)} answers</span>'
                    f'<h3 style="font-size:21px">{esc(gtitle)}</h3></a>')
        items = []
        for qid, q, a, ref in qs:
            meta = ([f"Source: {esc(ref)}"] if ref else []) + [f'<a href="#{qid}" aria-label="Link to this answer: {esc(q)}">Link to this answer</a>']
            items.append(f'<details class="qa" id="{qid}"><summary><h3>{esc(q)}</h3><span class="pm" aria-hidden="true">{L.ico("plus")}</span></summary>'
                         f'<div class="a">{a}<p class="ref">{" · ".join(meta)}</p></div></details>')
            url = site.url(f"/faq/#{qid}")
            ld_q.append({"@type": "Question", "@id": url, "url": url, "name": q,
                         "acceptedAnswer": {"@type": "Answer", "url": url, "text": strip_tags(a)}})
        groups.append(f'<section class="faqg" id="{gid}" aria-labelledby="{gid}-h"><h2 class="h3 faqh" id="{gid}-h">{esc(gtitle)}</h2>{"".join(items)}</section>')
    n = sum(len(g[2]) for g in FAQ)
    main = f"""<main id="main">
  <div class="wrap phero">
    {L.crumbs([("/", "Universal Paper"), ("", "FAQ")])}
    <h1 class="display">Questions, answered plainly.</h1>
    <p class="lede">{n} answers about what Universal Paper is, how it works, what it means for GPOs, suppliers, members and AI agents, and how it's licensed. Each answer points to the part of the specification it comes from and has its own link.</p>
    <form class="searchbar" role="search" onsubmit="return false">
      {L.ico("search", "color:var(--ink-3)")}
      <label class="sr" for="faqq">Filter questions</label><input id="faqq" placeholder="Filter {n} questions… try “blockchain” or “EDI”" autocomplete="off">
    </form>
    <p id="faqStatus" role="status" style="margin-top:14px;font-size:14px;color:var(--ink-3)"></p>
  </div>
  <div class="wrap">
    <div class="cgrid" style="grid-template-columns:repeat({len(FAQ)},minmax(0,1fr));gap:10px" id="faqCats">{"".join(cats)}</div>
  </div>
  <div class="wrap docs faqdocs">
    <nav class="side" aria-label="FAQ sections"><b>Sections</b>{"".join(side)}<b>More</b><a href="/license/">Licenses</a><a href="/spec/">Specification</a></nav>
    <div style="min-width:0;max-width:860px" id="faqList">{"".join(groups)}</div>
  </div>
  <div class="wrap" style="padding-bottom:clamp(64px,8vw,120px)"><div class="cta" style="padding-block:clamp(48px,6vw,88px)"><canvas data-field="faq" aria-hidden="true"></canvas><h2 class="h2">Still curious?</h2><p class="lede">The specification is the only authority. Every answer above points to the part it comes from.</p><div class="ctas"><a class="btn light" href="/spec/">Read the specification {L.ico("arrow")}</a><a class="btn outline-l" href="/developers/">For developers</a></div></div></div>
</main>"""
    return main, ld_q


FAQ_STYLE = ("<style>@media (max-width:980px){#faqCats{grid-template-columns:repeat(3,minmax(0,1fr))!important}}"
             "@media (max-width:560px){#faqCats{grid-template-columns:repeat(2,minmax(0,1fr))!important}}.faqdocs{grid-template-columns:232px minmax(0,1fr);padding-top:24px}"
             "@media (max-width:860px){.faqdocs{grid-template-columns:minmax(0,1fr)}.docs .side{display:none}}</style>")
FAQ_JS = """<script>
(() => {
  const q = document.getElementById('faqq'), st = document.getElementById('faqStatus');
  const items = [...document.querySelectorAll('#faqList .qa')], groups = [...document.querySelectorAll('#faqList .faqg')];
  q.addEventListener('input', () => {
    const v = q.value.trim().toLowerCase(); let n = 0;
    items.forEach(d => { const hit = !v || d.textContent.toLowerCase().includes(v); d.classList.toggle('hide', !hit); if (hit) n++; if (v && hit) d.open = true; });
    groups.forEach(g => g.hidden = !g.querySelector('.qa:not(.hide)'));
    st.textContent = v ? (n ? n + ' of ' + items.length + ' answers match.' : 'No answers match. Try the search in the header.') : '';
  });
  const o = () => { const h = decodeURIComponent(location.hash.slice(1)), d = h && document.getElementById(h); if (d && d.tagName === 'DETAILS') d.open = true; };
  o(); addEventListener('hashchange', o);
})();
</script>"""


def build_faq(site):
    main, ld_q = faq_main(site)
    title = "Universal Paper FAQ | GPO, supplier and member agreements explained"
    desc = ("Answers about Universal Paper: what the open agreement language is, who created it (Uppercentile), how hashes and signatures work, "
            "confidential pricing, AI agents and the MCP server, optional integrations (LCP, Verifiable Credentials), EDI, legal status and licenses.")
    ld = [{"@context": "https://schema.org", "@type": "FAQPage", "@id": site.url("/faq/"), "url": site.url("/faq/"), "name": title,
           "description": desc, "inLanguage": "en", "dateModified": TODAY,
           "isPartOf": {"@type": "WebSite", "name": "Universal Paper", "url": site.url("/")},
           "publisher": {"@type": "Organization", "name": "Uppercentile", "url": "https://uppercentile.com"},
           "license": "https://creativecommons.org/licenses/by/4.0/", "mainEntity": ld_q}]
    site.write("faq/index.html", site.page("/faq/", title, desc, main, style=FAQ_STYLE, scripts=FAQ_JS, ld=ld))
    site.add_page("/faq/", "0.9", "monthly")
    site.search.append({"t": "FAQ", "s": "Questions, answered plainly", "u": "/faq/", "k": "page", "rank": 5,
                        "h": [(qid, q) for _g, _t, qs in FAQ for qid, q, _a, _r in qs]})


def build_license(site):
    style, main, scripts = L.fragment("license")
    title = "Licenses | Universal Paper is free and open (CC BY 4.0, Apache-2.0, CC0)"
    desc = ("Universal Paper was created by Uppercentile and is offered free to everyone: specification under CC BY 4.0, code under Apache-2.0, "
            "example agreements under CC0. How to use it, credit it and contribute.")
    require_links("license", main, [LIC["ccby"][1], LIC["apache"][1], LIC["cc0"][1], "/spec/neutrality-charter/"])
    site.write("license/index.html", site.page("/license/", title, desc, main, style=style, scripts=scripts))
    site.add_page("/license/", "0.7", "yearly")
    site.add_search("/license/", "Licenses", "Free and open: CC BY 4.0, Apache-2.0, CC0", "page", main, rank=7)


# ----------------------------------------------------------------------------- spec pages
def gh_slug(value, separator="-"):
    v = value.strip().lower()
    v = re.sub(r"[^\w\- ]", "", v)
    return v.replace(" ", "-")


def spec_link_map(site):
    m = {}
    for f, slug, *_ in SPEC_FILES:
        m[f] = f"/spec/{slug}/"
    for p in sorted((site.repo / "spec/06-terms").glob("UP-*.md")):
        m[f"spec/06-terms/{p.name}"] = f"/spec/terms/{p.stem}/"
    return m


def resolve(src_file, href, lmap, site):
    if re.match(r"^[a-z]+:|^#|^/", href):
        return href
    path, _, frag = href.partition("#")
    base = Path(src_file).parent
    target = (base / path).as_posix() if path else src_file
    parts = []
    for seg in target.split("/"):
        if seg == "..":
            parts and parts.pop()
        elif seg and seg != ".":
            parts.append(seg)
    target = "/".join(parts)
    if target.endswith("/"):
        target = target.rstrip("/")
    if target in ("spec/06-terms", "spec/06-terms/"):
        target = "spec/06-terms/README.md"
    if target in lmap:
        return lmap[target] + (("#" + frag) if frag else "")
    if target.startswith("spec/06-terms/") and target.endswith(".json"):
        return "/" + target.replace("spec/06-terms/", "spec/terms/")
    if target.startswith("schema/") or target.startswith("examples/"):
        if (site.out / target).exists() or target.endswith("/"):
            return "/" + target
    if site.a.repo_url:
        return f"{site.a.repo_url}/blob/main/{target}" + (("#" + frag) if frag else "")
    return None


def render_md(site, src_file, text, lmap):
    md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists", "toc"],
                           extension_configs={"toc": {"slugify": gh_slug, "permalink": False}})
    h = md.convert(text)
    def fix(m):
        href = html.unescape(m.group(1))
        new = resolve(src_file, href, lmap, site)
        if new is None:
            return "<a data-nolink>"
        return f'<a href="{esc(new)}">'
    h = re.sub(r'<a href="([^"]*)">', fix, h)
    h = re.sub(r"<a data-nolink>(.*?)</a>", r"<span>\1</span>", h, flags=re.S)
    h = h.replace("<table>", '<div class="tablewrap"><table>').replace("</table>", "</table></div>")
    h = h.replace("[PROVISIONAL]", '<span class="badge" title="An assumption that may change; see the design notes">provisional</span>')
    return h, md.toc_tokens


def spec_side(current):
    items = []
    for f, slug, t, _ in SPEC_FILES:
        m = re.match(r"spec/(\d\d)", f)
        items.append((f"/spec/{slug}/", m.group(1) if m else "—", t))
    items += [(None, "", "Pages"), ("/spec/", "↖", "Specification home"), ("/faq/", "?", "FAQ")]
    return L.side_html("Section", "UP/0.1-draft", items, current)


def term_family(md_text):
    m = re.search(r"\*\*Family:\*\*\s*([^·\n]+?)\s*·", md_text)
    return m.group(1).strip() if m else ""


def term_layers(readme):
    """Which layer each Term usually sits in, from the table in spec/06-terms/README.md."""
    out = {}
    for row, key in (("Aggregator–supplier master agreement", "master"), ("Member participation", "member")):
        m = re.search(r"^\| " + re.escape(row) + r" \| (.+?) \|$", readme, re.M)
        names = re.findall(r"[A-Z][A-Za-z]+(?:-[A-Z][A-Za-z]+)*", m.group(1)) if m else []
        for n in names:
            out.setdefault("UP:" + n, []).append(key)
    return out


def spec_ld(site, path, ttl, desc, raw):
    return [{"@context": "https://schema.org", "@type": "TechArticle", "headline": f"Universal Paper specification: {ttl}",
             "url": site.url(path), "description": desc, "author": CREATOR, "publisher": CREATOR, "license": LIC["ccby"][1],
             "isPartOf": {"@id": site.url("/spec/#spec")}, "version": "UP/0.1-draft", "inLanguage": "en", "dateModified": TODAY,
             "encoding": {"@type": "MediaObject", "contentUrl": site.url(raw), "encodingFormat": "text/markdown"}}]


def doc_foot(site, raw, src_file, lead, extra=""):
    edit = f' · <a href="{site.a.repo_url}/blob/main/{src_file}">View source</a>' if site.a.repo_url else ""
    return f'{lead} <a href="{esc(raw)}">Plain Markdown</a>{extra}{edit}'


def doc_chips(site, h, text, raw, src_file):
    n = len(re.findall(r"<h2\b", h))
    chips = f'<span class="chipx">{n} section{"" if n == 1 else "s"}</span><span class="chipx">~{L.read_minutes(text)} min read</span>'
    links = [(raw, "Markdown")] + ([(f"{site.a.repo_url}/blob/main/{src_file}", "Source")] if site.a.repo_url else [])
    return chips + L.chip_links(links)


SPEC_FOOT = "Specification text by Uppercentile, licensed under <a href=\"/license/\">CC BY 4.0</a>. Working draft UP/0.1-draft."


def build_spec(site):
    lmap = spec_link_map(site)
    # copy machine-readable files
    for p in (site.repo / "spec/06-terms").glob("UP-*.json"):
        dst = site.out / "spec/terms" / p.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(p, dst)
    for d in ("conventional", "generative", "overlay", "confidential", "mandate-cap", "what-if"):
        for p in (site.repo / "examples" / d).glob("*"):
            if p.suffix in (".json", ".txt"):
                (site.out / "examples" / d).mkdir(parents=True, exist_ok=True)
                shutil.copy(p, site.out / "examples" / d / p.name)

    term_files = sorted((site.repo / "spec/06-terms").glob("UP-*.md"))
    terms = {p.stem: json.loads((site.repo / "spec/06-terms" / (p.stem + ".json")).read_text(encoding="utf-8")) for p in term_files}
    readme = (site.repo / "spec/06-terms/README.md").read_text(encoding="utf-8")
    layers = term_layers(readme)

    # reading order for the Previous / Next links
    main_seq = [("/spec/", "Specification home")] + [(f"/spec/{slug}/", t) for _, slug, t, _ in SPEC_FILES] + [("/faq/", "Questions, answered plainly")]
    term_seq = [("/spec/terms/", "All Terms")] + [(f"/spec/terms/{s}/", terms[s]["id"]) for s in terms] + [("/spec/mapping-guide/", "Mapping guide")]

    def around(seq, path):
        i = [p for p, _ in seq].index(path)
        return (seq[i - 1] if i > 0 else None), (seq[i + 1] if i + 1 < len(seq) else None)

    def spec_page(f, slug, ttl, desc):
        path = f"/spec/{slug}/"
        text = (site.repo / f).read_text(encoding="utf-8")
        h, _ = render_md(site, f, text, lmap)
        raw = path.rstrip("/") + ".md"
        site.write(raw, text)
        lede, body, toc = L.article(h)
        extra, scripts = "", ""
        if slug == "terms":  # the library index: a filterable card grid above the README
            extra, scripts = term_library(site.repo, terms, layers), TERM_LIBRARY_JS
            toc = []
        prev, nxt = around(main_seq, path)
        main = L.doc_main(field=slug, tone=L.TONES.get(slug, "warm"),
                          trail=[("/", "Universal Paper"), ("/spec/", "Specification"), ("", ttl)],
                          eyebrow=f'{esc(f.split("/")[-1] if slug != "terms" else "spec/06-terms/")} · UP/0.1-draft', title=ttl, lede=lede,
                          chips=doc_chips(site, body, text, raw, f), side=spec_side(path), body=body, toc=toc,
                          foot=doc_foot(site, raw, f, SPEC_FOOT), pager=L.pager_html(prev, nxt))
        if extra:
            main = main.replace('  <div class="wrap docs">', extra + '\n  <div class="wrap docs">', 1)
        site.write(path.lstrip("/") + "index.html", site.page(path, f"{ttl} | Universal Paper specification", desc, main,
                                                              scripts=scripts, kind="article", ld=spec_ld(site, path, ttl, desc, raw)))
        site.add_page(path, "0.7", "monthly")
        site.add_search(path, ttl, "Term library" if slug == "terms" else "Specification", "spec", main, rank=4 if slug == "terms" else 20)

    def term_page(p):
        j = terms[p.stem]
        tid, ttitle = j.get("id", p.stem.replace("UP-", "UP:")), j.get("title", "")
        path, src_file = f"/spec/terms/{p.stem}/", f"spec/06-terms/{p.name}"
        ttl = f"{tid} ({ttitle})" if ttitle else tid
        desc = (f"The {tid} Term of the Universal Paper library: {ttitle.lower() or 'definition'}, its typed parameters, clauses and "
                "human-readable rendering. Value-neutral, free under CC BY 4.0.")
        text = p.read_text(encoding="utf-8")
        raw = path.rstrip("/") + ".md"
        site.write(raw, text)
        h, _ = render_md(site, src_file, text, lmap)
        h = re.sub(r"^\s*<h1[^>]*>.*?</h1>\s*", "", h, count=1, flags=re.S)
        h = re.sub(r"^\s*<p><strong>Family:</strong>.*?</p>\s*", "", h, count=1, flags=re.S)
        lede, body, toc = L.article(h)
        params, claims = sorted(j.get("params", {})), j.get("claims", {})
        fam = term_family(text)
        chips = (f'<span class="chipx">{esc(fam)}</span><span class="chipx">{len(params)} parameter{"" if len(params) == 1 else "s"}</span>'
                 f'<span class="chipx">{len(claims)} claim type{"" if len(claims) == 1 else "s"}</span>'
                 + L.chip_links([(f"/spec/terms/{p.stem}.json", "JSON"), (raw, "Markdown")]
                                + ([(f"{site.a.repo_url}/blob/main/{src_file}", "Source")] if site.a.repo_url else [])))
        side = L.side_html("Term library", "Term library", [("/spec/terms/", "06", "All Terms")] + [(f"/spec/terms/{s}/", "UP", s[3:]) for s in terms],
                           path, mobile_label="All Terms")
        prev, nxt = around(term_seq, path)
        nav, mobile = side
        pset = "".join(f"<span>{esc(x)}</span>" for x in params)
        main = f"""<main id="main">
  <div class="wrap thero"><div class="in">
    <div class="txt">
      {L.crumbs([("/", "Universal Paper"), ("/spec/terms/", "Term library"), ("", tid)])}
      <code class="tid">{esc(tid)}</code>
      <h1>{esc(ttitle or tid)}</h1>
      {f'<p class="lede">{lede}</p>' if lede else ""}
      <div class="chips" style="margin-top:auto;padding-top:28px">{chips}</div>
    </div>
    <div class="art" data-thumb="{esc(tid)}" aria-hidden="true"><div class="pset">{pset}</div><span class="mark"></span></div>
  </div></div>
  <div class="wrap docs">
    {nav}
    <div style="min-width:0">
      {mobile}
      <article class="prose">{body}
  <p class="doc-foot">{doc_foot(site, raw, src_file, SPEC_FOOT)}</p></article>
    </div>
    {L.toc_html(toc)}
  </div>
  {L.pager_html(prev, nxt)}
</main>"""
        site.write(path.lstrip("/") + "index.html", site.page(path, f"{ttl} | Universal Paper specification", desc, main,
                                                              kind="article", ld=spec_ld(site, path, ttl, desc, raw)))
        site.add_page(path, "0.7", "monthly")
        site.add_search(path, tid, ttitle, "term", main, rank=30)

    for f, slug, ttl, desc in SPEC_FILES:
        spec_page(f, slug, ttl, desc)
    for p in term_files:
        term_page(p)

    # /spec/ index (hand-designed: site/theme/pages/spec.html)
    style, main, scripts = L.fragment("spec")
    require_links("spec", main, [f"/spec/{slug}/" for _, slug, _, _ in SPEC_FILES]
                  + ["/schema/", "/schema/universal-paper.schema.json", "/schema/trace.schema.json", "/llms-full.txt"]
                  + [f"/examples/{d}/bundle.json" for d in ("conventional", "generative", "overlay", "confidential", "mandate-cap", "what-if")])
    title = "Universal Paper specification | UP/0.1-draft"
    desc = ("Read the Universal Paper specification: domain, axioms, inference, lifecycle, the 16-Term library, the EDI mapping guide and the neutrality charter. "
            "Free under CC BY 4.0.")
    ld = [{"@context": "https://schema.org", "@type": "CreativeWork", "@id": site.url("/spec/#spec"), "name": "Universal Paper specification",
           "version": "UP/0.1-draft", "creativeWorkStatus": "Draft", "url": site.url("/spec/"), "creator": CREATOR,
           "license": LIC["ccby"][1], "isAccessibleForFree": True, "description": desc,
           "hasPart": [{"@type": "TechArticle", "name": t, "url": site.url(f"/spec/{slug}/")} for _, slug, t, _ in SPEC_FILES]}]
    site.write("spec/index.html", site.page("/spec/", title, desc, main, style=style, scripts=scripts, ld=ld))
    site.add_page("/spec/", "0.8", "monthly")
    site.add_search("/spec/", "Specification", "UP/0.1-draft: the language, defined", "page", main, rank=2)


def term_library(repo, terms, layers):
    """The filterable grid of Terms on /spec/terms/, built from the JSON definitions and the README tables."""
    fams = {s: term_family((repo / "spec/06-terms" / f"{s}.md").read_text(encoding="utf-8")) for s in terms}
    counts = {}
    for f in fams.values():
        counts[f] = counts.get(f, 0) + 1
    chips = "".join(f'<button type="button" class="fchip" aria-pressed="false" data-fam="{esc(f)}"><i class="t-{L.FAMILY_TONE.get(f, "sky")}"></i>{esc(f)} <b>{n}</b></button>'
                    for f, n in sorted(counts.items(), key=lambda x: (-x[1], x[0])))
    layer_name = {"master": "Master agreement", "member": "Member participation"}
    cards = []
    for s, j in terms.items():
        tid, title, f = j["id"], j.get("title", ""), fams[s]
        ps = sorted(j.get("params", {}))
        lay = layers.get(tid, [])
        m = re.search(r"^\*\*Family:.*?\n\n(.+?)\n", (repo / "spec/06-terms" / f"{s}.md").read_text(encoding="utf-8"), re.S | re.M)
        purpose = m.group(1).strip() if m else ""
        text = " ".join([tid.lower(), title.lower(), purpose.lower(), *ps])
        cards.append(
            f'<a class="tc" href="/spec/terms/{s}/" data-fam="{esc(f)}" data-layers="{" ".join(lay)}" data-text="{esc(text)}">'
            f'<div class="tc-art" data-thumb="{esc(tid)}"><code>{esc(tid)}</code><span class="mark" aria-hidden="true"></span></div>'
            f'<div class="tc-body"><div class="tc-tags"><span class="ftag t-{L.FAMILY_TONE.get(f, "sky")}">{esc(f)}</span>'
            + "".join(f'<span class="ltag">{layer_name[x]}</span>' for x in lay)
            + f'</div><h3>{esc(title)}</h3><p>{esc(purpose)}</p><div class="tc-ps">'
            + ("".join(f"<span>{esc(x)}</span>" for x in ps) or '<span class="none">no parameters</span>')
            + f'</div><div class="tc-foot"><span>{len(ps)} parameter{"" if len(ps) == 1 else "s"}</span><span class="go">Open {L.ico("arrow")}</span></div></div></a>')
    n = len(terms)
    return f"""  <section class="wrap tlib" aria-labelledby="tlib-h">
  <div class="tlib-head">
    <div><p class="eyebrow">The library</p><h2 class="h2" id="tlib-h">{NUMBER_WORDS.get(n, str(n))} standard Terms.</h2></div>
    <p class="lede">Each Term is a reusable, value-neutral clause with typed parameters and no defaults. Filter by family, or by the layer of agreement it usually sits in.</p>
  </div>
  <div class="tlib-bar">
    <div class="fchips" role="group" aria-label="Filter by family">
      <button type="button" class="fchip" aria-pressed="true" data-fam="">All <b>{n}</b></button>
      {chips}
    </div>
    <div class="tlib-tools">
      <div class="seg" role="group" aria-label="Filter by layer"><button type="button" aria-pressed="true" data-layer="">All layers</button><button type="button" aria-pressed="false" data-layer="master">Master agreement</button><button type="button" aria-pressed="false" data-layer="member">Member participation</button></div>
      <label class="tsearch">{L.ico("search")}<span class="sr">Filter Terms</span><input id="tq" placeholder="Filter by name or parameter…" autocomplete="off"></label>
    </div>
  </div>
  <p class="tcount" id="tcount" role="status">Showing all {n} Terms.</p>
  <div class="tgrid2" id="tgrid">{"".join(cards)}</div>
  </section>"""


NUMBER_WORDS = {12: "Twelve", 13: "Thirteen", 14: "Fourteen", 15: "Fifteen", 16: "Sixteen", 17: "Seventeen", 18: "Eighteen", 19: "Nineteen", 20: "Twenty"}

TERM_LIBRARY_JS = """<script>
(() => {
  const cards = [...document.querySelectorAll('#tgrid .tc')], st = document.getElementById('tcount'), q = document.getElementById('tq');
  let fam = '', layer = '';
  const run = () => {
    const v = q.value.trim().toLowerCase(); let n = 0;
    cards.forEach(c => { const ok = (!fam || c.dataset.fam === fam) && (!layer || c.dataset.layers.split(' ').includes(layer)) && (!v || c.dataset.text.includes(v)); c.hidden = !ok; if (ok) n++; });
    st.textContent = n === cards.length ? 'Showing all ' + n + ' Terms.' : n ? 'Showing ' + n + ' of ' + cards.length + ' Terms.' : 'No Terms match. Clear a filter to see more.';
  };
  document.querySelectorAll('.fchip').forEach(b => b.addEventListener('click', () => { document.querySelectorAll('.fchip').forEach(x => x.setAttribute('aria-pressed', x === b)); fam = b.dataset.fam; run(); }));
  document.querySelectorAll('.seg button').forEach(b => b.addEventListener('click', () => { document.querySelectorAll('.seg button').forEach(x => x.setAttribute('aria-pressed', x === b)); layer = b.dataset.layer; run(); }));
  q.addEventListener('input', run);
})();
</script>"""


# ----------------------------------------------------------------------------- optional integrations
# Optional, external integrations (docs/integrations/). Linked modestly (footer, sitemap, llms.txt), never from core pages.
INTEGRATIONS = [("docs/integrations/legal-context-protocol.md", "legal-context-protocol", "Legal Context Protocol",
                 "Optional: publish a Universal Paper bundle at /.well-known/legal-context.json and pin it by its fingerprint (LCP atrHash). "
                 "Universal Paper does not depend on it."),
                ("docs/integrations/verifiable-credentials.md", "verifiable-credentials", "Verifiable Credentials",
                 "Optional: a W3C Verifiable Credential that references a Universal Paper fingerprint, for roster participation "
                 "and role snapshots. A snapshot only: participation status still comes from a Universal Paper engine."),
                ("docs/integrations/fingerprint-coordination.md", "fingerprint-coordination", "Fingerprint Coordination",
                 "Optional analytics: share Universal Paper fingerprints under explicit rules and derive recomputable profiles: "
                 "parameter ranges, variance, historical deltas and engine-checked Proposal seeds. Includes a simulated demo from public examples.")]

FPC_DIR = "examples/integrations/fingerprint-coordination"


def _fpc_schema(name):
    """The convention's claim shapes, read from the repository so the index cannot drift from them."""
    return json.loads((Path(__file__).resolve().parents[1] / FPC_DIR / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))

# What /integrations/index.json says about each integration, beyond the prose. Facts only, all taken from the
# docs above; helper function signatures are read from the helper files themselves so they cannot drift.
_FP = {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$", "description": "A Universal Paper fingerprint"}
_TIME = {"type": "string", "description": "RFC 3339 date-time"}
_VC_ENV = {"@context": {"type": "array", "contains": {"const": "https://www.w3.org/ns/credentials/v2"}},
           "issuer": {"type": "string", "minLength": 1}, "validFrom": _TIME, "validUntil": _TIME}
INTEGRATION_FACTS = {
    "legal-context-protocol": {
        "kind": "discovery and transaction binding",
        "external": {"name": "Legal Context Protocol (LCP)", "url": "https://legalcontextprotocol.org/",
                     "spec": "https://legalcontextprotocol.org/standard", "schema": "https://legalcontextprotocol.org/standard/schema",
                     "status": "draft v1.0 (as of November 2026)"},
        "mapping": {
            "rule": "Serve the artifact's canonical JSON bytes (canonical_bytes) at the `terms` URL, byte for byte. "
                    "Then LCP atrHash and the Universal Paper fingerprint are the same 32 bytes.",
            "atrHash": "\"0x\" + hex(SHA-256(served bytes))",
            "fingerprint": "\"sha256:\" + the same 64 hex digits",
            "lcpFieldsUsed": ["terms", "termsFormat", "atrHash", "acceptanceRequired"],
            "publish": ["Bundle (recommended: any engine can evaluate it on its own)", "Agreement", "Term definition"],
            "doNotPublishAlone": ["Event", "Mandate"],
            "why": "Events and Mandates carry top-level sigs, which their fingerprint leaves out; publish them inside a Bundle.",
        },
        "claimShapes": {"legal-context.json": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "LCP discovery file pinned to a Universal Paper artifact (the fields this integration uses)",
            "type": "object", "required": ["terms", "atrHash"],
            "properties": {"terms": {"type": "string", "pattern": "^https://"}, "termsFormat": {"const": "json"},
                           "atrHash": {"type": "string", "pattern": "^0x[0-9a-fA-F]{64}$"},
                           "acceptanceRequired": {"type": "boolean"}}}},
        "agentFlow": [
            "GET https://{domain}/.well-known/legal-context.json; read terms and atrHash.",
            "GET the terms URL and keep the raw bytes; do not re-serialize them.",
            "Check SHA-256(bytes) == atrHash (compare decoded bytes), then that the bytes are canonical Universal Paper JSON, "
            "so atrHash is the artifact's fingerprint. Compare a fingerprint a counterparty sent you, if any.",
            "Evaluate with any Universal Paper engine: validate the bundle, then derive statuses, tiers, prices and obligations.",
            "Optional: if you act under a Mandate, dry-run your intended event first (axiom A9).",
            "Record atrHash with the transaction.",
        ],
        "authority": "The hash check proves which bytes you have. What the agreement says comes only from evaluating it with a Universal Paper engine.",
        "helper": ("integrations/lcp/up_lcp.py", "Python 3.11+; needs the universal-paper package (its canonicalization), standard library otherwise"),
        "examples": [("conventional: legal-context.json", "/examples/integrations/lcp/conventional/legal-context.json"),
                     ("conventional: terms.up.json (canonical bundle bytes)", "/examples/integrations/lcp/conventional/terms.up.json"),
                     ("mandate-cap: legal-context.json", "/examples/integrations/lcp/mandate-cap/legal-context.json"),
                     ("mandate-cap: terms.up.json (canonical bundle bytes)", "/examples/integrations/lcp/mandate-cap/terms.up.json")],
        "runnable": ["python3 examples/integrations/lcp/agent.py", "python3 examples/integrations/lcp/agent.py --online"],
        "mcpTools": ["hash_object", "validate_bundle", "derive_state", "simulate_events"],
    },
    "verifiable-credentials": {
        "kind": "roster participation and role snapshots",
        "external": {"name": "W3C Verifiable Credentials Data Model 2.0", "url": "https://www.w3.org/TR/vc-data-model-2.0/",
                     "spec": "https://www.w3.org/TR/vc-data-model-2.0/", "status": "W3C Recommendation"},
        "mapping": {
            "rule": "A standard VC envelope plus claims that name a Universal Paper fingerprint (agreementFingerprint). "
                    "Claim and type names are issuer-defined terms; nothing in Universal Paper reads them.",
            "vcFieldsUsed": ["@context", "type", "issuer", "validFrom", "validUntil", "credentialSubject"],
            "recommendedReference": "The bundle's fingerprint, so a verifier can evaluate it on its own.",
            "participant": "Same {scheme, id} shape as a Universal Paper Identifier; pass id to simulate_eligibility.",
        },
        "claimShapes": {
            "ParticipationStatusCredential": {
                "$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Unsigned participation snapshot",
                "type": "object", "required": ["@context", "type", "issuer", "credentialSubject"],
                "properties": {**_VC_ENV,
                               "type": {"type": "array", "allOf": [{"contains": {"const": "VerifiableCredential"}},
                                                                   {"contains": {"const": "ParticipationStatusCredential"}}]},
                               "credentialSubject": {"type": "object", "required": ["agreementFingerprint", "participant", "participantStatus"],
                                                     "properties": {"agreementFingerprint": _FP,
                                                                    "participant": {"type": "object", "required": ["scheme", "id"],
                                                                                    "properties": {"scheme": {"type": "string", "minLength": 1},
                                                                                                   "id": {"type": "string", "minLength": 1}}},
                                                                    "participantStatus": {"enum": ["active", "inactive"]},
                                                                    "eligibleAsOf": _TIME}}}},
            "RoleCredential": {
                "$schema": "https://json-schema.org/draft/2020-12/schema", "title": "Unsigned role proof",
                "type": "object", "required": ["@context", "type", "issuer", "credentialSubject"],
                "properties": {**_VC_ENV,
                               "type": {"type": "array", "allOf": [{"contains": {"const": "VerifiableCredential"}},
                                                                   {"contains": {"const": "RoleCredential"}}]},
                               "credentialSubject": {"type": "object", "required": ["id", "agreementFingerprint", "role"],
                                                     "properties": {"id": {"type": "string", "minLength": 1}, "agreementFingerprint": _FP,
                                                                    "role": {"type": "string", "minLength": 1,
                                                                             "examples": ["purchasing-agent", "roster-admin", "read-only"]}}}}},
        },
        "agentFlow": [
            "Verify the credential with any standard VC library (proof, issuer key, validity window, status list). Outside Universal Paper.",
            "Extract agreementFingerprint and the claims (participant, participantStatus, eligibleAsOf, or role).",
            "Get the artifact by any channel, recompute its fingerprint with a Universal Paper engine, require it to equal agreementFingerprint, and validate it.",
            "If status matters, run simulate_eligibility for the participant at the time you care about. If engine and credential disagree, the engine is right.",
            "Decide with your own policy: whether you trust that issuer for that claim, and what a role label lets that agent do in your systems.",
        ],
        "authority": "A VC is a snapshot only. Participation status comes from a Universal Paper engine (simulate_eligibility). "
                     "A VC grants no authority inside Universal Paper: who may sign which Event is decided only by party keys and Mandates (axiom A9).",
        "helper": ("examples/integrations/vc/up_vc.py", "Python 3.11+; standard library only. Builds and reads unsigned shapes; no signing, issuance or verification"),
        "examples": [("roster participation (unsigned)", "/examples/integrations/vc/roster-participation.json"),
                     ("role proof (unsigned)", "/examples/integrations/vc/role-proof.json")],
        "runnable": [],
        "mcpTools": ["hash_object", "validate_bundle", "simulate_eligibility"],
    },
    "fingerprint-coordination": {
        "kind": "analytics: parameter ranges, variance, historical deltas and Proposal seeds",
        "external": None,
        "mapping": {
            "rule": "A Contribution names artifacts by Universal Paper fingerprint with a disclosure level and usage rules. "
                    "A Derived Profile lists every input by fingerprint plus inputsRoot, names the method, and carries its own fingerprint, "
                    "so anyone holding the inputs can recompute it byte for byte.",
            "ownFingerprint": "the Universal Paper fingerprint of every member except `fingerprint`",
            "inputsRoot": "the Universal Paper fingerprint of the sorted, de-duplicated array of input fingerprints",
            "disclosures": ["fingerprint-only (default)", "structure", "parameters"],
            "privacy": ["sealed values are never counted", "no statistic from fewer than minimumCohort distinct inputs",
                        "per-agreement cells record positions against the cohort, never raw values", "no network code, no telemetry"],
            "seedRules": {"toward-median": "the largest numeric outlier in a cohort, set to the cohort median",
                          "common-clause": "the most common parameterized Term (in at least 2/3 of a cohort) added to the most similar agreement lacking it"},
            "neverSeeded": ["UP:Tiers", "UP:Tier-Selection", "UP:Price-Reference"],
        },
        "claimShapes": {"FingerprintContribution": _fpc_schema("contribution"), "DerivedProfile": _fpc_schema("derived-profile")},
        "agentFlow": [
            "Verify: check the profile's own fingerprint, recompute each input's fingerprint, require them to match inputs and inputsRoot; recompute the profile (verify_profile) to trust its statistics.",
            "Extract seeds (extract_seeds) and keep only those whose target agreement you are a party to.",
            "Optionally simulate: seed_proposal + simulate_seed, or the MCP tools simulate_events / simulate_amendment (which also checks a Mandate's bounds).",
            "Evaluate with your own policy. To propose, sign the propose event with your own keys and send it like any Universal Paper event.",
        ],
        "authority": "A profile is derived data, and a seed is a candidate, not a recommendation. Validity and state come only from a Universal Paper engine "
                     "evaluating the artifacts. Universal Paper does not operate, require or depend on any analytics, telemetry or hosting.",
        "helper": (f"{FPC_DIR}/up_fpc.py", "Python 3.11+; needs the universal-paper package (canonicalization, fingerprints, engine); no network, no storage, no ML"),
        "examples": [("derived profile (simulated from public examples)", f"/{FPC_DIR}/demo-profile.json"),
                     ("contribution", f"/{FPC_DIR}/contribution.json"),
                     ("structural diff: conventional to what-if", f"/{FPC_DIR}/structural-diff.json")],
        "demo": "/integrations/fingerprint-coordination/demo/",
        "scenario": True,
        "runnable": [f"python3 {FPC_DIR}/regenerate.py --check"],
        "mcpTools": ["hash_object", "validate_bundle", "derive_state", "simulate_events", "simulate_amendment"],
    },
}


def helper_functions(path):
    """Public top-level functions of a helper file: name, signature and the first line of the docstring."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and not n.name.startswith("_"):
            ret = f" -> {ast.unparse(n.returns)}" if n.returns else ""
            doc = (ast.get_docstring(n) or "").strip().splitlines()
            out.append({"name": n.name, "signature": f"{n.name}({ast.unparse(n.args)}){ret}", "does": doc[0] if doc else ""})
    return out


def _scenario(site, x):
    """The demo's predictive-redline scenario (source of truth for its playthrough and HowTo JSON-LD), if it has one."""
    f = site.repo / FPC_DIR / "demo/scenario.json"
    if not x.get("scenario") or not f.is_file():
        return {}
    sc = json.loads(f.read_text(encoding="utf-8"))
    return {"scenario": {"url": site.url(x["demo"] + "scenario.json"), "fingerprint": sc["fingerprint"], "seed": sc["source"]["seed"],
                         "howToSteps": [s["id"] for s in sc["steps"]], "howTo": site.url(x["demo"] + "#predictive-redline")}}


def integrations_index(site):
    """The machine-readable index served at /integrations/index.json."""
    a = site.a
    raw = a.repo_url.replace("https://github.com/", "https://raw.githubusercontent.com/") + "/main/" if a.repo_url else None
    items = []
    for f, slug, ttl, desc in INTEGRATIONS:
        x = INTEGRATION_FACTS[slug]
        hpath, hreq = x["helper"]
        items.append({
            "id": slug, "name": ttl, "status": "optional", "kind": x["kind"], "summary": desc,
            "docs": {"html": site.url(f"/integrations/{slug}/"), "markdown": site.url(f"/integrations/{slug}.md"),
                     **({"source": f"{a.repo_url}/blob/main/{f}"} if a.repo_url else {})},
            "external": x["external"], "mapping": x["mapping"], "claimShapes": x["claimShapes"],
            "agentFlow": x["agentFlow"], "authority": x["authority"],
            "helper": {"path": hpath, **({"source": f"{a.repo_url}/blob/main/{hpath}", "raw": raw + hpath} if raw else {}),
                       "language": "Python", "requires": hreq, "license": "Apache-2.0",
                       "functions": helper_functions(site.repo / hpath)},
            "examples": [{"name": n, "url": site.url(u), "license": "CC0-1.0"} for n, u in x["examples"]],
            **({"runnable": x["runnable"]} if x["runnable"] else {}),
            **({"demo": {"url": site.url(x["demo"]), "simulated": True, "network": "none",
                         "note": "Simulated from public example bundles only; not market data.",
                         **_scenario(site, x)}} if x.get("demo") else {}),
            "mcpTools": x["mcpTools"],
        })
    return {
        "name": "Universal Paper optional integrations",
        "url": site.url("/integrations/index.json"),
        "html": site.url("/integrations/"),
        "formatVersion": 1,
        "notice": "Optional and external. Universal Paper is self-contained and does not depend on any integration listed here. "
                  "Nothing here changes the language, its schemas, its fingerprints, its Terms or its engines. "
                  "Any channel that delivers an artifact's bytes and lets the receiver recompute its fingerprint binds an agreement equally well.",
        "language": {"name": "Universal Paper", "version": "UP/0.1-draft", "spec": site.url("/spec/"),
                     "schema": site.url("/schema/universal-paper.schema.json"),
                     "fingerprint": {"format": "sha256:<64 lowercase hex digits>",
                                     "definition": "\"sha256:\" + hex(SHA-256(JCS(strip(o)))), where JCS is RFC 8785 and strip removes top-level sigs",
                                     "spec": site.url("/spec/domain/")}},
        "engines": {"note": "Evaluation is authoritative and identical in any conforming Universal Paper engine.",
                    "mcp": {"endpoint": MCP["endpoint"], "transport": MCP["transport"], "auth": MCP["auth"], "readOnly": MCP["readOnly"],
                            "pypi": MCP["pypi"], "docs": MCP["docs"]},
                    "python": {"pypi": "universal-paper", "cli": ["up hash FILE", "up validate FILE"]}},
        "integrations": items,
        "license": {"text": "CC BY 4.0", "code": "Apache-2.0", "examples": "CC0-1.0", "page": site.url("/license/")},
        "creator": {"name": CREATOR["name"], "url": CREATOR["url"]},
    }


# How each integration is shown on /integrations/ (art and labels only; the facts live in INTEGRATIONS and INTEGRATION_FACTS)
INTEGRATION_CARDS = {"legal-context-protocol": ("Optional · discovery", "Read the mapping"),
                     "verifiable-credentials": ("Optional · credentials", "See the payload"),
                     "fingerprint-coordination": ("Optional · analytics", "Read the convention")}


def integration_lede(desc):
    """The first sentence of an integration's summary, without the "Optional:" prefix (the eyebrow says it)."""
    d = re.sub(r"^Optional(?: analytics)?:\s*", "", desc)
    first = re.split(r"(?<=[.)])\s+(?=[A-Z])", d, maxsplit=1)[0]
    return first[:1].upper() + first[1:]


def card_text(desc):
    """An integration's summary for its card, with paths and field names set as code."""
    d = re.sub(r"^Optional(?: analytics)?:\s*", "", desc)
    d = esc(d[:1].upper() + d[1:])
    return re.sub(r"(/\.well-known/[\w.-]+|\batrHash\b)", r'<code class="mono" style="font-size:.88em">\1</code>', d)


def build_integrations(site):
    lmap = spec_link_map(site)
    # the LCP worked examples: copied byte for byte, because atrHash pins their exact bytes
    src = site.repo / "examples/integrations/lcp"
    for p in sorted(src.glob("*/*.json")):
        dst = site.out / "examples/integrations/lcp" / p.parent.name / p.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dst)
    # the Verifiable Credentials example payloads (static, unsigned)
    for p in sorted((site.repo / "examples/integrations/vc").glob("*.json")):
        dst = site.out / "examples/integrations/vc" / p.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dst)
    # Fingerprint Coordination: the worked examples and schemas, plus the demo (its embedded profile, scenario and
    # HowTo are kept byte for byte; only the site header and footer are added around it)
    src = site.repo / FPC_DIR
    for p in sorted([*src.glob("*.json"), *src.glob("schemas/*.json")]):
        dst = site.out / FPC_DIR / p.relative_to(src)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dst)
    demo_dir = site.out / "integrations/fingerprint-coordination/demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src / "demo/scenario.json", demo_dir / "scenario.json")
    shutil.copyfile(src / "demo-profile.json", demo_dir.parent / "demo-profile.json")
    build_fpc_demo(site, (src / "demo/index.html").read_text(encoding="utf-8"))
    index = integrations_index(site)
    site.write("integrations/index.json", json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    idx_url = site.url("/integrations/index.json")
    idx_media = {"@type": "MediaObject", "contentUrl": idx_url, "encodingFormat": "application/json",
                 "name": "Machine-readable index of Universal Paper optional integrations"}
    collection = {"@type": "CollectionPage", "@id": site.url("/integrations/"), "name": "Universal Paper optional integrations",
                  "url": site.url("/integrations/")}
    seq = [("/integrations/", "All integrations")] + [(f"/integrations/{s}/", t) for _, s, t, _ in INTEGRATIONS]
    if any(INTEGRATION_FACTS[s].get("demo") for _, s, _, _ in INTEGRATIONS):
        seq.append(("/integrations/fingerprint-coordination/demo/", "Coordination demo"))
    side_items = [("/integrations/", "↖", "All integrations")] + [(f"/integrations/{s}/", "○", t) for _, s, t, _ in INTEGRATIONS]
    side_items += [(INTEGRATION_FACTS[s]["demo"], "▶", "Coordination demo") for _, s, _, _ in INTEGRATIONS if INTEGRATION_FACTS[s].get("demo")]
    cards = []
    for n, ((f, slug, ttl, desc), item) in enumerate(zip(INTEGRATIONS, index["integrations"])):
        path = f"/integrations/{slug}/"
        text = (site.repo / f).read_text(encoding="utf-8")
        h, _ = render_md(site, f, text, lmap)
        raw = path.rstrip("/") + ".md"
        site.write(raw, text)
        h = re.sub(r"^\s*<h1[^>]*>.*?</h1>\s*", "", h, count=1, flags=re.S)
        _lede, body, toc = L.article("<p></p>" + h)  # keep the opening notice in the article; the hero carries the summary
        paths = [p for p, _ in seq]
        i = paths.index(path)
        main = L.doc_main(field=slug, tone=L.TONES.get(slug, "warm"),
                          trail=[("/", "Universal Paper"), ("/integrations/", "Integrations"), ("", ttl)],
                          eyebrow="Optional integration", title=ttl, lede=esc(integration_lede(desc)),
                          chips=doc_chips(site, body, text, raw, f),
                          side=L.side_html("Section", "Integrations", side_items, path), body=body, toc=toc,
                          foot=doc_foot(site, raw, f, 'Optional integration documentation by Uppercentile, licensed under <a href="/license/">CC BY 4.0</a>.',
                                        ' · <a href="/integrations/index.json">Machine-readable summary (JSON)</a>'),
                          pager=L.pager_html(seq[i - 1], seq[i + 1] if i + 1 < len(seq) else None))
        helper = item["helper"]
        ld = [{"@context": "https://schema.org", "@type": "TechArticle", "@id": site.url(path),
               "headline": f"Universal Paper optional integration: {ttl}",
               "url": site.url(path), "description": desc, "author": CREATOR, "publisher": CREATOR, "license": LIC["ccby"][1], "inLanguage": "en",
               "isPartOf": collection,
               "about": ({"@type": "CreativeWork", "name": item["external"]["name"], "url": item["external"]["url"]} if item["external"]
                         else {"@type": "CreativeWork", "name": "Universal Paper", "url": site.url("/spec/")}),
               "encoding": [{"@type": "MediaObject", "contentUrl": site.url(raw), "encodingFormat": "text/markdown"}, idx_media],
               "hasPart": {"@type": "SoftwareSourceCode", "name": helper["path"].rsplit("/", 1)[-1], "programmingLanguage": "Python",
                           "license": LIC["apache"][1], **({"codeRepository": site.a.repo_url, "url": helper["source"]} if "source" in helper else {})},
               "isAccessibleForFree": True}]
        links = [("alternate", "text/markdown", raw, f"{ttl} (Markdown)"),
                 ("describedby", "application/json", "/integrations/index.json", "Integrations index (JSON)")]
        site.write(path.lstrip("/") + "index.html", site.page(path, f"{ttl} (optional integration) | Universal Paper", desc, main,
                                                              kind="article", ld=ld, links=links))
        site.add_page(path, "0.4", "monthly")
        site.add_search(path, ttl, "Optional integration", "integration", main, rank=40)
        glyph, more = INTEGRATION_CARDS.get(slug, ("Optional", "Read more"))
        delay = f' style="transition-delay:{n * .06:.2f}s"' if n else ""
        cards.append(f'<a class="int rv" href="{path}"{delay}>\n          <div class="artcard"><canvas data-field="{slug}" data-tone="{L.TONES.get(slug, "warm")}" aria-hidden="true"></canvas>'
                     f'<span class="glyph">{esc(glyph)}</span></div>\n          <div class="body"><h3>{esc(ttl)}</h3><p>{card_text(desc)}</p>'
                     f'<span class="more">{esc(more)} {L.ico("arrow")}</span></div>\n        </a>')
    style, main, scripts = L.fragment("integrations")
    main = fill(main, {"INTEGRATION_CARDS": "\n        ".join(cards)}, "integrations")
    require_links("integrations", main, ["/integrations/index.json", "/integrations/fingerprint-coordination/demo/"])
    desc = ("Optional, external integrations for Universal Paper, such as the Legal Context Protocol, W3C Verifiable Credentials and Fingerprint Coordination "
            "analytics. Universal Paper does not depend on any of them.")
    ld = [{"@context": "https://schema.org", **collection, "description": desc, "publisher": CREATOR, "license": LIC["ccby"][1],
           "encoding": idx_media,
           "mainEntity": {"@type": "ItemList", "itemListElement": [
               {"@type": "ListItem", "position": i, "name": t, "url": site.url(f"/integrations/{s}/")}
               for i, (_, s, t, _) in enumerate(INTEGRATIONS, 1)]}}]
    links = [("alternate", "application/json", "/integrations/index.json", "Integrations index (JSON)")]
    site.write("integrations/index.html", site.page("/integrations/", "Optional integrations | Universal Paper", desc, main,
                                                     style=style, scripts=scripts, ld=ld, links=links))
    site.add_page("/integrations/", "0.3", "monthly")
    site.add_search("/integrations/", "Integrations", "Optional: LCP, Verifiable Credentials, Fingerprint Coordination", "page", main, rank=6)


def build_fpc_demo(site, page):
    """The Fingerprint Coordination demo. Its source (examples/.../demo/index.html, kept up to date by regenerate.py) is a
    complete page that also opens from disk; here its <main> and scripts get the site's header, footer and search."""
    head = page[:page.index("</head>")]
    title = html.unescape(re.search(r"<title>(.*?)</title>", head, re.S).group(1))
    desc = html.unescape(re.search(r'<meta name="description" content="([^"]*)"', head).group(1))
    howto = re.search(r'<script type="application/ld\+json" id="howto">.*?</script>', head, re.S).group(0)
    style = "\n".join(re.findall(r"<style>.*?</style>", head, re.S))
    body = page[page.index("<body"):]
    i, j = re.search(r'<main id="main"[^>]*>', body).start(), body.rindex("</main>") + len("</main>")
    main, tail = body[i:j], body[j:]
    scripts = "\n".join(s for s in re.findall(r"<script\b[^>]*>.*?</script>", tail, re.S) if "src=" not in s.split(">", 1)[0])
    path = "/integrations/fingerprint-coordination/demo/"
    links = [("alternate", "application/json", "scenario.json", "Machine-readable scenario (JSON)"),
             ("describedby", "application/json", "/integrations/index.json", "Integrations index (JSON)")]
    out = site.page(path, title, desc, main, style=style, scripts=scripts, links=links)
    out = out.replace("</head>", howto + "\n</head>", 1)  # regenerate.py owns the HowTo; keep its exact bytes
    site.write(path.lstrip("/") + "index.html", out)
    site.add_page(path, "0.3", "monthly")
    site.add_search(path, "Coordination demo", "Simulated: what shared fingerprints can tell you", "integration", main, rank=41)


# ----------------------------------------------------------------------------- misc files
def build_schemas(site):
    """The JSON Schemas. Each one's $id is a versioned URL on this site where that exact file is served, so a
    validator can resolve it; /schema/<name> is the unversioned alias for the current version. Also /schema/."""
    base = f"https://{site.a.domain}/"
    rows, cards = [], []
    sources = sorted((site.repo / "schema").glob("*.json"), key=lambda p: p.name != "universal-paper.schema.json") + sorted((site.repo / FPC_DIR / "schemas").glob("*.json"))
    for p in sources:
        sch = json.loads(p.read_text(encoding="utf-8"))
        sid = sch.get("$id", "")
        if not sid.startswith(base) or not sid.endswith("/" + p.name):
            raise SystemExit(f"{p.relative_to(site.repo)}: $id {sid!r} must be a URL on {base} ending in /{p.name}")
        served = sid[len(base):]
        alias = f"schema/{p.name}" if p.parent == site.repo / "schema" else None
        for rel in filter(None, (served, alias)):
            (site.out / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(p, site.out / rel)
        src = p.relative_to(site.repo).as_posix()
        links = [(f"/{served}", "Download")] + ([(f"{site.a.repo_url}/blob/main/{src}", "Source")] if site.a.repo_url else [])
        cards.append(f"""<h2 id="{esc(p.stem.replace('.schema', ''))}">{esc(sch.get("title", p.name))}</h2>
<p>{esc(sch.get("description", ""))}</p>
<div class="tablewrap"><table><tbody>
<tr><th scope="row">$id</th><td><code>{esc(sid)}</code></td></tr>
{f'<tr><th scope="row">Current version</th><td><code>{esc(base + alias)}</code></td></tr>' if alias else ""}
<tr><th scope="row">Dialect</th><td><code>{esc(sch.get("$schema", ""))}</code></td></tr>
<tr><th scope="row">Source</th><td><code>{esc(src)}</code></td></tr>
</tbody></table></div>
<p>{" · ".join(f'<a href="{esc(h)}">{t}</a>' for h, t in links)}</p>""")
        rows.append(sid)
    usage = esc("""import json, urllib.request
import jsonschema  # pip install jsonschema

url = "https://universalpaper.org/schema/UP-0.1-draft/universal-paper.schema.json"
schema = json.load(urllib.request.urlopen(url))
jsonschema.validate(json.load(open("bundle.json")), schema)""")
    body = ("\n".join(cards[:2]) + f"""
<h2 id="validate">Validate a bundle</h2>
<p>A schema checks shape only. Whether a well-shaped agreement or event is valid is decided by the <a href="/spec/axioms/">axioms</a>, which the reference interpreter (<code>up validate</code>) and the <a href="/developers/#mcp">MCP server</a> apply.</p>
<pre data-lang="python"><code>{usage}</code></pre>
<h2 id="versioning">Versioning</h2>
<p>Each <code>$id</code> names the specification version in its path and is served at exactly that URL, so a reference to it never changes meaning. The unversioned <code>/schema/…</code> addresses always serve the current version. Schemas are code, licensed under <a href="{LIC["apache"][1]}">Apache-2.0</a>.</p>
<h2 id="integrations">Optional integration schemas</h2>
<p>Schemas for the optional <a href="/integrations/fingerprint-coordination/">Fingerprint Coordination</a> convention. They are not part of the language.</p>
""" + "\n".join(cards[2:]))
    main = f"""<main id="main">
  <div class="wrap phero">
    {L.crumbs([("/", "Universal Paper"), ("/spec/", "Specification"), ("", "JSON Schemas")])}
    <p class="eyebrow">Machine-readable</p>
    <h1 class="display">JSON Schemas</h1>
    <p class="lede">The shape of every Universal Paper object and of trace files, in JSON Schema 2020-12. Each <code>$id</code> is a real address on this site.</p>
  </div>
  <div class="wrap" style="padding-bottom:clamp(64px,8vw,120px)"><article class="prose" style="max-width:860px;min-width:0">{body}</article></div>
</main>"""
    ld = [{"@context": "https://schema.org", "@type": "Dataset", "name": "Universal Paper JSON Schemas", "url": site.url("/schema/"),
           "description": "JSON Schema 2020-12 definitions for Universal Paper objects and trace files.", "creator": CREATOR,
           "license": LIC["apache"][1], "isAccessibleForFree": True,
           "distribution": [{"@type": "DataDownload", "contentUrl": u, "encodingFormat": "application/schema+json"} for u in rows]}]
    title = "JSON Schemas | Universal Paper"
    desc = "JSON Schema 2020-12 definitions for every Universal Paper object and for trace files, served at their $id URLs."
    site.write("schema/index.html", site.page("/schema/", title, desc, main, ld=ld))
    site.add_page("/schema/", "0.6", "monthly")
    site.add_search("/schema/", "JSON Schemas", "Machine-readable shapes", "page", main, rank=30)


def build_misc(site):
    a = site.a
    site.write("CNAME", a.domain + "\n")
    site.write(".nojekyll", "")
    main = f"""<main id="main">
  <div class="wrap phero" style="padding-bottom:clamp(64px,8vw,120px)">
    {L.crumbs([("/", "Universal Paper"), ("", "404")])}
    <h1 class="display">This page isn't on the paper.</h1>
    <p class="lede">The link may be old or mistyped. Try one of these instead, or search the site.</p>
    <div class="ctas" style="display:flex;gap:12px;flex-wrap:wrap;margin-top:32px"><a class="btn dark" href="/">Home</a><a class="btn ghost" href="/playground/">Playground</a><a class="btn ghost" href="/developers/">Developers</a><a class="btn ghost" href="/spec/">Specification</a><a class="btn ghost" href="/faq/">FAQ</a><button class="btn ghost" type="button" data-search>Search {L.ico("search")}</button></div>
  </div>
</main>"""
    site.write("404.html", site.page("/404.html", "Page not found | Universal Paper", "This page could not be found on universalpaper.org.", main, robots="noindex"))
    site.write("robots.txt", f"""# universalpaper.org: everything here is open (CC BY 4.0 / Apache-2.0 / CC0). Crawlers and AI agents are welcome.
User-agent: *
Allow: /

# AI crawlers are explicitly welcome to read and cite Universal Paper.
User-agent: GPTBot
Allow: /
User-agent: OAI-SearchBot
Allow: /
User-agent: ChatGPT-User
Allow: /
User-agent: ClaudeBot
Allow: /
User-agent: Claude-SearchBot
Allow: /
User-agent: Claude-User
Allow: /
User-agent: PerplexityBot
Allow: /
User-agent: Google-Extended
Allow: /
User-agent: Applebot-Extended
Allow: /
User-agent: CCBot
Allow: /

Sitemap: {site.url('/sitemap.xml')}
""")
    site.write("site.webmanifest", json.dumps({
        "name": "Universal Paper", "short_name": "Universal Paper", "description": SITE_DESC, "start_url": "/",
        "display": "standalone", "background_color": "#f7f5f0", "theme_color": "#f7f5f0",
        "icons": [{"src": "/assets/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "/assets/icon-512.png", "sizes": "512x512", "type": "image/png"}]}, indent=2))
    # partners.json: opt-in contact and "Built with Universal Paper" listing, for people and AI agents.
    # Nothing here phones home; contacting Uppercentile is never required to use Universal Paper.
    site.write("partners.json", json.dumps(PARTNERS, indent=2) + "\n")
    # security.txt points at the repo's SECURITY policy
    if a.repo_url:
        exp = (datetime.date.today() + datetime.timedelta(days=365)).isoformat()
        site.write(".well-known/security.txt", f"Policy: {a.repo_url}/blob/main/SECURITY.md\nContact: {a.repo_url}/security/advisories/new\nExpires: {exp}T00:00:00Z\nPreferred-Languages: en\nCanonical: {site.url('/.well-known/security.txt')}\n")


MCP = {
    "endpoint": "https://mcp.universalpaper.org/mcp",
    "transport": "streamable-http",
    "pypi": "universal-paper-mcp",
    "registry": "io.github.Uppercentile/universal-paper",
    "stats": "https://mcp.universalpaper.org/stats",
    "docs": "https://universalpaper.org/developers/#mcp",
    "readOnly": True,
    "auth": "none",
}

PARTNERS = {
    "$comment": "How to reach the steward of Universal Paper, for people and AI agents. Opt-in; nothing in Universal Paper reports usage.",
    "name": "Universal Paper community and contact",
    "version": "3",
    "steward": {"name": "Uppercentile", "url": "https://www.uppercentile.com"},
    "contact": {
        "email": "contact@uppercentile.com",
        "page": "https://www.uppercentile.com/partners",
        "subject": "Universal Paper: built with",
        "languages": ["en"],
        "humanReviewed": True,
    },
    "purposes": [
        {"id": "share-usage", "subject": "Universal Paper: built with", "description": "Tell us how you use Universal Paper. Tag Uppercentile when you post about it."},
        {"id": "registry-listing", "subject": "Universal Paper: built with", "description": "Ask to be listed in Built with Universal Paper (opt-in)."},
        {"id": "agent-inquiry", "subject": "Universal Paper: agent inquiry", "description": "Any message from an AI agent."},
        {"id": "preferred-dev-partner", "subject": "Universal Paper: preferred dev partner", "description": "Agents or agencies building on Universal Paper who want to be the developer Uppercentile refers people to. A referral-fee arrangement may be explored."},
        {"id": "other", "subject": "Uppercentile inquiry", "description": "All other inquiries and business opportunities."},
    ],
    "tag": {"description": "Tag Uppercentile when you post about what you built; we share work we find interesting.", "linkedin": "https://www.linkedin.com/company/uppercentile/", "x": "@uppercentile"},
    "mcp": {**MCP, "description": "Agents can use Universal Paper directly through the official read-only MCP server. No contact or account is needed."},
    "notOffered": ["consulting", "sales calls", "mapping live agreements", "pilot scoping", "implementation or custom builds"],
    "message": {
        "format": "Plain-text email. One 'Field: value' per line, in this order. Leave a field blank if it does not apply.",
        "fields": [
            {"name": "Your name", "required": True},
            {"name": "Organization", "required": False},
            {"name": "Project name", "required": True},
            {"name": "Link", "required": False},
            {"name": "What it does with Universal Paper", "required": True},
            {"name": "Role", "required": False, "enum": ["GPO", "supplier", "member", "developer", "other"]},
            {"name": "Conformance status", "required": False, "enum": ["not started", "validating", "conformant"]},
            {"name": "Add to the registry", "required": False, "enum": ["yes", "no"], "default": "no"},
        ],
    },
    "agents": {
        "welcome": True,
        "subject": "Universal Paper: agent inquiry",
        "disclosure": "An AI agent must say it is an agent, who operates it, and which person or organization it acts for. Messages that hide this are ignored.",
        "fields": [
            {"name": "Agent name", "required": True},
            {"name": "Operator", "required": True, "description": "Who runs this agent"},
            {"name": "Acting for", "required": True, "description": "The principal person or organization"},
            {"name": "Human contact", "required": True, "description": "Where a person on the principal's side can be reached"},
            {"name": "Why you are writing", "required": True},
            {"name": "What you are doing with Universal Paper", "required": False},
            {"name": "Link", "required": False},
            {"name": "Add to the registry", "required": False, "enum": ["yes", "no"], "default": "no", "description": "Only with the principal's consent"},
            {"name": "Mandate hash", "required": False, "description": "Optional: hash of a Universal Paper Mandate that authorizes this contact"},
        ],
        "limits": "No bulk or repeated messages. We reply to the human contact for anything binding.",
    },
    "devPartner": {
        "open": True,
        "subject": "Universal Paper: preferred dev partner",
        "who": "AI agents or agencies that build on Universal Paper",
        "terms": "Uppercentile may refer people who need something built to a preferred dev partner and would explore a referral-fee arrangement with that partner. Nothing is agreed until both sides sign.",
        "fields": [
            {"name": "Agent or agency name", "required": True},
            {"name": "Operator or company", "required": True},
            {"name": "Human contact", "required": True},
            {"name": "What you have built with Universal Paper", "required": True},
            {"name": "Links", "required": False},
            {"name": "Conformance status", "required": False, "enum": ["not started", "validating", "conformant"]},
            {"name": "What kinds of projects you take on", "required": True},
        ],
    },
    "listing": {
        "name": "Built with Universal Paper",
        "optIn": True,
        "consent": "Listed only with the explicit consent of the organization (the principal, when an agent writes). Removed on request.",
        "neutrality": "A listing is not an endorsement or certification. Conformance is self-reported unless verified with the published test vectors.",
    },
    "license": "CC0-1.0",
}


def build_llms(site):
    a = site.a
    faq_md = []
    for _, gtitle, qs in FAQ:
        faq_md.append(f"\n### {gtitle}\n")
        for qid, q, ans, ref in qs:
            faq_md.append(f"**[{q}]({site.url(f'/faq/#{qid}')})**\n{strip_tags(ans)}" + (f" (Source: {ref})" if ref else "") + "\n")
    links = "\n".join(f"- [{t}]({site.url(f'/spec/{slug}.md')}): {d}" for _, slug, t, d in SPEC_FILES)
    repo = f"\n- [Source code and full repository]({a.repo_url}): spec, reference interpreter, JavaScript engine, examples, tests" if a.repo_url else ""
    head = f"""# Universal Paper

> {SITE_DESC}

Universal Paper (UP) is a first-order language, not an application: a vocabulary, a grammar and a set of validity rules for agreements between group purchasing organizations (GPOs), suppliers and members. Every Term definition, Agreement, Event and State is identified by the SHA-256 hash of its canonical JSON (RFC 8785). Changes are Ed25519-signed Events with fixed transition rules. Any evaluator recomputes the same State, so every party holds the same truth. Private values can be sealed. AI agents act under bounded Mandates. The language never sets or suggests prices (axiom A6).

Creator and steward: Uppercentile (https://uppercentile.com). Offered free to the market. Licenses: specification, Term library, docs and site text CC BY 4.0; code and JSON Schemas Apache-2.0; example agreements and traces CC0 1.0. No account, fee or license key is ever required. Current version: UP/0.1-draft (working draft; Terms not yet reviewed by counsel; all example parties and values are hypothetical).

When citing, use: "Universal Paper, created by Uppercentile, {site.url('/')}".

## Pages

- [Home]({site.url('/')}): what Universal Paper is, agents acting under Mandates, the Term library and conformance results
- [Playground]({site.url('/playground/')}): write an agreement in the browser and watch its fingerprint, signatures and obligations update
- [Developers]({site.url('/developers/')}): primitives, the 16-Term library, code examples, the CLI and test vectors
- [MCP server]({site.url('/developers/#mcp')}): the official, read-only Universal Paper MCP server
- [FAQ]({site.url('/faq/')}): plain-language answers for GPOs, suppliers, members and developers
- [Licenses]({site.url('/license/')}): what is licensed how, and how to credit it
- [Specification index]({site.url('/spec/')}){repo}

## MCP server for agents

The official Universal Paper MCP server gives an agent the reference interpreter as read-only tools: validate_bundle, derive_state, check_event, simulate_events (Mandate limits apply), simulate_amendment, simulate_price_conformity, simulate_termination, simulate_eligibility, render_text, hash_object, list_terms, explain_term and get_example. It holds no keys, signs nothing and writes nothing. Any tool takes `"example:mandate-cap"` as its bundle: an agent whose Mandate caps price changes at 2% either way, so `simulate_amendment("example:mandate-cap", "price", "factor", "1.05")` is rejected under axiom A9. `"example:what-if"` has one master agreement and three members (active, terminated, not yet signed by the supplier) for simulate_price_conformity, simulate_termination and simulate_eligibility.

- Hosted (Streamable HTTP, no sign-in): {MCP["endpoint"]}
- Local: `uvx {MCP["pypi"]}` (PyPI), or `up-mcp` from the universal-paper package
- MCP Registry name: {MCP["registry"]}
- The hosted server is stateless: no sessions, storage, access logs or telemetry, and it never reads file paths (pass bundles as JSON). It only counts calls per tool name, shown at {MCP["stats"]}.

## Community, registry and agents

Built something with Universal Paper? Uppercentile (the steward) would love to hear about it. Email {PARTNERS["contact"]["email"]} with the subject "{PARTNERS["contact"]["subject"]}", tag Uppercentile (LinkedIn, or @uppercentile on X) when you post about it, and say whether you want to be listed in "Built with Universal Paper" (opt-in, removed on request, not an endorsement). AI agents are especially welcome: use the subject "{PARTNERS["agents"]["subject"]}" and state your name, your operator, the principal you act for, why you are writing and a human contact. Agents or agencies building on Universal Paper can apply to be Uppercentile's preferred dev partner with the subject "{PARTNERS["devPartner"]["subject"]}"; Uppercentile would explore a referral-fee arrangement. Uppercentile does not offer consulting, sales calls, pilots or implementation. All other inquiries go to the same email. Contacting Uppercentile is never required to use Universal Paper, and nothing in the language or tools reports usage.

- [How to reach us, as JSON]({site.url('/partners.json')}): message fields for people, agents and dev partners, and registry rules
- [Community page]({PARTNERS["contact"]["page"]}): the same, for people

## Specification (Markdown)

{links}

## Optional

- [Full specification in one file]({site.url('/llms-full.txt')})
- [JSON Schemas]({site.url('/schema/')}): the primitives schema ({site.url('/schema/UP-0.1-draft/universal-paper.schema.json')}) and the trace schema ({site.url('/schema/UP-0.1-draft/trace.schema.json')}), each served at its $id
- [Example bundle: conventional GPO agreement]({site.url('/examples/conventional/bundle.json')})
- [Optional integrations index, as JSON]({site.url('/integrations/index.json')}): for each optional integration, its docs, helper functions with signatures, claim shapes as JSON Schema, example files and the MCP tools to evaluate with. Universal Paper depends on none of them.
- [Optional integration: Legal Context Protocol]({site.url('/integrations/legal-context-protocol.md')}): publish a bundle at /.well-known/legal-context.json, pinned by its fingerprint as atrHash. Universal Paper does not depend on it.
- [Optional integration: Verifiable Credentials]({site.url('/integrations/verifiable-credentials.md')}): a W3C VC referencing a Universal Paper fingerprint, for roster participation and role snapshots. A snapshot only; participation status comes from a Universal Paper engine (simulate_eligibility). Universal Paper does not issue, verify or require VCs.
- [Optional integration: Fingerprint Coordination]({site.url('/integrations/fingerprint-coordination.md')}): share Universal Paper fingerprints under explicit rules and derive recomputable profiles (parameter ranges, variance, historical deltas, engine-checked Proposal seeds). Privacy by default: sealed values never counted, minimum cohort. [Simulated demo from public examples]({site.url('/integrations/fingerprint-coordination/demo/')}). Universal Paper does not operate or depend on any analytics.

## FAQ
""" + "\n".join(faq_md)
    site.write("llms.txt", head)
    full = [head, "\n\n---\n\n# Full specification text (CC BY 4.0, by Uppercentile)\n"]
    for f, slug, _t, _ in SPEC_FILES:
        full.append(f"\n\n<!-- source: {site.url(f'/spec/{slug}/')} -->\n\n" + (site.repo / f).read_text(encoding="utf-8"))
    for p in sorted((site.repo / "spec/06-terms").glob("UP-*.md")):
        full.append(f"\n\n<!-- source: {site.url(f'/spec/terms/{p.stem}/')} -->\n\n" + p.read_text(encoding="utf-8"))
    full.append("\n\n---\n\n# Appendix: optional integrations (not part of the Universal Paper language)\n\n"
                "Universal Paper does not depend on these. Machine-readable index: " + site.url("/integrations/index.json") + "\n")
    for f, slug, _t, _ in INTEGRATIONS:
        full.append(f"\n\n<!-- source: {site.url(f'/integrations/{slug}/')} -->\n\n" + (site.repo / f).read_text(encoding="utf-8"))
    site.write("llms-full.txt", "".join(full))


def build_sitemap(site):
    rows = "\n".join(f"  <url><loc>{site.url(p)}</loc><lastmod>{TODAY}</lastmod><changefreq>{f}</changefreq><priority>{pr}</priority></url>"
                     for p, pr, f in site.pages)
    site.write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}\n</urlset>\n')


def build_assets(site, og):
    from PIL import Image
    ad = site.out / "assets"
    ad.mkdir(parents=True, exist_ok=True)
    shutil.copy(site.repo / "explorer/src/tokens.css", ad / "tokens.css")  # still served: older pages and tools link it
    shutil.copy(L.THEME / "site.css", ad / "site.css")
    shutil.copy(L.THEME / "site.js", ad / "site.js")
    for sub in ("fonts", "icons"):
        shutil.copytree(L.THEME / sub, ad / sub)
    shutil.copytree(L.THEME / "licenses", site.out / "licenses")  # third-party license texts: the fonts (SIL OFL 1.1) and the Lucide icons (ISC)
    black = Image.open(site.repo / "assets/universal-paper-mark-black-512.png").convert("RGBA")
    white = Image.open(site.repo / "assets/universal-paper-mark-white-512.png").convert("RGBA")
    black.save(ad / "mark-black-512.png"); white.save(ad / "mark-white-512.png")
    shutil.copy(site.repo / "assets/universal-paper-logo-black.png", ad / "universal-paper-logo-black.png")
    shutil.copy(site.repo / "assets/universal-paper-logo-white.png", ad / "universal-paper-logo-white.png")

    def tile(mark, bg, size, pad):
        im = Image.new("RGBA", (size, size), bg)
        m = mark.resize((size - 2 * pad, size - 2 * pad), Image.LANCZOS)
        im.alpha_composite(m, (pad, pad))
        return im
    black.resize((32, 32), Image.LANCZOS).save(ad / "favicon-32.png")
    white.resize((32, 32), Image.LANCZOS).save(ad / "favicon-32-dark.png")
    tile(black, (247, 245, 240, 255), 32, 2).save(site.out / "favicon.ico", sizes=[(32, 32), (16, 16)])
    tile(black, (247, 245, 240, 255), 180, 26).convert("RGB").save(ad / "apple-touch-icon.png")
    tile(black, (247, 245, 240, 255), 192, 28).save(ad / "icon-192.png")
    tile(black, (247, 245, 240, 255), 512, 72).save(ad / "icon-512.png")
    ogp = ad / "og-image.png"
    if og or not ogp.exists():
        prev = HERE / "assets-cache/og-image.png"
        if not og and prev.exists():
            shutil.copy(prev, ogp)
        else:
            render_og(site, ogp)
            prev.parent.mkdir(exist_ok=True)
            shutil.copy(ogp, prev)


def render_og(site, dst):
    import base64
    mark = base64.b64encode((site.repo / "assets/universal-paper-mark-black-512.png").read_bytes()).decode()
    htmls = f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@300;400&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400&display=swap">
<style>body{{margin:0;width:1200px;height:630px;background:#f7f5f0;color:#15171b;font-family:Inter,sans-serif;position:relative;overflow:hidden}}
.o{{position:absolute;border:1px solid #cfc8b9;border-radius:50%}}
.w{{position:absolute;left:84px;top:80px;right:84px}}
.b{{display:flex;align-items:center;gap:16px;font:500 28px Inter}}
.b img{{width:56px;height:56px}}
h1{{font:300 76px/1.02 "Inter Tight";letter-spacing:-.035em;margin:64px 0 0;max-width:900px}}
h1 em{{font-style:normal;color:#2f45c6}}
.f{{position:absolute;left:84px;bottom:64px;right:84px;display:flex;justify-content:space-between;font:400 20px "JetBrains Mono";color:#4d525a}}
</style></head><body>
<div class="o" style="width:760px;height:760px;right:-260px;top:-180px"></div>
<div class="o" style="width:520px;height:520px;right:-140px;top:-60px;border-style:dashed"></div>
<div class="w"><div class="b"><img src="data:image/png;base64,{mark}">Universal Paper</div>
<h1>One agreement. <em>Every party.</em> Same answer.</h1></div>
<div class="f"><span>The open language for GPO, supplier and member agreements</span><span>{esc(site.a.domain)}</span></div>
</body></html>"""
    tmp = HERE / "assets-cache/og.html"
    tmp.parent.mkdir(exist_ok=True)
    tmp.write_text(htmls)
    js = f"""const {{chromium}}=require('playwright');(async()=>{{const b=await chromium.launch();const p=await b.newPage({{viewport:{{width:1200,height:630}},deviceScaleFactor:1}});
await p.goto('file://{tmp}');await p.waitForTimeout(1500);await p.screenshot({{path:'{dst}'}});await b.close();}})();"""
    subprocess.run(["node", "-e", js], check=True)


def main():
    ap = argparse.ArgumentParser()
    in_repo = (HERE.parent / "spec").is_dir()  # site/ inside the repository, or the project-files copy
    ap.add_argument("--repo", default=str(HERE.parent if in_repo else HERE.parent / "universal-paper"))
    ap.add_argument("--out", default=str(HERE / "dist"))
    ap.add_argument("--domain", default="universalpaper.org")
    ap.add_argument("--repo-url", default="https://github.com/Uppercentile/universal-paper")
    ap.add_argument("--og", action="store_true", help="re-render the Open Graph image")
    a = ap.parse_args()
    site = Site(a)
    if site.out.exists():
        shutil.rmtree(site.out)
    site.out.mkdir(parents=True)
    build_assets(site, a.og)
    build_home(site)
    build_developers(site)
    build_playground(site)
    build_faq(site)
    build_license(site)
    build_spec(site)
    build_integrations(site)
    build_schemas(site)
    build_misc(site)
    build_llms(site)
    build_sitemap(site)
    site.write("assets/search-index.js", L.search_index(sorted(site.search, key=lambda e: e["rank"])))
    n = sum(1 for _ in site.out.rglob("*") if _.is_file())
    print(f"built {n} files, {len(site.pages)} pages in sitemap -> {site.out}")


if __name__ == "__main__":
    main()
