"""Build the single-file Explorer from explorer/src/.

Writes explorer/index.html (a complete document, opened from the repository so it can fetch
examples/traces/). With --artifact PATH, also writes the body-only form used for publishing,
which a host wraps in its own document skeleton.

    python3 tools/build_explorer.py [--artifact PATH]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "explorer" / "src"


def build() -> str:
    page = (SRC / "app.html").read_text()
    terms = [json.loads(p.read_text()) for p in sorted((ROOT / "spec" / "06-terms").glob("*.json"))]
    parts = {
        "/*@@TERMS@@*/": json.dumps(terms, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"),
        "/*@@UP_CRYPTO@@*/": (SRC / "up-crypto.js").read_text(),
        "/*@@UP_ENGINE@@*/": (SRC / "up-engine.js").read_text(),
        "/*@@UP_LAB@@*/": (SRC / "up-lab.js").read_text(),
        "/*@@APP@@*/": (SRC / "app.js").read_text(),
    }
    for k, v in parts.items():
        if "</script" in v.lower():
            raise SystemExit(f"{k} contains </script")
        page = page.replace(k, v)
    return page


def main(argv: list[str]) -> None:
    body = build()
    head, _, rest = body.partition("<!--BODY-->")
    doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
           + head + "</head>\n<body>\n" + rest + "</body>\n</html>\n")
    out = ROOT / "explorer" / "index.html"
    out.write_text(doc)
    print(f"wrote {out.relative_to(ROOT)} ({len(doc) // 1024} KB)")
    if "--artifact" in argv:
        p = Path(argv[argv.index("--artifact") + 1])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(head + rest)
        print(f"wrote {p} ({len(head + rest) // 1024} KB)")


if __name__ == "__main__":
    main(sys.argv[1:])
