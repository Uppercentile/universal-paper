"""The v7 page layout for universalpaper.org: shared chrome, Markdown post-processing and the search index.

build_site.py decides what each page says; this module decides how it looks. The stylesheet, script, fonts and
icons live in site/theme/ and are served from /assets/. Hand-designed page bodies (home, developers, the
specification index, integrations, licenses) live in site/theme/pages/ as fragments: an optional <style>, one
<main id="main"> and optional <script>s. Everything else is generated.
"""
import hashlib
import html
import json
import re
from pathlib import Path

THEME = Path(__file__).resolve().parent / "theme"
SPRITE = (THEME / "sprite.svg").read_text(encoding="utf-8").strip()

# top navigation (desktop) and the phone menu sheet
MCP_URL = "https://mcp.universalpaper.org/mcp"

NAV = [("/developers/", "Developers"), ("/spec/", "Specification"), ("/spec/terms/", "Terms"),
       ("/integrations/", "Integrations"), ("/faq/", "FAQ")]
# which top-level item a path belongs to
SECTIONS = [("/spec/terms/", "/spec/terms/"), ("/spec/", "/spec/"), ("/integrations/", "/integrations/"),
            ("/developers/", "/developers/"), ("/faq/", "/faq/")]

# art for each document hero: the seeded flow field and its palette
TONES = {"overview": "warm", "domain": "lilac", "predicates-functions": "coral", "axioms": "mint", "inference": "warm",
         "lifecycle": "lilac", "terms": "coral", "mapping-guide": "mint", "neutrality-charter": "warm", "design-notes": "lilac",
         "legal-context-protocol": "lilac", "verifiable-credentials": "mint", "fingerprint-coordination": "coral"}
FAMILY_TONE = {"General": "sky", "Fees": "coral", "Term and renewal": "mint", "Termination": "mint", "Audit": "lilac",
               "Compliance": "coral", "Parties and participation": "sky", "Pricing reference": "sun", "Reporting": "lilac",
               "Tiers and attestation": "sun", "Tiers and pricing": "sun"}
CARD_TONES = ["lilac", "coral", "mint", "sun", "navy", "sky"]


def esc(s):
    return html.escape(s, quote=True)


def ico(name, style=""):
    st = f' style="{style}"' if style else ""
    return f'<svg class="ico"{st}><use href="#i-{name}"/></svg>'


def section_of(path):
    for prefix, item in SECTIONS:
        if path.startswith(prefix):
            return item
    return ""


# ----------------------------------------------------------------------------- chrome
def header(path, repo_url):
    cur = section_of(path)
    links = "".join(f'<li><a href="{h}"' + (' aria-current="page"' if h == cur else "") + f">{t}</a></li>" for h, t in NAV)
    sheet = "".join(f'<a href="{h}">{t}<small>' + ("You are here" if h == cur else "") + "</small></a>" for h, t in NAV)
    sheet += '<a href="/playground/">Playground<small>Runs in your browser</small></a>'
    if repo_url:
        sheet += f'<a href="{repo_url}">GitHub<small>Source ↗</small></a>'
    sheet += '<a href="/license/">Licenses<small></small></a>'
    gh = f'\n      <a class="txt" href="{repo_url}">GitHub</a>' if repo_url else ""
    return f"""<header class="nav" id="nav">
  <div class="wrap">
    <a class="brand" href="/" aria-label="Universal Paper home"><span class="mark" aria-hidden="true"></span>Universal Paper</a>
    <ul class="navlinks">{links}</ul>
    <div class="right">
      <button class="search-btn" type="button" data-search aria-label="Search the site">{ico("search")}<span>Search</span><kbd>⌘K</kbd></button>{gh}
      <a class="btn dark" href="/spec/">Read the spec</a>
      <button class="menu-btn" id="menuBtn" type="button" aria-expanded="false" aria-controls="menu" aria-label="Menu">{ico("menu")}</button>
    </div>
  </div>
  <nav class="menu-sheet" id="menu" aria-label="Site" hidden>{sheet}</nav>
</header>"""


def footer(legal, tagline, repo_url, extra_build=()):
    mcp = MCP_URL
    cmd = ('<p class="fine" style="margin:24px 0 10px">Give your agent the reference engine. Hosted MCP, no sign-in:</p>\n'
           f'<div class="cmd url" style="max-width:460px"><code>{mcp}</code><button class="cbtn" type="button" '
           f'data-copy="{mcp}">{ico("copy", "width:14px;height:14px")}Copy</button></div>\n'
           '<p class="fine" style="margin-top:10px">Or run it locally: <code class="mono" style="color:var(--ink)">uvx universal-paper-mcp</code></p>')
    build = [("/developers/", "Developers"), ("/developers/#mcp", "MCP server"), ("/playground/", "Playground"),
             ("/integrations/", "Integrations"), *extra_build]
    if repo_url:
        build.append((repo_url, "GitHub ↗"))
    col = lambda items: "".join(f'<li><a href="{h}">{t}</a></li>' for h, t in items)  # noqa: E731
    return f"""<footer>
  <div class="wrap">
    <div class="fgrid">
      <div>
        <p class="fine" style="font:400 26px/1.22 var(--serif);color:var(--ink);max-width:20ch;letter-spacing:-.012em">{esc(tagline)}.</p>
        {cmd}
      </div>
      <div><h4>Protocol</h4><ul>{col([("/spec/", "Specification"), ("/spec/overview/", "Overview"), ("/spec/axioms/", "Axioms"), ("/spec/terms/", "Term library"), ("/spec/mapping-guide/", "Mapping guide")])}</ul></div>
      <div><h4>Build</h4><ul>{col(build)}</ul></div>
      <div><h4>Project</h4><ul>{col([("/faq/", "FAQ"), ("/license/", "Licenses"), ("/spec/neutrality-charter/", "Neutrality charter"), ("/spec/design-notes/", "Design notes")])}</ul></div>
    </div>
    <div class="giant" aria-hidden="true"><span class="mark"></span>Universal Paper</div>
    {legal}
  </div>
</footer>"""


SEARCH = """<dialog class="sd" id="search" aria-label="Search">
  <form method="dialog" role="search"><svg class="ico" style="width:22px;height:22px;color:var(--ink-3)"><use href="#i-search"/></svg><label class="sr" for="searchInput">Search pages and sections</label><input id="searchInput" placeholder="Search Terms, axioms, pages…" autocomplete="off" role="combobox" aria-controls="searchList" aria-expanded="true"><kbd>esc</kbd></form>
  <ul id="searchList" role="listbox"></ul>
  <div class="foot"><span><kbd>↑</kbd> <kbd>↓</kbd> move</span><span><kbd>↵</kbd> open</span><span><kbd>esc</kbd> close</span></div>
</dialog>"""


def _asset_version():
    """Short hash of site.css + site.js. Pages caches assets for ten minutes, so without it a phone can
    pair fresh HTML with a stale stylesheet right after a deploy."""
    h = hashlib.sha256()
    for name in ("site.css", "site.js"):
        h.update((THEME / name).read_bytes())
    return h.hexdigest()[:10]


ASSET_V = _asset_version()


def document(*, title, head, header_html, footer_html, main, style="", scripts="", announce=""):
    """A whole page. `head` is the generated meta block (description, canonical, Open Graph, JSON-LD)."""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
{head}
<link rel="preload" href="/assets/fonts/hedvig-brand-serif-variable-latin.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/assets/site.css?v={ASSET_V}">
{style}
</head>
<body>
<a class="skip" href="#main">Skip to content</a>
{SPRITE}
{announce}
{header_html}

{main}

{footer_html}

{SEARCH}

<script src="/assets/search-index.js?v={ASSET_V}"></script>
<script src="/assets/site.js?v={ASSET_V}"></script>
{scripts}
</body>
</html>
"""


def fragment(name):
    """Split a page fragment from site/theme/pages/ into (style, main, scripts)."""
    s = (THEME / "pages" / f"{name}.html").read_text(encoding="utf-8")
    i, j = s.index('<main id="main">'), s.rindex("</main>") + len("</main>")
    return s[:i].strip(), s[i:j], s[j:].strip()


# ----------------------------------------------------------------------------- Markdown post-processing
_JSON_TOKEN = re.compile(r'"(?:[^"\\\n]|\\.)*"|[{}\[\],]|-?\b\d+(?:\.\d+)?\b')


def highlight_json(code):
    """Key / string / punctuation / number spans for a JSON-ish code block (the input is unescaped text)."""
    out, pos = [], 0
    for m in _JSON_TOKEN.finditer(code):
        out.append(esc(code[pos:m.start()]).replace("&#x27;", "'"))
        t = m.group(0)
        if t[0] == '"':
            cls = "k" if re.match(r"\s*:", code[m.end():]) else "s"
        elif t in "{}[],":
            cls = "p"
        else:
            cls = "num"
        out.append(f'<span class="{cls}">{esc(t)}</span>')
        pos = m.end()
    out.append(esc(code[pos:]).replace("&#x27;", "'"))
    return "".join(out)


def _code_blocks(h):
    def fix(m):
        lang, body = m.group(1), m.group(2)
        if lang == "json":
            body = highlight_json(html.unescape(body))
        return f'<pre data-lang="{lang}"><code>{body}</code></pre>'
    return re.sub(r'<pre><code class="language-([\w-]+)">(.*?)</code></pre>', fix, h, flags=re.S)


def _numbered_headings(h):
    def h2(m):
        attrs, text = m.group(1), m.group(2)
        n = re.match(r"(\d+)\.\s+(.*)$", text, re.S) or re.match(r"(A\d+)\s+(.*)$", text, re.S)
        if not n:
            return m.group(0)
        num = n.group(1)
        add = " add" if num.startswith("A") and int(num[1:]) > 10 else ""
        label = f"{int(num):02d}" if num.isdigit() else num
        return f'<h2{attrs} class="sec"><span class="sn{add}">{label}</span><span>{n.group(2)}</span></h2>'

    def h3(m):
        n = re.match(r"(\d+\.\d+)\.?\s+(.*)$", m.group(2), re.S)
        return f'<h3{m.group(1)}><span class="sn3">{n.group(1)}</span>{n.group(2)}</h3>' if n else m.group(0)
    h = re.sub(r"<h2([^>]*)>(.*?)</h2>", h2, h, flags=re.S)
    return re.sub(r"<h3([^>]*)>(.*?)</h3>", h3, h, flags=re.S)


def _checks(h):
    return re.sub(r"<p><em>Check:</em>\s*(.*?)</p>", r'<div class="check"><p>\1</p></div>', h, flags=re.S)


def article(h):
    """Post-process rendered Markdown for the v7 article: drop the H1, lift the first paragraph into the hero,
    number sections, box the axiom checks and highlight JSON. Returns (lede_html, body_html, toc)."""
    h = re.sub(r"^\s*<h1[^>]*>.*?</h1>\s*", "", h, count=1, flags=re.S)
    lede = ""
    m = re.match(r"\s*<p>(.*?)</p>\s*", h, re.S)
    if m:
        lede, h = m.group(1), h[m.end():]
    h = _code_blocks(_checks(_numbered_headings(h)))
    # wide tables scroll inside their own box on phones instead of widening the page
    h = re.sub(r'(?<!<div class="tablewrap">)<table>(.*?)</table>', r'<div class="tablewrap"><table>\1</table></div>', h, flags=re.S)
    toc = []
    for m in re.finditer(r'<h2 id="([^"]+)"[^>]*>(.*?)</h2>', h, re.S):
        sn = re.search(r'<span class="sn[^"]*">(.*?)</span>', m.group(2))
        text = re.sub(r"<[^>]+>", "", re.sub(r'<span class="sn[^"]*">.*?</span>', "", m.group(2))).strip()
        toc.append((m.group(1), sn.group(1) if sn else "", html.unescape(text)))
    return lede, h, toc


def read_minutes(text):
    return max(1, round(len(text.split()) / 250))


def toc_html(toc):
    items = "".join(f'<a href="#{i}">' + (f'<span class="tn">{esc(n)}</span>' if n else "") + f"{esc(t)}</a>" for i, n, t in toc)
    return f'<aside class="toc" aria-label="On this page"><b>On this page</b>{items}</aside>' if toc else ""


def side_html(label, title, items, current, mobile_label="In this section"):
    """items: (href, marker, text). Rendered twice: the desktop column and the phone disclosure."""
    links = "".join(f'<a href="{h}"' + (' aria-current="page"' if h == current else "") + f'><span class="n">{esc(n)}</span>{esc(t)}</a>'
                    if h else f"<b>{esc(t)}</b>" for h, n, t in items)
    nav = f'<nav class="side" aria-label="{esc(label)}"><b>{esc(title)}</b>{links}</nav>'
    return nav, f'<details class="side-mobile"><summary>{esc(mobile_label)} {ico("down")}</summary>{nav}</details>'


def pager_html(prev, nxt):
    p = f'<a class="prev" href="{prev[0]}"><small>← Previous</small><b>{esc(prev[1])}</b></a>' if prev else "<span></span>"
    n = f'<a class="next" href="{nxt[0]}"><small>Next →</small><b>{esc(nxt[1])}</b></a>' if nxt else ""
    return f'<div class="wrap"><nav class="pager" aria-label="Pages">{p}{n}</nav></div>'


def crumbs(trail):
    parts = []
    for href, text in trail:
        parts.append(f'<a href="{href}">{esc(text)}</a>' if href else f"<span>{esc(text)}</span>")
    return '<nav class="crumbs" aria-label="Breadcrumb">' + '<span aria-hidden="true">/</span>'.join(parts) + "</nav>"


def chip_links(links):
    return "".join(f'<a class="chipx" href="{esc(h)}">{esc(t)} {ico("ext")}</a>' for h, t in links)


def doc_main(*, field, tone, trail, eyebrow, title, lede, chips, side, body, toc, foot, pager):
    nav, mobile = side
    return f"""<main id="main">
  <div class="wrap dhero">
    <div class="artcard"><canvas data-field="{esc(field)}" data-tone="{tone}" aria-hidden="true"></canvas>
      {crumbs(trail)}
      <p class="eyebrow">{eyebrow}</p>
      <h1>{esc(title)}</h1>
      {f'<p class="lede">{lede}</p>' if lede else ""}
      <div class="chips">{chips}</div>
    </div>
  </div>
  <div class="wrap docs">
    {nav}
    <div style="min-width:0">
      {mobile}
      <article class="prose">{body}
  <p class="doc-foot">{foot}</p></article>
    </div>
    {toc_html(toc)}
  </div>
  {pager}
</main>"""


# ----------------------------------------------------------------------------- search index
def search_index(entries):
    """entries: dicts {t, s, u, k, h: [(id, text)]}. Served as /assets/search-index.js."""
    data = [{"t": e["t"], "s": e["s"], "u": e["u"], "k": e["k"], "h": [list(x) for x in e.get("h", [])]} for e in entries]
    return "window.UP_SEARCH=" + json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + ";\n"


def headings(main_html, level="h2"):
    """(id, text) for every heading with an id in a page body, for the search index."""
    out = []
    for m in re.finditer(rf'<{level}\b[^>]*\bid="([^"]+)"[^>]*>(.*?)</{level}>', main_html, re.S):
        text = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
        text = re.sub(r"^(A\d+|\d{2})\s+", "", text)
        if text:
            out.append((m.group(1), text))
    return out
