"""The website build (site/build_site.py, v7 design).

Not part of the language. These tests build the whole site once and check that it hangs together: every page in
the sitemap exists and carries the shared chrome, internal links resolve, the search index covers every page, and the
facts the hand-designed pages state (test counts, hashes, MCP tools) match the repository.
"""
from __future__ import annotations

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
from universal_paper.canon import content_hash  # noqa: E402

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


def test_developer_page_hashes_and_tools_match_the_repository():
    s = (PAGES / "developers.html").read_text(encoding="utf-8")
    bundle = json.loads((ROOT / "examples/conventional/bundle.json").read_text())
    master = bundle["chains"][0][0]["body"]["agreement"]
    admin = json.loads((ROOT / "spec/06-terms/UP-Admin-Fee.json").read_text())
    assert set(re.findall(r"sha256:[0-9a-f]{64}", s)) == {content_hash(master), content_hash(admin)}
    for tool in mcp_server.TOOL_DOCS:
        assert tool in s, tool


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
