// The live proving ground must pass every invariant on a fixed set of seeds (the Explorer runs endless random ones).
// Usage: node tests/js_lab.mjs [runs]
import { readFileSync, readdirSync } from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const root = new URL("..", import.meta.url).pathname;
require(root + "explorer/src/up-crypto.js"); require(root + "explorer/src/up-engine.js");
const UP = require(root + "explorer/src/up-lab.js");
const terms = {};
for (const f of readdirSync(root + "spec/06-terms")) if (f.endsWith(".json")) { const t = JSON.parse(readFileSync(root + "spec/06-terms/" + f, "utf8")); terms[t.id] = t; }
const N = +process.argv[2] || 60; let bad = 0; const seen = {};
for (let i = 0; i < N; i++) {
  const r = UP.lab.runOne("ci-" + i, terms);
  for (const x of r.invariants) { seen[x.id] = (seen[x.id] || 0) + 1; if (!x.ok) { bad++; console.log(`FAIL seed ci-${i} ${x.id}: ${x.detail}`); } }
}
const missing = Object.keys(UP.lab.INVARIANTS).filter(k => !seen[k]);
if (missing.length) { bad++; console.log("never exercised: " + missing.join(", ")); }
console.log(`${N} generated runs, ${bad} failures; invariant checks: ${JSON.stringify(seen)}`);
process.exit(bad ? 1 : 0);
