"""The website build (site/build_site.py, v7 design).

Not part of the language. These tests build the whole site once and check that it hangs together: every page in
the sitemap exists and carries the shared chrome, internal links resolve, the search index covers every page, and the
facts the hand-designed pages state (test counts, hashes, MCP tools) match the repository.
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

import pytest

pytest.importorskip("markdown")
pytest.importorskip("PIL")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site"))

import build_site  # noqa: E402

from universal_paper import mcp_server  # noqa: E402
from universal_paper.canon import content_hash, jcs  # noqa: E402

PAGES = ROOT / "site" / "theme" / "pages"


@pytest.fixture(scope="module")
def dist(tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    argv = sys.argv
    sys.argv = ["build_site.py", "--out", str(out)]
    try:
        build_site.main()
    finally:
        sys.argv = argv
    return out


def page_file(dist: Path, url_path: str) -> Path:
    p = dist / url_path.lstrip("/")
    return p / "index.html" if url_path.endswith("/") else p


def sitemap_paths(dist: Path) -> list[str]:
    xml = (dist / "sitemap.xml").read_text(encoding="utf-8")
    return [u.replace("https://universalpaper.org", "") for u in re.findall(r"<loc>([^<]+)</loc>", xml)]


def test_every_page_has_the_shared_chrome(dist):
    paths = sitemap_paths(dist)
    assert "/playground/" in paths and "/" in paths
    for path in paths + ["/404.html"]:
        s = page_file(dist, path).read_text(encoding="utf-8")
        assert s.count('<main id="main"') == 1, path
        assert '<header class="nav" id="nav">' in s and '<dialog class="sd" id="search"' in s, path
        assert "/assets/site.css" in s and "/assets/site.js" in s and "/assets/search-index.js" in s, path
        assert 'id="up-scroll-top"' in s, path
        assert "Created by <a href=\"https://uppercentile.com\">Uppercentile</a>" in s, path
        assert "submitllms.com/directory/universalpaper.org" in s, path  # the listing requires this badge link
        assert "design preview" not in s.lower(), path
        assert "Fonts: Hedvig" not in s, path  # the font credit lives on /license/ only (Joe, 2026-11-26)
        if path != "/404.html":
            assert f'<link rel="canonical" href="https://universalpaper.org{path}">' in s, path


def test_internal_links_resolve(dist):
    missing = set()
    for f in dist.rglob("*.html"):
        s = f.read_text(encoding="utf-8")
        for ref in re.findall(r'(?:href|src)="(/[^"#?$]*)"', s):
            if ref.startswith("//"):
                continue
            target = dist / ref.lstrip("/")
            if not (target.is_file() or (target / "index.html").is_file()):
                missing.add((str(f.relative_to(dist)), ref))
    assert not missing, sorted(missing)[:20]


def test_search_index_covers_every_page(dist):
    js = (dist / "assets/search-index.js").read_text(encoding="utf-8")
    data = json.loads(js[js.index("=") + 1:].rstrip().rstrip(";"))
    urls = {e["u"] for e in data}
    assert set(sitemap_paths(dist)) <= urls
    assert data[0]["u"] == "/"


def test_faq_anchors_and_structured_data(dist):
    s = (dist / "faq/index.html").read_text(encoding="utf-8")
    ids = [qid for _g, _t, qs in build_site.FAQ for qid, *_ in qs]
    for qid in ids:
        assert f'<details class="qa" id="{qid}">' in s, qid
    ld = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S)]
    faq = next(x for x in ld if x.get("@type") == "FAQPage")
    assert [q["@id"].split("#")[1] for q in faq["mainEntity"]] == ids


def test_home_figures_come_from_the_recorded_run(dist):
    s = (dist / "index.html").read_text(encoding="utf-8")
    r = json.loads((ROOT / "explorer/conformance-results.json").read_text())
    assert f'<b>{r["pytest"]["passed"]}/{r["pytest"]["passed"] + r["pytest"]["failed"]}</b> conformance tests passing' in s
    assert f'data-count="{r["js"]["passed"]}"' in s and f'data-count="{r["lab"]["runs"]}"' in s
    assert r["run"] in s
    # old links to the Playground on the home page still arrive at it
    assert 'location.replace("/playground/"' in s


def test_home_mandate_is_the_example_mandate():
    s = (PAGES / "home.html").read_text(encoding="utf-8")
    bundle = json.loads((ROOT / "examples/mandate-cap/bundle.json").read_text())
    assert set(re.findall(r"sha256:[0-9a-f]{64}", s)) <= {content_hash(m) for m in bundle["mandates"]}


def known_hashes() -> set[str]:
    """Every hash the hand-designed pages may show: anything in the conventional and confidential examples or the
    conventional trace, the Admin-Fee definition, and the conventional fee clause as signed and with one digit changed."""
    text = "".join((ROOT / p).read_text(encoding="utf-8") for p in (
        "examples/conventional/bundle.json", "examples/confidential/bundle.json", "examples/traces/conventional.trace.json"))
    found = set(re.findall(r"sha256:[0-9a-f]{64}", text))
    master = json.loads((ROOT / "examples/conventional/bundle.json").read_text())["chains"][0][0]["body"]["agreement"]
    fee = next(c for c in master["clauses"] if c["n"] == "fee")
    changed = json.loads(json.dumps(fee))
    changed["params"]["rate"] = "0.015"
    admin = json.loads((ROOT / "spec/06-terms/UP-Admin-Fee.json").read_text())
    return found | {content_hash(master), content_hash(fee), content_hash(changed), content_hash(admin)}


def test_developer_page_hashes_and_tools_match_the_repository():
    s = (PAGES / "developers.html").read_text(encoding="utf-8")
    known = known_hashes()
    shown = re.findall(r"sha256:([0-9a-f]{8,64})(?:…([0-9a-f]{4,}))?", s)
    assert len(shown) >= 6
    for head, tail in shown:  # full hashes, and shortened ones such as sha256:b6f070ef…8f990f6d
        assert any(h[7:].startswith(head) and h.endswith(tail) for h in known), f"sha256:{head}…{tail}"
    for tool in mcp_server.TOOL_DOCS:
        assert tool in s, tool


def test_home_stage_hashes_the_signed_example(dist):
    """The Write / Agree / Build stage embeds the conventional master agreement and the hash both parties signed."""
    s = (dist / "index.html").read_text(encoding="utf-8")
    bundle = json.loads((ROOT / "examples/conventional/bundle.json").read_text())
    master = bundle["chains"][0][0]["body"]["agreement"]
    embedded = json.loads(re.search(r'<script type="application/json" id="agreementData">(.*?)</script>', s, re.S).group(1))
    assert embedded == master
    assert f"const SIGNED = '{content_hash(master)[7:]}';" in s
    assert f'<b id="stBytes">{len(jcs(master)):,}</b>' in s
    names = [c["n"] for c in master["clauses"]]
    assert f"Clause {names.index('fee') + 1} of {len(names)}," in s
    fee = master["clauses"][names.index("fee")]["params"]
    assert f'<li data-p="rate"><code>rate</code><em>Rate</em><b>"{fee["rate"]}"</b></li>' in s
    assert f'<b>{{"count": {fee["due"]["count"]}, "unit": "{fee["due"]["unit"]}"}}</b>' in s


def test_home_mandate_verdicts_are_the_engines():
    s = (PAGES / "home.html").read_text(encoding="utf-8")
    ok = mcp_server.simulate_amendment("example:mandate-cap", "price", "factor", "1.02")
    no = mcp_server.simulate_amendment("example:mandate-cap", "price", "factor", "1.05")
    assert ok["accepted"] and not no["accepted"]
    assert "1.05 is above the maximum 1.02" in no["reason"] and "factor 1.05 is above the maximum 1.02" in s
    assert "Mandate cap 1.02: a 1.05 proposal is rejected (A9)" in s


def test_footer_names_the_hosted_mcp_server(dist):
    s = (dist / "faq/index.html").read_text(encoding="utf-8")
    assert build_site.L.MCP_URL in mcp_server.__doc__ and f'data-copy="{build_site.L.MCP_URL}"' in s
    assert "uvx universal-paper-mcp" in s and "uvx universal-paper-mcp" in mcp_server.__doc__


def test_playground_page_frames_the_explorer(dist):
    s = (dist / "playground/index.html").read_text(encoding="utf-8")
    assert '<iframe id="pgframe"' in s and 'src="/playground/app.html"' in s
    app = (dist / "playground/app.html").read_text(encoding="utf-8")
    assert 'data-embed="playground"' in app and 'content="noindex,follow"' in app and 'id="pg-body"' in app
    assert not re.search(r"<link[^>]+fonts\.googleapis\.com", app)


def test_spec_pages_keep_their_section_anchors(dist):
    s = (dist / "spec/axioms/index.html").read_text(encoding="utf-8")
    for i in range(1, 14):
        assert re.search(rf'<h2 id="a{i}-[a-z-]+" class="sec"><span class="sn[^"]*">A{i}</span>', s), i
    assert s.count('<div class="check">') == 13
    d = (dist / "spec/domain/index.html").read_text(encoding="utf-8")
    assert 'id="33-what-may-be-sealed"' in d and '<pre data-lang="json"><code><span class="p">{</span>' in d


def test_every_schema_is_served_at_its_id_and_no_placeholders_remain(dist):
    sources = sorted((ROOT / "schema").glob("*.json")) + sorted((ROOT / "examples/integrations/fingerprint-coordination/schemas").glob("*.json"))
    assert len(sources) >= 4
    for p in sources:
        sid = json.loads(p.read_text(encoding="utf-8"))["$id"]
        assert sid.startswith("https://universalpaper.org/"), sid
        served = dist / sid.removeprefix("https://universalpaper.org/")
        assert served.read_bytes() == p.read_bytes(), sid
    for name in ("universal-paper.schema.json", "trace.schema.json"):  # the unversioned alias keeps serving the current one
        assert (dist / "schema" / name).read_bytes() == (ROOT / "schema" / name).read_bytes()
    placeholder = re.compile(r"https?://[a-z0-9.-]*\.(?:example|invalid|test)(?:[/\"']|$)")
    leaks = [str(f.relative_to(dist)) for f in dist.rglob("*") if f.suffix in (".json", ".html", ".txt", ".md")
             and placeholder.search(f.read_text(encoding="utf-8"))]
    assert not leaks, leaks


def test_faq_list_is_full_width_on_phones(dist):
    """An inline grid on the FAQ once overrode the phone layout and squeezed every answer into half the screen."""
    s = (dist / "faq/index.html").read_text(encoding="utf-8")
    assert re.search(r'<div class="wrap docs faqdocs">', s) and "grid-template-columns:232px" not in s.split("<main", 1)[1]
    assert "@media (max-width:860px){.faqdocs{grid-template-columns:minmax(0,1fr)}" in s


def test_playground_frame_links_stay_on_the_site():
    app = (ROOT / "explorer/index.html").read_text(encoding="utf-8")
    assert "claude.ai/artifact" not in app


def test_agent_json_describes_only_what_exists(dist):
    """/.well-known/agent.json (and the root copy) for AI agents: the MCP server, its real tools, served resources."""
    a = json.loads((dist / ".well-known/agent.json").read_text(encoding="utf-8"))
    assert (dist / "agent.json").read_text(encoding="utf-8") == (dist / ".well-known/agent.json").read_text(encoding="utf-8")
    assert not (dist / ".well-known/agent-card.json").exists()  # not an A2A agent, so no A2A Agent Card
    assert [t["name"] for t in a["mcp"]["tools"]] == list(mcp_server.TOOL_DOCS)
    assert a["mcp"]["url"] == build_site.L.MCP_URL and a["mcp"]["readOnly"] is True and a["mcp"]["auth"] == "none"
    server = json.loads((ROOT / "server.json").read_text(encoding="utf-8"))
    assert a["mcp"]["registryName"] == server["name"] and a["mcp"]["version"] == server["version"]
    r = a["resources"]
    for u in [v for v in r.values() if isinstance(v, str)] + r["schemas"] + r["examples"]:
        f = dist / u.removeprefix("https://universalpaper.org/")
        assert f.is_file() or (f / "index.html").is_file(), u
    assert "/.well-known/agent.json" in (dist / "llms.txt").read_text(encoding="utf-8")


def test_home_hero_copy(dist):
    s = (dist / "index.html").read_text(encoding="utf-8")
    assert '<h1 class="display">Everything comes from <em>agreement</em>.</h1>' in s
    assert "Sign one, and every system and agent reaches the same answers." in s
    # the underline is a background on <em>, drawn at every width (no ::after that a phone rule could hide)
    assert ".hero .display em { font-style: normal; background: linear-gradient(var(--coral)" in s
    assert ".hero .display em::after" not in s


def test_titles_and_descriptions_fit_search_results(dist):
    """Search results cut titles past ~60 characters and descriptions past ~155; every page stays within both."""
    for f in dist.rglob("*.html"):
        s = f.read_text(encoding="utf-8")
        t = re.search(r"<title>(.*?)</title>", s, re.S)
        m = re.search(r'<meta name="description" content="([^"]*)"', s)
        assert t and len(html.unescape(t.group(1))) <= 60, (f, t and t.group(1))
        assert m and len(html.unescape(m.group(1))) <= 155, (f, m and m.group(1))


def test_counters_carry_real_numbers_without_script(dist):
    """Crawlers and agents read the raw HTML, so each count-up holds its real value before any script runs."""
    s = (dist / "index.html").read_text(encoding="utf-8")
    counts = re.findall(r'<span data-count="(\d+)">([^<]*)</span>', s)
    assert len(counts) == 4 and all(v == n for v, n in counts), counts
    assert counts[0][0] == str(json.loads((ROOT / "explorer/conformance-results.json").read_text())["pytest"]["passed"])


def test_developers_headline_is_agreement_led(dist):
    s = (dist / "developers/index.html").read_text(encoding="utf-8")
    assert '<h1 class="display">The agreement layer every system can read.</h1>' in s
    assert "contract layer" not in s


def test_hero_timeline_uses_the_real_fingerprint(dist):
    """The underline under "agreement" plays out the conventional example: its real fingerprint, both signatures, active."""
    s = (dist / "index.html").read_text(encoding="utf-8")
    sys.path.insert(0, str(ROOT / "src"))
    from universal_paper.canon import content_hash
    agreement = json.loads((ROOT / "examples/conventional/bundle.json").read_text(encoding="utf-8"))["chains"][0][0]["body"]["agreement"]
    h = content_hash(agreement).split(":", 1)[1]
    tl = s[s.index('<div class="tl" id="tl"'):s.index("</div>", s.index('<div class="tl" id="tl"'))]
    assert 'aria-hidden="true" hidden' in tl  # decorative; script reveals it, so no-JS readers get the plain headline
    assert f"{h[:8]}…{h[-8:]}" in tl
    for label in ("Aggregator signed", "Supplier signed", "Status: active"):
        assert label in tl
    assert "animation: underline-in 2.8s" in s and "const START = 600, DRAW = 2800" in s  # CSS and script keep one clock


TRUST = ("/privacy/", "/terms/", "/security/", "/support/", "/accessibility/")


def test_trust_pages_are_served_and_linked_everywhere(dist):
    """The five trust pages exist, every page's footer links all five, and llms.txt, agent.json and the sitemap list them."""
    for p in TRUST:
        s = (dist / p.strip("/") / "index.html").read_text(encoding="utf-8")
        assert s.count("<h1") == 1 and f'<a href="{p}" aria-current="page">' in s
    for f in dist.rglob("index.html"):
        s = f.read_text(encoding="utf-8")
        if '<footer' in s:
            assert all(f'<a href="{p}"' in s for p in TRUST), f
    llms, sitemap = (dist / "llms.txt").read_text(encoding="utf-8"), (dist / "sitemap.xml").read_text(encoding="utf-8")
    agent = json.loads((dist / ".well-known/agent.json").read_text(encoding="utf-8"))["resources"]
    for p in TRUST:
        assert f"https://universalpaper.org{p}" in llms and f"<loc>https://universalpaper.org{p}</loc>" in sitemap
        assert f"https://universalpaper.org{p}" in agent.values()


def test_privacy_policy_matches_what_the_site_loads(dist):
    """The privacy policy says the only third-party request is the SubmitLLMs footer badge. Keep that true on every page."""
    hosts = set()
    for f in dist.rglob("*.html"):
        s = f.read_text(encoding="utf-8")
        for m in re.finditer(r'<(?:script|img|iframe|link)\b[^>]*\b(?:src|href)="(https?://[^/"]+)[^"]*"', s):
            tag = m.group(0)
            if tag.startswith("<link") and not re.search(r'rel="(?:stylesheet|preconnect|icon|preload|modulepreload)"', tag):
                continue
            hosts.add(m.group(1))
        assert "document.cookie" not in s, f
    assert hosts <= {"https://submitllms.com"}, hosts
    privacy = (dist / "privacy/index.html").read_text(encoding="utf-8")
    assert "SubmitLLMs" in privacy and "mcp.universalpaper.org/stats" in privacy


def test_security_fallback_matches_security_md(dist):
    page = (dist / "security/index.html").read_text(encoding="utf-8")
    policy = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert "contact@uppercentile.com" in page and "email contact@uppercentile.com and ask for a private channel" in policy
    assert "Contact: mailto:contact@uppercentile.com" in (dist / ".well-known/security.txt").read_text(encoding="utf-8")


def test_no_page_shows_raw_css(dist):
    """Page styles sit inside <style>; CSS never leaks into the page text."""
    for f in dist.rglob("*.html"):
        body = re.sub(r"<(style|script)\b.*?</\1>", "", f.read_text(encoding="utf-8").split("<body", 1)[-1], flags=re.S)
        assert not re.search(r"\.[a-z-]+ \{ [a-z-]+: ", body), f


def test_shared_assets_are_versioned_by_content(dist):
    """Every page asks for site.css and site.js by a hash of their content, so a phone never pairs fresh
    HTML with a cached old stylesheet after a deploy (GitHub Pages caches assets for ten minutes)."""
    import hashlib

    want = hashlib.sha256((dist / "assets/site.css").read_bytes() + (dist / "assets/site.js").read_bytes()).hexdigest()[:10]
    for path in ("index.html", "privacy/index.html", "faq/index.html"):
        s = (dist / path).read_text(encoding="utf-8")
        assert f'/assets/site.css?v={want}"' in s and f'/assets/site.js?v={want}"' in s, path


def test_trust_pages_promise_no_reply_time_and_keep_the_audit_caveat(dist):
    """Joe's rule: replies to email are best effort, never a promised time. The audit stays labelled as our own."""
    for path in ("privacy/index.html", "support/index.html"):
        s = (dist / path).read_text(encoding="utf-8")
        assert "30 days" not in s and "best-effort" in s.replace("best effort", "best-effort"), path
    sec = (dist / "security/index.html").read_text(encoding="utf-8")
    for fact in ("signed provenance attestation", "trusted publishing", "Dependabot", "read-only token", "non-root user",
                 "16 issues", "our own team"):
        assert fact in sec, fact


def test_claude_connector_guide_is_served_and_linked(dist):
    """/docs/claude/ is the documentation link on the Claude directory listing, so its address is permanent."""
    page = (dist / "docs/claude/index.html").read_text(encoding="utf-8")
    assert "<h1 class=\"display\">Universal Paper in Claude</h1>" in page
    assert page.count('type="application/ld+json"') >= 3 and '"@type":"HowTo"' in page.replace('": "', '":"')
    assert "13 read-only tools" in page and "https://mcp.universalpaper.org/mcp" in page
    for tool in ("validate_bundle", "simulate_price_conformity", "get_example"):
        assert f"<code>{tool}</code>" in page
    assert 'href="/docs/claude/"' in (dist / "index.html").read_text(encoding="utf-8")  # footer, every page
    assert "/docs/claude/" in (dist / "developers/index.html").read_text(encoding="utf-8").split('id="mcp"', 1)[1]
    assert 'href="/docs/claude/#troubleshooting"' in (dist / "support/index.html").read_text(encoding="utf-8")
    assert "https://universalpaper.org/docs/claude/" in (dist / "llms.txt").read_text(encoding="utf-8")
    assert "https://universalpaper.org/docs/claude/" in (dist / "sitemap.xml").read_text(encoding="utf-8")
    assert json.loads((dist / ".well-known/agent.json").read_text(encoding="utf-8"))["resources"]["claudeGuide"].endswith("/docs/claude/")
    short = (dist / "claude/index.html").read_text(encoding="utf-8")
    assert 'url=/docs/claude/' in short and 'content="noindex"' in short and "/claude/" not in (dist / "sitemap.xml").read_text(encoding="utf-8").replace("/docs/claude/", "")


def test_claude_directory_listing_is_the_claude_option(dist):
    """The connector is published in Claude's directory: Claude users are sent there, other clients keep every option."""
    d = "https://claude.ai/directory/universal-paper"
    guide = (dist / "docs/claude/index.html").read_text(encoding="utf-8")
    assert guide.count(d) >= 2 and "add-custom-connector" not in guide
    assert "https://mcp.universalpaper.org/mcp" in guide  # the custom-connector fallback stays
    for path in ("index.html", "developers/index.html", "support/index.html", "faq/index.html"):
        assert d in (dist / path).read_text(encoding="utf-8"), path
    dev = (dist / "developers/index.html").read_text(encoding="utf-8")
    assert "claude mcp add --transport http" in dev and "uvx universal-paper-mcp" in dev
    assert d in (dist / "llms.txt").read_text(encoding="utf-8")
    assert json.loads((dist / ".well-known/agent.json").read_text(encoding="utf-8"))["mcp"]["claudeDirectory"] == d


def test_chatgpt_plugin_guide_is_served_and_linked(dist):
    """/docs/chatgpt/ mirrors the Claude guide for the ChatGPT plugin listing; its address is permanent too."""
    d = "https://chatgpt.com/plugins/plugin_asdk_app_6b09c3ea78c48191a51566aae625917a"
    page = (dist / "docs/chatgpt/index.html").read_text(encoding="utf-8")
    assert "<h1 class=\"display\">Universal Paper in ChatGPT</h1>" in page
    assert page.count('type="application/ld+json"') >= 3 and '"@type":"HowTo"' in page.replace('": "', '":"')
    assert "13 read-only tools" in page and "https://mcp.universalpaper.org/mcp" in page and page.count(d) >= 2
    assert "Let&rsquo;s build an app using Universal Paper" in page and 'id="build-an-app"' in page
    for tool in ("validate_bundle", "simulate_price_conformity", "get_example"):
        assert f"<code>{tool}</code>" in page
    article = page.split('<article class="prose">', 1)[1].split("</article>", 1)[0]
    assert "Anthropic" not in article and "Claude" not in article.replace('Using Claude? See the <a href="/docs/claude/">Claude connector guide</a>', "")
    # Both guides list each other, and every Claude placement now offers ChatGPT beside it.
    claude = (dist / "docs/claude/index.html").read_text(encoding="utf-8")
    assert 'href="/docs/chatgpt/"' in claude and 'href="/docs/claude/"' in page
    for path in ("index.html", "developers/index.html", "support/index.html", "faq/index.html"):
        s = (dist / path).read_text(encoding="utf-8")
        assert d in s and "https://claude.ai/directory/universal-paper" in s, path
    home = (dist / "index.html").read_text(encoding="utf-8")
    foot = home.split("<footer>", 1)[1]
    assert "Listed in <a" in foot and 'class="lpill"' not in foot  # footer, every page: plain text links, no buttons
    assert 'class="listed on-dark"' in (dist / "developers/index.html").read_text(encoding="utf-8")  # the pills stay here
    assert 'href="/docs/chatgpt/#troubleshooting"' in (dist / "support/index.html").read_text(encoding="utf-8")
    for f in ("llms.txt", "sitemap.xml"):
        assert "https://universalpaper.org/docs/chatgpt/" in (dist / f).read_text(encoding="utf-8"), f
    agent = json.loads((dist / ".well-known/agent.json").read_text(encoding="utf-8"))
    assert agent["mcp"]["chatgptDirectory"] == d and agent["resources"]["chatgptGuide"].endswith("/docs/chatgpt/")


# ----------------------------------------------------------------------------- Research (not part of the language)
import research  # noqa: E402
import research_library  # noqa: E402

RESEARCH_NOTICE = "Research is not part of the Universal Paper language. It may grow, change, or be withdrawn. Agreements do not depend on it."
RESEARCH_PAGES = ["/research/"] + [f"/research/{e['slug']}/" for e in research_library.ENTRIES]
EXAMPLE = ROOT / "site/theme/research/example"
# the published fingerprints of the four example files (Reusable 003); they must never change
EXAMPLE_FINGERPRINTS = {
    "manifest.json": "sha256:44bb1bb2ebbbd0bd3e05f9c3f7b539c5057b43d194f56a027d458167d3d293ae",
    "trace-eligibility.json": "sha256:0da4824fb755d7c1acb3a7b85c21a11a063db5666adac06ac333fd057e262e38",
    "trace-fee.json": "sha256:c398d0b7052d0c4ee706011a41363091198a66a3c2906ba1130ceb97d52326d0",
    "trace-amendment.json": "sha256:5210769fdb99b09fe422cc202350117c5f77b369d1258a211029769558eee6df",
}


def test_header_groups_on_every_page(dist):
    """Three dropdown groups (Language, Build, Research) plus FAQ, each button wired to its panel, and the same groups
    in the phone menu. Research pages mark the Research group as current."""
    for f in dist.rglob("*.html"):
        s = f.read_text(encoding="utf-8")
        if '<header class="nav" id="nav">' not in s:
            continue  # redirects and the framed Playground app
        head = s[s.index('<header class="nav" id="nav">'):s.index("</header>")]
        assert re.findall(r'aria-controls="(nx-\w+)"', head) == ["nx-language", "nx-build", "nx-research"], f
        for g in ("language", "build", "research"):
            assert f'<div class="nx-panel" id="nx-{g}" role="group"' in head and f"nx-{g}\" role=\"group\" aria-label=" in head, f
        assert '<li><a href="/faq/"' in head and head.count('<details class="nx-group"') == 3, f
        assert 'href="/research/"' in head and 'href="https://github.com/Uppercentile/universal-paper">GitHub</a>' in head, f
        foot = s.split("<footer>", 1)[1]
        assert '<h4>Project</h4><ul>' in foot and '<li><a href="/research/">Research</a></li>' in foot, f
    page = (dist / "research/trace-freshness/index.html").read_text(encoding="utf-8")
    assert 'aria-controls="nx-research" data-current="true"' in page and '<details class="nx-group" open><summary>Research' in page
    spec = (dist / "spec/axioms/index.html").read_text(encoding="utf-8")
    assert 'aria-controls="nx-language" data-current="true"' in spec and 'class="nx-link" href="/spec/axioms/" aria-current="page"' in spec
    css, js = (ROOT / "site/theme/site.css").read_text(encoding="utf-8"), (ROOT / "site/theme/site.js").read_text(encoding="utf-8")
    assert ".nx-panel {" in css and "@media (max-width: 1100px) { .nx-panel { display: none !important; } }" in css
    assert "Header dropdowns: click or hover to open" in js


def test_research_pages_carry_the_notice_and_files(dist):
    paths = sitemap_paths(dist)
    for p in RESEARCH_PAGES:
        assert p in paths, p
        s = page_file(dist, p).read_text(encoding="utf-8")
        notice = ('<div class="announce rs-notice" role="note" aria-label="Research notice"><div class="wrap"><span class="pill">Research</span>'
                  f"<span>{RESEARCH_NOTICE}</span></div></div>")
        assert notice in s.split("<header", 1)[0], p  # word for word, above the header
        assert '<meta name="robots" content="index,follow">' in s and "Preview only" not in s and "sample-" not in s, p
        assert "<style>" in s and ".rs-hero .display" in s, p
    for e in research_library.ENTRIES:
        s = page_file(dist, f"/research/{e['slug']}/").read_text(encoding="utf-8")
        assert f'data-research-kind="{e["kind"]}" data-research-number="{e["n"]}"' in s
        assert "/* A thin progress line while reading a note. */" in s  # research-read.js on every entry
        assert ("Research note: recompute each example trace" in s) == (e["kind"] == "experiment")  # research.js on the experiment only
        assert (dist / "research" / e["slug"] / "entry.json").is_file() and (dist / "research" / f"{e['slug']}.md").is_file()
        ld = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', s, re.S)]
        crumbs = [x for x in ld if x["@type"] == "BreadcrumbList"]
        assert len(crumbs) == 1 and len(crumbs[0]["itemListElement"]) == 4
    index = (dist / "research/index.html").read_text(encoding="utf-8")
    assert "Research library: search, facets, sort and paging" in index and index.count('<li class="rs-row"') == len(research_library.ENTRIES)
    exp = (dist / "research/three-traces-recomputed/index.html").read_text(encoding="utf-8")
    assert '<p class="rs-result-v">Held in part</p>' in exp and "The repository&#39;s JavaScript engine was not run for this experiment." in exp
    # the research schemas live apart from the language's /schema/
    assert not list((dist / "schema").rglob("*research*")) and not (dist / "schema/entry.schema.json").exists()
    search = (dist / "assets/search-index.js").read_text(encoding="utf-8")
    for p in RESEARCH_PAGES:
        assert f'"u":"{p}"' in search, p


def test_research_example_files_are_served_byte_for_byte(dist):
    for name, fp in EXAMPLE_FINGERPRINTS.items():
        served = (dist / "research/query-test-vectors" / name).read_bytes()
        assert served == (EXAMPLE / name).read_bytes(), name
        assert content_hash(json.loads(served)) == fp, name
    summary = json.loads((EXAMPLE / "summary.json").read_text(encoding="utf-8"))
    assert summary["manifest"]["fingerprint"] == EXAMPLE_FINGERPRINTS["manifest.json"]
    assert [t["fingerprint"] for t in summary["example"]["traces"]] == [EXAMPLE_FINGERPRINTS[f"trace-{q}.json"] for q in ("eligibility", "fee", "amendment")]


def test_research_trace_states_are_the_reference_engines():
    """Every state fingerprint the example traces name is the one the reference interpreter derives from the public bundle."""
    bundle = json.loads((ROOT / "examples/generative/bundle.json").read_text(encoding="utf-8"))
    derived = mcp_server.derive_state(bundle, "2027-03-01T00:00:00Z")
    state = {content_hash(bundle["chains"][c["chain"]][0]): c["state_hash"] for c in derived["chains"]}
    assert state["sha256:306149286ea760f5a855d1ea2ad9da8ed7a349a272d0d9ed0128c179c09fc3af"] == "sha256:c198cefe6c519bf30af389a71fb0bc346f5fd3906865d1662941b47db3e31424"
    for name in EXAMPLE_FINGERPRINTS:
        if name.startswith("trace-"):
            for s in json.loads((EXAMPLE / name).read_text(encoding="utf-8"))["state"]:
                assert state[s["chain"]] == s["fingerprint"], (name, s["chain"])


def _research_validator(dist):
    """A standard draft 2020-12 validator (jsonschema), with the four research schemas registered at their $id."""
    jsonschema = pytest.importorskip("jsonschema")
    referencing = pytest.importorskip("referencing")
    schemas = {n: json.loads((dist / "research/schema/0" / f"{n}.schema.json").read_text(encoding="utf-8"))
               for n in ("entry", "index", "query-manifest", "query-trace")}
    registry = referencing.Registry().with_resources(
        (s["$id"], referencing.Resource.from_contents(s, default_specification=referencing.jsonschema.DRAFT202012)) for s in schemas.values())
    for s in schemas.values():
        jsonschema.Draft202012Validator.check_schema(s)  # each schema is itself valid draft 2020-12
    fmt = jsonschema.Draft202012Validator.FORMAT_CHECKER
    return {n: jsonschema.Draft202012Validator(s, registry=registry, format_checker=fmt) for n, s in schemas.items()}


def test_research_json_validates_against_its_schemas(dist):
    v = _research_validator(dist)
    for n, s in ((n, json.loads((dist / "research/schema/0" / f"{n}.schema.json").read_text(encoding="utf-8"))) for n in v):
        assert s["$id"] == f"https://universalpaper.org/research/schema/0/{n}.schema.json"  # served at its $id
        assert s["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    index = json.loads((dist / "research/index.json").read_text(encoding="utf-8"))
    errors = {"index.json": [e.message for e in v["index"].iter_errors(index)]}
    assert len(index["entries"]) == len(research_library.ENTRIES)
    for row in index["entries"]:
        full = json.loads((dist / "research" / row["slug"] / "entry.json").read_text(encoding="utf-8"))
        errors[f"{row['slug']}/entry.json"] = [e.message for e in v["entry"].iter_errors(full)]
        assert {k: full[k] for k in row} == row, row["slug"]  # each entry.json agrees with its row in the index
    vec = dist / "research/query-test-vectors"
    errors["manifest.json"] = [e.message for e in v["query-manifest"].iter_errors(json.loads((vec / "manifest.json").read_text()))]
    for q in ("eligibility", "fee", "amendment"):
        errors[f"trace-{q}.json"] = [e.message for e in v["query-trace"].iter_errors(json.loads((vec / f"trace-{q}.json").read_text()))]
    assert len(errors) == 1 + 9 + 1 + 3 and not any(errors.values()), {k: x for k, x in errors.items() if x}
    for k in ("summary.json",):
        json.loads((dist / "research/query-surfaces" / k).read_text(encoding="utf-8"))


def test_research_schemas_refuse_bad_records(dist):
    """The six records validate.rb refuses are refused by a standard validator too."""
    v = _research_validator(dist)
    question = json.loads((dist / "research/who-may-name-questions/entry.json").read_text(encoding="utf-8"))
    note = json.loads((dist / "research/query-surfaces/entry.json").read_text(encoding="utf-8"))
    manifest = json.loads((dist / "research/query-test-vectors/manifest.json").read_text(encoding="utf-8"))
    bad = [("a question with status exploring", "entry", {**question, "status": "exploring"}),
           ("an unknown kind", "entry", {**question, "kind": "paper"}),
           ("four topics", "entry", {**question, "topics": ["queries", "fees", "pricing", "sealing"]}),
           ("an answered question with no answered_by", "entry", {**question, "status": "answered"}),
           ("a note with a parent", "entry", {**note, "parent": 2}),
           ("a manifest that names a new engine call", "query-manifest", {**manifest, "questions": [{**manifest["questions"][0], "call": "my_new_call"}]})]
    accepted = [label for label, schema, data in bad if v[schema].is_valid(data)]
    assert not accepted, accepted
    assert v["entry"].is_valid(question) and v["entry"].is_valid(note) and v["query-manifest"].is_valid(manifest)


def test_research_check_stops_the_build_on_a_bad_entry():
    good = research_library.ENTRIES
    research_library.check(good)
    q = next(e for e in good if e["kind"] == "question")
    for change, why in [({"kind": "paper"}, "unknown kind"), ({"status": "exploring"}, "not allowed"), ({"topics": ["queries", "fees", "pricing", "sealing"]}, "one to three"),
                        ({"topics": ["queries", "queries"]}, "one to three"), ({"topics": ["nope"]}, "unknown topic"), ({"impact": "maybe"}, "impact"),
                        ({"parent": 99}, "does not exist"), ({"status": "answered"}, "answered_by")]:
        with pytest.raises(SystemExit, match=why):
            research_library.check([e if e is not q else {**q, **change} for e in good])
    with pytest.raises(SystemExit, match="a note has no parent"):
        research_library.check([e if e["n"] != 1 else {**e, "parent": 2} for e in good])
    with pytest.raises(SystemExit, match="used twice"):
        research_library.check(good + [{**q, "n": 99}])


def test_research_wording_is_kept():
    """The nine entries keep Joe's wording; a few phrases the README singles out are pinned here."""
    by = {e["n"]: e for e in research_library.ENTRIES}
    assert [e["n"] for e in research_library.ENTRIES] == list(range(1, 10)) and by[2]["outcome"] == "held_in_part"
    assert len(by[2]["limits"]) == 4 and by[2]["limits"][0] == "One engine derived the verdicts. The repository's JavaScript engine was not run for this experiment."
    assert "`no base reported yet`" in by[6]["known"][2]


def test_research_discovery_files(dist):
    llms = (dist / "llms.txt").read_text(encoding="utf-8")
    assert "## Research (not part of the language)\n\n" + RESEARCH_NOTICE in llms
    for e in research_library.ENTRIES:
        assert f"- [{e['title']}](https://universalpaper.org/research/{e['slug']}.md): " in llms
    agent = json.loads((dist / ".well-known/agent.json").read_text(encoding="utf-8"))["research"]
    assert agent["notice"] == RESEARCH_NOTICE and agent["kinds"] == ["note", "experiment", "reusable", "question"]
    for u in [agent["index"], agent["feed"], agent["page"], *agent["schemas"]]:
        f = dist / u.removeprefix("https://universalpaper.org/")
        assert f.is_file() or (f / "index.html").is_file(), u
    feed = (dist / "research/feed.xml").read_text(encoding="utf-8")
    assert feed.count("<entry>") == len(research_library.ENTRIES) and research.NOTICE in feed
