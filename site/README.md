# universalpaper.org

`python3 site/build_site.py` builds the public website into `site/dist/` (ignored by git). The `Website` workflow builds it on every push to `main` and deploys it to GitHub Pages at https://universalpaper.org.

| Source | Becomes |
|---|---|
| `explorer/index.html` | `/` (home and Playground) |
| `site/src/developers.html` | `/developers/` (the developer explainer) |
| `site/content/faq.py` | `/faq/`, plus the FAQ in `llms.txt` and FAQPage structured data |
| `spec/**/*.md`, `DESIGN_NOTES.md` | `/spec/...` pages and the raw `.md` next to each |
| generated | `/license/`, `sitemap.xml`, `robots.txt`, `llms.txt`, `llms-full.txt`, `404.html`, icons, `CNAME` |

The build only reads its inputs. It adds titles, descriptions, canonical URLs, Open Graph and JSON-LD, rewrites links to site paths, and appends the license strip to every footer. `--og` re-renders `assets-cache/og-image.png` (needs Node and Playwright); otherwise the committed image is used. Requires `pip install markdown pillow`.

Website text is CC BY 4.0; the build script is Apache-2.0.
