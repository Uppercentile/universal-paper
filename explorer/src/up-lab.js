/* Universal Paper — live proving ground. Generates random agreements and histories from a seed, runs them
 * through the JavaScript engine, attacks copies of them, and checks invariants against independent oracles.
 * Every run is reproducible from its seed. Requires up-crypto.js and up-engine.js. Licensed Apache-2.0. */
(function (root) {
  "use strict";
  var UP = root.UP || (typeof require !== "undefined" ? require("./up-engine.js") : null);
  var ch = UP.contentHash, SPEC = UP.SPEC;

  // ---- Seeded randomness ---------------------------------------------------------
  function rng(seed) {
    var a = 0; for (var i = 0; i < seed.length; i++) a = (Math.imul(a ^ seed.charCodeAt(i), 2654435761) + i) >>> 0;
    var r = function () { a = (a + 0x6D2B79F5) >>> 0; var t = a; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
    r.int = function (lo, hi) { return lo + Math.floor(r() * (hi - lo + 1)); };
    r.pick = function (xs) { return xs[Math.floor(r() * xs.length)]; };
    r.chance = function (p) { return r() < p; };
    r.hex = function (n) { var s = ""; while (s.length < n) s += ("00000000" + (Math.floor(r() * 4294967296) >>> 0).toString(16)).slice(-8); return s.slice(0, n); };
    r.shuffle = function (xs) { xs = xs.slice(); for (var i = xs.length - 1; i > 0; i--) { var j = Math.floor(r() * (i + 1)), t = xs[i]; xs[i] = xs[j]; xs[j] = t; } return xs; };
    return r;
  }
  function clone(x) { return JSON.parse(JSON.stringify(x)); }
  function cents(n) { var s = String(n), neg = s[0] === "-"; if (neg) s = s.slice(1); while (s.length < 3) s = "0" + s; return (neg ? "-" : "") + s.slice(0, -2) + "." + s.slice(-2); }
  function USD(c) { return { value: cents(c), currency: "USD" }; }
  var DAY = 86400000;
  function t(ms) { return UP.fmtTime(new Date(ms)); }
  function ms(s) { return UP.parseTime(s).getTime(); }

  // ---- Incremental builder (a port of build.py's World that re-runs only the touched chain) ----
  function Builder(terms, r) {
    this.terms = terms; this.r = r;
    this.data = { type: "Bundle", spec: SPEC, terms: Object.keys(terms).map(function (k) { return terms[k]; }), mandates: [], chains: [], disclosures: [] };
    this.b = new UP.Bundle(this.data); this.ev = new UP.Evaluator(this.b);
    this.keys = {}; this.log = [];
  }
  Builder.prototype.actor = function (name, seed) {
    var k = UP.Key.fromSeed(seed); this.keys[k.public] = k;
    return { name: name, key: k, pub: k.public, party: function () { return { key: k.public, name: name }; } };
  };
  Builder.prototype.agentKey = function (seed) { var k = UP.Key.fromSeed(seed); this.keys[k.public] = k; return k; };
  Builder.prototype.clause = function (n, term, params, over) {
    var c = { n: n, term: term, def: ch(this.terms[term]), params: params }; if (over) c.over = over; return c;
  };
  Builder.prototype.agreement = function (parties, clauses, label) {
    var ps = parties.map(function (p) { return { role: p[0], party: p[1].party() }; });
    ps.sort(function (a, b) { return a.role < b.role ? -1 : a.role > b.role ? 1 : a.party.key < b.party.key ? -1 : a.party.key > b.party.key ? 1 : 0; });
    return { type: "Agreement", spec: SPEC, parties: ps, clauses: clauses, label: label };
  };
  Builder.prototype.seal = function (value) {
    var salt = this.r.hex(64), s = UP.sealOf(value, salt), d = { seal: s.seal, salt: salt, value: value };
    this.data.disclosures.push(d); this.b.disclosures.set(d.seal, d); return s;
  };
  Builder.prototype.mandate = function (principal, agentKey, nb, ex, scope) {
    var m = { type: "Mandate", spec: SPEC, principal: principal.pub, agent: agentKey.public, not_before: nb, expires: ex, scope: scope };
    m = UP.attach(m, principal.key.signObj(m));
    this.data.mandates.push(m); this.b.mandates.set(ch(m), m); return ch(m);
  };
  Builder.prototype.cid = function (pos) { return ch(this.data.chains[pos][0]); };
  Builder.prototype.state = function (pos) { return this.ev.stateAt(this.cid(pos)); };
  Builder.prototype.event = function (pos, kind, by, at, body, opt) {
    opt = opt || {};
    var E = { type: "Event", spec: SPEC, kind: kind, at: at, by: by.pub, body: body };
    if (pos !== null) { E.chain = this.cid(pos); E.prev = ch(this.state(pos)); }
    var sigs = [opt.agent ? opt.agent[0].signObj(E, opt.agent[1]) : by.key.signObj(E)];
    (opt.cosigners || []).forEach(function (c) { sigs.push(c.key.signObj(E)); });
    E = UP.attach.apply(null, [E].concat(sigs));
    if (kind === "propose") this.b.agreements.set(ch(body.agreement), body.agreement);
    var cid;
    if (pos === null) {
      this.data.chains.push([E]); pos = this.data.chains.length - 1; cid = ch(E);
      var arr = [E]; this.b.chain_list.push(arr); this.b.chains.set(cid, arr); this.b.chain_pos.set(cid, pos);
    } else {
      this.data.chains[pos].push(E); cid = this.cid(pos); this.b.chain_list[pos].push(E);
    }
    this.ev._runs.delete(cid);
    var steps = this.ev.run(cid), step = steps[steps.length - 1], expect = opt.expect !== false;
    this.log.push({ pos: pos, index: steps.length - 1, kind: kind, at: at, expect: expect, accepted: step.accepted, reason: step.reason, note: opt.note || "" });
    if (step.accepted !== expect) {
      var err = new Error("event at " + at + " by " + by.name + " expected " + (expect ? "accept" : "reject") + ": " + (step.reason || "accepted"));
      err.invariant = "honest-events"; throw err;
    }
    return { pos: pos, hash: ch(E), step: step };
  };
  Builder.prototype.propose = function (by, ag, at, opt) { return this.event(opt && opt.pos != null ? opt.pos : null, "propose", by, at, { agreement: ag }, opt); };
  Builder.prototype.accept = function (pos, by, target, at, opt) { return this.event(pos, "accept", by, at, { target: target }, opt); };
  Builder.prototype.attest = function (pos, by, clause, type, data, at, opt) { return this.event(pos, "attest", by, at, { claim: { type: type, clause: clause, data: data } }, opt); };

  // ---- Scenario generator ------------------------------------------------------------
  var ORGS = ["Northwind", "Bluewater", "Granite", "Cedar", "Harbor", "Summit", "Riverbend", "Lakeside", "Juniper", "Meridian", "Prairie", "Coastal", "Highland", "Maple", "Orchard", "Redwood"];
  var TIER_SETS = [["A", "B"], ["A", "B", "C"], ["A", "B", "C", "D"], ["Gold", "Silver", "Bronze"], ["Committed", "Standard"], ["Tier 1", "Tier 2", "Tier 3"]];
  var MODES = ["half-even", "half-up", "down", "up"];

  function generate(seed, terms, opts) {
    opts = opts || {};
    var r = rng("universal-paper-lab:" + seed), w = new Builder(terms, r);
    var names = r.shuffle(ORGS);
    var cfg = {
      seed: seed, members: r.int(1, 3), tiers: r.pick(TIER_SETS), items: r.int(1, 4),
      unit: r.chance(0.7) ? "month" : "quarter", sealed: opts.sealed != null ? opts.sealed : r.chance(0.35),
      agent: opts.agent != null ? opts.agent : r.chance(0.45), renewing: r.chance(0.4),
      bp: r.int(5, 400), mode: r.pick(MODES), cosignTiers: r.chance(0.5)
    };
    var S = cfg.sealed ? function (v) { return w.seal(v); } : function (v) { return v; };
    var agg = w.actor("Hypothetical " + names[0] + " Purchasing Group", "lab:" + seed + ":agg");
    var sup = w.actor("Example " + names[1] + " Supply Co.", "lab:" + seed + ":sup");
    var members = []; for (var i = 0; i < cfg.members; i++) members.push(w.actor("Sample " + names[2 + i] + " Clinic", "lab:" + seed + ":m" + i));
    var items = []; for (i = 0; i < cfg.items; i++) items.push({ scheme: "GTIN", id: "0" + String(10000000000000 + r.int(1, 89999999999999)).slice(1) });
    // prices: tier 0 cheapest
    var priceC = items.map(function () { var base = r.int(150, 9000), p = []; cfg.tiers.forEach(function (_, k) { p.push(base + k * r.int(5, 120)); }); return p; });
    var rate = (cfg.bp / 10000).toFixed(4).replace(/0+$/, "");
    var rounding = { scale: 2, mode: cfg.mode };
    var startMs = Date.UTC(2027, r.int(0, 11), r.int(1, 28)), start = t(startMs), end = UP.addPeriod(start, { unit: "year", count: 1 });
    var period = { unit: cfg.unit, count: 1 }, feeDue = { unit: "day", count: r.int(10, 45) };
    var termClause = cfg.renewing
      ? w.clause("term", "UP:Renewing-Term", { start: start, end: end, renewal_period: { unit: "year", count: 1 }, max_renewals: r.int(0, 3), optout_roles: ["aggregator", "supplier"], optout_notice: { unit: "day", count: 90 } })
      : w.clause("term", "UP:Fixed-Term", { start: start, end: end });
    var table = items.map(function (it, ii) { var by = {}; cfg.tiers.forEach(function (tn, k) { by[tn] = S(USD(priceC[ii][k])); }); return { item: it, by: by }; });
    var masterClauses = [
      termClause,
      w.clause("tiers", "UP:Tiers", { tiers: cfg.tiers.map(function (tn) { return { name: tn, conditions: S("Hypothetical conditions for tier " + tn) }; }), prices: table }),
      w.clause("reporting", "UP:Sales-Reporting", { reporter: "supplier", recipient: "aggregator", period: period, due: { unit: "day", count: 15 } }),
      w.clause("fee", "UP:Admin-Fee", { payer: "supplier", payee: "aggregator", rate: S(rate), report_clause: "reporting", period: period, due: feeDue, rounding: rounding }),
      w.clause("exit", "UP:Termination-Convenience", { holders: ["aggregator", "supplier"], notice: { unit: "day", count: 90 } }),
      w.clause("notices", "UP:Notices", {})
    ];
    var master = w.agreement([["aggregator", agg], ["supplier", sup]], masterClauses, "Master agreement " + seed + " (hypothetical)");
    var clock = startMs - r.int(20, 40) * DAY + r.int(8, 17) * 3600000;
    function tick(minH, maxH) { clock += r.int(minH, maxH) * 3600000 + r.int(0, 59) * 60000; return t(clock); }
    var a, ah;
    if (r.chance(0.3)) { a = w.propose(agg, master, tick(0, 1), { cosigners: [sup] }); }
    else { a = w.propose(agg, master, tick(0, 1)); w.accept(a.pos, sup, a.hash, tick(2, 72)); }
    var A = a.pos, cidA = w.cid(A);
    var executedAt = w.state(A).executed_at;

    // optional agent for member 0, bounded to a subset of tiers
    var agentInfo = null;
    if (cfg.agent) {
      var bot = w.agentKey("lab:" + seed + ":agent"), anyB = { any: true };
      var allowed = r.shuffle(cfg.tiers).slice(0, r.int(1, cfg.tiers.length - 1));
      var mh = w.mandate(members[0], bot, t(clock - 5 * DAY), UP.addPeriod(end, { unit: "year", count: 1 }), {
        kinds: ["propose", "accept", "attest"], roles: ["member"],
        terms: { "UP:Participation": { parent: anyB }, "UP:Tier-Selection": { tiers_clause: anyB, initial: { "in": cfg.tiers.slice() }, effective: anyB },
          "UP:Fixed-Term": { start: anyB, end: anyB }, "UP:Termination-Convenience": { holders: anyB, notice: { max_period: { unit: "day", count: 60 } } }, "UP:Notices": {} },
        claims: { "UP:Tier-Selection/selects": { option: { "in": allowed }, basis: anyB } }
      });
      agentInfo = { key: bot, mandate: mh, allowed: allowed };
    }

    // participations
    var parts = [], timeline = {};
    members.forEach(function (m, mi) {
      var initial = r.pick(cfg.tiers);
      var useAgent = agentInfo && mi === 0, ag = useAgent ? [agentInfo.key, agentInfo.mandate] : null;
      var P = w.agreement([["aggregator", agg], ["member", m], ["supplier", sup]], [
        w.clause("participation", "UP:Participation", { parent: cidA }),
        w.clause("tier", "UP:Tier-Selection", { tiers_clause: "tiers", initial: initial, effective: "on-ack" }),
        w.clause("term", "UP:Fixed-Term", { start: start, end: end }),
        w.clause("exit", "UP:Termination-Convenience", { holders: ["member"], notice: { unit: "day", count: 30 } }),
        w.clause("notices", "UP:Notices", {})
      ], "Participation of " + m.name);
      var p = w.propose(m, P, tick(1, 48), { agent: ag });
      w.accept(p.pos, agg, p.hash, tick(1, 24));
      w.accept(p.pos, sup, p.hash, tick(1, 24));
      parts.push({ member: m, pos: p.pos, cid: w.cid(p.pos), initial: initial, agent: ag });
      timeline[p.pos] = [];
    });

    function selectTier(pt, option, expect, note) {
      var data = { option: option, basis: S("Hypothetical basis " + r.hex(6)) };
      if (cfg.cosignTiers && expect) {
        var at1 = tick(1, 30);
        w.attest(pt.pos, pt.member, "tier", "UP:Tier-Selection/selects", data, at1, { cosigners: [sup], agent: pt.agent, expect: expect, note: note });
        timeline[pt.pos].push({ option: option, at: at1 });
      } else {
        var x = w.attest(pt.pos, pt.member, "tier", "UP:Tier-Selection/selects", data, tick(1, 30), { agent: pt.agent, expect: expect, note: note });
        if (expect) { var at2 = tick(1, 30); w.accept(pt.pos, sup, x.hash, at2); timeline[pt.pos].push({ option: option, at: at2 }); }
      }
    }
    var mandateChecks = [];
    parts.forEach(function (pt) {
      var opts2 = pt.agent ? agentInfo.allowed : cfg.tiers;
      if (r.chance(0.8)) selectTier(pt, r.pick(opts2), true);
    });
    if (agentInfo) {
      var outside = cfg.tiers.filter(function (x) { return agentInfo.allowed.indexOf(x) < 0; });
      var bad = r.pick(outside), before = w.log.length;
      selectTier(parts[0], bad, false, "Agent tries tier " + bad + ", outside its Mandate (" + agentInfo.allowed.join(", ") + ")");
      var entry = w.log[before];
      var stp = w.ev.run(parts[0].cid)[entry.index];
      mandateChecks.push({ option: bad, rejected: !stp.accepted, rule: (stp.checks.filter(function (c) { return !c.passed; })[0] || {}).rule, reason: stp.reason });
    }

    // periods: reports, fees, tier changes
    var nPeriods = cfg.unit === "month" ? r.int(2, 5) : r.int(1, 3), reports = [], payments = [];
    for (var k = 0; k < nPeriods; k++) {
      var b0 = UP.addPeriod(start, period, k), b1 = UP.addPeriod(start, period, k + 1);
      if (ms(b1) > clock) clock = ms(b1);
      parts.forEach(function (pt) { if (r.chance(0.25)) selectTier(pt, r.pick(pt.agent ? agentInfo.allowed : cfg.tiers), true); });
      if (r.chance(0.1)) { reports.push({ k: k, period: { start: b0, end: b1 }, skipped: true }); continue; }
      var lines = [], total = 0;
      parts.forEach(function (pt) {
        items.forEach(function (it, ii) {
          if (!r.chance(0.7)) return;
          var qty = r.int(1, 600), unit = priceC[ii][r.int(0, cfg.tiers.length - 1)], net = qty * unit;
          total += net;
          lines.push({ participation: pt.cid, item: it, quantity: S(String(qty)), net: S(USD(net)) });
        });
      });
      var rep = w.attest(A, sup, "reporting", "UP:Sales-Reporting/report", { period: { start: b0, end: b1 }, lines: lines, total_net: S(USD(total)) }, tick(24, 14 * 24));
      reports.push({ k: k, period: { start: b0, end: b1 }, total: total, at: rep.step.event.at });
      var owed = oracleFee(total, cfg.bp, cfg.mode), due = UP.addPeriod(b1, feeDue);
      var how = r.pick(["exact", "exact", "exact", "under", "over", "late", "skip"]);
      if (how === "skip") { payments.push({ k: k, how: how }); continue; }
      var amount = how === "under" ? owed - 1 : how === "over" ? owed + 1 : owed;
      if (amount < 0) { payments.push({ k: k, how: "skip" }); continue; }
      var payAt = how === "late" ? t(Math.max(clock, ms(due)) + r.int(1, 10) * DAY) : tick(1, 5 * 24);
      if (ms(payAt) > clock) clock = ms(payAt);
      var cos = r.chance(0.4);
      var pay = w.attest(A, sup, "fee", "UP:Admin-Fee/paid", { period: { start: b0, end: b1 }, amount: S(USD(amount)), reference: S("Hypothetical remittance " + r.hex(8)) }, payAt, cos ? { cosigners: [agg] } : {});
      var ackAt = payAt;
      if (!cos) { ackAt = tick(1, 48); w.accept(A, agg, pay.hash, ackAt); }
      payments.push({ k: k, how: how, amount: amount, ackAt: ackAt });
    }
    var finalAt = t(clock + r.int(1, 20) * DAY);
    return { cfg: cfg, w: w, data: w.data, finalAt: finalAt, A: A, cidA: cidA, parts: parts, timeline: timeline, items: items, priceC: priceC,
      reports: reports, payments: payments, start: start, end: end, period: period, feeDue: feeDue, executedAt: executedAt, mandateChecks: mandateChecks,
      actors: { agg: agg, sup: sup, members: members } };
  }

  // ---- Independent oracles (never call the engine) -------------------------------------
  // fee in cents = round(total_cents × bp / 10 000) with the given mode, on integers only.
  function oracleFee(totalCents, bp, mode) {
    var x = BigInt(totalCents) * BigInt(bp), q = x / 10000n, rem = x % 10000n, up;
    if (mode === "down") up = false; else if (mode === "up") up = rem > 0n;
    else if (mode === "half-up") up = rem >= 5000n; else up = rem > 5000n || (rem === 5000n && q % 2n === 1n);
    return Number(up ? q + 1n : q);
  }
  function oracleTier(g, pt, at) {
    var best = null;
    g.timeline[pt.pos].forEach(function (s, i) { if (s.at <= at && (!best || s.at > best.at || (s.at === best.at && i >= best.i))) best = { at: s.at, i: i, option: s.option }; });
    return best ? best.option : pt.initial;
  }

  // ---- Attacks ---------------------------------------------------------------------------
  function resign(g, E, mutate) {
    var E2 = clone(E), sigs = E2.sigs; delete E2.sigs; mutate(E2);
    var out = sigs.map(function (s) { return g.w.keys[s.key].signObj(E2, s.mandate); });
    return UP.attach.apply(null, [E2].concat(out));
  }
  var ATTACKS = {
    "altered-term": { label: "Altered agreement term after signing", pick: function (g, r) { return { pos: g.A, index: 0 }; },
      apply: function (g, E, r) { var c = E.body.agreement.clauses.find(function (c) { return c.n === "fee"; }); c.params.rate = UP.isSeal(c.params.rate) ? { seal: "sha256:" + r.hex(64) } : (Number(c.params.rate) + 0.005).toFixed(4); return E; } },
    "altered-claim": { label: "Altered sales report after signing", pick: function (g, r) { var xs = idx(g, g.A, function (E) { return E.kind === "attest" && E.body.claim.type === "UP:Sales-Reporting/report"; }); return xs.length ? { pos: g.A, index: r.pick(xs) } : null; },
      apply: function (g, E, r) { var tn = E.body.claim.data.total_net; E.body.claim.data.total_net = UP.isSeal(tn) ? { seal: "sha256:" + r.hex(64) } : { value: cents(Math.round(Number(tn.value) * 100) - r.int(1, 5000)), currency: "USD" }; return E; } },
    "backdated": { label: "Backdated and re-signed event", pick: function (g, r) { return anyLater(g, r); },
      apply: function (g, E, r, prev) { return resign(g, E, function (e) { e.at = t(ms(prev.at) - r.int(1, 30) * DAY); }); } },
    "dropped-signature": { label: "Required signature removed", pick: function (g, r) { return anyLater(g, r); },
      apply: function (g, E) { var by = E.by; E.sigs = E.sigs.filter(function (s) { return s.key !== by && !s.mandate; }); return E; } },
    "wrong-history": { label: "Event rebuilt on a different history", pick: function (g, r) { var c = r.pick(g.data.chains.map(function (_, i) { return i; }).filter(function (i) { return g.data.chains[i].length > 2; })); return c == null ? null : { pos: c, index: r.int(2, g.data.chains[c].length - 1) }; },
      apply: function (g, E, r) { var steps = g.w.ev.run(ch(g.data.chains[E.__pos][0])), older = steps[r.int(0, Math.max(0, E.__index - 2))].state; var e2 = resign(g, strip2(E), function (e) { e.prev = ch(older); }); return e2; } },
    "impersonation": { label: "Outsider signs as a party", pick: function (g, r) { return anyLater(g, r); },
      apply: function (g, E, r) { var k = UP.Key.fromSeed("lab-outsider:" + r.hex(8)); var e2 = clone(E); delete e2.sigs; return UP.attach(e2, k.signObj(e2)); } },
    "cross-chain-replay": { label: "Signed event replayed on another chain", pick: function (g, r) { if (g.data.chains.length < 2) return null; var from = anyLater(g, r); var to = r.pick(g.data.chains.map(function (_, i) { return i; }).filter(function (i) { return i !== from.pos; })); return { pos: to, index: g.data.chains[to].length, from: from }; },
      apply: null }
  };
  function strip2(E) { var e = clone(E); delete e.__pos; delete e.__index; return e; }
  function idx(g, pos, f) { var o = []; g.data.chains[pos].forEach(function (E, i) { if (i > 0 && f(E)) o.push(i); }); return o; }
  function anyLater(g, r) { var c = r.pick(g.data.chains.map(function (_, i) { return i; }).filter(function (i) { return g.data.chains[i].length > 1; })); return { pos: c, index: r.int(1, g.data.chains[c].length - 1) }; }

  function runAttack(g, name, r) {
    var A = ATTACKS[name], tgt = A.pick(g, r);
    if (!tgt) return null;
    var data = clone(g.data), chain = data.chains[tgt.pos];
    if (name === "cross-chain-replay") chain.push(clone(data.chains[tgt.from.pos][tgt.from.index]));
    else {
      var E = clone(chain[tgt.index]); E.__pos = tgt.pos; E.__index = tgt.index;
      var E2 = A.apply(g, E, r, chain[tgt.index - 1]); delete E2.__pos; delete E2.__index;
      chain[tgt.index] = E2;
    }
    var ev = new UP.Evaluator(new UP.Bundle(data)), steps = ev.run(ch(chain[0]));
    var honest = g.w.ev.run(ch(g.data.chains[tgt.pos][0]));
    var st = steps[tgt.index], prefixOk = true;
    for (var i = 0; i < tgt.index; i++) if (!steps[i] || !honest[i] || steps[i].accepted !== honest[i].accepted || ch(steps[i].state || {}) !== ch(honest[i].state || {})) prefixOk = false;
    var failed = st ? st.checks.filter(function (c) { return !c.passed; })[0] : null;
    var cid0 = ch(chain[0]), finalHonest = ch(g.w.ev.stateAt(ch(g.data.chains[tgt.pos][0])) || {}), finalAttacked = ch(ev.stateAt(cid0) || {});
    return { _data: data, attack: name, label: A.label, chain: tgt.pos, index: tgt.index, detected: !!st && !st.accepted && prefixOk, rule: failed ? failed.rule : null, check: failed ? failed.id : null,
      reason: st ? st.reason : "no step", diverged: finalHonest !== finalAttacked || name === "cross-chain-replay" };
  }

  // ---- Invariants ---------------------------------------------------------------------------
  function shuffleKeys(x, r) {
    if (Array.isArray(x)) return x.map(function (v) { return shuffleKeys(v, r); });
    if (x && typeof x === "object") { var o = {}; r.shuffle(Object.keys(x)).forEach(function (k) { o[k] = shuffleKeys(x[k], r); }); return o; }
    return x;
  }
  function worldHash(ev, data) { return ch({ chains: data.chains.map(function (c) { var S = ev.stateAt(ch(c[0])); return S ? ch(S) : "none"; }) }); }

  function runOne(seed, terms, opts) {
    var t0 = Date.now(), r = rng("attacks:" + seed), res = { seed: seed, invariants: [], attacks: [], events: 0, sigs: 0 };
    function inv(id, ok, detail) { res.invariants.push({ id: id, ok: !!ok, detail: detail || "" }); }
    var g;
    try { g = generate(seed, terms, opts); }
    catch (e) { inv(e.invariant || "generator", false, e.message); res.ms = Date.now() - t0; return res; }
    inv("honest-events", true, g.w.log.filter(function (l) { return l.expect; }).length + " honest events accepted");
    res.cfg = g.cfg; res.g = g;
    res.events = g.data.chains.reduce(function (n, c) { return n + c.length; }, 0);
    res.sigs = g.data.chains.reduce(function (n, c) { return n + c.reduce(function (m, E) { return m + E.sigs.length; }, 0); }, 0) + g.data.mandates.length;

    // 1. Determinism: three independent copies plus one with every object's fields reordered.
    var hashes = [0, 1, 2].map(function () { UP.clearVerifyCache(); var d = clone(g.data); return worldHash(new UP.Evaluator(new UP.Bundle(d)), d); });
    UP.clearVerifyCache(); var shuffled = shuffleKeys(g.data, r); hashes.push(worldHash(new UP.Evaluator(new UP.Bundle(shuffled)), shuffled));
    inv("determinism", hashes.every(function (h) { return h === hashes[0]; }), "4 evaluators → " + hashes[0].slice(0, 19) + "…");

    // 2. Attacks: each must be caught at exactly the tampered event, with history before it untouched.
    var names = r.shuffle(Object.keys(ATTACKS)).slice(0, opts && opts.attacks || 3);
    names.forEach(function (n) { var a = runAttack(g, n, r); if (a) res.attacks.push(a); });
    var missed = res.attacks.filter(function (a) { return !a.detected; });
    inv("tamper-detected", !missed.length, missed.length ? "missed: " + missed.map(function (a) { return a.attack + " (" + a.reason + ")"; }).join("; ") : res.attacks.length + " attacks caught");

    // 3. Mandate bounds.
    if (g.mandateChecks.length) {
      var mc = g.mandateChecks[0];
      inv("mandate-bounds", mc.rejected && mc.rule === "A9", "agent tried tier " + mc.option + ": " + (mc.rejected ? "rejected by " + mc.rule : "ACCEPTED"));
    }
    // 4. Sealed observer.
    if (g.cfg.sealed) {
      var hidden = clone(g.data); delete hidden.disclosures;
      var obs = new UP.Evaluator(new UP.Bundle(hidden)), same = true;
      g.data.chains.forEach(function (c) {
        var a = g.w.ev.run(ch(c[0])), b = obs.run(ch(c[0]));
        a.forEach(function (s, i) { if (!b[i] || s.accepted !== b[i].accepted || ch(s.state || {}) !== ch(b[i].state || {})) same = false; });
      });
      var snap = UP.snapshot(obs, g.finalAt), seesSealed = JSON.stringify(snap).indexOf('"sealed"') >= 0;
      inv("sealed-observer", same && seesSealed, same ? "observer without disclosures matched every state hash" : "observer diverged");
    }
    // 5. Fee oracle and 6. price oracle, against the engine's derived values.
    var snapF = UP.snapshot(g.w.ev, g.finalAt), master = snapF.chains.find(function (c) { return c.chain === g.A; });
    var fees = (master.obligations || []).filter(function (o) { return o.clause === "fee"; }), feeBad = [];
    var expectN = 0, at = g.finalAt;
    for (var k = 0; k < 100; k++) { var b1 = UP.addPeriod(g.start, g.period, k + 1); if (b1 > at || UP.addPeriod(g.start, g.period, k) >= master.window.end) break; if (b1 > g.executedAt) expectN++; }
    if (fees.length !== expectN) feeBad.push("expected " + expectN + " fee periods, engine has " + fees.length);
    fees.forEach(function (o) {
      var rep = g.reports.find(function (x) { return x.period.start === o.period.start; }), pay = g.payments.find(function (x) { return rep && x.k === rep.k; });
      var want, status;
      if (!rep || rep.skipped) { want = "no base reported yet"; status = at >= o.due ? "overdue" : "open"; }
      else {
        want = USD(oracleFee(rep.total, g.cfg.bp, g.cfg.mode));
        var paidOk = pay && pay.how !== "skip" && pay.amount >= oracleFee(rep.total, g.cfg.bp, g.cfg.mode) && pay.ackAt <= at;
        status = paidOk ? "discharged" : at >= o.due ? "overdue" : "open";
        if (paidOk && o.late !== (pay.ackAt > o.due)) feeBad.push(o.period.start + ": late flag " + o.late);
      }
      if (JSON.stringify(o.amount) !== JSON.stringify(want)) feeBad.push(o.period.start.slice(0, 10) + ": engine " + JSON.stringify(o.amount) + " vs oracle " + JSON.stringify(want));
      if (o.status !== status) feeBad.push(o.period.start.slice(0, 10) + ": status " + o.status + " vs oracle " + status);
    });
    inv("fee-oracle", !feeBad.length, feeBad.length ? feeBad.join("; ") : fees.length + " fee commitments match integer arithmetic");
    var priceBad = [];
    g.parts.forEach(function (pt) {
      var c = snapF.chains.find(function (x) { return x.chain === pt.pos; }), tier = oracleTier(g, pt, at);
      if (!c || c.selections[pt.member.pub] !== tier) priceBad.push(pt.member.name + ": tier " + (c && c.selections[pt.member.pub]) + " vs " + tier);
      (c && c.prices || []).forEach(function (p) {
        var ii = g.items.findIndex(function (it) { return it.id === p.item.id; }), want = USD(g.priceC[ii][g.cfg.tiers.indexOf(tier)]);
        if (JSON.stringify(p.price) !== JSON.stringify(want)) priceBad.push(p.item.id + ": " + JSON.stringify(p.price) + " vs " + JSON.stringify(want));
      });
    });
    inv("price-oracle", !priceBad.length, priceBad.length ? priceBad.join("; ") : g.parts.length + " members' tiers and prices match");

    // 7. Rendering binding.
    var b = g.w.b, ag = b.agreements.get(g.w.state(g.A).agreement), text = UP.renderAgreement(b, ag), h = ch(ag);
    var ag2 = clone(ag), c2 = ag2.clauses.find(function (c) { return c.n === "reporting"; }); c2.params.due = { unit: "day", count: c2.params.due.count + 1 };
    var text2 = UP.renderAgreement(b, ag2);
    inv("render-binding", text.indexOf(h) >= 0 && text === UP.renderAgreement(b, clone(ag)) && ch(ag2) !== h && text2 !== text,
      "one-word change → new fingerprint " + ch(ag2).slice(7, 15) + "… and new text");
    res.ms = Date.now() - t0;
    return res;
  }

  function traceOf(res) {
    var g = res.g, d = g.data, evs = [{ id: "a", name: "Evaluator A", data: clone(d) }, { id: "b", name: "Evaluator B", data: clone(d) }];
    if (g.cfg.sealed) { var h = clone(d); delete h.disclosures; evs.push({ id: "observer", name: "Observer (hashes only)", data: h, hashes_only: true }); }
    else evs.push({ id: "c", name: "Evaluator C", data: clone(d) });
    var att = (res.attacks || []).filter(function (a) { return a._data; })[0];
    if (att) evs.push({ id: "tampered", name: "Tampered copy", data: att._data, tampered: att.label + " (chain " + att.chain + ", event " + att.index + ")." });
    return UP.makeTrace(d, evs, { title: "Live run " + res.seed, description: "Generated in your browser from seed " + res.seed + ". Computed live by the JavaScript engine." }, g.finalAt);
  }

  UP.lab = { rng: rng, generate: generate, runOne: runOne, traceOf: traceOf, ATTACKS: ATTACKS, oracleFee: oracleFee,
    INVARIANTS: {
      "honest-events": "Every honestly signed event is accepted",
      determinism: "Independent evaluators reach the same fingerprint",
      "tamper-detected": "Every tampered copy is caught at the tampered event",
      "mandate-bounds": "Agents cannot act outside their Mandate",
      "sealed-observer": "An observer with no disclosures reaches the same verdicts",
      "fee-oracle": "Fees match independent integer arithmetic",
      "price-oracle": "Prices match the tier in force",
      "render-binding": "The readable text is bound to the fingerprint"
    } };
  if (typeof module !== "undefined" && module.exports) module.exports = UP;
})(typeof globalThis !== "undefined" ? globalThis : this);
