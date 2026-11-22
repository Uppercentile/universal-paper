/* Universal Paper — Playground history: signs an agreement written in the Playground, adds example sales reports
 * and fee payments the visitor enters, and evaluates the chain with the engine. Requires up-crypto.js and up-engine.js.
 * Licensed Apache-2.0. */
(function (root) {
  "use strict";
  var UP = root.UP || (typeof require !== "undefined" ? require("./up-engine.js") : null);
  var ch = UP.contentHash, SPEC = UP.SPEC, DAY = 86400000;
  function shift(t, days) { return UP.fmtTime(new Date(UP.parseTime(t).getTime() + days * DAY)); }
  function money(s) {
    var v = String(s || "").replace(/[,\s$]/g, "");
    if (!/^(0|[1-9][0-9]{0,11})(\.[0-9]{1,2})?$/.test(v)) return null;
    var p = v.split("."); return p[0] + "." + ((p[1] || "") + "00").slice(0, 2);
  }

  // keyOf(publicKey) -> Key. inputs: {reports: {periodStart: "1234.56"}, paid: {periodStart: true}, disclosures: [...]}
  // Disclosures open sealed values for the parties, so fees can be computed from a sealed rate.
  function history(ag, terms, keyOf, inputs) {
    inputs = inputs || {};
    var discs = inputs.disclosures || [];
    var data = { type: "Bundle", spec: SPEC, terms: terms, chains: [], disclosures: discs };
    var b0 = new UP.Bundle(data), issues = UP.agreementIssues(b0, ag);
    if (issues.length) return { issues: issues };
    var cfs = UP.clauseForms(b0, ag);
    var w = cfs.filter(function (c) { return c.kind === "Window"; })[0];
    var start = w ? w.form.start : "2027-01-01T00:00:00Z";
    var signAt = shift(start, -7);
    var horizon = w ? w.form.end : UP.addPeriod(start, { unit: "year", count: 1 });
    var parties = ag.parties, roleKey = {};
    parties.forEach(function (p) { if (!roleKey[p.role]) roleKey[p.role] = p.party.key; });

    var G = { type: "Event", spec: SPEC, kind: "propose", at: signAt, by: parties[0].party.key, body: { agreement: ag } };
    G = UP.attach.apply(null, [G].concat(parties.map(function (p) { return keyOf(p.party.key).signObj(G); })));
    var cid = ch(G);

    function evaluate(planned) {
      var chain = [G], d = { type: "Bundle", spec: SPEC, terms: terms, chains: [chain], disclosures: discs }, log = [];
      planned.slice().sort(function (a, b) { return a.at < b.at ? -1 : a.at > b.at ? 1 : a.n - b.n; }).forEach(function (p) {
        var ev = new UP.Evaluator(new UP.Bundle(d)), S = ev.stateAt(cid);
        var E = { type: "Event", spec: SPEC, kind: "attest", at: p.at, by: p.by, chain: cid, prev: ch(S), body: { claim: p.claim } };
        E = UP.attach.apply(null, [E].concat([p.by].concat(p.cosign || []).map(function (k) { return keyOf(k).signObj(E); })));
        chain.push(E);
        var steps = new UP.Evaluator(new UP.Bundle(d)).run(cid), st = steps[steps.length - 1];
        log.push({ at: p.at, what: p.what, accepted: st.accepted, reason: st.reason, hash: ch(E) });
        if (!st.accepted) chain.pop();
      });
      var ev2 = new UP.Evaluator(new UP.Bundle(d));
      return { ev: ev2, data: d, log: log };
    }

    var rep = cfs.filter(function (c) { return c.tid === "UP:Sales-Reporting"; })[0];
    var fee = rep && cfs.filter(function (c) { return c.tid === "UP:Admin-Fee" && c.form.amount && c.form.amount.base.clause === rep.name; })[0];
    var planned = [], n = 0, notes = [];
    var first = evaluate([]);
    var repPeriods = [];
    if (rep) {
      var reporter = roleKey[rep.form.obligor];
      if (!reporter) notes.push("Sales reports need a party in the " + rep.form.obligor + " role.");
      repPeriods = first.ev.obligations(cid, horizon).filter(function (o) { return o.clause === rep.name; }).map(function (o) { return o.period; });
      repPeriods.forEach(function (pd) {
        var v = money((inputs.reports || {})[pd.start]);
        if (v === null || !reporter) return;
        planned.push({ n: n++, at: shift(pd.end, 2), by: reporter, what: "Sales report for the period starting " + pd.start.slice(0, 10) + ": USD " + v,
          claim: { type: "UP:Sales-Reporting/report", clause: rep.name, data: { period: pd, lines: [], total_net: { value: v, currency: "USD" } } } });
      });
    }
    var mid = evaluate(planned);
    if (fee) {
      var payer = roleKey[fee.form.obligor], payee = roleKey[fee.form.obligee];
      mid.ev.obligations(cid, horizon).filter(function (o) { return o.clause === fee.name; }).forEach(function (o) {
        if (!(inputs.paid || {})[o.period.start] || typeof o.amount !== "object" || !payer || !payee) return;
        planned.push({ n: n++, at: shift(o.due, -3), by: payer, cosign: payer === payee ? [] : [payee], what: "Fee paid for the period starting " + o.period.start.slice(0, 10) + ": " + o.amount.currency + " " + o.amount.value,
          claim: { type: "UP:Admin-Fee/paid", clause: fee.name, data: { period: o.period, amount: o.amount, reference: "Example remittance" } } });
      });
    }
    var out = evaluate(planned);
    return { cid: cid, ev: out.ev, data: out.data, log: out.log, start: start, end: w ? w.form.end : null, signAt: signAt, horizon: horizon,
      reportClause: rep ? rep.name : null, feeClause: fee ? fee.name : null, reportPeriods: repPeriods, notes: notes, issues: [] };
  }

  UP.play = { history: history, money: money };
  if (typeof module !== "undefined" && module.exports) module.exports = UP;
})(typeof globalThis !== "undefined" ? globalThis : this);
