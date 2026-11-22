// Conformance: the JavaScript engine must reproduce the Python reference interpreter exactly.
// Usage: node tests/js_conformance.mjs FIXTURES.json   (fixtures from tools/dump_conformance.py)
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
require("../explorer/src/up-crypto.js");
const UP = require("../explorer/src/up-engine.js");

const fx = JSON.parse(readFileSync(process.argv[2], "utf8"));
let failures = 0, checks = 0;
function diff(a, b, path, out) {
  if (out.length > 8) return;
  if (a === b) return;
  if (typeof a !== typeof b || a === null || b === null || typeof a !== "object" || Array.isArray(a) !== Array.isArray(b)) {
    out.push(`${path}: python=${JSON.stringify(a)?.slice(0, 300)} js=${JSON.stringify(b)?.slice(0, 300)}`); return;
  }
  if (Array.isArray(a)) {
    if (a.length !== b.length) out.push(`${path}: length python=${a.length} js=${b.length}`);
    for (let i = 0; i < Math.min(a.length, b.length); i++) diff(a[i], b[i], `${path}[${i}]`, out);
    return;
  }
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  for (const k of keys) {
    if (!(k in a)) out.push(`${path}.${k}: missing in python, js=${JSON.stringify(b[k])?.slice(0, 200)}`);
    else if (!(k in b)) out.push(`${path}.${k}: missing in js, python=${JSON.stringify(a[k])?.slice(0, 200)}`);
    else diff(a[k], b[k], `${path}.${k}`, out);
  }
}
function expect(name, a, b) {
  checks++;
  const out = []; diff(a, b, name, out);
  if (out.length) { failures++; console.log(`FAIL ${name}\n  ` + out.join("\n  ")); }
}

// 1. Signature: same seed, same key, same deterministic signature.
const s = fx.signature, k = UP.Key.fromSeed(s.seed);
expect("signature.public", s.public, k.public);
expect("signature.sig", s.sig, k.signObj(s.object).sig);
expect("signature.verifies", true, UP.verifySig(s.public, s.sig, s.object));

// 2. Traces: every step, check, reason, state hash, world hash, and derived snapshot.
let steps = 0;
const t0 = Date.now();
for (const t of fx.traces) {
  const js = UP.makeTrace(t.reference, t.evaluators, t.meta, t.final_at);
  const exp = { ...t.expected }; delete exp.generated_by; delete js.generated_by;
  expect(`trace[${t.meta.title}]`, exp, js);
  steps += t.expected.steps.length;
}

// 3. Renders and validity of every agreement.
for (const r of fx.renders) {
  const b = new UP.Bundle(fx.bundles[r.bundle]);
  const ev = new UP.Evaluator(b);
  const ch = b.chain_list[r.chain];
  const ag = ev.agreement(ev.stateAt(UP.contentHash(ch[0]))) || ch[0].body.agreement;
  expect(`render[${r.bundle}#${r.chain}].hash`, r.agreement_hash, UP.contentHash(ag));
  expect(`render[${r.bundle}#${r.chain}].text`, r.text, UP.renderAgreement(b, ag));
  expect(`render[${r.bundle}#${r.chain}].issues`, r.issues, UP.agreementIssues(b, ag));
}
// 4. Simulations (hypothetical events run forward, Mandates still enforced).
fx.simulations.forEach((sm, i) => expect(`simulation[${i}]`, sm.expected, UP.simulate(sm.data, sm.events, sm.at)));
console.log(`${checks - failures}/${checks} conformance checks passed (${fx.traces.length} traces, ${steps} steps, ${fx.renders.length} renders) in ${Date.now() - t0} ms`);
process.exit(failures ? 1 : 0);
