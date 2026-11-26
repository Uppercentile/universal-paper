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
