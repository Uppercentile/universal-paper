(function () {
  "use strict";
  var UP = window.UP, ch = UP.contentHash;
  var TERMS = {};
  JSON.parse(document.getElementById("terms-json").textContent).forEach(function (t) { TERMS[t.id] = t; });
  var $ = function (id) { return document.getElementById(id); };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function short(h) { return h ? String(h).replace("sha256:", "").slice(0, 10) : "none"; }
  function clone(x) { return JSON.parse(JSON.stringify(x)); }
  function fmtN(n) { return n.toLocaleString("en-US"); }
  function store(k, v) { try { if (v === undefined) { var s = localStorage.getItem(k); return s ? JSON.parse(s) : null; } localStorage.setItem(k, JSON.stringify(v)); } catch (e) { return null; } }
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  $("spec-ver").textContent = UP.SPEC;

  function fpHTML(h, prev, label) {
    var hex = h.replace("sha256:", ""), ph = prev ? prev.replace("sha256:", "") : null, out = "";
    for (var i = 0; i < hex.length; i++) out += ph && ph[i] !== hex[i] ? '<span class="flip">' + hex[i] + "</span>" : hex[i];
    return '<span class="lab">' + esc(label || "Fingerprint") + "</span>sha256:" + out;
  }
  function flash(el) { el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash"); }
  var RULES = {
    A1: "Composition", A2: "Unanimity", A3: "Chained transitions", A4: "Determinism", A5: "Non-retroactivity", A6: "Value neutrality",
    A7: "Role symmetry", A8: "Rendering binding", A9: "Bounded delegation", A10: "Verifiable confidentiality", A11: "Closed evidence",
    A12: "Single attribution", A13: "Resolved precedence"
  };
  function ruleName(r) { return r ? r + (RULES[r] ? " " + RULES[r] : "") : "—"; }

  // ======================================================================== Navigation
  var navLinks = document.querySelectorAll("[data-nav]");
  if ("IntersectionObserver" in window) {
    var navObs = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) navLinks.forEach(function (a) { a.classList.toggle("on", a.dataset.nav === e.target.id); }); });
    }, { rootMargin: "-45% 0px -50% 0px" });
    ["story", "proof", "playground", "replay"].forEach(function (id) { navObs.observe($(id)); });
  }

  // ======================================================================== Story
  var story = (function () {
    var agg = UP.Key.fromSeed("story:aggregator"), sup = UP.Key.fromSeed("story:supplier");
    var rate = "0.02", prevFp = null, stage = 1, timer = null;
    function agreement(r) {
      var t = TERMS["UP:Admin-Fee"];
      return {
        type: "Agreement", spec: UP.SPEC, label: "Example master agreement (hypothetical)",
        parties: [{ role: "aggregator", party: { key: agg.public, name: "Hypothetical Purchasing Group" } }, { role: "supplier", party: { key: sup.public, name: "Example Supply Co." } }].sort(function (a, b) { return a.role < b.role ? -1 : 1; }),
        clauses: [{ n: "fee", term: "UP:Admin-Fee", def: ch(t), params: { payer: "supplier", payee: "aggregator", rate: r, report_clause: "reporting", period: { unit: "month", count: 1 }, due: { unit: "day", count: 30 }, rounding: { scale: 2, mode: "half-even" } } }]
      };
    }
    function genesis(ag) {
      var E = { type: "Event", spec: UP.SPEC, kind: "propose", at: "2026-12-01T15:00:00Z", by: agg.public, body: { agreement: ag } };
      return UP.attach(E, agg.signObj(E), sup.signObj(E));
    }
    function stateOf(E) {
      var b = new UP.Bundle({ type: "Bundle", spec: UP.SPEC, terms: [TERMS["UP:Admin-Fee"]], chains: [[E]] });
      var st = new UP.Evaluator(b).run(ch(E))[0];
      return st;
    }
    function draw() {
      var ag = agreement(rate), b = new UP.Bundle({ terms: [TERMS["UP:Admin-Fee"]] });
      var text = UP.renderTemplate(b, TERMS["UP:Admin-Fee"].render, ag.clauses[0].params);
      var pct = esc((Number(rate) * 100).toString() + "%");
      $("sv-text").innerHTML = esc(text).replace(pct, "<mark>" + pct + "</mark>");
      var json = JSON.stringify({ n: "fee", term: "UP:Admin-Fee", def: short(ag.clauses[0].def) + "…", params: ag.clauses[0].params }, null, 1);
      $("sv-json").innerHTML = esc(json).replace('"rate": "' + rate + '"', '<b>"rate": "' + rate + '"</b>');
      var h = ch(ag), fpEl = $("sv-fp");
      fpEl.innerHTML = fpHTML(h, prevFp, "Agreement fingerprint");
      if (prevFp && prevFp !== h) flash(fpEl);
      prevFp = h;
      var E = genesis(ag), honest = stateOf(E);
      var rows = [["Aggregator’s contract system", honest], ["Supplier’s ERP", null], ["Member’s spreadsheet", stateOf(clone(E))]];
      if (stage >= 6) {
        var T = clone(E); T.body.agreement.clauses[0].params.rate = rate === "0.02" ? "0.015" : "0.02";
        rows[1][1] = stateOf(T); rows[1][2] = true;
      } else rows[1][1] = stateOf(clone(E));
      $("sv-evals").innerHTML = rows.map(function (r) {
        var st = r[1], ok = st.accepted, sh = ok ? ch(st.state) : null;
        return '<div class="evrow' + (ok ? "" : " bad") + '"><b>' + esc(r[0]) + (r[2] ? ' <span class="muted">(copy edited after signing)</span>' : "") + '</b>' +
          '<span class="pill ' + (ok ? "ok" : "bad") + '">' + (ok ? "executed" : "rejected") + "</span>" +
          '<span class="h">' + (ok ? "state " + esc(sh) : "no valid state") + "</span>" +
          (ok ? "" : '<span class="why">' + esc(st.reason) + "</span>") + "</div>";
      }).join("");
    }
    function setStage(n) {
      if (n === stage) return;
      stage = n; $("visual").dataset.stage = String(Math.min(n, 5));
      clearInterval(timer); timer = null;
      if (n === 4 && !reduceMotion) timer = setInterval(toggle, 2600);
      draw();
    }
    function toggle() { rate = rate === "0.02" ? "0.025" : "0.02"; draw(); }
    $("story-toggle").addEventListener("click", function () { clearInterval(timer); timer = null; toggle(); });
    var steps = document.querySelectorAll(".step");
    if ("IntersectionObserver" in window) {
      var obs = new IntersectionObserver(function (es) {
        es.forEach(function (e) {
          if (!e.isIntersecting) return;
          steps.forEach(function (s) { s.classList.toggle("on", s === e.target); });
          setStage(Number(e.target.dataset.step));
        });
      }, { rootMargin: "-40% 0px -45% 0px" });
      steps.forEach(function (s) { obs.observe(s); });
    } else steps.forEach(function (s) { s.classList.add("on"); });
    draw();
  })();

  // ======================================================================== Proving ground
  var proof = (function () {
    var prefix = Math.random().toString(36).slice(2, 6), worker = null, running = true, mode = "starting", lastResult = 0;
    var S = { runs: 0, events: 0, sigs: 0, attacks: 0, caught: 0, invOk: 0, invBad: 0, inv: {}, att: {}, t0: Date.now(), recent: [] };
    var fails = store("up-explorer-failures") || [];
    var INV = UP.lab.INVARIANTS, selected = null;
    Object.keys(INV).forEach(function (k) { S.inv[k] = { ok: 0, bad: 0 }; });
    Object.keys(UP.lab.ATTACKS).forEach(function (k) { S.att[k] = { n: 0, caught: 0, rules: {} }; });
    var TERM_LIST = Object.keys(TERMS).map(function (k) { return TERMS[k]; });
    var WORKER_MAIN = "var running=false,terms=null,prefix='',n=0;" +
      "function strip(a){return a.map(function(x){var o={};for(var k in x)if(k!=='_data')o[k]=x[k];return o;});}function summ(r){return {seed:r.seed,cfg:r.cfg,invariants:r.invariants,attacks:strip(r.attacks),events:r.events,sigs:r.sigs,ms:r.ms};}" +
      "function loop(){if(!running)return;var seed=prefix+'-'+(n++);var r;try{r=summ(UP.lab.runOne(seed,terms));}catch(e){r={seed:seed,invariants:[{id:'generator',ok:false,detail:String(e&&e.message)}],attacks:[],events:0,sigs:0,ms:0};}postMessage({type:'result',res:r});setTimeout(loop,0);}" +
      "onmessage=function(e){var m=e.data;if(m.type==='init'){terms={};m.terms.forEach(function(t){terms[t.id]=t;});prefix=m.prefix;n=m.n||0;}" +
      "if(m.type==='start'&&!running){running=true;loop();}if(m.type==='pause')running=false;" +
      "if(m.type==='one'){postMessage({type:'result',res:summ(UP.lab.runOne(m.seed,terms)),manual:true});}};";
    function startWorker() {
      try {
        var src = ["src-crypto", "src-engine", "src-lab"].map(function (id) { return $(id).textContent; }).join("\n;\n") + "\n" + WORKER_MAIN;
        worker = new Worker(URL.createObjectURL(new Blob([src], { type: "text/javascript" })));
        worker.onmessage = function (e) { if (e.data.type === "result") { mode = "worker"; onResult(e.data.res, e.data.manual); } };
        worker.onerror = function () { fallback(); };
        worker.postMessage({ type: "init", terms: TERM_LIST, prefix: prefix });
        worker.postMessage({ type: "start" });
        setTimeout(function () { if (mode === "starting") fallback(); }, 8000);
      } catch (e) { fallback(); }
    }
    var n = 0, mainTimer = null;
    function fallback() {
      if (mode === "main") return;
      if (worker) { try { worker.terminate(); } catch (e) { /* ignore */ } worker = null; }
      mode = "main"; n = S.runs; mainLoop();
    }
    function mainLoop() {
      clearTimeout(mainTimer);
      if (!running || mode !== "main") return;
      var seed = prefix + "-" + (n++);
      onResult(summarize(UP.lab.runOne(seed, TERMS)));
      mainTimer = setTimeout(mainLoop, 120);
    }
    function summarize(r) { return { seed: r.seed, cfg: r.cfg, invariants: r.invariants, attacks: r.attacks.map(function (a) { var o = {}; Object.keys(a).forEach(function (k) { if (k !== "_data") o[k] = a[k]; }); return o; }), events: r.events, sigs: r.sigs, ms: r.ms }; }
    function runSeed(seed) {
      if (mode === "worker" && worker) worker.postMessage({ type: "one", seed: seed });
      else onResult(summarize(UP.lab.runOne(seed, TERMS)), true);
    }
    function onResult(r, manual) {
      lastResult = Date.now();
      var bad = r.invariants.filter(function (x) { return !x.ok; });
      if (!manual) {
        S.runs++; S.events += r.events; S.sigs += r.sigs;
        r.invariants.forEach(function (x) { if (!S.inv[x.id]) S.inv[x.id] = { ok: 0, bad: 0 }; S.inv[x.id][x.ok ? "ok" : "bad"]++; S[x.ok ? "invOk" : "invBad"]++; S.inv[x.id].last = x.detail; });
        r.attacks.forEach(function (a) {
          var s = S.att[a.attack]; s.n++; S.attacks++;
          if (a.detected) { s.caught++; S.caught++; s.rules[a.rule] = (s.rules[a.rule] || 0) + 1; }
        });
      }
      if (bad.length && !fails.some(function (f) { return f.seed === r.seed; })) {
        fails.unshift({ seed: r.seed, failed: bad.map(function (b) { return b.id + ": " + b.detail; }), at: new Date().toISOString() });
        fails = fails.slice(0, 50); store("up-explorer-failures", fails);
      }
      S.recent.push(r); if (S.recent.length > 40) S.recent.shift();
      addBlock(r, manual);
      paint();
      if (manual) select(r.seed);
    }
    function addBlock(r, manual) {
      var train = $("pr-train"), empty = train.querySelector(".empty");
      if (empty) empty.remove();
      var ok = r.invariants.every(function (x) { return x.ok; }), c = r.cfg || {};
      var el = document.createElement("button");
      el.type = "button"; el.className = "blk new" + (ok ? "" : " fail"); el.dataset.seed = r.seed;
      el.innerHTML = '<span class="seed">' + esc(r.seed) + (manual ? " ↺" : "") + '</span><span class="big num">' + r.events + '</span><span class="meta">events · ' + r.ms + " ms</span>" +
        '<span class="meta">' + (c.members || 0) + " member" + (c.members === 1 ? "" : "s") + " · " + (c.tiers ? c.tiers.length : 0) + " tiers<br>" +
        [c.unit === "quarter" ? "quarterly" : "monthly", c.sealed ? "sealed" : "", c.agent ? "agent" : ""].filter(Boolean).join(" · ") + "</span>";
      el.addEventListener("click", function () { select(r.seed); });
      train.appendChild(el);
      while (train.children.length > 40) train.removeChild(train.firstChild);
      var nearEnd = train.scrollWidth - train.scrollLeft - train.clientWidth < 260;
      if (nearEnd) train.scrollLeft = train.scrollWidth;
    }
    function paint() {
      var secs = Math.max(1, (Date.now() - S.t0) / 1000);
      $("t-runs").textContent = fmtN(S.runs);
      $("t-rate").textContent = (S.runs / secs * 60).toFixed(0) + " runs a minute";
      $("t-events").textContent = fmtN(S.events);
      $("t-sigs").textContent = fmtN(S.sigs) + " signatures made and verified";
      $("t-attacks").textContent = fmtN(S.caught);
      $("t-attacks-s").textContent = "of " + fmtN(S.attacks) + " attempted";
      $("t-inv").textContent = fmtN(S.invOk);
      $("t-fail").textContent = fmtN(S.invBad);
      $("t-fail-tile").className = "tile " + (S.invBad ? "alarm" : "good");
      $("pr-status").textContent = running ? "Running live in your browser" : "Paused";
      $("pr-status").classList.toggle("running", running);
      $("pr-where").textContent = mode === "worker" ? "in a background worker" : mode === "main" ? "on the page (no background worker available)" : "";
      $("pr-inv").innerHTML = Object.keys(INV).map(function (k) {
        var s = S.inv[k], tot = s.ok + s.bad;
        return "<tr><td>" + esc(INV[k]) + '<div class="muted" style="font-size:0.78rem">' + esc(s.last || "") + '</div></td><td class="num">' + fmtN(s.ok) + '</td><td class="num" style="color:' + (s.bad ? "var(--bad)" : "inherit") + '">' + fmtN(s.bad) + "</td></tr>";
      }).join("");
      $("pr-att").innerHTML = Object.keys(S.att).map(function (k) {
        var s = S.att[k], rules = Object.keys(s.rules).map(function (r) { return '<span class="pill">' + esc(ruleName(r)) + "</span>"; }).join(" ");
        return "<tr><td>" + esc(UP.lab.ATTACKS[k].label) + '</td><td class="num">' + fmtN(s.caught) + " / " + fmtN(s.n) + '</td><td><div class="chips">' + (rules || '<span class="muted">—</span>') + "</div></td></tr>";
      }).join("");
      var fc = $("pr-fails-card");
      fc.hidden = !fails.length;
      if (fails.length) $("pr-fails").innerHTML = fails.map(function (f) {
        return '<div class="ev-item bad"><div><b class="mono">' + esc(f.seed) + '</b> <button class="btn small" type="button" data-replay="' + esc(f.seed) + '">Replay</button></div><div class="muted" style="font-size:0.82rem">' + f.failed.map(esc).join("<br>") + "</div></div>";
      }).join("");
    }
    function select(seed) {
      selected = seed;
      document.querySelectorAll("#pr-train .blk").forEach(function (b) { b.classList.toggle("sel", b.dataset.seed === seed); });
      var r = S.recent.filter(function (x) { return x.seed === seed; }).pop();
      if (!r) return;
      var c = r.cfg || {};
      var desc = c.members ? [c.members + " member" + (c.members === 1 ? "" : "s"), c.tiers.length + " tiers (" + c.tiers.join(", ") + ")", c.items + " item" + (c.items === 1 ? "" : "s"),
        (c.unit === "quarter" ? "quarterly" : "monthly") + " reporting", "fee " + (c.bp / 100).toFixed(2) + "% rounded " + c.mode, c.renewing ? "renewing term" : "fixed term",
        c.sealed ? "every price, rate, quantity and amount sealed" : "values in the clear", c.agent ? "member 1 acts through an agent under a Mandate" : "no agents"].join(" · ") : "";
      $("pr-detail").innerHTML = '<div class="clause-head"><h3>Run <span class="mono">' + esc(seed) + "</span></h3>" +
        '<button class="btn small primary" type="button" data-replay="' + esc(seed) + '">Replay this run</button></div>' +
        '<p class="muted" style="font-size:0.88rem;margin-top:0.3rem">' + esc(desc) + ". " + r.events + " events, computed in " + r.ms + " ms.</p>" +
        '<div class="grid2" style="margin-top:0.8rem"><div><h3 style="font-size:0.9rem">Invariants</h3><ul class="inv-list">' +
        r.invariants.map(function (x) { return '<li><span class="ic ' + (x.ok ? "ok" : "bad") + '">' + (x.ok ? "✓" : "✗") + "</span><span><b>" + esc(INV[x.id] || x.id) + '</b><br><span class="muted">' + esc(x.detail) + "</span></span></li>"; }).join("") +
        '</ul></div><div><h3 style="font-size:0.9rem">Attacks</h3><ul class="inv-list">' +
        r.attacks.map(function (a) { return '<li><span class="ic ' + (a.detected ? "ok" : "bad") + '">' + (a.detected ? "✓" : "✗") + "</span><span><b>" + esc(a.label) + "</b> on chain " + a.chain + ", event " + a.index + '<br><span class="muted">Caught by ' + esc(ruleName(a.rule)) + ": " + esc(a.reason) + "</span></span></li>"; }).join("") +
        "</ul></div></div>";
    }
    document.addEventListener("click", function (e) {
      var b = e.target.closest && e.target.closest("[data-replay]");
      if (!b) return;
      var seed = b.dataset.replay;
      b.disabled = true; b.textContent = "Computing…";
      setTimeout(function () {
        var res = UP.lab.runOne(seed, TERMS);
        if (!res.g) { b.textContent = "Could not generate"; return; }
        replay.loadLive(UP.lab.traceOf(res), seed);
        b.disabled = false; b.textContent = "Replay";
        $("replay").scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
      }, 30);
    });
    $("pr-toggle").addEventListener("click", function () {
      running = !running;
      this.textContent = running ? "Pause" : "Resume";
      if (mode === "worker" && worker) worker.postMessage({ type: running ? "start" : "pause" });
      else if (mode === "main") mainLoop();
      paint();
    });
    $("pr-seedform").addEventListener("submit", function (e) { e.preventDefault(); var s = $("pr-seed").value.trim(); if (s) runSeed(s); });
    paint();
    setTimeout(startWorker, 400);
    return {};
  })();

  // ======================================================================== Playground
  var pg = (function () {
    var D = function (n) { return { unit: "day", count: n }; }, M = { unit: "month", count: 1 }, Q = { unit: "quarter", count: 1 }, Y = { unit: "year", count: 1 };
    var R2 = { scale: 2, mode: "half-even" }, G = function (s) { return { scheme: "GTIN", id: s }; }, USD = function (v) { return { value: v, currency: "USD" }; };
    var SAMPLE = {
      "UP:Admin-Fee": { payer: "supplier", payee: "aggregator", rate: "0.02", report_clause: "reporting", period: M, due: D(30), rounding: R2 },
      "UP:Audit": { auditor: "aggregator", auditee: "supplier", response: D(30), max_requests: 1, per: Y },
      "UP:Fee-Disclosure": { period: Q, due: D(30) },
      "UP:Fixed-Term": { start: "2027-01-01T00:00:00Z", end: "2028-01-01T00:00:00Z" },
      "UP:Governing-Law": { law: "[hypothetical jurisdiction]", forum: "[hypothetical forum]" },
      "UP:Notices": {},
      "UP:Overlay": { document: "sha256:" + UP.hex(UP.sha256(UP.utf8("Hypothetical existing agreement"))), document_title: "Hypothetical Group Purchasing Agreement", document_date: "2024-03-01T00:00:00Z", governs: "document" },
      "UP:Participation": { parent: "sha256:" + UP.hex(UP.sha256(UP.utf8("Hypothetical master agreement"))) },
      "UP:Price-Reference": { items: [G("00000000000017"), G("00000000000024")], list_role: "supplier", factor: "0.95", rounding: R2 },
      "UP:Purchase-Commitment": { category: "Hypothetical product category", share: "0.8", period: Q, due: D(30) },
      "UP:Renewing-Term": { start: "2027-01-01T00:00:00Z", end: "2028-01-01T00:00:00Z", renewal_period: Y, max_renewals: 2, optout_roles: ["aggregator", "supplier"], optout_notice: D(90) },
      "UP:Sales-Reporting": { reporter: "supplier", recipient: "aggregator", period: M, due: D(15) },
      "UP:Termination-Cause": { holders: ["aggregator", "supplier"], cure_period: D(30), notice: D(30) },
      "UP:Termination-Convenience": { holders: ["aggregator", "supplier"], notice: D(90) },
      "UP:Tier-Selection": { tiers_clause: "tiers", initial: "C", effective: "on-ack" },
      "UP:Tiers": { tiers: [{ name: "A", conditions: "Hypothetical: annual purchases at or above level A" }, { name: "B", conditions: "Hypothetical: annual purchases at or above level B" }, { name: "C", conditions: "Hypothetical: any participating member" }],
        prices: [{ item: G("00000000000017"), by: { A: USD("9.10"), B: USD("9.40"), C: USD("9.80") } }, { item: G("00000000000024"), by: { A: USD("21.00"), B: USD("21.75"), C: USD("22.50") } }] }
    };
    var NAMES = { "UP:Admin-Fee": "fee", "UP:Audit": "audit", "UP:Fee-Disclosure": "disclosure", "UP:Fixed-Term": "term", "UP:Governing-Law": "law", "UP:Notices": "notices", "UP:Overlay": "overlay",
      "UP:Participation": "participation", "UP:Price-Reference": "prices", "UP:Purchase-Commitment": "commitment", "UP:Renewing-Term": "term", "UP:Sales-Reporting": "reporting",
      "UP:Termination-Cause": "cause", "UP:Termination-Convenience": "exit", "UP:Tier-Selection": "tier", "UP:Tiers": "tiers" };
    var PRESETS = {
      master: { label: "Master agreement (example)", roles: ["aggregator", "supplier"], terms: ["UP:Fixed-Term", "UP:Tiers", "UP:Sales-Reporting", "UP:Admin-Fee", "UP:Termination-Convenience", "UP:Governing-Law"] },
      participation: { label: "Participation of a member (example)", roles: ["aggregator", "member", "supplier"], terms: ["UP:Participation", "UP:Tier-Selection", "UP:Fixed-Term", "UP:Termination-Convenience"] },
      overlay: { label: "Overlay of an existing agreement (example)", roles: ["aggregator", "supplier"], terms: ["UP:Overlay", "UP:Fixed-Term", "UP:Sales-Reporting", "UP:Admin-Fee"] }
    };
    var SEALABLE = { Rate: 1, Decimal: 1, string: 1 };
    var st = {
      label: "", parties: { aggregator: { name: "Hypothetical Purchasing Group", on: true }, supplier: { name: "Example Supply Co.", on: true }, member: { name: "Sample Community Clinic", on: false } },
      clauses: [], salts: {}, sigs: null, signedHash: null, prevHash: null, observer: false
    };
    function newClause(term) {
      var base = NAMES[term] || "clause", n = base, i = 2;
      while (st.clauses.some(function (c) { return c.n === n; })) n = base + "-" + (i++);
      return { n: n, term: term, params: clone(SAMPLE[term] || {}), over: [], sealed: {}, raw: {} };
    }
    function preset(name) {
      var p = PRESETS[name];
      st.label = p.label; st.clauses = [];
      ["aggregator", "supplier", "member"].forEach(function (r) { st.parties[r].on = p.roles.indexOf(r) >= 0; });
      p.terms.forEach(function (t) { st.clauses.push(newClause(t)); });
      st.sigs = null; st.signedHash = null;
      drawEditor(); update();
    }
    var keyCache = {};
    function keyFor(role, name) { var s = "playground:" + role + ":" + name; return keyCache[s] || (keyCache[s] = UP.Key.fromSeed(s)); }
    function build() {
      var discs = [];
      var parties = ["aggregator", "member", "supplier"].filter(function (r) { return st.parties[r].on; }).map(function (r) {
        return { role: r, party: { key: keyFor(r, st.parties[r].name).public, name: st.parties[r].name } };
      }).sort(function (a, b) { return a.role < b.role ? -1 : a.role > b.role ? 1 : a.party.key < b.party.key ? -1 : 1; });
      var clauses = st.clauses.map(function (c) {
        var params = {};
        Object.keys(c.params).forEach(function (p) {
          var v = c.params[p];
          if (c.sealed[p]) {
            var sk = c.n + "/" + p + "/" + JSON.stringify(v);
            var salt = st.salts[sk] || (st.salts[sk] = randomHex());
            var s = UP.sealOf(v, salt); discs.push({ seal: s.seal, salt: salt, value: v }); v = s;
          }
          params[p] = v;
        });
        var o = { n: c.n, term: c.term, def: ch(TERMS[c.term]), params: params };
        if (c.over.length) o.over = c.over.slice();
        return o;
      });
      var ag = { type: "Agreement", spec: UP.SPEC, parties: parties, clauses: clauses };
      if (st.label) ag.label = st.label;
      return { ag: ag, discs: discs };
    }
    function randomHex() { var a = new Uint8Array(32); (window.crypto || {}).getRandomValues ? window.crypto.getRandomValues(a) : a.forEach(function (_, i) { a[i] = Math.floor(Math.random() * 256); }); return UP.hex(a); }

    // ---- editors
    function typeEditor(ci, p, type, v) {
      var id = "pg-" + ci + "-" + p, c = st.clauses[ci];
      var sealBtn = SEALABLE[type] ? '<button type="button" class="sealbtn' + (c.sealed[p] ? " on" : "") + '" data-seal="' + ci + "|" + esc(p) + '" title="Seal this value: only a hash goes into the agreement">' + (c.sealed[p] ? "sealed" : "seal") + "</button>" : "";
      var head = '<span><label for="' + id + '">' + esc(p) + ' <span class="mono" style="opacity:0.7">' + esc(type) + "</span></label>" + sealBtn + "</span>";
      var body;
      if (type === "Time") body = '<input type="date" id="' + id + '" data-k="time" value="' + esc(String(v).slice(0, 10)) + '">';
      else if (type === "Period") body = '<div class="row"><input type="number" min="1" id="' + id + '" data-k="pcount" value="' + esc(v.count) + '"><select data-k="punit" aria-label="' + esc(p) + ' unit">' + ["day", "month", "quarter", "year"].map(function (u) { return "<option" + (u === v.unit ? " selected" : "") + ">" + u + "</option>"; }).join("") + "</select></div>";
      else if (type === "Role") body = '<select id="' + id + '" data-k="role">' + UP.ROLES.map(function (r) { return "<option" + (r === v ? " selected" : "") + ">" + r + "</option>"; }).join("") + "</select>";
      else if (type === "[Role]") body = '<div class="checks-inline" id="' + id + '">' + UP.ROLES.map(function (r) { return '<label><input type="checkbox" data-k="roles" value="' + r + '"' + (v.indexOf(r) >= 0 ? " checked" : "") + "> " + r + "</label>"; }).join("") + "</div>";
      else if (type === "int") body = '<input type="number" id="' + id + '" data-k="int" value="' + esc(v) + '">';
      else if (type === "Rounding") body = '<div class="row"><input type="number" min="0" max="6" id="' + id + '" data-k="rscale" value="' + esc(v.scale) + '"><select data-k="rmode" aria-label="rounding mode">' + ["half-even", "half-up", "down", "up"].map(function (m) { return "<option" + (m === v.mode ? " selected" : "") + ">" + m + "</option>"; }).join("") + "</select></div>";
      else if (/^"on-ack"/.test(type)) body = '<select id="' + id + '" data-k="effective"><option value="on-ack"' + (v === "on-ack" ? " selected" : "") + '>on acknowledgment</option><option value="month"' + (v !== "on-ack" && v.next.unit === "month" ? " selected" : "") + '>start of next month</option><option value="quarter"' + (v !== "on-ack" && v.next.unit === "quarter" ? " selected" : "") + ">start of next quarter</option></select>";
      else if (/^"document"/.test(type)) body = '<select id="' + id + '" data-k="enum">' + ["document", "this-record"].map(function (x) { return "<option" + (x === v ? " selected" : "") + ">" + x + "</option>"; }).join("") + "</select>";
      else if (type === "Rate" || type === "Decimal" || type === "string" || type === "Hash" || type === "ChainId") body = '<input type="text" id="' + id + '" data-k="' + (type === "Rate" || type === "Decimal" ? "dec" : "str") + '" value="' + esc(v) + '" spellcheck="false">';
      else body = '<textarea id="' + id + '" data-k="json" spellcheck="false">' + esc(JSON.stringify(v, null, 1)) + "</textarea>";
      return '<div class="field" data-ci="' + ci + '" data-p="' + esc(p) + '">' + head + body + '<span class="errmsg" hidden></span></div>';
    }
    function drawEditor() {
      var html = '<div class="card"><div class="clause-head"><h3>Start from</h3></div><div class="controls">' +
        Object.keys(PRESETS).map(function (k) { return '<button class="btn small" type="button" data-preset="' + k + '">' + esc(PRESETS[k].label.replace(" (example)", "")) + "</button>"; }).join("") + "</div>" +
        '<div class="field"><span><label for="pg-label">Label</label></span><input type="text" id="pg-label" value="' + esc(st.label) + '"></div></div>';
      html += '<div class="card"><h3>Parties</h3>' + ["aggregator", "supplier", "member"].map(function (r) {
        return '<div class="field"><span><label for="pg-party-' + r + '">' + r + '</label><label style="display:flex;gap:0.3rem"><input type="checkbox" data-party-on="' + r + '"' + (st.parties[r].on ? " checked" : "") + "> include</label></span>" +
          '<input type="text" id="pg-party-' + r + '" data-party="' + r + '" value="' + esc(st.parties[r].name) + '"></div>';
      }).join("") + '<p class="muted" style="font-size:0.78rem">Each name derives an example key, so renaming a party changes the fingerprint.</p></div>';
      html += st.clauses.map(function (c, ci) {
        var t = TERMS[c.term], ps = Object.keys(t.params);
        return '<details class="card clause" open><summary><div class="clause-head"><span><span class="t">' + esc(t.title) + '</span><br><span class="id">' + esc(c.term) + "</span></span>" +
          '<button class="btn small" type="button" data-remove="' + ci + '" aria-label="Remove ' + esc(t.title) + '">Remove</button></div></summary>' +
          '<div class="field"><span><label for="pg-n-' + ci + '">clause name</label></span><input type="text" id="pg-n-' + ci + '" data-cname="' + ci + '" value="' + esc(c.n) + '"></div>' +
          (ps.length ? ps.map(function (p) { return typeEditor(ci, p, t.params[p].type, c.params[p]); }).join("") : '<p class="muted" style="font-size:0.82rem">This Term takes no parameters.</p>') +
          '<div class="field"><span><label for="pg-over-' + ci + '">takes precedence over</label><span class="mono" style="opacity:0.7">clause names</span></span><input type="text" id="pg-over-' + ci + '" data-over="' + ci + '" value="' + esc(c.over.join(", ")) + '" placeholder="none"></div></details>';
      }).join("");
      html += '<div class="card"><div class="field"><span><label for="pg-add">Add a Term from the library</label></span><select id="pg-add"><option value="">Choose a Term…</option>' +
        Object.keys(TERMS).sort().map(function (k) { return '<option value="' + esc(k) + '">' + esc(TERMS[k].title) + " (" + esc(k) + ")</option>"; }).join("") + "</select></div></div>";
      $("pg-editor").innerHTML = html;
    }
    var ed = $("pg-editor");
    ed.addEventListener("click", function (e) {
      var t = e.target;
      if (t.dataset.preset) preset(t.dataset.preset);
      else if (t.dataset.remove != null) { e.preventDefault(); st.clauses.splice(Number(t.dataset.remove), 1); drawEditor(); update(); }
      else if (t.dataset.seal) { var a = t.dataset.seal.split("|"), c = st.clauses[Number(a[0])]; c.sealed[a[1]] = !c.sealed[a[1]]; t.classList.toggle("on"); t.textContent = c.sealed[a[1]] ? "sealed" : "seal"; update(); }
    });
    ed.addEventListener("change", function (e) {
      var t = e.target;
      if (t.id === "pg-add" && t.value) { st.clauses.push(newClause(t.value)); drawEditor(); update(); return; }
      if (t.dataset.partyOn) { st.parties[t.dataset.partyOn].on = t.checked; update(); return; }
      onInput(e);
    });
    ed.addEventListener("input", onInput);
    function onInput(e) {
      var t = e.target;
      if (t.id === "pg-label") { st.label = t.value; return update(); }
      if (t.dataset.party) { st.parties[t.dataset.party].name = t.value; return update(); }
      if (t.dataset.cname != null) { st.clauses[Number(t.dataset.cname)].n = t.value; return update(); }
      if (t.dataset.over != null) { st.clauses[Number(t.dataset.over)].over = t.value.split(",").map(function (s) { return s.trim(); }).filter(Boolean); return update(); }
      var f = t.closest(".field"); if (!f || f.dataset.ci == null) return;
      var c = st.clauses[Number(f.dataset.ci)], p = f.dataset.p, k = t.dataset.k, v = c.params[p], err = "";
      try {
        if (k === "time") { if (!t.value) throw new Error("Choose a date."); v = t.value + "T00:00:00Z"; }
        else if (k === "pcount" || k === "punit") { var cnt = Number(f.querySelector('[data-k="pcount"]').value); if (!(cnt >= 1 && Number.isInteger(cnt))) throw new Error("Use a whole number of 1 or more."); v = { unit: f.querySelector('[data-k="punit"]').value, count: cnt }; }
        else if (k === "role" || k === "enum") v = t.value;
        else if (k === "roles") v = Array.prototype.filter.call(f.querySelectorAll('[data-k="roles"]'), function (x) { return x.checked; }).map(function (x) { return x.value; });
        else if (k === "int") { var n = Number(t.value); if (!Number.isInteger(n)) throw new Error("Use a whole number."); v = n; }
        else if (k === "rscale" || k === "rmode") { var sc = Number(f.querySelector('[data-k="rscale"]').value); if (!Number.isInteger(sc) || sc < 0) throw new Error("Use a whole number of places."); v = { scale: sc, mode: f.querySelector('[data-k="rmode"]').value }; }
        else if (k === "effective") v = t.value === "on-ack" ? "on-ack" : { next: { unit: t.value, count: 1 } };
        else if (k === "dec") { if (!/^-?(0|[1-9][0-9]*)(\.[0-9]+)?$/.test(t.value)) throw new Error("Write a decimal such as 0.02, with no % sign."); v = t.value; }
        else if (k === "str") v = t.value;
        else if (k === "json") { v = JSON.parse(t.value); UP.jcsString(v); }
      } catch (ex) { err = ex instanceof SyntaxError ? "That is not valid JSON yet." : ex.message; }
      f.classList.toggle("err", !!err);
      var em = f.querySelector(".errmsg"); em.hidden = !err; em.textContent = err;
      if (!err) { c.params[p] = v; update(); }
    }

    // ---- outputs
    function mdToHTML(md) {
      var out = [], inList = false;
      function inline(s) {
        return esc(s).replace(/\[sealed (sha256:[0-9a-f]{64})\]/g, '<span class="sealed" title="$1">sealed $1</span>')
          .replace(/(sha256:[0-9a-f]{64}|ed25519:[0-9a-f]{64})/g, function (m, h, off, str) { return str.slice(Math.max(0, off - 21), off).indexOf('class="sealed"') >= 0 || str.slice(Math.max(0, off - 7), off) === "sealed " || str.slice(off - 7, off) === 'title="' ? m : "<code>" + m + "</code>"; });
      }
      md.split("\n").forEach(function (l) {
        if (/^- /.test(l)) { if (!inList) { out.push("<ul>"); inList = true; } out.push("<li>" + inline(l.slice(2)) + "</li>"); return; }
        if (inList) { out.push("</ul>"); inList = false; }
        if (/^### /.test(l)) out.push("<h6>" + inline(l.slice(4)) + "</h6>");
        else if (/^## /.test(l)) out.push("<h5>" + inline(l.slice(3)) + "</h5>");
        else if (/^# /.test(l)) out.push("<h4>" + inline(l.slice(2)) + "</h4>");
        else if (/^(Spec version|Agreement hash):/.test(l)) out.push('<p class="meta">' + inline(l) + "</p>");
        else if (l.trim()) out.push("<p>" + inline(l) + "</p>");
      });
      if (inList) out.push("</ul>");
      return out.join("");
    }
    function update() {
      var built = build(), ag = built.ag, h = ch(ag);
      var data = { type: "Bundle", spec: UP.SPEC, terms: Object.keys(TERMS).map(function (k) { return TERMS[k]; }) };
      if (!st.observer) data.disclosures = built.discs;
      var b = new UP.Bundle(data);
      var issues = UP.agreementIssues(b, ag);
      var fpEl = $("pg-fp");
      fpEl.innerHTML = fpHTML(h, st.prevHash, "Agreement fingerprint" + (st.prevHash && st.prevHash !== h ? " · changed" : ""));
      $("pg-fpmini").innerHTML = fpHTML(h, st.prevHash, "Fingerprint").replace('class="lab"', 'class="lab" style="display:none"');
      if (st.prevHash && st.prevHash !== h) flash(fpEl);
      st.prevHash = h;
      $("pg-valid").innerHTML = issues.length ? '<span class="pill bad">' + issues.length + " problem" + (issues.length === 1 ? "" : "s") + "</span>" : '<span class="pill ok">Valid under A1, A6, A10, A13</span>';
      var text = "";
      try { text = UP.renderAgreement(b, ag); } catch (e) { text = "# " + (ag.label || "Agreement") + "\n\nThe text cannot be generated until the problems listed on the cover sheet are fixed (" + e.message + ")."; }
      $("pg-contract").innerHTML = mdToHTML(text);
      // cover sheet
      var sigHtml;
      if (!st.sigs) sigHtml = '<span class="muted">Not signed yet. Press “Sign as every party”.</span>';
      else {
        var now = ag.parties.map(function (p) { return p.party.key; });
        sigHtml = st.sigs.map(function (s) {
          var ok = UP.verifySig(s.key, s.sig, ag) && now.indexOf(s.key) >= 0;
          return '<div class="s"><span style="color:' + (ok ? "#17804f" : "#c43535") + '">' + (ok ? "✓" : "✗") + "</span><span>" + esc(s.name) + " · " + (ok ? "verifies over " + short(h) + "…" : "signed " + short(st.signedHash) + "…, which is no longer this agreement") + "</span></div>";
        }).join("");
        if (st.signedHash !== h) sigHtml += '<p style="color:#c43535;font-size:0.85rem;margin-top:0.3rem">The agreement changed after signing, so these signatures no longer verify. Nothing about the old text can be reused.</p>';
      }
      var termsHtml = st.clauses.map(function (c, i) {
        var t = TERMS[c.term], line = "";
        try { line = UP.renderTemplate(b, t.render, ag.clauses[i].params); var m = line.match(/^[\s\S]*?[.!?](\s|$)/); line = m ? m[0] : line; } catch (e) { line = "(fill in this clause’s values)"; }
        return "<li><b>" + esc(t.title) + ' · “' + esc(c.n) + '”</b>' + mdToHTML(line).replace(/^<p>|<\/p>$/g, "") + "</li>";
      }).join("");
      $("pg-cover").innerHTML = '<h5 style="margin-top:0">Cover sheet</h5><h4>' + esc(ag.label || "Untitled agreement") + "</h4>" +
        '<dl><dt>Fingerprint</dt><dd class="meta">' + esc(h) + "</dd><dt>Spec</dt><dd>" + esc(UP.SPEC) + "</dd>" +
        ag.parties.map(function (p) { return "<dt>" + esc(p.role) + "</dt><dd>" + esc(p.party.name) + '<div class="meta">' + esc(p.party.key.slice(0, 24)) + "…</div></dd>"; }).join("") +
        "<dt>Status</dt><dd>" + (issues.length ? '<ul class="issues">' + issues.map(function (x) { return "<li>" + esc(x[0]) + " " + esc(RULES[x[0]] || "") + ": " + esc(x[1]) + "</li>"; }).join("") + "</ul>" : "Valid: built only from defined Terms, every value supplied by the parties, conflicts resolved.") + "</dd>" +
        (built.discs.length ? "<dt>Sealed</dt><dd>" + built.discs.length + " value" + (built.discs.length === 1 ? "" : "s") + (st.observer ? ", hidden from you as an outsider" : ", visible to you as a party") + "</dd>" : "") +
        '</dl><ul class="terms">' + (termsHtml || '<li class="muted">No Terms yet. Add one from the library.</li>') + '</ul><h5>Signatures</h5><div class="sigs">' + sigHtml + "</div>";
      $("pg-json").textContent = (function () { try { return UP.jcsString(ag); } catch (e) { return e.message; } })();
    }
    $("pg-sign").addEventListener("click", function () {
      var ag = build().ag;
      st.sigs = ag.parties.map(function (p) { var k = keyFor(p.role, p.party.name); var s = k.signObj(ag); s.name = p.party.name; return s; });
      st.signedHash = ch(ag); update();
    });
    $("pg-observer").addEventListener("change", function () { st.observer = this.checked; update(); });
    preset("master");
    return {};
  })();

  // ======================================================================== Replay
  var replay = (function () {
    var RECORDED = [
      { file: "conventional.trace.json", label: "Conventional GPO arrangement" },
      { file: "conventional.tamper-supplier-fee.trace.json", label: "Fault: supplier copy has a changed fee" },
      { file: "conventional.tamper-member-backdate.trace.json", label: "Fault: member copy has a backdated attestation" },
      { file: "conventional.tamper-aggregator-missing-signature.trace.json", label: "Fault: aggregator copy is missing a signature" },
      { file: "generative.trace.json", label: "Generative: agents under Mandates" },
      { file: "confidential.trace.json", label: "Confidential: verification from hashes only" },
      { file: "overlay.trace.json", label: "Overlay of an existing agreement" }
    ];
    var BASES = ["../examples/traces/", "examples/traces/", "traces/", ""];
    var KIND = { propose: "P", accept: "A", attest: "T" }, KIND_NAME = { propose: "Proposal", accept: "Acceptance", attest: "Attestation" };
    var trace = null, cur = 0, timer = null, checkWho = null, live = [], liveFlag = false;
    function hue(pos) { return "var(--c" + (pos % 6) + ")"; }
    function nm(k) { return (trace.parties && trace.parties[k]) || (k ? k.slice(0, 16) + "…" : ""); }
    function amt(a) { if (a === "sealed") return '<span class="pill">sealed</span>'; if (typeof a === "string") return '<span class="muted">' + esc(a) + "</span>"; return a ? esc(a.currency + " " + a.value) : "—"; }
    function fillPick() {
      $("rp-pick").innerHTML = '<optgroup label="Recorded by the Python reference interpreter">' + RECORDED.map(function (s) { return '<option value="rec:' + esc(s.file) + '">' + esc(s.label) + "</option>"; }).join("") + "</optgroup>" +
        (live.length ? '<optgroup label="Live runs from this page">' + live.map(function (l, i) { return '<option value="live:' + i + '">Live run ' + esc(l.seed) + "</option>"; }).join("") + "</optgroup>" : "");
    }
    function fetchTrace(file) {
      var i = 0;
      function next() { if (i >= BASES.length) return Promise.reject(new Error("not found")); return fetch(BASES[i++] + file).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }).catch(next); }
      return next();
    }
    function pick(v) {
      stop();
      if (v.indexOf("live:") === 0) return load(live[Number(v.slice(5))].trace, true);
      $("rp-event").innerHTML = '<p class="muted">Loading the recorded trace…</p>';
      fetchTrace(v.slice(4)).then(function (t) { load(t, false); }).catch(function () {
        trace = null; $("rp-train").innerHTML = ""; $("rp-legend").innerHTML = ""; $("rp-desc").textContent = "";
        $("rp-event").innerHTML = '<p class="empty">This recorded trace could not be loaded here. Open explorer/index.html from the repository, next to examples/traces/. Live runs from the proving ground replay anywhere.</p>';
        ["rp-evals", "rp-checks", "rp-derived"].forEach(function (id) { $(id).innerHTML = ""; });
      });
    }
    function load(t, isLive) {
      trace = t; liveFlag = isLive; cur = 0;
      checkWho = (t.evaluators.filter(function (e) { return e.tampered; })[0] || t.evaluators[0]).id;
      $("rp-source").innerHTML = isLive ? '<span class="pill live">Live · computed in your browser</span>' : '<span class="pill">Recorded · Python reference interpreter</span>';
      $("rp-desc").textContent = t.description || "";
      $("rp-legend").innerHTML = t.chains.map(function (c) { return '<span style="--hue:' + hue(c.position) + '">' + esc(c.label) + "</span>"; }).join("") + '<span style="--hue:var(--bad)">rejected by an evaluator (dot) · evaluators disagree (dashed)</span>';
      $("rp-train").innerHTML = t.steps.map(function (s, i) {
        var e = s.event, rej = Object.keys(s.results).some(function (k) { return !s.results[k].accepted; });
        return '<button type="button" class="eb' + (rej ? " rej" : "") + (s.consensus ? "" : " div") + '" style="--hue:' + hue(e.chain) + '" data-i="' + i + '" title="' + esc(e.description) + '"><span class="kd">' + KIND[e.kind] + "</span><span>" + esc(e.at.slice(5, 10)) + "<br>#" + i + "</span></button>";
      }).join("");
      go(0);
    }
    function go(i) {
      if (!trace) return;
      cur = Math.max(0, Math.min(trace.steps.length - 1, i));
      var bs = $("rp-train").children;
      for (var k = 0; k < bs.length; k++) { bs[k].classList.toggle("cur", k === cur); bs[k].classList.toggle("future", k > cur); }
      var cb = bs[cur]; if (cb) { var tr = $("rp-train"); var l = cb.offsetLeft - tr.offsetLeft; if (l < tr.scrollLeft || l > tr.scrollLeft + tr.clientWidth - 70) tr.scrollLeft = l - tr.clientWidth / 2; }
      $("rp-count").textContent = "Event " + (cur + 1) + " of " + trace.steps.length;
      var s = trace.steps[cur], e = s.event;
      var mand = "";
      if (e.mandate) {
        var lim = [];
        Object.keys(e.mandate.scope.claims || {}).forEach(function (c) { var b = e.mandate.scope.claims[c]; Object.keys(b).forEach(function (f) { if (!b[f].any) lim.push(c.split("/")[1] + " · " + f + ": " + JSON.stringify(b[f])); }); });
        Object.keys(e.mandate.scope.terms || {}).forEach(function (t) { var b = e.mandate.scope.terms[t]; Object.keys(b).forEach(function (p) { if (!b[p].any) lim.push(t + " · " + p + ": " + JSON.stringify(b[p])); }); });
        mand = "<dt>Mandate</dt><dd>Agent acting for " + esc(e.mandate.principal_name) + ", valid " + esc(e.mandate.not_before.slice(0, 10)) + " to " + esc(e.mandate.expires.slice(0, 10)) + (lim.length ? '<div class="muted" style="font-size:0.8rem">Limits: ' + lim.map(esc).join("; ") + "</div>" : "") + "</dd>";
      }
      $("rp-event").innerHTML = '<span class="eyebrow" style="color:' + hue(e.chain) + '">' + esc(e.chain_label) + " · event " + e.index + "</span><h3 style=\"margin-top:0.35rem\">" + esc(e.description) + "</h3>" +
        '<dl class="kv"><dt>Kind</dt><dd>' + KIND_NAME[e.kind] + "</dd><dt>Time</dt><dd class=\"mono\">" + esc(e.at) + "</dd><dt>Author</dt><dd>" + esc(e.by_name) + "</dd>" +
        "<dt>Signed by</dt><dd>" + e.signers.map(function (g) { return esc(g.name) + (g.mandate ? " (agent, under Mandate)" : ""); }).join("; ") + "</dd>" + mand +
        '<dt>Event</dt><dd class="hash">' + esc(e.hash) + '</dd><dt>Builds on</dt><dd class="hash">' + esc(e.prev || "nothing (this event starts the chain)") + "</dd></dl>";
      var counts = {};
      trace.evaluators.forEach(function (ev) { var h = s.results[ev.id].world_hash; counts[h] = (counts[h] || 0) + 1; });
      var major = Object.keys(counts).sort(function (a, b) { return counts[b] - counts[a]; })[0];
      $("rp-evals").innerHTML = "<h3>Independent evaluators</h3><p class=\"muted\" style=\"font-size:0.84rem;margin:0.3rem 0 0.6rem\">" + (s.consensus ? "All evaluators hold the same world fingerprint." : "The evaluators disagree. The copy that differs is identified at this exact event.") + '</p><div class="ev-list">' +
        trace.evaluators.map(function (ev) {
          var r = s.results[ev.id], same = r.world_hash === major;
          return '<div class="ev-item' + (same ? "" : " bad") + '"><div class="clause-head"><b>' + esc(ev.name) + "</b>" + '<span class="pill ' + (r.accepted ? "ok" : "bad") + '">' + (r.accepted ? "accepted" : "rejected") + "</span></div>" +
            (ev.tampered ? '<span style="color:var(--bad);font-size:0.8rem">' + esc(ev.tampered) + "</span>" : "") + (ev.hashes_only ? '<span class="muted" style="font-size:0.8rem">Holds no disclosures: sees only seals.</span>' : "") +
            '<span class="hash" style="color:' + (same ? "var(--ok)" : "var(--bad)") + '">world ' + esc(short(r.world_hash)) + "…</span>" + (r.accepted ? "" : '<span style="font-size:0.82rem">' + esc(r.reason) + "</span>") + "</div>";
        }).join("") + "</div>";
      drawChecks(); drawDerived();
    }
    function drawChecks() {
      var s = trace.steps[cur], r = s.results[checkWho];
      $("rp-checks").innerHTML = "<h3>Validation</h3>" + '<div class="tabs">' + trace.evaluators.map(function (ev) { return '<button type="button" data-who="' + esc(ev.id) + '" class="' + (ev.id === checkWho ? "on" : "") + '">' + esc(ev.name) + "</button>"; }).join("") + "</div>" +
        (r.checks.length ? r.checks.map(function (c) { return '<div class="chk"><span class="' + (c.passed ? "y" : "n") + '">' + (c.passed ? "✓" : "✗") + "</span><span>" + esc(c.reason) + '<br><span class="r">' + esc(c.rule) + " · " + esc(c.label) + "</span></span></div>"; }).join("") : '<p class="muted">' + esc(r.reason) + "</p>");
    }
    function drawDerived() {
      var d = trace.steps[cur].results[checkWho].derived;
      var html = "<h3>What follows, as of " + esc(d.at.slice(0, 10)) + "</h3><p class=\"muted\" style=\"font-size:0.82rem\">Statuses, tiers, prices, and obligations as " + esc((trace.evaluators.filter(function (e) { return e.id === checkWho; })[0] || {}).name) + " computes them.</p>";
      (d.chains || []).forEach(function (c) {
        html += '<div class="derived-chain"><div class="clause-head"><b style="color:' + hue(c.chain) + '">' + esc(c.label) + '</b><span class="pill">' + esc(c.status) + "</span></div>";
        if (c.window) html += '<span class="muted" style="font-size:0.82rem">In force ' + esc((c.window.start || "").slice(0, 10)) + " to " + esc(c.window.end ? c.window.end.slice(0, 10) : "open-ended") + "</span>";
        if (c.selections) html += Object.keys(c.selections).map(function (k) { return '<span style="font-size:0.85rem">Tier for ' + esc(nm(k)) + ": <b>" + esc(c.selections[k] || "none") + "</b></span>"; }).join("");
        if (c.prices && c.prices.length) html += '<div class="scroll-x"><table><thead><tr><th>Item</th><th class="num">Price</th></tr></thead><tbody>' + c.prices.map(function (p) { return "<tr><td class=\"mono\">" + esc(p.item.scheme + " " + (typeof p.item.id === "string" ? p.item.id : "sealed")) + '</td><td class="num">' + amt(p.price) + "</td></tr>"; }).join("") + "</tbody></table></div>";
        if (c.obligations && c.obligations.length) html += '<div class="scroll-x"><table><thead><tr><th>Duty</th><th>Period</th><th class="num">Amount</th><th>Status</th></tr></thead><tbody>' + c.obligations.map(function (o) {
          var bad = o.status === "overdue";
          return "<tr><td>" + esc(o.clause) + " · " + esc(o.duty) + '</td><td class="mono" style="white-space:nowrap">' + esc(o.period.start.slice(0, 10)) + (o.period.end !== o.period.start ? " → " + esc(o.period.end.slice(5, 10)) : "") + '</td><td class="num">' + (o.amount !== undefined ? amt(o.amount) : "—") + '</td><td><span class="pill ' + (o.status === "discharged" ? "ok" : bad ? "bad" : "") + '">' + esc(o.status) + (o.late ? " late" : "") + "</span></td></tr>";
        }).join("") + "</tbody></table></div>";
        html += "</div>";
      });
      $("rp-derived").innerHTML = html;
    }
    function stop() { clearInterval(timer); timer = null; $("rp-play").textContent = "Play"; }
    function play() {
      if (!trace) return;
      if (cur >= trace.steps.length - 1) go(0);
      $("rp-play").textContent = "Pause";
      timer = setInterval(function () { if (cur >= trace.steps.length - 1) stop(); else go(cur + 1); }, Number($("rp-speed").value));
    }
    $("rp-train").addEventListener("click", function (e) { var b = e.target.closest(".eb"); if (b) { stop(); go(Number(b.dataset.i)); } });
    $("rp-checks").addEventListener("click", function (e) { var b = e.target.closest("[data-who]"); if (b) { checkWho = b.dataset.who; drawChecks(); drawDerived(); } });
    $("rp-play").addEventListener("click", function () { timer ? stop() : play(); });
    $("rp-first").addEventListener("click", function () { stop(); go(0); });
    $("rp-last").addEventListener("click", function () { stop(); go(trace ? trace.steps.length - 1 : 0); });
    $("rp-prev").addEventListener("click", function () { stop(); go(cur - 1); });
    $("rp-next").addEventListener("click", function () { stop(); go(cur + 1); });
    $("rp-speed").addEventListener("change", function () { if (timer) { stop(); play(); } });
    $("rp-pick").addEventListener("change", function () { pick(this.value); });
    $("replay").addEventListener("keydown", function (e) {
      if (/INPUT|SELECT|TEXTAREA/.test(e.target.tagName)) return;
      if (e.key === "ArrowRight") { stop(); go(cur + 1); e.preventDefault(); } else if (e.key === "ArrowLeft") { stop(); go(cur - 1); e.preventDefault(); }
    });
    fillPick(); pick($("rp-pick").value);
    return {
      loadLive: function (t, seed) {
        live.unshift({ seed: seed, trace: t }); live = live.slice(0, 10); fillPick();
        $("rp-pick").value = "live:0"; stop(); load(t, true);
      }
    };
  })();
})();
