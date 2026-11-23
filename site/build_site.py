#!/usr/bin/env python3
"""Build the public website for Universal Paper (universalpaper.org).

Inputs (read only, never edited):
  REPO/explorer/index.html           -> /            (Playground page, the home page)
  EXPLAINER                          -> /developers/ (developer explainer)
  REPO/spec/**/*.md, DESIGN_NOTES.md -> /spec/...    (rendered pages plus the raw .md)
  REPO/schema/*.json, spec/06-terms/*.json, examples/*/bundle.json (copied as is)
  content/faq.py                     -> /faq/ and the FAQ parts of llms.txt

Output: dist/ (a static site for GitHub Pages: CNAME, .nojekyll, sitemap.xml, robots.txt,
llms.txt, llms-full.txt, 404.html, og image, favicons).

  python3 build_site.py [--repo PATH] [--explainer PATH] [--out dist] [--domain universalpaper.org]
                        [--repo-url https://github.com/Uppercentile/universal-paper] [--og]
"""
import argparse
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
from faq import SECTIONS as FAQ  # noqa: E402

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


class Site:
    def __init__(self, a):
        self.a = a
        self.base = "https://" + a.domain
        self.out = Path(a.out)
        self.repo = Path(a.repo)
        self.pages = []  # (path, priority, changefreq)

    def url(self, path):
        return self.base + path

    def write(self, rel, text):
        p = self.out / rel.lstrip("/")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def add_page(self, path, prio="0.6", freq="monthly"):
        self.pages.append((path, prio, freq))

    # ---- <head> pieces shared by every page
    def head_meta(self, path, title, desc, kind="website", extra_ld=(), robots="index,follow"):
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
            '<meta name="theme-color" content="#f7f5f0" media="(prefers-color-scheme: light)">',
            '<meta name="theme-color" content="#0f1114" media="(prefers-color-scheme: dark)">',
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
            '<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png" media="(prefers-color-scheme: light)">',
            '<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32-dark.png" media="(prefers-color-scheme: dark)">',
            '<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">',
            '<link rel="manifest" href="/site.webmanifest">',
            '<link rel="alternate" type="text/plain" title="LLM summary" href="/llms.txt">',
            '<link rel="sitemap" type="application/xml" href="/sitemap.xml">',
        ]
        if crumbs:
            lines.append(jsonld(crumbs))
        for o in extra_ld:
            lines.append(jsonld(o))
        return "\n".join(lines)

    # ---- the legal strip appended inside every page footer
    def legal_strip(self):
        r = self.a.repo_url
        gh = f'<a href="{r}">GitHub</a>' if r else ""
        links = " · ".join(x for x in [
            '<a href="/">Home</a>', '<a href="/developers/">Developers</a>', '<a href="/#playground">Playground</a>',
            '<a href="/spec/">Specification</a>', '<a href="/faq/">FAQ</a>', '<a href="/license/">Licenses</a>', gh] if x)
        return (
            '<div class="up-legal"><style>'
            '.up-legal{max-width:1180px;margin:0 auto;padding:20px max(16px,env(safe-area-inset-left)) 28px;font:400 .8125rem/1.6 Inter,system-ui,sans-serif;'
            'color:inherit;opacity:.85;border-top:1px solid color-mix(in srgb,currentColor 14%,transparent);display:grid;gap:6px}'
            '.up-legal a{color:inherit;text-decoration:underline;text-underline-offset:3px;text-decoration-color:color-mix(in srgb,currentColor 35%,transparent)}'
            '.up-legal a:hover{text-decoration-color:currentColor}.up-legal p{margin:0;max-width:none}'
            '</style>'
            f'<p><b>Created by <a href="https://uppercentile.com">Uppercentile</a>, free for everyone.</b> '
            f'Specification and docs <a href="{LIC["ccby"][1]}" rel="license">CC BY 4.0</a> · '
            f'code <a href="{LIC["apache"][1]}" rel="license">Apache-2.0</a> · '
            f'example agreements and traces <a href="{LIC["cc0"][1]}" rel="license">CC0 1.0</a>. '
            'No account, fee or license key is ever required. <a href="/license/">How to use and credit it</a>.</p>'
            f'<p>{links}</p></div>'
        )


# ----------------------------------------------------------------------------- transforms of existing pages
def rewrite_links(s, explorer_id="KnNSYjBF3HMQ5n8CzSboiw", explainer_id="HuTsuqeW18WiuMHVq9Cd39"):
    """Replace private claude.ai artifact links with site paths and drop new-tab targets on them."""
    def fix(m):
        tag = m.group(0)
        tag = re.sub(r'https://claude\.ai/artifact/' + explorer_id + r'(#[\w-]+)?', lambda k: "/" + (k.group(1) or ""), tag)
        tag = re.sub(r'https://claude\.ai/artifact/' + explainer_id + r'(#[\w-]+)?', lambda k: "/developers/" + (k.group(1) or ""), tag)
        tag = tag.replace(' target="_blank"', "").replace(' rel="noopener"', "")
        return tag
    s = re.sub(r'<a\b[^>]*claude\.ai/artifact/[^>]*>', fix, s)
    s = s.replace("Playground ↗", "Playground")
    # script strings such as open("https://claude.ai/artifact/…", "_blank", "noopener")
    s = re.sub(r'open\("https://claude\.ai/artifact/' + explorer_id + r'(#[\w-]+)?", "_blank", "noopener"\)',
               lambda k: 'location.assign("/' + (k.group(1) or "#playground") + '")', s)
    s = re.sub(r'open\("https://claude\.ai/artifact/' + explainer_id + r'(#[\w-]+)?", "_blank", "noopener"\)',
               lambda k: 'location.assign("/developers/' + (k.group(1) or "") + '")', s)
    s = re.sub(r'https://claude\.ai/artifact/' + explorer_id, "/", s)
    s = re.sub(r'https://claude\.ai/artifact/' + explainer_id, "/developers/", s)
    left = re.findall(r'claude\.ai/(?:code/)?artifact/[\w-]+', s)
    if left:
        print("warning: artifact links left:", sorted(set(left)), file=sys.stderr)
    return s


def set_head(s, title, meta):
    s = re.sub(r'<meta name="claude:[^"]*"[^>]*>\n?', "", s)
    s = re.sub(r'<meta name="description"[^>]*>\n?', "", s)
    s = re.sub(r"<title>.*?</title>", f"<title>{esc(title)}</title>\n{meta}", s, count=1, flags=re.S)
    return s


def add_nav(s, items):
    """Add links before the first </nav> unless they are already present."""
    extra = "".join(f'\n      <a href="{h}">{t}</a>' for h, t in items if f'href="{h}"' not in s.split("</nav>", 1)[0])
    return s.replace("</nav>", extra + "\n    </nav>", 1)


def add_legal(s, strip):
    i = s.rfind("</footer>")
    if i < 0:
        return s.replace("</body>", strip + "</body>") if "</body>" in s else s + strip
    return s[:i] + strip + s[i:]


def build_home(site):
    src = (site.repo / "explorer/index.html").read_text(encoding="utf-8")
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
        {"@context": "https://schema.org", "@type": "WebApplication", "name": "Universal Paper Playground", "url": site.url("/#playground"),
         "applicationCategory": "DeveloperApplication", "operatingSystem": "Any (web browser)", "isAccessibleForFree": True,
         "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}, "creator": CREATOR, "license": LIC["apache"][1],
         "description": "Write a Universal Paper agreement in the browser and watch its fingerprint, signatures, rendering and obligations update live."},
    ]
    s = set_head(src, title, site.head_meta("/", title, desc, extra_ld=ld))
    s = rewrite_links(s)
    s = add_nav(s, [("/developers/", "Developers"), ("/faq/", "FAQ")])
    s = add_legal(s, site.legal_strip())
    site.write("index.html", s)
    site.add_page("/", "1.0", "weekly")


def build_developers(site, path):
    src = Path(path).read_text(encoding="utf-8")
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
    s = set_head(src, title, site.head_meta("/developers/", title, desc, kind="article", extra_ld=ld))
    if not s.lstrip().lower().startswith("<!doctype"):
        s = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
             '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n' + s)
        s = s.replace('<header class="site-header', '</head>\n<body>\n<header class="site-header', 1)
        s = s.rstrip() + "\n</body>\n</html>\n"
    s = rewrite_links(s)
    s = add_nav(s, [("/faq/", "FAQ")])
    # footer spec paths -> real pages
    for f, slug, *_ in SPEC_FILES:
        s = s.replace(f'<li class="mono">{f}</li>', f'<li class="mono"><a href="/spec/{slug}/">{f}</a></li>')
    s = s.replace('<li><a href="#faq">FAQ</a></li>', '<li><a href="#faq">FAQ</a></li><li><a href="/faq/">All questions</a></li><li><a href="/license/">Licenses</a></li>')
    s = add_legal(s, site.legal_strip())
    site.write("developers/index.html", s)
    site.add_page("/developers/", "0.9", "weekly")


# ----------------------------------------------------------------------------- new pages
PAGE_CSS = """
.page-hero{padding:clamp(48px,8vw,104px) 0 clamp(32px,5vw,56px)}
.page-hero .lead{margin-top:20px}
.crumbs{font:500 var(--t-eyebrow)/1 var(--f-mono);text-transform:uppercase;letter-spacing:.12em;color:var(--ink-3);margin-bottom:20px}
.crumbs a{color:var(--ink-3);text-decoration:none}.crumbs a:hover{color:var(--ink)}
.prose{max-width:76ch}
.prose h1{font:300 var(--t-h2)/1.08 var(--f-display);letter-spacing:-.03em;margin:0 0 24px}
.prose h2{font:400 1.6rem/1.2 var(--f-display);letter-spacing:-.02em;margin:56px 0 12px;scroll-margin-top:calc(var(--header-h) + 16px)}
.prose h3{font:600 1.1rem/1.3 var(--f-body);margin:36px 0 8px;scroll-margin-top:calc(var(--header-h) + 16px)}
.prose h4{font:600 1rem/1.3 var(--f-body);margin:28px 0 6px}
.prose p,.prose li{color:var(--ink-2)}.prose strong{color:var(--ink)}
.prose code{font:400 .86em/1.4 var(--f-mono);background:var(--bg-2);border:1px solid var(--rule);border-radius:4px;padding:1px 5px}
.prose pre{background:var(--surface);border:1px solid var(--rule);border-radius:var(--r-2);padding:16px;overflow:auto;font:400 .84rem/1.55 var(--f-mono)}
.prose pre code{background:none;border:0;padding:0}
.prose blockquote{margin:20px 0;padding:4px 0 4px 18px;border-left:2px solid var(--accent);color:var(--ink-2)}
.tablewrap{overflow-x:auto;margin:20px 0;border:1px solid var(--rule);border-radius:var(--r-2);background:var(--surface)}
.prose table{border-collapse:collapse;width:100%;font-size:.9rem}
.prose th,.prose td{text-align:left;vertical-align:top;padding:10px 14px;border-bottom:1px solid var(--rule)}
.prose th{font:500 .75rem/1.4 var(--f-mono);text-transform:uppercase;letter-spacing:.08em;color:var(--ink-3);background:var(--bg-2)}
.prose tr:last-child td{border-bottom:0}
.layout{display:grid;grid-template-columns:220px minmax(0,1fr);gap:56px;padding-bottom:96px}
.side{position:sticky;top:calc(var(--header-h) + 24px);align-self:start;font-size:.875rem;display:grid;gap:4px}
.side b{font:500 var(--t-eyebrow)/1 var(--f-mono);text-transform:uppercase;letter-spacing:.12em;color:var(--ink-3);margin:0 0 10px}
.side a{color:var(--ink-2);text-decoration:none;padding:5px 10px;border-radius:6px}
.side a:hover{color:var(--ink);background:var(--bg-2)}.side a[aria-current="page"]{color:var(--ink);background:var(--bg-2);font-weight:500}
@media (max-width:860px){.layout{grid-template-columns:1fr;gap:24px}.side{position:static;display:flex;flex-wrap:wrap;gap:6px}.side b{width:100%}.side a{border:1px solid var(--rule)}}
.faq-group{margin-top:48px}.faq-group h2{margin-top:0}
.faq details{border-top:1px solid var(--rule);padding:4px 0}.faq details:last-child{border-bottom:1px solid var(--rule)}
.faq summary{cursor:pointer;list-style:none;display:flex;justify-content:space-between;gap:16px;padding:16px 0;font:500 1.05rem/1.4 var(--f-body);color:var(--ink)}
.faq summary::-webkit-details-marker{display:none}
.faq summary::after{content:"+";font:300 1.4rem/1 var(--f-display);color:var(--ink-3);transition:transform var(--d-fast) var(--ease)}
.faq details[open] summary::after{transform:rotate(45deg)}
.faq .a{padding:0 0 18px}.faq .a p{margin:0 0 8px}.faq .ref{font:400 .78rem/1.5 var(--f-mono);color:var(--ink-3)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;margin:28px 0}
.card{background:var(--surface);border:1px solid var(--rule);border-radius:var(--r-3);padding:24px;display:grid;gap:10px;align-content:start}
.card h3{margin:0;font:600 1.05rem/1.3 var(--f-body)}.card p{margin:0;color:var(--ink-2);font-size:.93rem}
.card .lic{font:500 .8rem/1 var(--f-mono);color:var(--accent)}
.card ul{margin:0;padding-left:18px;color:var(--ink-2);font-size:.9rem}
.attr{background:var(--surface);border:1px solid var(--rule);border-radius:var(--r-2);padding:16px;font:400 .86rem/1.6 var(--f-mono);color:var(--ink)}
.site-footer2{border-top:1px solid var(--rule);background:var(--bg-2);color:var(--ink-2)}
.site-footer2 .row{display:flex;flex-wrap:wrap;gap:12px 28px;align-items:center;padding-top:28px}
.site-footer2 .brand{color:var(--ink)}
.navr{display:flex;align-items:center;gap:12px}
"""

THEME_JS = """<script>(function(){var k="up-theme",r=document.documentElement;function g(){try{return localStorage.getItem(k)||"system"}catch(e){return"system"}}
function a(m){if(m==="system")r.removeAttribute("data-theme");else r.setAttribute("data-theme",m);var b=document.getElementById("themeBtn");if(b)b.setAttribute("aria-label","Color theme: "+m)}
a(g());document.addEventListener("DOMContentLoaded",function(){a(g());var b=document.getElementById("themeBtn");if(b)b.onclick=function(){var o=["system","light","dark"],n=o[(o.indexOf(g())+1)%3];try{localStorage.setItem(k,n)}catch(e){}a(n)}})})();</script>"""


def shell(site, path, title, desc, body, kind="website", ld=(), current=""):
    nav = [("/", "Home"), ("/developers/", "Developers"), ("/#playground", "Playground"), ("/spec/", "Specification"), ("/faq/", "FAQ")]
    cur_attr = ' aria-current="true"'
    navh = "".join(f'<a href="{h}"{cur_attr if h == current else ""}>{t}</a>' for h, t in nav)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
{site.head_meta(path, title, desc, kind=kind, extra_ld=ld)}
{THEME_JS}
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@300;400;500&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="/assets/tokens.css">
<style>:root{{--logo:url(/assets/mark-black-512.png)}}{PAGE_CSS}</style>
</head>
<body>
<a href="#main" style="position:absolute;left:-999px" onfocus="this.style.left='8px'" onblur="this.style.left='-999px'">Skip to content</a>
<header class="site-header">
  <div class="wrap">
    <a class="brand" href="/" aria-label="Universal Paper home"><span class="brand-mark" aria-hidden="true"></span>Universal Paper</a>
    <nav class="site-nav" aria-label="Site">{navh}</nav>
    <div class="navr">
      <button class="theme-toggle" id="themeBtn" type="button" aria-label="Color theme: system"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 0 0 0 16z" fill="currentColor"/></svg></button>
      <a class="btn primary" href="/#playground">Open the Playground</a>
    </div>
  </div>
</header>
<main id="main">
{body}
</main>
<footer class="site-footer2">
  <div class="wrap row"><a class="brand" href="/"><span class="brand-mark" aria-hidden="true"></span>Universal Paper</a><span>{esc(TAGLINE)}.</span></div>
  {site.legal_strip()}
</footer>
</body>
</html>
"""


def build_faq(site):
    groups, ld_q, side = [], [], []
    for gid, gtitle, qs in FAQ:
        side.append(f'<a href="#{gid}">{esc(gtitle)}</a>')
        items = []
        for q, a, ref in qs:
            qid = re.sub(r"[^a-z0-9]+", "-", q.lower()).strip("-")[:60]
            refh = f'<p class="ref">{esc(ref)}</p>' if ref else ""
            items.append(f'<details id="{qid}"><summary><h3 style="all:unset">{esc(q)}</h3></summary><div class="a">{a}{refh}</div></details>')
            ld_q.append({"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": strip_tags(a)}})
        groups.append(f'<section class="faq-group" id="{gid}" aria-labelledby="{gid}-h"><h2 id="{gid}-h">{esc(gtitle)}</h2><div class="faq">{"".join(items)}</div></section>')
    n = sum(len(g[2]) for g in FAQ)
    body = f"""<div class="wrap page-hero">
  <div class="crumbs"><a href="/">Universal Paper</a> / FAQ</div>
  <h1 class="display">Questions, answered plainly.</h1>
  <p class="lead">{n} answers about what Universal Paper is, how it works, what it means for GPOs, suppliers and members, and how it's licensed. Each answer points to the part of the specification it comes from.</p>
</div>
<div class="wrap layout">
  <nav class="side" aria-label="FAQ sections"><b>Sections</b>{"".join(side)}<a href="/license/">Licenses</a><a href="/spec/">Specification</a></nav>
  <div class="prose" style="max-width:none">{"".join(groups)}</div>
</div>
<script>document.addEventListener("DOMContentLoaded",function(){{var h=location.hash.slice(1),d=h&&document.getElementById(h);if(d&&d.tagName==="DETAILS")d.open=true}});</script>"""
    title = "Universal Paper FAQ | GPO, supplier and member agreements explained"
    desc = ("Answers about Universal Paper: what the open agreement language is, who created it (Uppercentile), how hashes and signatures work, "
            "confidential pricing, AI agents, EDI, legal status, and its free CC BY 4.0 and Apache-2.0 licenses.")
    ld = [{"@context": "https://schema.org", "@type": "FAQPage", "url": site.url("/faq/"), "inLanguage": "en", "mainEntity": ld_q}]
    site.write("faq/index.html", shell(site, "/faq/", title, desc, body, ld=ld, current="/faq/"))
    site.add_page("/faq/", "0.9", "monthly")


def build_license(site):
    r = site.a.repo_url
    repo_line = f' The full license texts ship with the source in <a href="{r}">the repository</a>.' if r else ""
    body = f"""<div class="wrap page-hero">
  <div class="crumbs"><a href="/">Universal Paper</a> / Licenses</div>
  <h1 class="display">Open by design. Free for everyone.</h1>
  <p class="lead">Universal Paper was created by <a href="https://uppercentile.com">Uppercentile</a>. Uppercentile offers it to the market for free, under open licenses that let anyone use, implement, extend, fork and sell products built on it, without permission or payment.</p>
</div>
<div class="wrap prose" style="max-width:var(--maxw);padding-bottom:96px">
  <div class="cards">
    <div class="card"><span class="lic">CC BY 4.0</span><h3>Specification and documentation</h3><p>The language itself: the specification, the Term library (prose and JSON definitions), the design notes, the mapping guide, the neutrality charter and the text of this website.</p><p><a href="{LIC['ccby'][1]}" rel="license">Creative Commons Attribution 4.0 International</a></p></div>
    <div class="card"><span class="lic">Apache-2.0</span><h3>Code and schemas</h3><p>The Python reference interpreter and <code>up</code> CLI, the JavaScript engine, the Playground page, the JSON Schemas, build tools, tests and test vectors. Includes an express patent license from every contributor.</p><p><a href="{LIC['apache'][1]}" rel="license">Apache License, Version 2.0</a></p></div>
    <div class="card"><span class="lic">CC0 1.0</span><h3>Example agreements and traces</h3><p>The example agreements, bundles and traces in <code>examples/</code> are dedicated to the public domain, so any implementation, product or test suite can copy them freely, with no conditions.</p><p><a href="{LIC['cc0'][1]}" rel="license">CC0 1.0 Universal</a></p></div>
  </div>

  <h2 id="what-you-can-do">What you can do</h2>
  <ul>
    <li>Use Universal Paper for any agreement, commercial or not, at no cost.</li>
    <li>Write your own implementation, in any language, open or closed source.</li>
    <li>Build and sell products, services and agents that read, write or verify Universal Paper.</li>
    <li>Copy, translate, adapt and redistribute the specification and the code.</li>
  </ul>
  <p>Using the language never requires an account, a fee, a license key or a connection to Uppercentile or anyone else. The <a href="/spec/neutrality-charter/">neutrality charter</a> forbids the core from ever requiring one.</p>

  <h2 id="what-the-licenses-ask">What the licenses ask in return</h2>
  <ul>
    <li><strong>CC BY 4.0:</strong> give credit, link to the license, and say if you made changes. You may not suggest that Uppercentile endorses your version.</li>
    <li><strong>Apache-2.0:</strong> keep the license and the NOTICE file with copies of the code, and mark files you changed.</li>
    <li><strong>CC0 1.0:</strong> nothing at all.</li>
  </ul>

  <h2 id="how-to-credit">How to credit Universal Paper</h2>
  <p>A line like this satisfies CC BY 4.0 for the specification or the Term library:</p>
  <div class="attr">"Universal Paper" specification by Uppercentile, https://{esc(site.a.domain)}, licensed under CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Changes: [describe, or "none"].</div>
  <p>For the code, keep the <code>LICENSE</code> and <code>NOTICE</code> files.{repo_line}</p>

  <h2 id="contributions">Contributions</h2>
  <p>Contributions are accepted under the same licenses: changes to the specification under CC BY 4.0, changes to code under Apache-2.0, and new example agreements and traces under CC0 1.0. Contributors keep their copyright and license their work to everyone on the same terms.</p>

  <h2 id="stewardship">Stewardship, not ownership</h2>
  <p>Uppercentile created Universal Paper and is its current steward. The steward maintains the specification for everyone who uses it and does not own the language. Products built on Universal Paper, including any Uppercentile offers, are separate from it and may not claim to be required. The steward has committed to hand stewardship to a neutral body once the language has users across segments. See the <a href="/spec/neutrality-charter/">neutrality charter</a>.</p>

  <h2 id="third-party">Third-party material</h2>
  <ul>
    <li>Web fonts Inter, Inter Tight, JetBrains Mono and Source Serif 4 are served by Google Fonts under the SIL Open Font License 1.1.</li>
    <li>Standards the language references (RFC 8785, RFC 8032, RFC 3339, ISO 4217, GS1, HIBCC, NDC and ASC X12) belong to their publishers. Universal Paper reuses their identifiers and does not redistribute their documents.</li>
    <li>The Python reference interpreter depends on the <code>cryptography</code> package (Apache-2.0 or BSD). The JavaScript engine has no dependencies.</li>
  </ul>
  <p style="margin-top:40px;font-size:.85rem;color:var(--ink-3)">This page summarizes the licenses for convenience. The license texts themselves govern. Nothing here is legal advice.</p>
</div>"""
    title = "Licenses | Universal Paper is free and open (CC BY 4.0, Apache-2.0, CC0)"
    desc = ("Universal Paper was created by Uppercentile and is offered free to everyone: specification under CC BY 4.0, code under Apache-2.0, "
            "example agreements under CC0. How to use it, credit it and contribute.")
    site.write("license/index.html", shell(site, "/license/", title, desc, body))
    site.add_page("/license/", "0.7", "yearly")


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


def build_spec(site):
    lmap = spec_link_map(site)
    side_items = [(f"/spec/{slug}/", t) for _, slug, t, _ in SPEC_FILES]
    # copy machine-readable files
    for p in (site.repo / "spec/06-terms").glob("UP-*.json"):
        dst = site.out / "spec/terms" / p.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(p, dst)
    for p in (site.repo / "schema").glob("*.json"):
        (site.out / "schema").mkdir(parents=True, exist_ok=True)
        shutil.copy(p, site.out / "schema" / p.name)
    for d in ("conventional", "generative", "overlay", "confidential"):
        for p in (site.repo / "examples" / d).glob("*"):
            if p.suffix in (".json", ".txt"):
                (site.out / "examples" / d).mkdir(parents=True, exist_ok=True)
                shutil.copy(p, site.out / "examples" / d / p.name)

    def page(src_file, path, ttl, desc, cur):
        text = (site.repo / src_file).read_text(encoding="utf-8")
        h, _ = render_md(site, src_file, text, lmap)
        raw = path.rstrip("/") + ".md"
        site.write(raw, text)
        page_attr = ' aria-current="page"'
        side = "".join(f'<a href="{u}"{page_attr if u == cur else ""}>{esc(t)}</a>' for u, t in side_items)
        edit = f' · <a href="{site.a.repo_url}/blob/main/{src_file}">View source</a>' if site.a.repo_url else ""
        body = f"""<div class="wrap" style="padding-top:40px"><div class="crumbs"><a href="/">Universal Paper</a> / <a href="/spec/">Specification</a> / {esc(ttl)}</div></div>
<div class="wrap layout">
  <nav class="side" aria-label="Specification"><b>UP/0.1-draft</b>{side}</nav>
  <article class="prose">{h}
  <p style="margin-top:56px;font-size:.85rem;color:var(--ink-3)">Specification text by Uppercentile, licensed under <a href="/license/">CC BY 4.0</a>. Working draft UP/0.1-draft. <a href="{esc(raw)}">Plain Markdown</a>{edit}</p></article>
</div>"""
        title = f"{ttl} | Universal Paper specification"
        ld = [{"@context": "https://schema.org", "@type": "TechArticle", "headline": f"Universal Paper specification: {ttl}",
               "url": site.url(path), "description": desc, "author": CREATOR, "publisher": CREATOR, "license": LIC["ccby"][1],
               "isPartOf": {"@id": site.url("/spec/#spec")}, "version": "UP/0.1-draft", "inLanguage": "en", "dateModified": TODAY,
               "encoding": {"@type": "MediaObject", "contentUrl": site.url(raw), "encodingFormat": "text/markdown"}}]
        site.write(path.lstrip("/") + "index.html", shell(site, path, title, desc, body, kind="article", ld=ld, current="/spec/"))
        site.add_page(path, "0.7", "monthly")

    for f, slug, ttl, desc in SPEC_FILES:
        page(f, f"/spec/{slug}/", ttl, desc, f"/spec/{slug}/")
    for p in sorted((site.repo / "spec/06-terms").glob("UP-*.md")):
        j = json.loads((site.repo / "spec/06-terms" / (p.stem + ".json")).read_text())
        tid = j.get("id", p.stem.replace("UP-", "UP:"))
        ttl = f"{tid} ({j.get('title', '')})" if j.get("title") else tid
        desc = f"The {tid} Term of the Universal Paper library: {j.get('title', '').lower() or 'definition'}, its typed parameters, clauses and human-readable rendering. Value-neutral, free under CC BY 4.0."
        page(f"spec/06-terms/{p.name}", f"/spec/terms/{p.stem}/", ttl, desc, "/spec/terms/")

    # /spec/ index
    cards = "".join(f'<a class="card" href="/spec/{slug}/" style="text-decoration:none"><span class="lic">{esc(f.split("/")[-1] if "06-terms" not in f else "spec/06-terms/")}</span><h3 style="color:var(--ink)">{esc(t)}</h3><p>{esc(d)}</p></a>' for f, slug, t, d in SPEC_FILES)
    body = f"""<div class="wrap page-hero">
  <div class="crumbs"><a href="/">Universal Paper</a> / Specification</div>
  <h1 class="display">The specification.</h1>
  <p class="lead">Universal Paper is defined by this document, not by any software. A person with the specification, a SHA-256 implementation and an Ed25519 verifier can check any agreement by hand. Current version: <code>UP/0.1-draft</code>, a working draft.</p>
  <p style="margin-top:20px"><a class="btn primary" href="/spec/overview/">Start with the overview</a> <a class="btn" href="/llms-full.txt">Full text for AI tools</a></p>
</div>
<div class="wrap prose" style="max-width:var(--maxw);padding-bottom:96px"><div class="cards">{cards}</div>
<h2 id="machine-readable">Machine-readable files</h2>
<ul><li>JSON Schemas: <a href="/schema/universal-paper.schema.json">universal-paper.schema.json</a>, <a href="/schema/trace.schema.json">trace.schema.json</a> (Apache-2.0)</li>
<li>Term definitions as JSON: <code>/spec/terms/UP-*.json</code>, for example <a href="/spec/terms/UP-Admin-Fee.json">UP-Admin-Fee.json</a> (CC BY 4.0)</li>
<li>Example bundles: <a href="/examples/conventional/bundle.json">conventional</a>, <a href="/examples/generative/bundle.json">generative</a>, <a href="/examples/overlay/bundle.json">overlay</a>, <a href="/examples/confidential/bundle.json">confidential</a> (CC0 1.0)</li>
<li>Every page is also available as Markdown: add <code>.md</code> to its path, for example <a href="/spec/axioms.md">/spec/axioms.md</a></li></ul>
<p style="font-size:.85rem;color:var(--ink-3)">Specification by Uppercentile, licensed under <a href="/license/">CC BY 4.0</a>.</p></div>"""
    title = "Universal Paper specification | UP/0.1-draft"
    desc = ("Read the Universal Paper specification: domain, axioms, inference, lifecycle, the 16-Term library, the EDI mapping guide and the neutrality charter. "
            "Free under CC BY 4.0.")
    ld = [{"@context": "https://schema.org", "@type": "CreativeWork", "@id": site.url("/spec/#spec"), "name": "Universal Paper specification",
           "version": "UP/0.1-draft", "creativeWorkStatus": "Draft", "url": site.url("/spec/"), "creator": CREATOR,
           "license": LIC["ccby"][1], "isAccessibleForFree": True, "description": desc,
           "hasPart": [{"@type": "TechArticle", "name": t, "url": site.url(f"/spec/{slug}/")} for _, slug, t, _ in SPEC_FILES]}]
    site.write("spec/index.html", shell(site, "/spec/", title, desc, body, ld=ld, current="/spec/"))
    site.add_page("/spec/", "0.8", "monthly")


# ----------------------------------------------------------------------------- misc files
def build_misc(site):
    a = site.a
    site.write("CNAME", a.domain + "\n")
    site.write(".nojekyll", "")
    # /playground/ -> /#playground
    site.write("playground/index.html", f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Universal Paper Playground</title>
<link rel="canonical" href="{site.url('/')}"><meta name="robots" content="noindex,follow">
<meta http-equiv="refresh" content="0; url=/#playground"><script>location.replace("/#playground")</script></head>
<body><p><a href="/#playground">Open the Universal Paper Playground</a></p></body></html>
""")
    body = """<div class="wrap page-hero"><div class="crumbs"><a href="/">Universal Paper</a> / 404</div>
<h1 class="display">This page isn't on the paper.</h1><p class="lead">The link may be old or mistyped. Try one of these instead.</p>
<p style="margin-top:24px;display:flex;gap:12px;flex-wrap:wrap"><a class="btn primary" href="/">Home</a><a class="btn" href="/#playground">Playground</a><a class="btn" href="/developers/">Developers</a><a class="btn" href="/spec/">Specification</a><a class="btn" href="/faq/">FAQ</a></p></div>"""
    site.write("404.html", shell(site, "/404.html", "Page not found | Universal Paper", "This page could not be found on universalpaper.org.", body).replace('content="index,follow"', 'content="noindex"'))
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


PARTNERS = {
    "$comment": "How to reach the steward of Universal Paper, for people and AI agents. Opt-in; nothing in Universal Paper reports usage.",
    "name": "Universal Paper community and contact",
    "version": "2",
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
        for q, ans, ref in qs:
            faq_md.append(f"**{q}**\n{strip_tags(ans)}" + (f" (Source: {ref})" if ref else "") + "\n")
    links = "\n".join(f"- [{t}]({site.url(f'/spec/{slug}.md')}): {d}" for _, slug, t, d in SPEC_FILES)
    repo = f"\n- [Source code and full repository]({a.repo_url}): spec, reference interpreter, JavaScript engine, examples, tests" if a.repo_url else ""
    head = f"""# Universal Paper

> {SITE_DESC}

Universal Paper (UP) is a first-order language, not an application: a vocabulary, a grammar and a set of validity rules for agreements between group purchasing organizations (GPOs), suppliers and members. Every Term definition, Agreement, Event and State is identified by the SHA-256 hash of its canonical JSON (RFC 8785). Changes are Ed25519-signed Events with fixed transition rules. Any evaluator recomputes the same State, so every party holds the same truth. Private values can be sealed. AI agents act under bounded Mandates. The language never sets or suggests prices (axiom A6).

Creator and steward: Uppercentile (https://uppercentile.com). Offered free to the market. Licenses: specification, Term library, docs and site text CC BY 4.0; code and JSON Schemas Apache-2.0; example agreements and traces CC0 1.0. No account, fee or license key is ever required. Current version: UP/0.1-draft (working draft; Terms not yet reviewed by counsel; all example parties and values are hypothetical).

When citing, use: "Universal Paper, created by Uppercentile, {site.url('/')}".

## Pages

- [Home and Playground]({site.url('/')}): what Universal Paper is, a vision of apps and agents built on it, an in-browser Playground, and conformance results
- [Developers]({site.url('/developers/')}): primitives, the 16-Term library, code examples, the CLI and test vectors
- [FAQ]({site.url('/faq/')}): plain-language answers for GPOs, suppliers, members and developers
- [Licenses]({site.url('/license/')}): what is licensed how, and how to credit it
- [Specification index]({site.url('/spec/')}){repo}

## Community, registry and agents

Built something with Universal Paper? Uppercentile (the steward) would love to hear about it. Email {PARTNERS["contact"]["email"]} with the subject "{PARTNERS["contact"]["subject"]}", tag Uppercentile (LinkedIn, or @uppercentile on X) when you post about it, and say whether you want to be listed in "Built with Universal Paper" (opt-in, removed on request, not an endorsement). AI agents are especially welcome: use the subject "{PARTNERS["agents"]["subject"]}" and state your name, your operator, the principal you act for, why you are writing and a human contact. Agents or agencies building on Universal Paper can apply to be Uppercentile's preferred dev partner with the subject "{PARTNERS["devPartner"]["subject"]}"; Uppercentile would explore a referral-fee arrangement. Uppercentile does not offer consulting, sales calls, pilots or implementation. All other inquiries go to the same email. Contacting Uppercentile is never required to use Universal Paper, and nothing in the language or tools reports usage.

- [How to reach us, as JSON]({site.url('/partners.json')}): message fields for people, agents and dev partners, and registry rules
- [Community page]({PARTNERS["contact"]["page"]}): the same, for people

## Specification (Markdown)

{links}

## Optional

- [Full specification in one file]({site.url('/llms-full.txt')})
- [JSON Schema]({site.url('/schema/universal-paper.schema.json')})
- [Example bundle: conventional GPO agreement]({site.url('/examples/conventional/bundle.json')})

## FAQ
""" + "\n".join(faq_md)
    site.write("llms.txt", head)
    full = [head, "\n\n---\n\n# Full specification text (CC BY 4.0, by Uppercentile)\n"]
    for f, slug, _t, _ in SPEC_FILES:
        full.append(f"\n\n<!-- source: {site.url(f'/spec/{slug}/')} -->\n\n" + (site.repo / f).read_text(encoding="utf-8"))
    for p in sorted((site.repo / "spec/06-terms").glob("UP-*.md")):
        full.append(f"\n\n<!-- source: {site.url(f'/spec/terms/{p.stem}/')} -->\n\n" + p.read_text(encoding="utf-8"))
    site.write("llms-full.txt", "".join(full))


def build_sitemap(site):
    rows = "\n".join(f"  <url><loc>{site.url(p)}</loc><lastmod>{TODAY}</lastmod><changefreq>{f}</changefreq><priority>{pr}</priority></url>"
                     for p, pr, f in site.pages)
    site.write("sitemap.xml", f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}\n</urlset>\n')


def build_assets(site, og):
    from PIL import Image
    ad = site.out / "assets"
    ad.mkdir(parents=True, exist_ok=True)
    shutil.copy(site.repo / "explorer/src/tokens.css", ad / "tokens.css")
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
    ap.add_argument("--explainer", default=str(HERE / "src/developers.html" if in_repo else HERE.parent / "universal-paper-explainer/index.html"))
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
    build_developers(site, a.explainer)
    build_faq(site)
    build_license(site)
    build_spec(site)
    build_misc(site)
    build_llms(site)
    build_sitemap(site)
    n = sum(1 for _ in site.out.rglob("*") if _.is_file())
    print(f"built {n} files, {len(site.pages)} pages in sitemap -> {site.out}")


if __name__ == "__main__":
    main()
