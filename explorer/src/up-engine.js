/* Universal Paper — JavaScript engine, part 2: the transition function, clause forms, derived values,
 * rendering, simulation, and traces. A faithful port of src/universal_paper/{engine,report,render,simulate,trace}.py.
 * The conformance harness (tests/js_conformance.mjs) requires this file to reproduce every Python trace exactly.
 * Requires up-crypto.js to be loaded first. Licensed Apache-2.0. */
(function (root) {
  "use strict";
  var UP = root.UP || (typeof require !== "undefined" ? require("./up-crypto.js") : null);
  if (!UP) throw new Error("load up-crypto.js first");
  var SPEC = UP.SPEC, SEALED = UP.SEALED, ch = UP.contentHash, addPeriod = UP.addPeriod;

  var ROLES = ["aggregator", "supplier", "member"];
  var KINDS = ["propose", "accept", "attest"];
  var FORMS = ["Window", "Exit", "Selection", "Valuation", "Duty", "Link"];
  var STRUCTURAL_TYPES = ["Time", "Period", "Role", "[Role]", "ChainId", "Hash", "int", "Rounding"];
  var AXIOM_LABELS = {
    A1: "Composition", A2: "Unanimity", A3: "Chained transitions", A4: "Determinism", A5: "Non-retroactivity",
    A6: "Value neutrality", A7: "Role symmetry", A8: "Rendering binding", A9: "Bounded delegation",
    A10: "Verifiable confidentiality", A11: "Closed evidence", A12: "Single attribution", A13: "Resolved precedence",
    "R-propose": "Rule: propose", "R-accept": "Rule: accept", "R-attest": "Rule: attest",
    "F-Link": "Form: Link", "F-Exit": "Form: Exit", "F-Selection": "Form: Selection", "F-Duty": "Form: Duty"
  };

  // ---- Python-compatible helpers (so reasons read identically) ------------------
  function isObj(x) { return !!x && typeof x === "object" && !Array.isArray(x); }
  function has(o, k) { return isObj(o) && Object.prototype.hasOwnProperty.call(o, k); }
  function get(o, k, d) { return has(o, k) ? o[k] : d; }
  function truthy(x) {
    if (x === undefined || x === null || x === false || x === 0 || x === "") return false;
    if (Array.isArray(x)) return x.length > 0;
    if (x instanceof Set || x instanceof Map) return x.size > 0;
    if (isObj(x) && x !== SEALED) return Object.keys(x).length > 0;
    return true;
  }
  function or() { for (var i = 0; i < arguments.length - 1; i++) if (truthy(arguments[i])) return arguments[i]; return arguments[arguments.length - 1]; }
  function pyStrRepr(s) {
    var q = s.indexOf("'") >= 0 && s.indexOf('"') < 0 ? '"' : "'", out = q;
    for (var i = 0; i < s.length; i++) {
      var c = s[i], n = s.charCodeAt(i);
      if (c === "\\") out += "\\\\"; else if (c === q) out += "\\" + q;
      else if (c === "\n") out += "\\n"; else if (c === "\r") out += "\\r"; else if (c === "\t") out += "\\t";
      else if (n < 0x20 || n === 0x7f) out += "\\x" + ("0" + n.toString(16)).slice(-2);
      else out += c;
    }
    return out + q;
  }
  function repr(x) {
    if (x === undefined || x === null) return "None";
    if (x === true) return "True";
    if (x === false) return "False";
    if (x === SEALED) return "sealed";
    if (typeof x === "number") return String(x);
    if (typeof x === "string") return pyStrRepr(x);
    if (Array.isArray(x)) return "[" + x.map(repr).join(", ") + "]";
    if (isObj(x)) return "{" + Object.keys(x).map(function (k) { return pyStrRepr(k) + ": " + repr(x[k]); }).join(", ") + "}";
    return String(x);
  }
  function str(x) { return typeof x === "string" ? x : repr(x); }
  // json.dumps(x, sort_keys=True, separators=(",", ":")) with ensure_ascii, as engine.canon_key
  function canonKey(x) {
    if (x === null || x === undefined) return "null";
    if (x === true) return "true";
    if (x === false) return "false";
    if (typeof x === "number") return String(x);
    if (typeof x === "string") {
      var o = '"';
      for (var i = 0; i < x.length; i++) {
        var c = x[i], n = x.charCodeAt(i);
        if (c === '"') o += '\\"'; else if (c === "\\") o += "\\\\"; else if (c === "\n") o += "\\n"; else if (c === "\r") o += "\\r";
        else if (c === "\t") o += "\\t"; else if (c === "\b") o += "\\b"; else if (c === "\f") o += "\\f";
        else if (n < 0x20 || n > 0x7e) o += "\\u" + ("000" + n.toString(16)).slice(-4);
        else o += c;
      }
      return o + '"';
    }
    if (Array.isArray(x)) return "[" + x.map(canonKey).join(",") + "]";
    var ks = Object.keys(x).sort(cmpStr);
    return "{" + ks.map(function (k) { return canonKey(k) + ":" + canonKey(x[k]); }).join(",") + "}";
  }
  function cmpStr(a, b) { return a < b ? -1 : a > b ? 1 : 0; }
  function sorted(xs) { return Array.from(xs).sort(cmpStr); }
  function eq(a, b) { return canonKey(a) === canonKey(b); }
  function clone(x) { return x === undefined ? x : JSON.parse(JSON.stringify(x)); }
  function asList(x) { return Array.isArray(x) ? x : [x]; }
  function uniq(xs) { return Array.from(new Set(xs)); }
  function setOf(xs) { return new Set(xs || []); }
  function inter(a, b) { var o = new Set(); a.forEach(function (x) { if (b.has(x)) o.add(x); }); return o; }
  function subsetEq(a, b) { var ok = true; a.forEach(function (x) { if (!b.has(x)) ok = false; }); return ok; }

  // ---- Checks -------------------------------------------------------------------
  function Reject(msg) { this.message = msg; }
  function Checks() { this.items = []; }
  Checks.prototype.check = function (id, rule, ok, yes, no) {
    ok = !!ok;
    this.items.push({ id: id, rule: rule, passed: ok, reason: ok ? yes : no });
    if (!ok) throw new Reject(no);
  };
  function checkJson(c) { return { id: c.id, rule: c.rule, label: AXIOM_LABELS[c.rule] || c.rule, passed: c.passed, reason: c.reason }; }

  // ---- Bundle -------------------------------------------------------------------
  function Bundle(data) {
    var self = this;
    this.data = data;
    this.terms = new Map(); (data.terms || []).forEach(function (t) { self.terms.set(ch(t), t); });
    this.mandates = new Map(); (data.mandates || []).forEach(function (m) { self.mandates.set(ch(m), m); });
    this.chain_list = (data.chains || []).map(function (c) { return c.slice(); });
    this.chains = new Map(); this.chain_pos = new Map();
    this.chain_list.forEach(function (c, i) { if (c.length) { var id = ch(c[0]); self.chains.set(id, c); self.chain_pos.set(id, i); } });
    this.disclosures = new Map();
    (data.disclosures || []).forEach(function (d) { if (isObj(d) && "seal" in d && UP.opens(d, { seal: d.seal })) self.disclosures.set(d.seal, d); });
    this.agreements = new Map();
    this.chain_list.forEach(function (c) {
      c.forEach(function (e) {
        var ag = isObj(e) && isObj(e.body) ? e.body.agreement : undefined;
        if (isObj(ag)) { try { self.agreements.set(ch(ag), ag); } catch (x) { /* not hashable */ } }
      });
    });
  }
  Bundle.prototype.reveal = function (x) {
    if (UP.isSeal(x)) { var d = this.disclosures.get(x.seal); return d ? d.value : SEALED; }
    return x;
  };

  // ---- Agreement helpers ----------------------------------------------------------
  function parties(ag) { return get(ag, "parties", []); }
  function partyKeys(ag) { return new Set(parties(ag).map(function (p) { return p.party.key; })); }
  function rolesOf(ag, key) { return new Set(parties(ag).filter(function (p) { return p.party.key === key; }).map(function (p) { return p.role; })); }
  function keysWithRole(ag, role) { if (!isObj(ag)) throw new TypeError("no agreement"); return sorted(parties(ag).filter(function (p) { return p.role === role; }).map(function (p) { return p.party.key; })); }
  function resolve(x, params) {
    if (isObj(x)) {
      var ks = Object.keys(x);
      if (ks.length === 1 && ks[0] === "param") { if (!has(params, x.param)) throw new Error("KeyError: " + repr(x.param)); return params[x.param]; }
      var o = {}; ks.forEach(function (k) { o[k] = resolve(x[k], params); }); return o;
    }
    if (Array.isArray(x)) return x.map(function (v) { return resolve(v, params); });
    return x;
  }
  function CF(clause, term, form) { this.clause = clause; this.term = term; this.form = form; this.name = clause.n; this.kind = form.form; this.tid = term.id; }
  function clauseForms(b, ag) {
    var out = [];
    get(ag, "clauses", []).forEach(function (c) {
      var t = b.terms.get(c.def);
      if (!t) return;
      (t.forms || []).forEach(function (f) { out.push(new CF(c, t, resolve(f, get(c, "params", {})))); });
    });
    return out;
  }
  function findClause(ag, name) { return get(ag, "clauses", []).find(function (c) { return c.n === name; }) || null; }

  // ---- Precedence -------------------------------------------------------------------
  function overClosure(ag) {
    var direct = new Map(); get(ag, "clauses", []).forEach(function (c) { direct.set(c.n, new Set(get(c, "over", []))); });
    var closure = new Map();
    direct.forEach(function (_, n) {
      var seen = new Set(), stack = Array.from(direct.get(n));
      while (stack.length) { var m = stack.pop(); if (seen.has(m)) continue; seen.add(m); stack.push.apply(stack, Array.from(direct.get(m) || [])); }
      closure.set(n, seen);
    });
    return closure;
  }
  function valItems(cf) {
    var src = get(cf.form, "source", {});
    if (has(src, "table")) return new Set(src.table.map(function (r) { return canonKey(r.item); }));
    return new Set(get(cf.form, "items", []).map(canonKey));
  }
  function during(cf) { var d = cf.form.during; return d ? [d.start, d.end] : null; }
  function intersects(a, b) { if (!a || !b) return true; return a[0] < b[1] && b[0] < a[1]; }
  function within(a, b) { if (!b) return true; if (!a) return false; return b[0] <= a[0] && a[1] <= b[1]; }
  function conflictKey(cf) {
    if (cf.kind === "Selection") return canonKey(["Selection", get(cf.form, "subject", null), get(cf.form, "options", null)]);
    if (cf.kind === "Duty") return canonKey(["Duty", get(cf.form, "duty", null), get(cf.form, "obligor", null), get(cf.form, "obligee", null)]);
    return null;
  }
  function governs(x, y, closure) {
    if ((closure.get(x.name) || new Set()).has(y.name)) return true;
    if (y.name !== x.name && (closure.get(y.name) || new Set()).has(x.name)) return false;
    if (x.kind === "Valuation" && y.kind === "Valuation") {
      var xi = valItems(x), yi = valItems(y), xd = during(x), yd = during(y);
      var proper = subsetEq(xi, yi) && xi.size < yi.size;
      if (subsetEq(xi, yi) && within(xd, yd) && (proper || (!eq(xd, yd) && within(xd, yd)))) return true;
    }
    return false;
  }
  function precedenceIssues(b, ag) {
    var issues = [], closure = overClosure(ag), names = new Set(get(ag, "clauses", []).map(function (c) { return c.n; }));
    get(ag, "clauses", []).forEach(function (c) {
      get(c, "over", []).forEach(function (o) { if (!names.has(o)) issues.push("clause " + repr(c.n) + " declares precedence over unknown clause " + repr(o)); });
    });
    closure.forEach(function (s, n) { if (s.has(n)) issues.push("precedence ('over') is circular through clause " + repr(n)); });
    if (issues.length) return issues;
    var cfs = clauseForms(b, ag);
    for (var i = 0; i < cfs.length; i++) for (var j = i + 1; j < cfs.length; j++) {
      var x = cfs[i], y = cfs[j], overlap;
      if (x.name === y.name || x.kind !== y.kind) continue;
      if (x.kind === "Valuation") overlap = inter(valItems(x), valItems(y)).size > 0 && intersects(during(x), during(y));
      else { var k = conflictKey(x); overlap = k !== null && k === conflictKey(y); }
      if (overlap && !(governs(x, y, closure) || governs(y, x, closure)))
        issues.push("clauses " + repr(x.name) + " and " + repr(y.name) + " conflict and neither takes precedence (no 'over' and neither is strictly more specific)");
    }
    return issues;
  }

  // ---- Value types (port of src/universal_paper/typecheck.py; reasons must match) ----
  var TC_ATOMS = ["Time", "Period", "Decimal", "Rate", "Amount", "Identifier", "Hash", "ChainId", "Role", "Rounding", "string", "Name", "int"];
  var TC_SEALABLE = ["Amount", "Rate", "Decimal", "string"];
  var TC_UNITS = ["day", "month", "quarter", "year"], TC_MODES = ["half-even", "half-up", "down", "up"];
  var TC_MAX_INT = 9007199254740991;
  var tcCache = new Map();
  function tcParse(text) {
    if (typeof text !== "string") throw new Error("not a type");
    if (tcCache.has(text)) return tcCache.get(text);
    var re = / *(?:("[^"]*")|(<?[A-Za-z_][A-Za-z0-9_]*>?)|([\[\]{}:,|]))/y, toks = [], i = 0;
    while (i < text.length) {
      if (/^ *$/.test(text.slice(i))) break;
      re.lastIndex = i; var m = re.exec(text);
      if (!m) throw new Error("cannot read type");
      toks.push(m[1] || m[2] || m[3]); i = re.lastIndex;
    }
    var pos = 0;
    function peek() { return pos < toks.length ? toks[pos] : null; }
    function take(exp) { var t = peek(); if (t === null || (exp !== undefined && t !== exp)) throw new Error("cannot read type"); pos++; return t; }
    function union() { var alts = [atom()]; while (peek() === "|") { take("|"); alts.push(atom()); } return alts.length === 1 ? alts[0] : ["union", alts]; }
    function atom() {
      var t = take();
      if (t[0] === '"') return ["lit", t.slice(1, -1)];
      if (t === "[") { var inner = union(); take("]"); return ["list", inner]; }
      if (t === "{") {
        var k = take();
        if (k[0] === "<" && k[k.length - 1] === ">") { take(":"); var v = union(); take("}"); return ["map", v]; }
        var fields = [];
        for (;;) {
          if (!/^[A-Za-z_][A-Za-z0-9_]*$/.test(k)) throw new Error("cannot read type");
          take(":"); fields.push([k, union()]);
          if (peek() === ",") { take(","); k = take(); continue; }
          take("}"); return ["record", fields];
        }
      }
      if (TC_ATOMS.indexOf(t) >= 0) return ["atom", t];
      throw new Error("unknown type");
    }
    var node = union();
    if (pos !== toks.length) throw new Error("cannot read type");
    tcCache.set(text, node);
    return node;
  }
  function tcKnown(text) { try { tcParse(text); return typeof text === "string"; } catch (e) { return false; } }
  function tcIsInt(v) { return typeof v === "number" && Number.isInteger(v); }
  function tcDecOk(v) { return typeof v === "string" && v.length <= UP.MAX_DECIMAL_LEN && /^-?(0|[1-9][0-9]*)(\.[0-9]+)?$/.test(v); }
  function tcKeysAre(v, names) { return isObj(v) && eq(sorted(Object.keys(v)), sorted(names)); }
  function tcAtom(name, v, path) {
    if (UP.isSeal(v)) return TC_SEALABLE.indexOf(name) >= 0 ? null : path + " is structural (" + name + ") and may not be sealed";
    var ok, what;
    if (name === "Time") { ok = (function () { try { UP.parseTime(v); return true; } catch (e) { return false; } })(); what = "a Time (YYYY-MM-DDThh:mm:ssZ)"; }
    else if (name === "Period") { ok = tcKeysAre(v, ["unit", "count"]) && TC_UNITS.indexOf(v.unit) >= 0 && tcIsInt(v.count) && v.count >= 1 && v.count <= UP.MAX_PERIOD_COUNT; what = "a Period (unit day, month, quarter or year; count from 1 to " + UP.MAX_PERIOD_COUNT + ")"; }
    else if (name === "Decimal" || name === "Rate") { ok = tcDecOk(v); what = "a Decimal string of at most " + UP.MAX_DECIMAL_LEN + " characters"; }
    else if (name === "Amount") { ok = tcKeysAre(v, ["value", "currency"]) && tcDecOk(v.value) && typeof v.currency === "string" && /^[A-Z]{3}$/.test(v.currency); what = "an Amount ({value: Decimal, currency: three-letter code})"; }
    else if (name === "Identifier") { ok = tcKeysAre(v, ["scheme", "id"]) && typeof v.scheme === "string" && v.scheme !== "" && ((typeof v.id === "string" && v.id !== "") || UP.isSeal(v.id)); what = "an Identifier ({scheme: string, id: string})"; }
    else if (name === "Hash" || name === "ChainId") { ok = typeof v === "string" && /^sha256:[0-9a-f]{64}$/.test(v); what = "a hash (sha256: and 64 lowercase hex digits)"; }
    else if (name === "Role") { ok = typeof v === "string" && ROLES.indexOf(v) >= 0; what = "a role"; }
    else if (name === "Rounding") { ok = tcKeysAre(v, ["scale", "mode"]) && tcIsInt(v.scale) && v.scale >= 0 && v.scale <= UP.MAX_ROUNDING_SCALE && TC_MODES.indexOf(v.mode) >= 0; what = "a Rounding (scale from 0 to " + UP.MAX_ROUNDING_SCALE + "; mode half-even, half-up, down or up)"; }
    else if (name === "string") { ok = typeof v === "string"; what = "a string"; }
    else if (name === "Name") { ok = typeof v === "string" && v !== ""; what = "a non-empty name"; }
    else { ok = tcIsInt(v) && v >= 0 && v <= TC_MAX_INT; what = "a non-negative integer"; }
    return ok ? null : path + " must be " + what;
  }
  function tcCheck(node, v, path) {
    var kind = node[0], i, err;
    if (kind === "atom") return tcAtom(node[1], v, path);
    if (UP.isSeal(v)) return path + " is structural and may not be sealed";
    if (kind === "lit") return v === node[1] ? null : path + ' must be "' + node[1] + '"';
    if (kind === "list") {
      if (!Array.isArray(v)) return path + " must be a list";
      for (i = 0; i < v.length; i++) { err = tcCheck(node[1], v[i], path + "[" + i + "]"); if (err) return err; }
      return null;
    }
    if (kind === "map") {
      if (!isObj(v) || !Object.keys(v).length) return path + " must be a non-empty object";
      var ks = sorted(Object.keys(v));
      for (i = 0; i < ks.length; i++) {
        if (ks[i] === "") return path + " has an empty key";
        err = tcCheck(node[1], v[ks[i]], path + "." + ks[i]); if (err) return err;
      }
      return null;
    }
    if (kind === "record") {
      var names = node[1].map(function (f) { return f[0]; });
      if (!tcKeysAre(v, names)) return path + " must have exactly the fields " + names.join(", ");
      for (i = 0; i < node[1].length; i++) { err = tcCheck(node[1][i][1], v[node[1][i][0]], path + "." + node[1][i][0]); if (err) return err; }
      return null;
    }
    for (i = 0; i < node[1].length; i++) if (tcCheck(node[1][i], v, path) === null) return null;
    return path + " does not match any allowed form";
  }
  function typeCheck(text, v, path) { return tcCheck(tcParse(text), v, path === undefined ? "value" : path); }

  // ---- Validation (A1, A6, A10, A13) ------------------------------------------------
  function termIssues(t) {
    var issues = [];
    if (get(t, "type") !== "TermDefinition") issues.push("not a TermDefinition");
    var ps = get(t, "params", {});
    Object.keys(ps).forEach(function (name) {
      var extra = Object.keys(ps[name]).filter(function (k) { return k !== "type" && k !== "doc"; });
      if (extra.length) issues.push("parameter " + repr(name) + " declares " + repr(sorted(extra)) + "; only 'type' and 'doc' are allowed (A6: no defaults)");
      if (!tcKnown(get(ps[name], "type", null))) issues.push("parameter " + repr(name) + " has an unrecognized type " + repr(get(ps[name], "type", null)));
    });
    var cl = get(t, "claims", {});
    Object.keys(cl).forEach(function (ctype) {
      var dd = get(cl[ctype], "data", {});
      Object.keys(dd).forEach(function (fname) { if (!tcKnown(dd[fname])) issues.push("claim " + ctype + " field " + repr(fname) + " has an unrecognized type " + repr(dd[fname])); });
    });
    get(t, "forms", []).forEach(function (f) { if (FORMS.indexOf(get(f, "form")) < 0) issues.push("unknown clause form " + repr(get(f, "form"))); });
    return issues;
  }
  function agreementIssues(b, ag) {
    var out = [];
    if (!isObj(ag) || ag.type !== "Agreement") return [["A1", "the proposed object is not an Agreement"]];
    if (get(ag, "spec") !== SPEC) out.push(["A1", "the Agreement declares spec " + repr(get(ag, "spec")) + ", expected " + repr(SPEC)]);
    var ps = parties(ag);
    if (!ps.length) out.push(["A1", "the Agreement has no parties"]);
    var order = ps.map(function (p) { return [get(p, "role"), get(get(p, "party", {}), "key")]; });
    var srt = order.slice().sort(function (a, c) { return cmpStr(a[0], c[0]) || cmpStr(a[1], c[1]); });
    if (!eq(order, srt)) out.push(["A1", "parties are not sorted by (role, key)"]);
    if (uniq(order.map(canonKey)).length !== order.length) out.push(["A1", "a party is listed twice in the same role"]);
    order.forEach(function (rk) {
      if (ROLES.indexOf(rk[0]) < 0) out.push(["A1", "unknown role " + repr(rk[0])]);
      if (!UP.validKey(rk[1])) out.push(["A1", "malformed party key " + repr(rk[1])]);
    });
    var names = get(ag, "clauses", []).map(function (c) { return get(c, "n"); });
    if (uniq(names).length !== names.length) out.push(["A1", "clause names are not unique"]);
    var windows = 0, links = 0;
    get(ag, "clauses", []).forEach(function (c) {
      var t = b.terms.get(get(c, "def"));
      if (!t) { out.push(["A1", "clause " + repr(get(c, "n")) + " pins a Term definition that is not in the bundle"]); return; }
      if (get(t, "id") !== get(c, "term")) out.push(["A1", "clause " + repr(get(c, "n")) + " names " + repr(get(c, "term")) + " but pins " + repr(get(t, "id"))]);
      if (get(t, "spec") !== get(ag, "spec")) out.push(["A1", "clause " + repr(get(c, "n")) + " uses a Term from spec " + repr(get(t, "spec"))]);
      termIssues(t).forEach(function (i) { out.push(["A6", "Term " + str(get(t, "id")) + ": " + i]); });
      var declared = Object.keys(get(t, "params", {})), bound = Object.keys(get(c, "params", {}));
      var missing = declared.filter(function (k) { return bound.indexOf(k) < 0; }), extra = bound.filter(function (k) { return declared.indexOf(k) < 0; });
      if (missing.length || extra.length) out.push(["A1", "clause " + repr(get(c, "n")) + ": parameters missing " + repr(sorted(missing)) + " / unexpected " + repr(sorted(extra))]);
      var cp = get(c, "params", {});
      Object.keys(cp).forEach(function (pname) {
        var pval = cp[pname], ptype = get(get(get(t, "params", {}), pname, {}), "type", "");
        if (UP.containsSeal(pval) && STRUCTURAL_TYPES.indexOf(ptype) >= 0) out.push(["A10", "clause " + repr(get(c, "n")) + ": parameter " + repr(pname) + " (" + ptype + ") is structural and may not be sealed"]);
        else if (ptype === "Role" && ROLES.indexOf(pval) < 0) out.push(["A1", "clause " + repr(get(c, "n")) + ": " + repr(pval) + " is not a role"]);
        else if (ptype === "[Role]" && !(Array.isArray(pval) && pval.every(function (r) { return ROLES.indexOf(r) >= 0; }))) out.push(["A1", "clause " + repr(get(c, "n")) + ": " + repr(pname) + " must be a list of roles"]);
        else if (has(get(t, "params", {}), pname) && tcKnown(ptype)) {
          var terr = typeCheck(ptype, pval, pname);
          if (terr) out.push(["A1", "clause " + repr(get(c, "n")) + ": parameter " + terr]);
        }
      });
      get(t, "forms", []).forEach(function (f) { if (get(f, "form") === "Window") windows++; if (get(f, "form") === "Link") links++; });
    });
    if (windows > 1) out.push(["A1", "more than one Window clause"]);
    if (links > 1) out.push(["A1", "more than one Link clause"]);
    if (!out.length) precedenceIssues(b, ag).forEach(function (i) { out.push(["A13", i]); });
    return out;
  }

  // ---- Mandates -----------------------------------------------------------------------
  function boundOk(b, bound, value) {
    if (get(bound, "any") === true) return [true, "any value allowed"];
    if (UP.isSeal(value) || UP.containsSeal(value)) return [false, "the value is sealed, so it cannot be checked against the bound (rule 6: bounded values must be unsealed)"];
    if (has(bound, "in")) {
      var ok = bound["in"].some(function (v) { return canonKey(value) === canonKey(v); });
      return [ok, repr(value) + " " + (ok ? "is" : "is not") + " in the allowed set"];
    }
    if (has(bound, "max_period")) {
      var ref = "2000-01-01T00:00:00Z";
      var ok2 = isObj(value) && addPeriod(ref, value) <= addPeriod(ref, bound.max_period);
      return [ok2, "period " + (ok2 ? "within" : "exceeds") + " the maximum"];
    }
    if (has(bound, "min") || has(bound, "max")) {
      var num = function (v) { if (isObj(v) && "value" in v) return [UP.dec(v.value), get(v, "currency", null)]; return [UP.dec(v), null]; };
      var vc;
      try { vc = num(value); } catch (e) { return [false, repr(value) + " is not a number or amount"]; }
      var sides = ["min", "max"];
      for (var i = 0; i < 2; i++) {
        var side = sides[i];
        if (!has(bound, side)) continue;
        var bc = num(bound[side]);
        if (bc[1] !== vc[1]) return [false, "currency does not match the bound"];
        var c = vc[0].cmp(bc[0]);
        if ((side === "min" && c < 0) || (side === "max" && c > 0))
          return [false, UP.decStr(vc[0]) + " is " + (side === "min" ? "below the minimum" : "above the maximum") + " " + UP.decStr(bc[0])];
      }
      return [true, "within bounds"];
    }
    return [false, "unrecognized bound"];
  }
  function mandateCoverage(b, m, agentKey, E, ctx) {
    if (get(m, "type") !== "Mandate") return [false, "the referenced object is not a Mandate"];
    if (!(UP.validKey(get(m, "principal", null)) && UP.validKey(get(m, "agent", null)) && typeCheck("Time", get(m, "not_before", null)) === null && typeCheck("Time", get(m, "expires", null)) === null))
      return [false, "the Mandate is malformed (its keys or validity times are not well formed)"];
    var psig = get(m, "sigs", []).filter(function (s) { return get(s, "key") === get(m, "principal"); });
    if (!psig.length || !UP.verifySig(m.principal, psig[0].sig, m)) return [false, "the Mandate is not validly signed by its principal"];
    if (get(m, "agent") !== agentKey) return [false, "the signing key is not the Mandate's agent"];
    if (!(m.not_before <= E.at && E.at < m.expires)) return [false, "the Mandate is not in force at " + E.at + " (valid " + m.not_before + " to " + m.expires + ")"];
    var scope = get(m, "scope", {});
    if (get(scope, "kinds", []).indexOf(get(E, "kind")) < 0) return [false, "the Mandate does not allow '" + str(get(E, "kind")) + "' events"];
    var roleAg = ctx.agreement;
    if (roleAg == null || inter(rolesOf(roleAg, m.principal), setOf(get(scope, "roles", []))).size === 0) return [false, "the principal does not hold a role the Mandate allows in this agreement"];
    var chains = get(scope, "chains", null);
    if (chains !== null && chains.indexOf(ctx.chain === undefined ? null : ctx.chain) < 0) return [false, "the Mandate does not cover this agreement's chain"];
    var prop = ctx.proposal;
    if (prop != null) {
      var terms = get(scope, "terms", {}), cl = get(prop, "clauses", []);
      for (var i = 0; i < cl.length; i++) {
        var c = cl[i];
        if (!has(terms, get(c, "term"))) return [false, "the Mandate does not allow Term " + str(get(c, "term"))];
        var bounds = terms[c.term], cp = get(c, "params", {}), pn = Object.keys(cp);
        for (var j = 0; j < pn.length; j++) {
          if (!has(bounds, pn[j])) return [false, "the Mandate sets no bound for " + c.term + " parameter '" + pn[j] + "'"];
          var r = boundOk(b, bounds[pn[j]], cp[pn[j]]);
          if (!r[0]) return [false, c.term + " parameter '" + pn[j] + "': " + r[1]];
        }
      }
    }
    var claim = ctx.claim;
    if (claim != null) {
      var claims = get(scope, "claims", {});
      if (!has(claims, get(claim, "type"))) return [false, "the Mandate does not allow claim " + str(get(claim, "type"))];
      var cb = claims[claim.type], data = get(claim, "data", {}), fn = Object.keys(data);
      for (var k = 0; k < fn.length; k++) {
        if (!has(cb, fn[k])) return [false, "the Mandate sets no bound for claim field '" + fn[k] + "'"];
        var r2 = boundOk(b, cb[fn[k]], data[fn[k]]);
        if (!r2[0]) return [false, "claim field '" + fn[k] + "': " + r2[1]];
      }
    }
    return [true, "the Mandate covers this event"];
  }

  // ---- Evaluator ------------------------------------------------------------------------
  function Evaluator(bundle, unverified) { this.b = bundle; this.unverified = new Set(unverified || []); this._runs = new Map(); }
  var EP = Evaluator.prototype;

  EP.run = function (cid) {
    if (this._runs.has(cid)) return this._runs.get(cid);
    this._runs.set(cid, []);
    var steps = [], S = null, chain = this.b.chains.get(cid) || [];
    for (var i = 0; i < chain.length; i++) {
      var E = chain[i], r = this.apply(S, E), ok = r[0] !== null;
      if (ok) S = r[0];
      var eh; try { eh = ch(E); } catch (e) { eh = null; }
      steps.push({ index: i, event: E, event_hash: eh, accepted: ok, checks: r[1], state: S, reason: r[2] });
    }
    this._runs.set(cid, steps);
    return steps;
  };
  EP.stateAt = function (cid, t) {
    var S = null;
    this.run(cid).forEach(function (st) { if (st.accepted && (t == null || st.event.at <= t)) S = st.state; });
    return S;
  };
  EP.agreement = function (S) { return S ? (this.b.agreements.get(S.agreement) || null) : null; };

  EP.principals = function (S, E, ck, ctxFor) {
    var out = new Map(), eh = ch(E), sigs = get(E, "sigs", []), self = this;
    ck.check("sigs-present", "A9", Array.isArray(sigs) && sigs.length > 0, "The event carries signatures.", "The event carries no signatures.");
    sigs.forEach(function (s) {
      var key = get(s, "key", "");
      if (!self.unverified.has(eh))
        ck.check("sig-" + key.slice(8, 16), "A9", UP.verifySig(key, get(s, "sig", ""), E),
          "Signature by " + key.slice(0, 16) + "… verifies over the event's hash.",
          "Signature by " + key.slice(0, 16) + "… does not verify: the event was altered after signing, or the signature is missing or forged.");
      if (has(s, "mandate")) {
        var m = self.b.mandates.get(s.mandate);
        ck.check("mandate-" + key.slice(8, 16), "A9", m !== undefined, "The agent's Mandate is in the bundle.", "The agent cites a Mandate that is not in the bundle.");
        var r = mandateCoverage(self.b, m, key, E, ctxFor(m.principal));
        ck.check("mandate-cover-" + key.slice(8, 16), "A9", r[0],
          "Agent " + key.slice(0, 16) + "… acts for " + m.principal.slice(0, 16) + "…: " + r[1] + ".",
          "Agent " + key.slice(0, 16) + "… is out of bounds: " + r[1] + ". Out-of-bounds agent actions are invalid by definition.");
        out.set(m.principal, s);
      } else out.set(key, s);
    });
    return out;
  };

  EP.apply = function (S, E) {
    var ck = new Checks();
    try { return [this._apply(S, E, ck), ck.items, ""]; }
    catch (r) {
      if (r instanceof Reject) return [null, ck.items, r.message];
      var msg = (r && r.message) || String(r), nm = (r && r.name) || "Error";
      ck.items.push({ id: "malformed", rule: "A1", passed: false, reason: "The event is malformed: " + nm + ": " + msg });
      return [null, ck.items, "malformed event: " + msg];
    }
  };

  EP._apply = function (S, E, ck) {
    var self = this;
    ck.check("envelope", "A1", isObj(E) && E.type === "Event" && E.spec === SPEC && KINDS.indexOf(E.kind) >= 0,
      "The record is a well-formed Universal Paper event.", "The record is not a well-formed Universal Paper event of this spec version.");
    var kind = E.kind, body = get(E, "body", {}), eh = ch(E);
    if (S === null) {
      ck.check("linkage", "A3", !has(E, "chain") && !has(E, "prev"), "This is a genesis event: it starts a new chain.",
        "This event continues a chain that has no valid starting event in this copy, so it cannot apply.");
      ck.check("genesis-kind", "A3", kind === "propose" && !has(body, "supersedes"), "The genesis event is a proposal.",
        "The first event of a chain must be a proposal of a new agreement.");
    } else {
      ck.check("linkage", "A3", get(E, "chain") === S.chain && get(E, "prev") === ch(S),
        "The event references this chain and the exact prior state hash.",
        "The event does not reference the current state hash: it was built on a different history.");
      ck.check("time", "A5", UP.parseTime(E.at) >= UP.parseTime(S.at), "The event's time is not earlier than the previous event.",
        "The event is backdated (" + E.at + " is before the previous event at " + S.at + "). Past states cannot be altered.");
    }
    UP.parseTime(E.at);
    var cur = this.agreement(S);
    var pend = S && truthy(S.pending) ? (this.b.agreements.get(S.pending.agreement) || null) : null;
    var prop = kind === "propose" ? get(body, "agreement", null) : null;
    var cid = S ? S.chain : eh;
    var targetClaim = null;
    if (kind === "accept" && S && !(truthy(S.pending) && get(body, "target") === S.pending.event)) targetClaim = this._findClaim(S, get(body, "target"));
    function ctxFor(principal) {
      if (kind === "propose") return { agreement: partyKeys(prop || {}).has(principal) ? prop : cur, proposal: prop, chain: S ? S.chain : null };
      if (kind === "accept" && targetClaim === null) return { agreement: pend || cur, proposal: pend, chain: cid };
      if (kind === "accept") return { agreement: cur, claim: { type: targetClaim[1].type, data: targetClaim[1].data }, chain: cid };
      return { agreement: cur, claim: get(body, "claim", null), chain: cid };
    }
    var P = this.principals(S, E, ck, ctxFor);
    ck.check("author", "A9", P.has(get(E, "by")), "A valid signature speaks for the event's author.", "No valid signature speaks for the event's author.");
    var known = new Set([].concat(Array.from(partyKeys(cur || {})), Array.from(partyKeys(pend || {})), Array.from(partyKeys(prop || {}))));
    var unknown = Array.from(P.keys()).filter(function (k) { return !known.has(k); });
    ck.check("signers-known", "A9", !unknown.length, "Every signer is a party to this agreement (directly or through a Mandate).",
      unknown.length ? "Signer " + unknown[0].slice(0, 16) + "… is not a party to this agreement." : "");
    if (kind === "propose") return this._propose(S, E, eh, P, cur, ck);
    if (kind === "accept") return this._accept(S, E, eh, P, pend, cur, targetClaim, ck);
    return this._attest(S, E, eh, P, cur, ck);
  };

  EP._checkAgreement = function (ag, ck, at) {
    agreementIssues(this.b, ag).forEach(function (ri) { ck.check("valid-" + ri[0], ri[0], false, "", "The proposed agreement is invalid: " + ri[1] + "."); });
    ck.check("valid", "A1", true, "The proposed agreement is well formed and uses one spec version (A1, A6).", "");
    ck.check("precedence", "A13", true, "Every conflict between clauses is resolved by explicit precedence or specificity.", "");
    this._checkLink(ag, ck, at);
  };
  EP._checkLink = function (ag, ck, at) {
    var self = this;
    clauseForms(this.b, ag).forEach(function (cf) {
      if (cf.kind !== "Link") return;
      var parent = cf.form.parent;
      ck.check("link-parent", "F-Link", self.b.chains.has(parent), "The parent agreement's chain is in the bundle.", "The parent agreement's chain is not in the bundle.");
      var PS = self.stateAt(parent, at);
      ck.check("link-executed", "F-Link", PS !== null && PS.status === "executed", "The parent agreement is executed.", "The parent agreement is not executed at this time.");
      var pag = self.agreement(PS);
      get(cf.form, "bind", []).forEach(function (role) {
        ck.check("link-bind-" + role, "F-Link", eq(keysWithRole(ag, role), keysWithRole(pag, role)),
          "The parent's " + role + " is a party here in the same role, so it must sign.", "The " + role + " here is not the parent agreement's " + role + ".");
      });
    });
  };
  EP._propose = function (S, E, eh, P, cur, ck) {
    var body = E.body, ag = get(body, "agreement", null), required, S2;
    if (S === null) {
      ck.check("propose-author", "R-propose", partyKeys(ag || {}).has(E.by), "The proposer is a party to the proposed agreement.", "The proposer is not a party to the proposed agreement.");
      this._checkAgreement(ag, ck, E.at);
      required = partyKeys(ag);
      S2 = { type: "State", spec: SPEC, chain: eh, height: 0, status: "proposed", agreement: ch(ag), facts: {} };
    } else {
      ck.check("amend-executed", "R-propose", S.status === "executed", "The current agreement is executed, so it can be amended.", "Only an executed agreement can be amended.");
      ck.check("amend-supersedes", "R-propose", get(body, "supersedes") === S.agreement, "The amendment names the current agreement it replaces.", "The amendment does not supersede the current agreement.");
      ck.check("amend-author", "R-propose", partyKeys(cur).has(E.by), "The proposer is a party to the current agreement.", "The proposer is not a party to the current agreement.");
      this._checkAgreement(ag, ck, E.at);
      required = new Set([].concat(Array.from(partyKeys(ag)), Array.from(partyKeys(cur))));
      S2 = clone(S);
    }
    var pending = { event: eh, agreement: ch(ag), signed: sorted(Array.from(P.keys()).filter(function (k) { return required.has(k); })) };
    if (has(body, "expires")) {
      ck.check("propose-expires", "R-propose", typeCheck("Time", body.expires) === null,
        "The proposal's expiry is a well-formed time.", "The proposal's expiry is not a well-formed time.");
      pending.expires = body.expires;
    }
    S2.pending = pending;
    S2 = this._advance(S2, E, eh);
    return this._maybeExecute(S2, E, ck);
  };
  EP._required = function (S) {
    var req = partyKeys(this.b.agreements.get(S.pending.agreement));
    if (S.status === "executed") partyKeys(this.b.agreements.get(S.agreement)).forEach(function (k) { req.add(k); });
    return req;
  };
  EP._maybeExecute = function (S2, E, ck) {
    var req = this._required(S2), signed = new Set(S2.pending.signed);
    if (subsetEq(req, signed)) {
      var newAg = this.b.agreements.get(S2.pending.agreement);
      this._checkLink(newAg, ck, E.at);
      ck.check("unanimity", "A2", true, "Every required party has now signed the same agreement hash: the agreement is executed.", "");
      if (S2.status === "executed") {
        var old = this.b.agreements.get(S2.agreement), oldT = {}, newT = {};
        old.clauses.forEach(function (c) { oldT[c.n] = c.def; });
        newAg.clauses.forEach(function (c) { newT[c.n] = c.def; });
        var facts = {};
        Object.keys(S2.facts).forEach(function (n) { if (has(newT, n) && newT[n] === get(oldT, n)) facts[n] = S2.facts[n]; });
        S2.facts = facts;
      } else S2.executed_at = E.at;
      S2.status = "executed";
      S2.agreement = S2.pending.agreement;
      delete S2.pending;
    } else {
      ck.check("unanimity", "A2", true, "Signatures recorded: " + inter(signed, req).size + " of " + req.size + " required parties have signed.", "");
    }
    return S2;
  };
  EP._advance = function (S2, E, eh) { S2.height = get(S2, "height", 0) + 1; S2.last = eh; S2.at = E.at; return S2; };
  EP._findClaim = function (S, target) {
    var facts = get(S, "facts", {}), names = Object.keys(facts);
    for (var i = 0; i < names.length; i++) {
      var cs = get(facts[names[i]], "claims", []);
      for (var j = 0; j < cs.length; j++) if (cs[j].event === target) return [names[i], cs[j]];
    }
    return null;
  };
  EP._accept = function (S, E, eh, P, pend, cur, targetClaim, ck) {
    ck.check("accept-chain", "R-accept", S !== null, "The acceptance belongs to an existing chain.", "An acceptance cannot start a chain.");
    var target = get(E.body, "target");
    if (truthy(S.pending) && target === S.pending.event) {
      var req = this._required(S);
      ck.check("accept-required", "R-accept", req.has(E.by), "The accepting party is a required signer of the proposal.", "The accepting party is not a required signer of the proposal.");
      ck.check("accept-new", "R-accept", S.pending.signed.indexOf(E.by) < 0, "The accepting party has not already signed.", "The accepting party has already signed this proposal.");
      var exp = get(S.pending, "expires", null);
      ck.check("accept-unexpired", "R-accept", exp === null || E.at < exp, "The proposal has not lapsed.", "The proposal lapsed at " + exp + ".");
      var S2 = clone(S);
      S2.pending.signed = sorted(new Set(S2.pending.signed.concat(Array.from(P.keys()).filter(function (k) { return req.has(k); }))));
      S2 = this._advance(S2, E, eh);
      return this._maybeExecute(S2, E, ck);
    }
    ck.check("accept-target", "R-accept", targetClaim !== null, "The acceptance acknowledges an earlier attestation in this chain.",
      "The acceptance targets neither the pending proposal nor an attestation in this chain.");
    var cname = targetClaim[0], claim = targetClaim[1];
    var S3 = clone(S);
    var claim2 = S3.facts[cname].claims.find(function (c) { return c.event === target; });
    var ackRoles = this._claimRules(cur, cname)[1].get(claim.type) || new Set();
    var mine = inter(rolesOf(cur, E.by), ackRoles);
    ck.check("ack-role", "R-accept", mine.size > 0, "The acknowledging party holds a role (" + sorted(mine).join(", ") + ") whose acknowledgment this claim needs.",
      "The acknowledging party holds no role whose acknowledgment this claim needs.");
    ck.check("ack-new", "R-accept", claim2.acks.every(function (a) { return a.by !== E.by; }), "The party has not already acknowledged this claim.", "The party has already acknowledged this claim.");
    claim2.acks = claim2.acks.concat([{ by: E.by, at: E.at, event: eh }]).sort(function (a, b) { return cmpStr(a.by, b.by); });
    return this._advance(S3, E, eh);
  };
  EP._claimRules = function (ag, cname) {
    var attest = new Map(), ack = new Map();
    function add(m, k, vals) { if (!m.has(k)) m.set(k, new Set()); var s = m.get(k); (typeof vals === "string" ? vals.split("") : vals).forEach(function (v) { s.add(v); }); }
    clauseForms(this.b, ag).forEach(function (cf) {
      if (cf.name !== cname) return;
      var f = cf.form, tid = cf.tid;
      if (f.form === "Window" && has(f, "renew")) add(attest, tid + "/optout", f.renew.optout_roles);
      else if (f.form === "Exit") {
        add(attest, tid + "/notice", f.holders);
        if (has(f, "requires")) { add(attest, f.requires.claim, f.holders); add(attest, f.requires.unless, ROLES); add(ack, f.requires.unless, f.holders); }
      } else if (f.form === "Selection") { add(attest, tid + "/selects", [f.subject]); add(ack, tid + "/selects", get(f, "ack", [])); }
      else if (f.form === "Valuation" && has(get(f, "source", {}), "reference")) { var r = f.source.reference; add(attest, r.claim, [r.role]); }
      else if (f.form === "Duty") {
        var d = f.discharge;
        add(attest, d.claim, [f.obligor]); add(ack, d.claim, asList(get(d, "ack", [])));
        if (has(f.trigger, "on")) add(attest, f.trigger.on, f.trigger.by);
      }
    });
    return [attest, ack];
  };
  EP._attest = function (S, E, eh, P, cur, ck) {
    ck.check("attest-chain", "R-attest", S !== null && S.status === "executed", "The agreement is executed, so claims can be recorded under it.", "Claims can only be recorded under an executed agreement.");
    var claim = get(E.body, "claim", {}), cname = get(claim, "clause", null), ctype = get(claim, "type", null), data = get(claim, "data", null);
    var clause = findClause(cur, cname);
    ck.check("attest-clause", "R-attest", clause !== null, "The claim is made under clause '" + str(cname) + "' of the current agreement.", "The current agreement has no clause named '" + str(cname) + "'.");
    var term = this.b.terms.get(clause.def);
    if (!term) throw new Error("KeyError: " + repr(clause.def));
    var decl = get(get(term, "claims", {}), ctype, null);
    ck.check("attest-type", "A11", decl !== null, "'" + str(ctype) + "' is a claim type that this clause's Term defines.", "'" + str(ctype) + "' is not a claim type defined by Term " + term.id + ".");
    var declF = sorted(Object.keys(get(decl, "data", {})));
    ck.check("attest-data", "R-attest", isObj(data) && eq(sorted(Object.keys(data)), declF), "The claim's data has exactly the fields its Term defines.",
      "The claim's data fields " + (isObj(data) ? repr(sorted(Object.keys(data))) : str(data)) + " do not match " + repr(declF) + ".");
    var dtypes = get(decl, "data", {}), bad = null, dn = Object.keys(dtypes);
    for (var di = 0; di < dn.length && bad === null; di++)
      bad = tcKnown(dtypes[dn[di]]) ? typeCheck(dtypes[dn[di]], data[dn[di]], dn[di]) : dn[di] + " has an unrecognized type";
    ck.check("attest-data-types", "R-attest", bad === null, "Each data field has the type its Term declares.", "The claim's data does not match its Term: " + bad + ".");
    var rules = this._claimRules(cur, cname), allowed = rules[0].get(ctype) || new Set();
    var mine = inter(rolesOf(cur, E.by), allowed);
    ck.check("attest-role", "A7", mine.size > 0, "The author holds a role allowed to make this claim (" + sorted(mine).join(", ") + ").",
      "The author holds no role allowed to make this claim (allowed: " + (sorted(allowed).join(", ") || "none") + ").");
    var needed = rules[1].get(ctype) || new Set(), acks = [];
    sorted(P.keys()).forEach(function (k) {
      if (k === E.by) return;
      ck.check("cosign-" + k.slice(8, 16), "R-attest", inter(rolesOf(cur, k), needed).size > 0, "The co-signer's signature counts as an acknowledgment.", "A co-signer holds no role whose acknowledgment this claim needs.");
      acks.push({ by: k, at: E.at, event: eh });
    });
    var rec = { event: eh, type: ctype, by: E.by, at: E.at, data: data, acks: acks };
    var S2 = clone(S);
    this._formEffects(S2, E, cur, cname, rec, ck);
    if (!has(S2.facts, cname)) S2.facts[cname] = { claims: [] };
    S2.facts[cname].claims.push(rec);
    return this._advance(S2, E, eh);
  };
  EP._formEffects = function (S2, E, cur, cname, rec, ck) {
    var self = this;
    clauseForms(this.b, cur).forEach(function (cf) {
      if (cf.name !== cname) return;
      var f = cf.form, tid = cf.tid;
      if (f.form === "Exit" && rec.type === tid + "/notice") {
        if (has(f, "requires")) {
          var req = f.requires, claims = get(get(S2.facts, cname, {}), "claims", []), ok = false;
          claims.forEach(function (b) {
            if (b.type !== req.claim || b.by !== rec.by) return;
            var br = get(rec.data, "breach", null);
            if (!(br === null || br === b.event)) return;
            if (addPeriod(b.at, req.age) > rec.at) return;
            var cured = claims.some(function (c) { return c.type === req.unless && get(c.data, "breach") === b.event && c.acks.some(function (a) { return a.by === rec.by; }); });
            if (!cured) ok = true;
          });
          ck.check("exit-requires", "F-Exit", ok, "An earlier breach notice by this party is old enough and has not been acknowledged as cured.",
            "Termination for cause needs an earlier breach notice by this party, older than the cure period and not acknowledged as cured.");
        }
        var end = addPeriod(rec.at, f.notice), prior = get(S2, "ends_at", end);
        S2.ends_at = prior < end ? prior : end;
        ck.check("exit-effect", "F-Exit", true, "Termination takes effect at " + S2.ends_at + ".", "");
      }
      if (f.form === "Selection" && rec.type === tid + "/selects") {
        var opts = self.options(cur, f), opt = get(rec.data, "option", null);
        ck.check("selection-option", "F-Selection", opts.indexOf(opt) >= 0, "'" + str(opt) + "' is one of the named options.", "'" + str(opt) + "' is not one of the named options (" + opts.join(", ") + ").");
      }
      if (f.form === "Duty" && has(f.trigger, "on") && rec.type === f.trigger.on) {
        var lim = get(f.trigger, "limit", null);
        if (truthy(lim)) {
          var n = get(get(S2.facts, cname, {}), "claims", []).filter(function (c) { return c.type === rec.type && addPeriod(c.at, lim.per) > rec.at; }).length;
          ck.check("duty-limit", "F-Duty", n < Number(lim.count), "This request is within the limit of " + str(lim.count) + " per period.", "This request exceeds the limit of " + str(lim.count) + " per period.");
        }
      }
    });
  };

  // ---- Derived values ----------------------------------------------------------------------
  EP.options = function (ag, selForm) {
    var src = selForm.options;
    if (Array.isArray(src)) return src.map(function (o) { return o.name; });
    var ref = src.from, targetAg = ag;
    if (truthy(get(ref, "link"))) {
      var link = clauseForms(this.b, ag).find(function (cf) { return cf.kind === "Link"; });
      if (!link) return [];
      targetAg = this.agreement(this.stateAt(link.form.parent));
    }
    var cfs = clauseForms(this.b, targetAg || {});
    for (var i = 0; i < cfs.length; i++) if (cfs[i].name === ref.clause) {
      var opts = or(get(cfs[i].form, "options"), get(get(cfs[i].form, "source", {}), "options"), []);
      return opts.map(function (o) { return o.name; });
    }
    return [];
  };
  EP.window = function (cid, t) {
    var S = this.stateAt(cid, t), ag = this.agreement(S);
    if (!S || S.status !== "executed") return [null, null];
    var w = clauseForms(this.b, ag).find(function (cf) { return cf.kind === "Window"; }), start, end;
    if (!w) { start = S.executed_at; end = null; }
    else {
      start = w.form.start; end = w.form.end;
      var r = get(w.form, "renew", null);
      if (truthy(r)) {
        // e_k = end + k x period, each computed directly from end (spec/04-inference.md §2, §3.1).
        var optouts = get(get(S.facts, w.name, {}), "claims", []).filter(function (c) { return c.type === w.tid + "/optout"; }), n = 0, e00 = end;
        while (end <= t && (get(r, "max", null) === null || n < Number(r.max))) {
          var e0 = end;
          if (optouts.some(function (c) { return addPeriod(c.at, r.optout_notice) <= e0; })) break;
          n++; end = addPeriod(e00, r.period, n);
        }
      }
    }
    if (truthy(S.ends_at) && (end === null || S.ends_at < end)) end = S.ends_at;
    return [start, end];
  };
  EP.parents = function (cid, t) {
    var ag = this.agreement(this.stateAt(cid, t));
    return clauseForms(this.b, ag || {}).filter(function (cf) { return cf.kind === "Link"; }).map(function (cf) { return cf.form.parent; });
  };
  EP.active = function (cid, t) {
    var S = this.stateAt(cid, t), self = this;
    if (!S || S.status !== "executed") return false;
    var w = this.window(cid, t);
    if (!(w[0] <= t && (w[1] === null || t < w[1]))) return false;
    return this.parents(cid, t).every(function (p) { return self.active(p, t); });
  };
  EP.status = function (cid, t) {
    var S = this.stateAt(cid, t), self = this;
    if (S === null) return "none";
    if (S.status === "proposed") { var exp = get(get(S, "pending", {}), "expires", null); return truthy(exp) && t >= exp ? "lapsed" : "proposed"; }
    var w = this.window(cid, t);
    if (truthy(S.ends_at) && t >= S.ends_at) return "terminated";
    if (w[1] !== null && t >= w[1]) return "expired";
    if (t < w[0]) return "executed";
    if (!this.parents(cid, t).every(function (p) { return self.active(p, t); })) return "suspended";
    return "active";
  };
  EP._acksComplete = function (ag, rec, roles) {
    var last = null, ok = true;
    roles.forEach(function (role) {
      if (!ok) return;
      var hits = rec.acks.filter(function (a) { return rolesOf(ag, a.by).has(role); });
      if (!hits.length) { ok = false; return; }
      var first = hits.map(function (a) { return a.at; }).sort(cmpStr)[0];
      last = last === null || first > last ? first : last;
    });
    if (!ok) return null;
    return truthy(last) ? last : rec.at;
  };
  EP.selection = function (cid, cname, key, t) {
    var S = this.stateAt(cid, t), ag = this.agreement(S), self = this;
    if (!ag) return null;
    var cf = clauseForms(this.b, ag).find(function (x) { return x.name === cname && x.kind === "Selection"; });
    if (!cf) return null;
    var f = cf.form, best = null;
    get(get(S.facts, cname, {}), "claims", []).forEach(function (c, i) {
      if (c.type !== cf.tid + "/selects" || c.by !== key) return;
      var at = self._acksComplete(ag, c, new Set(get(f, "ack", [])));
      if (at === null) return;
      var eff = at;
      if (isObj(get(f, "effective"))) {
        var start = self.window(cid, t)[0], k = 0;
        while (addPeriod(start, f.effective.next, k) <= at) k++;
        eff = addPeriod(start, f.effective.next, k);
      }
      if (eff <= t && (best === null || eff > best[0] || (eff === best[0] && i >= best[1]))) best = [eff, i, c.data.option];
    });
    if (best) return best[2];
    return get(f, "initial", null);
  };
  EP._valuationsFor = function (ag, item, t) {
    var ik = canonKey(item);
    return clauseForms(this.b, ag).filter(function (cf) {
      if (cf.kind !== "Valuation" || !valItems(cf).has(ik)) return false;
      var d = during(cf);
      return !(d && !(d[0] <= t && t < d[1]));
    });
  };
  EP.value = function (cid, item, option, t) {
    var S = this.stateAt(cid, t), ag = this.agreement(S), b = this.b;
    if (!ag) return null;
    var cands = this._valuationsFor(ag, item, t);
    if (!cands.length) return null;
    var closure = overClosure(ag);
    var gov = cands.find(function (x) { return cands.every(function (y) { return x === y || governs(x, y, closure); }); }) || cands[0];
    var src = gov.form.source;
    if (has(src, "table")) {
      var row = src.table.find(function (r) { return canonKey(r.item) === canonKey(item); });
      var by = b.reveal(row.by);
      if (by === SEALED) return SEALED;
      var amt = truthy(option) ? get(by, option, null) : null;
      return amt !== null ? b.reveal(amt) : null;
    }
    var ref = src.reference;
    var lists = get(get(S.facts, gov.name, {}), "claims", []).filter(function (c) { return c.type === ref.claim && rolesOf(ag, c.by).has(ref.role) && c.data.effective <= t; });
    if (!lists.length) return null;
    var latest = lists[0], li = 0;
    lists.forEach(function (c, i) { if (c.data.effective > latest.data.effective || (c.data.effective === latest.data.effective && i >= li)) { latest = c; li = i; } });
    var entry = latest.data.prices.find(function (p) { return canonKey(p.item) === canonKey(item); });
    if (!entry) return null;
    var price = b.reveal(entry.price), factor = b.reveal(ref.factor);
    if (price === SEALED || factor === SEALED) return SEALED;
    var v = UP.dec(price.value).mul(UP.dec(factor)).round(ref.rounding);
    return { value: UP.decStr(v), currency: price.currency };
  };
  EP.price = function (pid, item, t) {
    var S = this.stateAt(pid, t), ag = this.agreement(S);
    if (!ag) return null;
    var parents = this.parents(pid, t);
    if (!parents.length) return null;
    var sel = clauseForms(this.b, ag).find(function (cf) { return cf.kind === "Selection"; });
    var member = sel ? keysWithRole(ag, sel.form.subject)[0] : null;
    var option = sel ? this.selection(pid, sel.name, member, t) : null;
    return this.value(parents[0], item, option, t);
  };
  EP.obligations = function (cid, t) {
    var S = this.stateAt(cid, t), ag = this.agreement(S), self = this;
    if (!S || S.status !== "executed") return [];
    var cfs = clauseForms(this.b, ag), closure = overClosure(ag);
    var duties = cfs.filter(function (cf) { return cf.kind === "Duty"; });
    var live = duties.filter(function (d) { return !duties.some(function (o) { return o !== d && conflictKey(o) === conflictKey(d) && governs(o, d, closure); }); });
    var w = this.window(cid, t), out = [];
    live.forEach(function (d) {
      var f = d.form;
      keysWithRole(ag, f.obligor).forEach(function (obligor) {
        keysWithRole(ag, f.obligee).forEach(function (obligee) {
          self._dutyPeriods(S, d, w[0], w[1], t).forEach(function (pd) { out.push(self._commitment(S, ag, d, obligor, obligee, pd[0], pd[1], pd[2], t)); });
        });
      });
    });
    return out;
  };
  EP._dutyPeriods = function (S, d, start, end, t) {
    var f = d.form, out = [];
    if (has(f.trigger, "every")) {
      for (var k = 0; k < 10000; k++) {
        var b0 = addPeriod(start, f.trigger.every, k), b1 = addPeriod(start, f.trigger.every, k + 1);
        if ((end !== null && b0 >= end) || b1 > t) break;
        if (b1 > S.executed_at) out.push([{ start: b0, end: b1 }, addPeriod(b1, f.due), null]);
      }
    } else {
      get(get(S.facts, d.name, {}), "claims", []).forEach(function (c) {
        if (c.type === f.trigger.on) out.push([{ start: c.at, end: c.at }, addPeriod(c.at, f.due), c.event]);
      });
    }
    return out;
  };
  EP._commitment = function (S, ag, d, obligor, obligee, period, due, trig, t) {
    var f = d.form, b = this.b, self = this;
    var com = { chain: S.chain, clause: d.name, duty: f.duty, obligor: { role: f.obligor, key: obligor }, obligee: { role: f.obligee, key: obligee }, period: period, due: due };
    if (truthy(trig)) com.trigger = trig;
    var owed = null;
    if (has(f, "amount")) {
      var a = f.amount;
      var base = get(get(S.facts, get(a.base, "clause", d.name), {}), "claims", []).filter(function (c) { return c.type === a.base.claim && eq(get(c.data, "period", null), period); });
      if (base.length) {
        var vals = base.map(function (c) { return b.reveal(c.data[a.base.field]); }), rate = b.reveal(a.rate);
        if (vals.indexOf(SEALED) >= 0 || rate === SEALED) owed = SEALED;
        else {
          var curs = uniq(vals.map(function (v) { return v.currency; }));
          if (curs.length === 1) {
            var total = UP.dec("0");
            vals.forEach(function (v) { total = total.add(UP.dec(v.value)); });
            owed = { value: UP.decStr(total.mul(UP.dec(rate)).round(a.rounding)), currency: curs[0] };
          }
        }
      }
      com.amount = owed === SEALED ? "sealed" : owed ? owed : "no base reported yet";
    }
    var dis = f.discharge, ackRoles = new Set(asList(get(dis, "ack", []))), status = null;
    var claims = get(get(S.facts, d.name, {}), "claims", []);
    for (var i = 0; i < claims.length; i++) {
      var c = claims[i];
      if (c.type !== dis.claim || c.by !== obligor) continue;
      if (truthy(trig)) { if (get(c.data, "request", null) !== trig) continue; }
      else if (!eq(get(c.data, "period", null), period)) continue;
      var doneAt = self._acksComplete(ag, c, ackRoles);
      if (doneAt === null || doneAt > t) continue;
      if (has(f, "amount")) {
        var paid = b.reveal(get(c.data, "amount", null));
        if (owed === SEALED || paid === SEALED) { status = status || "sealed"; continue; }
        if (!isObj(owed) || get(paid, "currency") !== owed.currency || UP.dec(paid.value).cmp(UP.dec(owed.value)) < 0) continue;
      }
      status = "discharged"; com.discharged_at = doneAt; com.late = doneAt > due;
      break;
    }
    com.status = status || (t >= due ? "overdue" : "open");
    return com;
  };

  // ---- Snapshot (report.py) ------------------------------------------------------------------
  function amt(x) { return x === SEALED ? "sealed" : x; }
  function snapshot(ev, t, positions) {
    var b = ev.b, chains = [];
    b.chain_list.forEach(function (chain, pos) {
      if (!chain.length || (positions != null && positions.indexOf(pos) < 0)) return;
      var cid = ch(chain[0]), S = ev.stateAt(cid, t), ag = ev.agreement(S);
      var entry = { chain: pos, label: get(ag || {}, "label", "chain " + pos), status: ev.status(cid, t), state_hash: S ? ch(S) : null };
      if (ag && S && S.status === "executed") {
        var cfs = clauseForms(b, ag), w = ev.window(cid, t);
        entry.window = { start: w[0], end: w[1] };
        var sel = cfs.find(function (cf) { return cf.kind === "Selection"; });
        if (sel) { var tiers = {}; keysWithRole(ag, sel.form.subject).forEach(function (k) { tiers[k] = ev.selection(cid, sel.name, k, t); }); entry.selections = tiers; }
        var parents = ev.parents(cid, t);
        if (parents.length) {
          var pag = ev.agreement(ev.stateAt(parents[0], t)), items = [];
          clauseForms(b, pag || {}).forEach(function (cf) { if (cf.kind === "Valuation") sorted(valItems(cf)).forEach(function (i) { items.push(JSON.parse(i)); }); });
          var seen = new Set(), prices = [];
          items.forEach(function (it) { var k = canonKey(it); if (seen.has(k)) return; seen.add(k); prices.push({ item: it, price: amt(ev.price(cid, it, t)) }); });
          entry.prices = prices;
        }
        var obs = ev.obligations(cid, t);
        if (obs.length) entry.obligations = obs;
      }
      chains.push(entry);
    });
    return { at: t, chains: chains };
  }

  // ---- Rendering (render.py) --------------------------------------------------------------------
  var ROLE_NAMES = { aggregator: "the Aggregator", supplier: "the Supplier", member: "the Member" };
  var MODES = { "half-even": "half to even", "half-up": "half up", down: "down", up: "up" };
  var MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
  function sealedText(x) { return "[sealed " + x.seal + "]"; }
  function fmt(b, value, f) {
    if (UP.isSeal(value)) { var v = b.reveal(value); if (v === SEALED) return sealedText(value); value = v; }
    if (f === "role") return asList(value).map(function (r) { return ROLE_NAMES[r] || r; }).join(" or ");
    if (f === "amount") {
      if (isObj(value) && "value" in value) return value.currency + " " + value.value;
      if (isObj(value)) return sorted(Object.keys(value)).map(function (k) { return k + ": " + fmt(b, value[k], "amount"); }).join("; ");
    }
    if (f === "rate") {
      var s = UP.dec(String(value)).mul(UP.dec("100")).toString();
      if (s.indexOf(".") >= 0) s = s.replace(/0+$/, "").replace(/\.$/, "");
      return s + "%";
    }
    if (f === "period") return UP.fmtPeriod(value);
    if (f === "time") {
      var d = UP.parseTime(value), p2 = function (n) { return ("0" + n).slice(-2); };
      return d.getUTCDate() + " " + MONTHS[d.getUTCMonth()] + " " + d.getUTCFullYear() + ", " + p2(d.getUTCHours()) + ":" + p2(d.getUTCMinutes()) + " UTC";
    }
    if (f === "rounding") return "to " + value.scale + " decimal places, rounding " + MODES[value.mode];
    if (f === "effective") {
      if (value === "on-ack") return "upon acknowledgment";
      return "from the start of the next " + UP.fmtPeriod(value.next) + " period after acknowledgment";
    }
    if (f === "governs") return ({ document: "the existing agreement", "this-record": "this record" })[value] || str(value);
    if (isObj(value) && Object.keys(value).length === 2 && has(value, "scheme") && has(value, "id")) {
      var idv = UP.isSeal(value.id) ? b.reveal(value.id) : value.id;
      return value.scheme + " " + (idv === SEALED ? sealedText(value.id) : str(idv));
    }
    if (Array.isArray(value)) return value.map(function (x) { return fmt(b, x, f); }).join(", ");
    return str(value);
  }
  var EACH_RE = /\{\{#each (\w+)\}\}([\s\S]*?)\{\{\/each\}\}/g, VAR_RE = /\{\{(\w+)(?:\|(\w+))?\}\}/g, SENTENCE_RE = /(^|[.!?]\s+)([a-z])/g;
  function renderTemplate(b, template, params) {
    var text = template.replace(EACH_RE, function (m, name, inner) {
      var items = get(params, name, []);
      if (UP.isSeal(items)) return sealedText(items);
      return items.map(function (it) {
        var merged = Object.assign({}, params, it);
        return inner.replace(VAR_RE, function (v0, n, f) { return fmt(b, get(merged, n, v0), f); });
      }).join("");
    });
    text = text.replace(VAR_RE, function (v0, n, f) { return fmt(b, get(params, n, v0), f); }).trim();
    return text.replace(SENTENCE_RE, function (m, a, c) { return a + c.toUpperCase(); });
  }
  function renderAgreement(b, ag) {
    var h = ch(ag);
    var lines = ["# " + get(ag, "label", "Universal Paper agreement"), "", "Spec version: " + ag.spec, "Agreement hash: " + h, "", "## Parties", ""];
    ag.parties.forEach(function (p) {
      var party = p.party, ids = get(party, "ids", []).map(function (i) { return fmt(b, i, null); }).join("; ");
      lines.push("- " + get(party, "name", party.key) + ", as " + ROLE_NAMES[p.role] + " (key " + party.key + (ids ? "; " + ids : "") + ")");
    });
    lines.push("", "## Terms", "");
    ag.clauses.forEach(function (c, i) {
      var t = b.terms.get(c.def);
      lines.push("### " + (i + 1) + ". " + t.title + " (" + c.term + ", clause \"" + c.n + "\")", "", renderTemplate(b, t.render, c.params));
      if (truthy(get(c, "over"))) lines.push("", "This clause applies notwithstanding clause(s) " + c.over.map(function (o) { return "\"" + o + "\""; }).join(", ") + ".");
      lines.push("");
    });
    lines.push("## Signatures", "", "Each party below signs the agreement identified by " + h + ". The signed text above is generated from that " +
      "agreement and the Term definitions it pins by hash, so the text and the data cannot differ.", "");
    ag.parties.forEach(function (p) { lines.push("- " + get(p.party, "name", p.party.key) + " (" + ROLE_NAMES[p.role] + "): signature over " + h); });
    return lines.join("\n") + "\n";
  }

  // ---- Simulation (simulate.py) ------------------------------------------------------------------
  function simulate(data, hypothetical, at) {
    data = clone(data);
    var unverified = new Set(), results = [];
    hypothetical.forEach(function (h) {
      var b = new Bundle(data), ev = new Evaluator(b, unverified);
      var E = { type: "Event", spec: SPEC, kind: h.kind, at: h.at, by: h.by, body: h.body }, c = get(h, "chain", null), pos;
      if (typeof c === "number") pos = c; else if (typeof c === "string") pos = b.chain_pos.get(c); else pos = null;
      if (pos !== null) { var cid0 = ch(data.chains[pos][0]); E.chain = cid0; E.prev = ch(ev.stateAt(cid0)); }
      var sigs = [];
      if (truthy(get(h, "agent"))) sigs.push({ key: h.agent.key, mandate: h.agent.mandate }); else sigs.push({ key: h.by });
      get(h, "cosigners", []).forEach(function (k) { sigs.push({ key: k }); });
      E.sigs = sigs.sort(function (x, y) { return cmpStr(x.key, y.key); });
      unverified.add(ch(E));
      if (pos === null) { data.chains.push([E]); pos = data.chains.length - 1; } else data.chains[pos].push(E);
      b = new Bundle(data); ev = new Evaluator(b, unverified);
      var steps = ev.run(ch(data.chains[pos][0])), step = steps[steps.length - 1];
      results.push({ hypothetical: true, chain: pos, at: h.at, kind: h.kind, accepted: step.accepted, reason: step.reason,
        checks: step.checks.map(checkJson), state_hash: step.state ? ch(step.state) : null, derived: snapshot(ev, h.at) });
    });
    var finalAt = at || (hypothetical.length ? hypothetical[hypothetical.length - 1].at : null);
    var fin = finalAt ? snapshot(new Evaluator(new Bundle(data), unverified), finalAt) : null;
    return { type: "Simulation", spec: SPEC, hypothetical: true, steps: results, final: fin, at: finalAt };
  }

  // ---- Traces (trace.py) ----------------------------------------------------------------------------
  var FORMAT = "up-trace/0.1";
  function names(b) {
    var n = {};
    b.agreements.forEach(function (ag) { get(ag, "parties", []).forEach(function (p) { n[p.party.key] = get(p.party, "name", p.party.key.slice(0, 16)); }); });
    b.mandates.forEach(function (m) { if (!has(n, m.agent)) n[m.agent] = "Agent of " + (has(n, m.principal) ? n[m.principal] : m.principal.slice(0, 16)); });
    return n;
  }
  function describe(E, b, nm, label) {
    var by = get(E, "by", "?"), who = has(nm, by) ? nm[by] : by.slice(0, 16);
    var agent = get(E, "sigs", []).find(function (s) { return has(s, "mandate"); });
    var via = agent ? " (through its agent)" : "", kind = get(E, "kind"), body = get(E, "body", {});
    if (kind === "propose") {
      var ag = get(body, "agreement", {});
      if (has(body, "supersedes")) return who + via + " proposes an amendment to “" + label + "”.";
      return who + via + " proposes “" + get(ag, "label", "an agreement") + "”.";
    }
    if (kind === "accept") {
      var target = null;
      b.chain_list.some(function (c) { return c.some(function (x) { if (ch(x) === get(body, "target")) { target = x; return true; } return false; }); });
      if (target && target.kind === "propose") return who + via + " signs " + (has(get(target, "body", {}), "supersedes") ? "the amendment to" : "the proposed") + " “" + label + "”.";
      if (target && target.kind === "attest") {
        var ctype = target.body.claim.type.split("/")[0];
        return who + via + " acknowledges " + (has(nm, target.by) ? nm[target.by] : "a party") + "’s " + ctype + " claim under “" + label + "”.";
      }
      return who + via + " accepts an earlier event in “" + label + "”.";
    }
    var claim = get(body, "claim", {}), ct = get(claim, "type", "");
    var nice = {
      "UP:Sales-Reporting/report": "reports sales for the period",
      "UP:Admin-Fee/paid": "attests payment of the administrative fee",
      "UP:Tier-Selection/selects": "attests qualification for tier " + str(get(get(claim, "data", {}), "option", "?")),
      "UP:Fee-Disclosure/disclosed": "discloses administrative fees received",
      "UP:Audit/request": "requests an audit",
      "UP:Audit/available": "makes records available for audit",
      "UP:Termination-Convenience/notice": "gives notice of termination",
      "UP:Renewing-Term/optout": "gives notice of non-renewal"
    }[ct] || ("attests " + ct);
    return who + via + " " + nice + " under “" + label + "”.";
  }
  function makeTrace(reference, evaluators, meta, finalAt, generatedBy) {
    var ref = new Bundle(reference), nm = names(ref), order = [], labels = {};
    ref.chain_list.forEach(function (c, pos) { c.forEach(function (E, i) { order.push([E.at, pos, i]); }); });
    order.sort(function (a, b) { return cmpStr(a[0], b[0]) || a[1] - b[1] || a[2] - b[2]; });
    ref.chain_list.forEach(function (c, pos) { labels[pos] = get(get(get(c[0], "body", {}), "agreement", {}), "label", "Chain " + pos); });
    var evs = evaluators.map(function (e) {
      var b = new Bundle(e.data), ev = new Evaluator(b);
      return { e: e, b: b, ev: ev, runs: b.chain_list.map(function (c) { return c.length ? ev.run(ch(c[0])) : []; }) };
    });
    var processed = new Map(), steps = [];
    order.forEach(function (o, n) {
      var pos = o[1], i = o[2], E = ref.chain_list[pos][i];
      processed.set(pos, i);
      var agentSig = get(E, "sigs", []).find(function (s) { return has(s, "mandate"); });
      var event = {
        chain: pos, chain_label: labels[pos], index: i, kind: E.kind, at: E.at, by: E.by, by_name: has(nm, E.by) ? nm[E.by] : E.by.slice(0, 16),
        prev: get(E, "prev", null), hash: ch(E), description: describe(E, ref, nm, labels[pos]),
        signers: get(E, "sigs", []).map(function (s) { return { key: s.key, name: has(nm, s.key) ? nm[s.key] : s.key.slice(0, 16), mandate: get(s, "mandate", null) }; }),
        body: get(E, "body", null)
      };
      if (agentSig) {
        var m = ref.mandates.get(agentSig.mandate);
        if (m) event.mandate = { hash: agentSig.mandate, principal: m.principal, principal_name: get(nm, m.principal, ""), agent: m.agent, not_before: m.not_before, expires: m.expires, scope: m.scope };
      }
      var results = {}, sortedPos = sorted(Array.from(processed.keys()).map(String)).map(Number).sort(function (a, b) { return a - b; });
      evs.forEach(function (x) {
        var st = pos < x.runs.length && i < x.runs[pos].length ? x.runs[pos][i] : null, hashes = [];
        for (var p = 0; p < ref.chain_list.length; p++) {
          var h = null;
          if (processed.has(p) && p < x.runs.length) {
            var acc = x.runs[p].slice(0, processed.get(p) + 1).filter(function (s) { return s.accepted; });
            h = acc.length ? ch(acc[acc.length - 1].state) : null;
          }
          hashes.push(h);
        }
        results[x.e.id] = {
          event_hash: st ? st.event_hash : null, accepted: !!(st && st.accepted),
          reason: st ? st.reason : "This evaluator's copy has no such event.",
          checks: st ? st.checks.map(checkJson) : [], chain_state_hash: hashes[pos],
          world_hash: ch({ chains: hashes.map(function (h) { return h || "none"; }) }),
          derived: snapshot(x.ev, E.at, sortedPos)
        };
      });
      var worlds = new Set(Object.keys(results).map(function (k) { return results[k].world_hash; }));
      var refAcc;
      if (!truthy(get(evaluators[0], "tampered"))) refAcc = results[evaluators[0].id].accepted;
      else { var clean = evaluators.find(function (e2) { return !truthy(get(e2, "tampered")); }); refAcc = clean ? results[clean.id].accepted : null; }
      steps.push({ step: n, event: event, results: results, consensus: worlds.size === 1, reference_accepted: refAcc });
    });
    var fin = {}; evs.forEach(function (x) { fin[x.e.id] = snapshot(x.ev, finalAt); });
    var chains = Object.keys(labels).map(Number).map(function (p) { return { position: p, label: labels[p], chain_id: ch(ref.chain_list[p][0]) }; });
    return {
      type: "Trace", format: FORMAT, spec: SPEC, generated_by: generatedBy || "universal-paper JavaScript engine 0.1.0",
      title: get(meta, "title", ""), description: get(meta, "description", ""), hypothetical: true,
      evaluators: evaluators.map(function (e) { return { id: e.id, name: e.name, hashes_only: !!get(e, "hashes_only"), tampered: get(e, "tampered", null) }; }),
      parties: nm, chains: chains, steps: steps, final: { at: finalAt, by_evaluator: fin }
    };
  }

  Object.assign(UP, {
    ROLES: ROLES, FORMS: FORMS, AXIOM_LABELS: AXIOM_LABELS, Bundle: Bundle, Evaluator: Evaluator, Checks: Checks,
    clauseForms: clauseForms, agreementIssues: agreementIssues, typeCheck: typeCheck, typeKnown: tcKnown, termIssues: termIssues, precedenceIssues: precedenceIssues,
    mandateCoverage: mandateCoverage, snapshot: snapshot, renderAgreement: renderAgreement, renderTemplate: renderTemplate,
    simulate: simulate, makeTrace: makeTrace, describe: describe, checkJson: checkJson, canonKey: canonKey, repr: repr, partyKeys: partyKeys, keysWithRole: keysWithRole
  });
  if (typeof module !== "undefined" && module.exports) module.exports = UP;
})(typeof globalThis !== "undefined" ? globalThis : this);
