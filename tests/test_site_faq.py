"""The FAQ at universalpaper.org/faq/ (site/content/faq.py).

Not part of the language. These tests keep the FAQ safe to link to and to quote: every answer has a
permanent, unique anchor, published anchors never disappear, and the facts it states about the MCP
server and the optional integrations match the repository.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "site" / "content"))

from faq import SECTIONS  # noqa: E402

from universal_paper import mcp_server  # noqa: E402

ENTRIES = [e for _gid, _title, qs in SECTIONS for e in qs]
TEXT = " ".join(a for _id, _q, a, _ref in ENTRIES)

# Anchors already published at universalpaper.org/faq/#<id>. Other sites and AI answers link to them.
PUBLISHED = """what-is-universal-paper who-created-universal-paper-and-who-owns-it is-universal-paper-free-to-use
what-does-universal-paper-mean what-problem-does-it-solve is-universal-paper-a-product-or-a-platform
how-can-every-party-be-sure-they-hold-the-same-agreement how-are-changes-to-an-agreement-approved what-is-a-term
can-it-calculate-what-each-party-owes does-universal-paper-use-a-blockchain where-do-our-agreements-live
do-we-have-to-renegotiate-existing-contracts how-do-confidential-prices-stay-private can-ai-agents-act-on-behalf-of-a-party
how-does-it-work-with-edi does-the-language-set-or-suggest-prices-or-fees is-a-universal-paper-agreement-legally-binding
does-it-address-the-gpo-safe-harbor-in-u-s-healthcare is-it-neutral-between-gpos-suppliers-and-members
how-do-i-try-universal-paper how-is-the-reference-implementation-tested can-i-write-my-own-implementation
what-licenses-does-universal-paper-use can-i-use-universal-paper-commercially
who-governs-the-specification-and-how-does-it-change what-is-the-current-status-of-the-specification""".split()


def test_anchors_are_unique_slugs():
    ids = [e[0] for e in ENTRIES] + [gid for gid, _t, _q in SECTIONS]
    assert len(ids) == len(set(ids))
    for i in ids:
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", i) and len(i) <= 60, i


def test_published_anchors_are_kept():
    assert not set(PUBLISHED) - {e[0] for e in ENTRIES}


def test_answers_stand_alone():
    for qid, q, a, _ref in ENTRIES:
        assert q.endswith("?"), qid
        assert a.startswith("<p>") and a.endswith("</p>"), qid
        plain = re.sub(r"<[^>]+>", "", a)
        assert 80 <= len(plain) <= 700, f"{qid}: {len(plain)} characters"


def test_mcp_facts_match_the_server():
    n = len(mcp_server.TOOL_DOCS)
    assert f"{n} read-only tools" in TEXT
    named = set(re.findall(r"\b(?:validate|derive|check|simulate|render|hash|list|explain|get)_[a-z_]+\b", TEXT))
    assert named and named <= set(mcp_server.TOOL_DOCS), named - set(mcp_server.TOOL_DOCS)


def test_integration_links_exist():
    for slug in re.findall(r'href="/integrations/([a-z-]+)/"', TEXT):
        assert (ROOT / "docs/integrations" / f"{slug}.md").is_file(), slug
    assert "optional" in TEXT.lower()
