# universalpaper.org

`python3 site/build_site.py` builds the public website into `site/dist/` (ignored by git). The `Website` workflow builds it on every push to `main` and deploys it to GitHub Pages at https://universalpaper.org.

The look is the v7 design: Hedvig Letters Serif, Funnel Sans and Recursive (self-hosted, SIL OFL 1.1), a warm canvas with navy, coral, lilac, mint and sun accents, generative "flow field" art, a ⌘K site search and a phone menu. It is light only.

| Source | Becomes |
|---|---|
| `site/theme/site.css`, `site.js`, `fonts/`, `icons/` | `/assets/...` (shared by every page) |
| `site/layout.py` | the shared header (three dropdown groups, Language, Build and Research, plus FAQ; the grouped phone menu below 1100 px), footer, search dialog and document layout, and the Markdown post-processing (numbered sections, axiom checks, JSON highlighting, tables of contents) |
| `site/theme/pages/home.html` | `/` (figures filled from `explorer/conformance-results.json` and `AUDIT.md`, the Term rail from `spec/06-terms/*.json`) |
| `site/theme/pages/developers.html` | `/developers/` |
| `site/theme/pages/spec.html`, `integrations.html`, `license.html` | `/spec/`, `/integrations/` (cards generated), `/license/` |
| `explorer/index.html` | `/playground/app.html`, framed by `/playground/` (old `/#playground` links redirect there) |
| `site/content/faq.py` | `/faq/`, plus the FAQ in `llms.txt` and FAQPage structured data |
| `spec/**/*.md`, `DESIGN_NOTES.md` | `/spec/...` pages and the raw `.md` next to each; `/spec/terms/` adds a filterable grid of the Terms |
| `docs/integrations/*.md` | `/integrations/...` pages, plus `/integrations/index.json` |
| `site/research_library.py`, `research_schemas.py`, `research.py`, `site/theme/research/` | `/research/` (not part of the language): the index, one page, `entry.json` and `.md` per entry, `index.json`, `feed.xml`, the four schemas at their `$id` under `/research/schema/0/`, and the example files at `/research/query-test-vectors/` (served byte for byte). Add an entry by adding a dict to `ENTRIES`; the build stops on a bad kind, topic or status. `--research-sample N` adds sample rows to check the layout at scale; that build is noindex and must never be published |
| `examples/integrations/fingerprint-coordination/demo/index.html` | `/integrations/fingerprint-coordination/demo/` (its `<main>` and scripts, inside the site chrome) |
| generated | `sitemap.xml`, `robots.txt`, `llms.txt`, `llms-full.txt`, `404.html`, `assets/search-index.js`, icons, `CNAME` |

Page fragments in `site/theme/pages/` are an optional `<style>`, one `<main id="main">` and optional `<script>`s; `{{NAME}}` placeholders are filled by the build, which fails if one is left or if a fragment stops linking a page it must list. `tests/test_site_pages.py` builds the whole site and checks every page, internal link, search entry and stated hash. After adding tests, rerun `python3 tools/build_explorer.py --run-tests` so the home page figures match.

The build only reads its inputs. `--og` re-renders `assets-cache/og-image.png` (needs Node and Playwright); otherwise the committed image is used. Requires `pip install markdown pillow`.

Website text is CC BY 4.0; the build script is Apache-2.0. The fonts are SIL OFL 1.1 (texts in `site/theme/licenses/`, served at `/licenses/`).
