// Differential oracle: runs a batch of primitive operations on the JavaScript engine so the
// Python tests can compare results with the reference interpreter.
// Usage: node tests/js_oracle.mjs OPS.json   (prints a JSON array of results, one per op)
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
require("../explorer/src/up-crypto.js");
const UP = require("../explorer/src/up-engine.js");

function run(op) {
  try {
    switch (op.op) {
      case "jcs": return { ok: UP.jcsString(op.value) };
      case "hash": return { ok: UP.contentHash(op.value) };
      case "verify": return { ok: UP.verifySig(op.pub, op.sig, op.obj) };
      case "valid_key": return { ok: UP.validKey(op.pub) };
      case "sign": return { ok: UP.Key.fromSeed(op.seed).signObj(op.obj) };
      case "time": UP.parseTime(op.value); return { ok: true };
      case "add_period": return { ok: UP.addPeriod(op.t, op.p, op.k) };
      case "dec": return { ok: UP.decStr(UP.dec(op.value)) };
      case "mul_round": return { ok: UP.decStr(UP.dec(op.a).mul(UP.dec(op.b)).round(op.rounding)) };
      case "sum_mul_round": {
        let t = UP.dec("0");
        for (const v of op.values) t = t.add(UP.dec(v));
        return { ok: UP.decStr(t.mul(UP.dec(op.rate)).round(op.rounding)) };
      }
      case "typecheck": return { ok: UP.typeKnown(op.type) ? UP.typeCheck(op.type, op.value, op.path) : "unknown type" };
      case "agreement_issues": {
        const b = new UP.Bundle(op.bundle);
        return { ok: UP.agreementIssues(b, op.agreement) };
      }
      default: return { error: "unknown op " + op.op };
    }
  } catch (e) {
    return { error: true };
  }
}

const ops = JSON.parse(readFileSync(process.argv[2], "utf8"));
process.stdout.write(JSON.stringify(ops.map(run)));
