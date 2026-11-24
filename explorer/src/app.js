(function () {
  "use strict";
  var UP = window.UP, ch = UP.contentHash;
  var TERMS = {}, TERM_LIST = JSON.parse(document.getElementById("terms-json").textContent);
  TERM_LIST.forEach(function (t) { TERMS[t.id] = t; });
  var CONF = (function () { try { return JSON.parse(document.getElementById("conformance-json").textContent); } catch (e) { return null; } })();
  var $ = function (id) { return document.getElementById(id); };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function short(h) { return h ? String(h).replace("sha256:", "").slice(0, 10) : "none"; }
  function clone(x) { return JSON.parse(JSON.stringify(x)); }
  function fmtN(n) { return Number(n).toLocaleString("en-US"); }
  function store(k, v) { try { if (v === undefined) { var s = localStorage.getItem(k); return s ? JSON.parse(s) : null; } localStorage.setItem(k, JSON.stringify(v)); } catch (e) { return null; } }
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var SVGNS = "http://www.w3.org/2000/svg";
  $("spec-ver").textContent = UP.SPEC;
  var RULES = { A1: "Composition", A2: "Unanimity", A3: "Chained transitions", A4: "Determinism", A5: "Non-retroactivity", A6: "Value neutrality",
    A7: "Role symmetry", A8: "Rendering binding", A9: "Bounded delegation", A10: "Verifiable confidentiality", A11: "Closed evidence", A12: "Single attribution", A13: "Resolved precedence" };
  function ruleName(r) { return r ? r + (RULES[r] ? " " + RULES[r] : "") : "—"; }
  function fpHTML(h, prev, label) {
    var hex = h.replace("sha256:", ""), ph = prev ? prev.replace("sha256:", "") : null, out = "";
    for (var i = 0; i < hex.length; i++) out += ph && ph[i] !== hex[i] ? '<span class="flip">' + hex[i] + "</span>" : hex[i];
    return (label ? '<span class="lab">' + esc(label) + "</span>" : "") + "sha256:" + out;
  }
  function flash(el) { el.classList.remove("flash"); void el.offsetWidth; el.classList.add("flash"); }

  // ---- navigation highlight
  // ---- theme toggle (a per-viewer convenience; the page works without storage)
  (function () {
    var root = document.documentElement, saved = store("up-theme");
    if (saved === "light" || saved === "dark") root.setAttribute("data-theme", saved);
    $("theme-toggle").addEventListener("click", function () {
      var dark = root.getAttribute("data-theme") ? root.getAttribute("data-theme") === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
      var next = dark ? "light" : "dark"; root.setAttribute("data-theme", next); store("up-theme", next);
    });
  })();
  // ---- one-shot reveals
  (function () {
    var els = document.querySelectorAll(".reveal");
    if (reduceMotion || !("IntersectionObserver" in window)) { els.forEach(function (e) { e.classList.add("is-in"); }); return; }
    var o = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("is-in"); o.unobserve(e.target); } }); }, { rootMargin: "0px 0px -10% 0px" });
    els.forEach(function (e) { o.observe(e); });
  })();
  // ---- hero stats
  (function () {
    var st = [[TERM_LIST.length, "Terms in the library"], [13, "axioms"], ["2 → 1", "engines, one answer"]];
    if (CONF && CONF.pytest) st.push([CONF.pytest.passed, "tests passing"]);
    $("hero-stats").innerHTML = st.map(function (x) { return '<div class="stat"><b>' + esc(x[0]) + "</b><span>" + esc(x[1]) + "</span></div>"; }).join("");
  })();
  var navLinks = document.querySelectorAll("[data-nav]");
  if ("IntersectionObserver" in window) {
    var navObs = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) navLinks.forEach(function (a) { a.classList.toggle("on", a.dataset.nav === e.target.id); }); });
    }, { rootMargin: "-45% 0px -50% 0px" });
    ["how", "vision", "playground", "conformance"].forEach(function (id) { navObs.observe($(id)); });
  }

  // ======================================================================== Intro demo
  (function () {
    var agg = UP.Key.fromSeed("story:aggregator"), sup = UP.Key.fromSeed("story:supplier"), fee = TERMS["UP:Admin-Fee"];
    var rate = "0.02", prevFp = null, tampered = false;
    function agreement(r) {
      return { type: "Agreement", spec: UP.SPEC, label: "Example master agreement (hypothetical)",
        parties: [{ role: "aggregator", party: { key: agg.public, name: "Hypothetical Purchasing Group" } }, { role: "supplier", party: { key: sup.public, name: "Example Supply Co." } }],
        clauses: [{ n: "fee", term: "UP:Admin-Fee", def: ch(fee), params: { payer: "supplier", payee: "aggregator", rate: r, report_clause: "reporting", period: { unit: "month", count: 1 }, due: { unit: "day", count: 30 }, rounding: { scale: 2, mode: "half-even" } } }] };
    }
    function run(E) { return new UP.Evaluator(new UP.Bundle({ type: "Bundle", spec: UP.SPEC, terms: [fee], chains: [[E]] })).run(ch(E))[0]; }
    function draw() {
      var ag = agreement(rate), b = new UP.Bundle({ terms: [fee] });
      var text = UP.renderTemplate(b, fee.render, ag.clauses[0].params), pct = esc((Number(rate) * 100) + "%");
      $("d-text").innerHTML = esc(text).replace(pct, "<mark>" + pct + "</mark>");
      var h = ch(ag), base = rate === "0.02" ? null : ch(agreement("0.02"));
      $("d-fp").innerHTML = fpHTML(h, base, "Agreement fingerprint" + (base ? " · changed" : ""));
      if (prevFp && prevFp !== h) flash($("d-fp"));
      prevFp = h;
      $("hero-hash").innerHTML = "sha256:" + esc(h.slice(7, 15)) + "… <b>✓ same everywhere</b>";
      var E = { type: "Event", spec: UP.SPEC, kind: "propose", at: "2026-12-01T15:00:00Z", by: agg.public, body: { agreement: ag } };
      E = UP.attach(E, agg.signObj(E), sup.signObj(E));
      var T = clone(E); if (tampered) T.body.agreement.clauses[0].params.rate = rate === "0.02" ? "0.015" : "0.02";
      var rows = [["Aggregator’s contract system", run(clone(E))], ["Supplier’s ERP", run(T), tampered], ["Member’s spreadsheet", run(clone(E))]];
      $("d-evals").innerHTML = rows.map(function (r) {
        var st = r[1], ok = st.accepted;
        return '<div class="evrow' + (ok ? "" : " bad") + '"><b>' + esc(r[0]) + (r[2] ? ' <span class="muted">(rate edited after signing)</span>' : "") + "</b>" +
          '<span class="pill ' + (ok ? "ok" : "bad") + '">' + (ok ? "signed and valid" : "rejected") + "</span>" +
          '<span class="h">' + (ok ? "state " + esc(ch(st.state)) : "no valid state") + "</span>" + (ok ? "" : '<span class="why">' + esc(st.reason) + "</span>") + "</div>";
      }).join("");
    }
    var scrolly = $("how-scrolly"), steps = scrolly.querySelectorAll(".scrolly-step");
    function setStep(n) {
      scrolly.dataset.step = n;
      steps.forEach(function (st) { st.classList.toggle("is-active", Number(st.dataset.step) === n); });
      var r = n >= 2 ? "0.025" : "0.02", t = n >= 4;
      if (r !== rate || t !== tampered) { rate = r; tampered = t; draw(); }
    }
    if (reduceMotion || !("IntersectionObserver" in window)) { steps.forEach(function (st) { st.classList.add("is-active"); }); rate = "0.025"; tampered = true; scrolly.dataset.step = 4; }
    else {
      var so = new IntersectionObserver(function (es) { es.forEach(function (e) { if (e.isIntersecting) setStep(Number(e.target.dataset.step)); }); }, { rootMargin: window.innerWidth <= 820 ? "-72% 0px -27% 0px" : "-50% 0px -50% 0px" });
      steps.forEach(function (st) { so.observe(st); });
      steps[0].classList.add("is-active");
    }
    draw();
  })();

  // ======================================================================== Vision
  (function () {
    var svg = $("v-svg"), seedN = 0, g = null, trace = null, L = null, queue = [], packets = [], paused = false, visible = true, nextAt = 0, done = 0, raf = 0;
    var narrow = false;
    function el(tag, attrs, parent, text) { var e = document.createElementNS(SVGNS, tag); for (var k in attrs) e.setAttribute(k, attrs[k]); if (text != null) e.textContent = text; (parent || svg).appendChild(e); return e; }
    function shortName(n) { var w = n.split(" "); return w.length > 2 ? w[1] : n; }
    function scenario() {
      for (var tries = 0; tries < 6; tries++) {
        var seed = "vision-" + Math.random().toString(36).slice(2, 7) + "-" + (seedN++);
        try {
          g = UP.lab.generate(seed, TERMS, { agent: true, sealed: false });
          trace = UP.makeTrace(g.data, [{ id: "e", name: "Engine", data: g.data }], {}, g.finalAt);
          return seed;
        } catch (e) { g = null; }
      }
      return null;
    }
    function layout() {
      narrow = svg.getBoundingClientRect().width < 640;
      // Desktop coordinates are close to the stage's real width (about 810px), so 1 unit is about 1px and the labels read at their CSS size.
      var W = narrow ? 420 : 860, P = {}, A = {}, lanes = [];
      var mem = g.actors.members, agent = g.parts[0] && g.parts[0].agent;
      if (!narrow) {
        P[g.actors.agg.pub] = { x: 102, y: 74, role: "aggregator" }; P[g.actors.sup.pub] = { x: 758, y: 74, role: "supplier" };
        mem.forEach(function (m, i) { P[m.pub] = { x: mem.length === 1 ? 430 : 350 + i * (160 / (mem.length - 1)), y: 74, role: "member" }; });
        A = { aggregator: { x: 102, y: 198, w: 152, t: "Contract management", s: "the aggregator’s app" }, price: { x: 266, y: 198, w: 152, t: "Price activation", s: "a shared service" },
          member: { x: 430, y: 198, w: 152, t: "Member procurement", s: "each member’s app" }, settle: { x: 594, y: 198, w: 152, t: "Fee settlement", s: "a shared service" },
          supplier: { x: 758, y: 198, w: 152, t: "Supplier ERP", s: "the supplier’s app" } };
        var agentNode = agent ? { x: 430, y: 296 } : null;
        var fy = 334, n = g.data.chains.length, gap = Math.min(36, 130 / Math.max(1, n - 1 || 1)), fh = 98 + (n - 1) * gap + 34;
        g.data.chains.forEach(function (c, i) { lanes.push({ y: fy + 98 + i * gap, x0: 230, x1: W - 40 }); });
        return { W: W, H: fy + fh + 10, P: P, A: A, agent: agentNode, fy: fy, fh: fh, lanes: lanes, labelX: 24, bands: [[30, "Parties"], [150, "Apps (hypothetical)"], [262, "Agents"]] };
      }
      P[g.actors.agg.pub] = { x: 52, y: 90, role: "aggregator" }; P[g.actors.sup.pub] = { x: 368, y: 90, role: "supplier" };
      mem.forEach(function (m, i) { P[m.pub] = { x: mem.length === 1 ? 210 : 140 + i * (140 / (mem.length - 1)), y: 90, role: "member" }; });
      A = { aggregator: { x: 75, y: 205, w: 128, t: "Contract mgmt", s: "aggregator" }, member: { x: 210, y: 205, w: 128, t: "Procurement", s: "members" },
        supplier: { x: 345, y: 205, w: 128, t: "Supplier ERP", s: "supplier" }, price: { x: 140, y: 275, w: 128, t: "Price activation", s: "service" }, settle: { x: 280, y: 275, w: 128, t: "Fee settlement", s: "service" } };
      var lanesN = [], gapN = Math.min(70, 280 / Math.max(1, g.data.chains.length)), fhN = 100 + (g.data.chains.length - 1) * gapN + 40;
      g.data.chains.forEach(function (c, i) { lanesN.push({ y: 520 + i * gapN, x0: 30, x1: 390, labelAbove: true }); });
      return { W: W, H: 420 + fhN + 10, P: P, A: A, agent: agent ? { x: 210, y: 368 } : null, fy: 420, fh: fhN, lanes: lanesN, labelX: 20, bands: [[30, "Parties"], [158, "Apps (hypothetical)"], [340, "Agents"]] };
    }
    function draw() {
      cancelAnimationFrame(raf); packets = [];
      while (svg.firstChild && svg.lastChild.nodeName !== "title" && svg.lastChild.nodeName !== "desc") svg.removeChild(svg.lastChild);
      L = layout();
      svg.setAttribute("viewBox", "0 0 " + L.W + " " + L.H);
      L.bands.forEach(function (b) { el("text", { x: L.labelX, y: b[0], "class": "layer-label" }, null, b[1]); });
      // links party -> app, app -> foundation
      var lines = el("g", { stroke: "var(--line)", "stroke-width": 1, fill: "none" });
      Object.keys(L.P).forEach(function (k) { var p = L.P[k], a = L.A[p.role]; el("line", { x1: p.x, y1: p.y + 16, x2: a.x, y2: a.y - 24 }, lines); });
      Object.keys(L.A).forEach(function (k) { var a = L.A[k]; el("line", { x1: a.x, y1: a.y + 24, x2: a.x, y2: L.fy, "stroke-dasharray": "3 4" }, lines); });
      if (L.agent) el("line", { x1: L.A.member.x, y1: L.A.member.y + 24, x2: L.agent.x, y2: L.agent.y - 14, stroke: "var(--accent)", "stroke-dasharray": "2 3" }, lines);
      // parties
      Object.keys(L.P).forEach(function (k) {
        var p = L.P[k], name = trace.parties[k] || "";
        var gg = el("g", { "data-node": "p:" + k });
        el("circle", { cx: p.x, cy: p.y, r: 15, fill: "var(--panel-2)", stroke: "var(--c" + ({ aggregator: 0, member: 2, supplier: 3 })[p.role] + ")", "stroke-width": 2 }, gg);
        el("text", { x: p.x, y: p.y + 32, "text-anchor": "middle", "class": "node-label" }, gg, shortName(name));
        if (!(narrow && p.role === "member" && g.actors.members.length > 1)) el("text", { x: p.x, y: p.y + 46, "text-anchor": "middle", "class": "node-sub" }, gg, p.role);
        else if (k === g.actors.members[0].pub) el("text", { x: 210, y: p.y + 46, "text-anchor": "middle", "class": "node-sub" }, gg, "members");
      });
      // apps
      Object.keys(L.A).forEach(function (k) {
        var a = L.A[k], gg = el("g", { "data-node": "a:" + k });
        a.box = el("rect", { x: a.x - a.w / 2, y: a.y - 24, width: a.w, height: 48, rx: 8, fill: "var(--panel-2)", stroke: "var(--line)" }, gg);
        el("text", { x: a.x, y: a.y - 3, "text-anchor": "middle", "class": "node-label" }, gg, a.t);
        el("text", { x: a.x, y: a.y + 13, "text-anchor": "middle", "class": "node-sub" }, gg, a.s);
      });
      // agent
      if (L.agent) {
        var ag = el("g", {}), x = L.agent.x, y = L.agent.y;
        L.agent.box = el("path", { d: "M" + x + " " + (y - 14) + " L" + (x + 14) + " " + y + " L" + x + " " + (y + 14) + " L" + (x - 14) + " " + y + "Z", fill: "var(--panel-2)", stroke: "var(--accent)", "stroke-width": 1.5 }, ag);
        el("text", { x: x + 22, y: y - 2, "class": "node-label halo" }, ag, "Procurement agent");
        el("text", { x: x + 22, y: y + 13, "class": "node-sub halo" }, ag, "Mandate allows tiers " + g.parts[0].agentAllowed);
      }
      // foundation
      el("rect", { x: 10, y: L.fy, width: L.W - 20, height: L.fh, rx: 12, fill: "var(--found)", stroke: "var(--found-line)" });
      el("image", { href: $("logo-src").getAttribute("src"), x: L.labelX + 10, y: L.fy + 14, width: 30, height: 30, "class": "logo-img" });
      el("text", { x: L.labelX + 48, y: L.fy + 34, "class": "found-title" }, null, "Universal Paper");
      el("text", { x: L.labelX + 10, y: L.fy + 62, "class": "found-sub" }, null, narrow ? "Terms · agreements · signed events · fingerprints" : "Terms · agreements · signed events · fingerprints, checked by every party’s own engine");
      L.dots = el("g", {});
      L.lanes.forEach(function (ln, i) {
        var lbl = trace.chains[i] ? trace.chains[i].label.replace(/ \(hypothetical\)$/, "").replace(/^Master agreement .*$/, "Master agreement").replace(/^Participation of Sample (\w+).*$/, "Participation: $1") : "";
        if (ln.labelAbove) el("text", { x: ln.x0, y: ln.y - 10, "class": "lane-label" }, null, lbl);
        else el("text", { x: L.labelX + 10, y: ln.y + 4, "class": "lane-label" }, null, lbl);
        el("line", { x1: ln.x0, y1: ln.y, x2: ln.x1, y2: ln.y, stroke: "var(--found-line)", "stroke-width": 1 });
      });
      L.hashLbl = el("text", { x: L.W - 30, y: L.fy + 34, "text-anchor": "end", "class": "hashlbl" }, null, "");
      L.pk = el("g", {});
    }
    function appOf(role) { return L.A[role]; }
    function recipients(step) {
      var e = step.event, out = [], chainAg = g.data.chains[e.chain][0].body.agreement;
      var roles = {}; chainAg.parties.forEach(function (p) { if (p.party.key !== e.by) roles[p.role] = 1; });
      Object.keys(roles).forEach(function (r) { out.push(appOf(r)); });
      var ct = e.kind === "attest" && e.body.claim ? e.body.claim.type : "";
      if (/Tier-Selection|Tiers/.test(ct) || (e.chain > 0 && e.kind !== "attest")) out.push(L.A.price);
      if (/Sales-Reporting|Admin-Fee/.test(ct)) out.push(L.A.settle);
      return out.filter(function (a, i) { return out.indexOf(a) === i; });
    }
    function originOf(step) {
      var e = step.event, viaAgent = e.signers.some(function (s) { return s.mandate; });
      if (viaAgent && L.agent) return L.agent;
      var role = g.data.chains[e.chain][0].body.agreement.parties.filter(function (p) { return p.party.key === e.by; })[0];
      return appOf(role ? role.role : "member");
    }
    function lanePoint(i, chainIdx) { var ln = L.lanes[chainIdx], n = trace.steps.length; return { x: ln.x0 + (i + 0.5) / n * (ln.x1 - ln.x0), y: ln.y }; }
    function addPacket(from, to, color, dur, onDone) {
      var c = el("circle", { r: 5, cx: from.x, cy: from.y, fill: color }, L.pk);
      packets.push({ c: c, a: { x: from.x, y: from.y + 24 }, b: to, t0: performance.now(), dur: dur, done: onDone });
    }
    function pulse(node) { if (!node || !node.box) return; node.box.setAttribute("stroke", "var(--accent)"); setTimeout(function () { node.box.setAttribute("stroke", node === L.agent ? "var(--accent)" : "var(--line)"); }, 500); }
    function land(i) {
      var step = trace.steps[i], ok = step.results.e.accepted, p = lanePoint(i, step.event.chain);
      el("circle", { cx: p.x, cy: p.y, r: ok ? 5 : 6, fill: ok ? "var(--c" + (step.event.chain % 6) + ")" : "var(--bad)", stroke: ok ? "none" : "var(--bad)" }, L.dots);
      if (!ok) el("path", { d: "M" + (p.x - 4) + " " + (p.y - 4) + " l8 8 m0 -8 l-8 8", stroke: "var(--panel)", "stroke-width": 2 }, L.dots);
      L.hashLbl.textContent = (narrow ? "" : "last event ") + step.event.hash.slice(0, 23) + "…";
      tick(step);
    }
    function tick(step) {
      var r = step.results.e, ok = r.accepted, t = $("v-ticker"), d = document.createElement("div");
      d.className = "tick" + (ok ? "" : " bad");
      d.innerHTML = "<span>" + esc(step.event.description.replace(/ vision-[a-z0-9]+-\d+/g, "")) + '</span><span class="h">' + esc(step.event.hash.slice(0, 30)) + '…</span><span class="v ' + (ok ? "ok" : "bad") + '">' +
        (ok ? "✓ valid · every counterparty computes the same state" : "✗ rejected for everyone · " + esc(r.reason)) + "</span>";
      t.insertBefore(d, t.firstChild);
      while (t.children.length > (narrow ? 3 : 4)) t.removeChild(t.lastChild);
    }
    function fire(i) {
      var step = trace.steps[i], o = originOf(step), p = lanePoint(i, step.event.chain), ok = step.results.e.accepted;
      pulse(o);
      addPacket(o, p, "var(--accent)", 750, function () {
        land(i);
        if (!ok) return;
        recipients(step).forEach(function (a) { addPacket({ x: p.x, y: p.y - 24 }, { x: a.x, y: a.y + 24 }, "var(--c" + (step.event.chain % 6) + ")", 700, function () { pulse(a); }); });
      });
    }
    function frame(now) {
      raf = requestAnimationFrame(frame);
      if (paused || !visible) { nextAt = Math.max(nextAt, now + 300); return; }
      var finished = [];
      packets = packets.filter(function (k) {
        var u = Math.min(1, (now - k.t0) / k.dur), e = u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2;
        k.c.setAttribute("cx", k.a.x + (k.b.x - k.a.x) * e); k.c.setAttribute("cy", k.a.y + (k.b.y - k.a.y) * e);
        if (u >= 1) { k.c.remove(); if (k.done) finished.push(k.done); return false; }
        return true;
      });
      finished.forEach(function (f) { f(); });
      if (now >= nextAt) {
        if (done < trace.steps.length) { fire(done++); nextAt = now + 1150; }
        else if (!packets.length) { start(); }
      }
    }
    function start() {
      var seed = scenario();
      if (!seed) { $("v-caption").textContent = "Could not generate a scenario."; return; }
      if (g.parts[0] && g.parts[0].agent) g.parts[0].agentAllowed = (g.mandateChecks.length ? "" : "") + allowedTiers();
      $("v-ticker").innerHTML = "";
      draw(); done = 0; nextAt = performance.now() + 500;
      var nr = trace.steps.filter(function (s) { return !s.results.e.accepted; }).length;
      $("v-caption").textContent = "Scenario " + seed + ": " + g.actors.members.length + " member" + (g.actors.members.length === 1 ? "" : "s") + ", " + trace.steps.length + " signed events" + (nr ? ", " + nr + " of them outside an agent’s Mandate" : "") + ".";
      if (reduceMotion) { for (var i = 0; i < trace.steps.length; i++) land(i); done = trace.steps.length; return; }
      cancelAnimationFrame(raf); raf = requestAnimationFrame(frame);
    }
    function allowedTiers() {
      var m = g.data.mandates[0]; if (!m) return "";
      var b = m.scope.claims["UP:Tier-Selection/selects"]; return b && b.option["in"] ? b.option["in"].join(", ") : "any";
    }
    $("v-pause").addEventListener("click", function () { paused = !paused; this.textContent = paused ? "Resume" : "Pause"; $("v-tag").classList.toggle("running", !paused); $("v-tag").textContent = paused ? "Paused" : "Live events"; });
    $("v-new").addEventListener("click", function () { start(); });
    if ("IntersectionObserver" in window) new IntersectionObserver(function (es) { visible = es[0].isIntersecting; }).observe(svg);
    var rw = 0;
    window.addEventListener("resize", function () { clearTimeout(rw); rw = setTimeout(function () { var n = svg.getBoundingClientRect().width < 640; if (n !== narrow && g) { draw(); for (var i = 0; i < done; i++) land(i); } }, 200); });
    start();
  })();

  // ======================================================================== Playground
  (function () {
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
      clauses: [], salts: {}, sigs: null, signedHash: null, prevHash: null, observer: false, base: null, tab: "write",
      hist: { reports: { "2027-01-01T00:00:00Z": "48,200.00", "2027-02-01T00:00:00Z": "51,375.50", "2027-03-01T00:00:00Z": "46,910.25" }, paid: { "2027-01-01T00:00:00Z": true } }, asOf: null
    };
    function newClause(term) {
      var base = NAMES[term] || "clause", n = base, i = 2;
      while (st.clauses.some(function (c) { return c.n === n; })) n = base + "-" + (i++);
      return { n: n, term: term, params: clone(SAMPLE[term] || {}), over: [], sealed: {} };
    }
    function preset(name) {
      var p = PRESETS[name];
      st.label = p.label; st.clauses = [];
      ["aggregator", "supplier", "member"].forEach(function (r) { st.parties[r].on = p.roles.indexOf(r) >= 0; });
      p.terms.forEach(function (t) { st.clauses.push(newClause(t)); });
      st.sigs = null; st.signedHash = null; st.base = null; st.prevHash = null;
      drawEditor(); drawSimple(); update();
      st.base = Object.assign(build(), { note: "the " + p.label.replace(" (example)", "").toLowerCase() + " as first loaded" });
      update();
    }
    var keyCache = {}, keyByPub = {};
    function keyFor(role, name) { var s = "playground:" + role + ":" + name; var k = keyCache[s] || (keyCache[s] = UP.Key.fromSeed(s)); keyByPub[k.public] = k; return k; }
    function randomHex() { var a = new Uint8Array(32); if (window.crypto && window.crypto.getRandomValues) window.crypto.getRandomValues(a); else for (var i = 0; i < 32; i++) a[i] = Math.floor(Math.random() * 256); return UP.hex(a); }
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
            var sk = c.n + "/" + p + "/" + JSON.stringify(v), salt = st.salts[sk] || (st.salts[sk] = randomHex()), s = UP.sealOf(v, salt);
            discs.push({ seal: s.seal, salt: salt, value: v }); v = s;
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
    function bundleFor(discs) { var d = { type: "Bundle", spec: UP.SPEC, terms: TERM_LIST }; if (!st.observer) d.disclosures = discs; return new UP.Bundle(d); }

    // ---- editor
    function typeEditor(ci, p, type, v) {
      var id = "pg-" + ci + "-" + p, c = st.clauses[ci];
      var sealBtn = SEALABLE[type] ? '<button type="button" class="sealbtn' + (c.sealed[p] ? " on" : "") + '" data-seal="' + ci + "|" + esc(p) + '" title="Seal this value: only a hash goes into the agreement">' + (c.sealed[p] ? "sealed" : "seal") + "</button>" : "";
      var head = '<span><label for="' + id + '">' + esc(p) + ' <span class="mono" style="opacity:0.7">' + esc(type) + "</span></label>" + sealBtn + "</span>", body;
      if (type === "Time") body = '<input type="date" id="' + id + '" data-k="time" value="' + esc(String(v).slice(0, 10)) + '">';
      else if (type === "Period") body = '<div class="row"><input type="number" min="1" id="' + id + '" data-k="pcount" value="' + esc(v.count) + '"><select data-k="punit" aria-label="' + esc(p) + ' unit">' + ["day", "month", "quarter", "year"].map(function (u) { return "<option" + (u === v.unit ? " selected" : "") + ">" + u + "</option>"; }).join("") + "</select></div>";
      else if (type === "Role") body = '<select id="' + id + '" data-k="role">' + UP.ROLES.map(function (r) { return "<option" + (r === v ? " selected" : "") + ">" + r + "</option>"; }).join("") + "</select>";
      else if (type === "[Role]") body = '<div class="checks-inline" id="' + id + '">' + UP.ROLES.map(function (r) { return '<label><input type="checkbox" data-k="roles" value="' + r + '"' + (v.indexOf(r) >= 0 ? " checked" : "") + "> " + r + "</label>"; }).join("") + "</div>";
      else if (type === "int") body = '<input type="number" id="' + id + '" data-k="int" value="' + esc(v) + '">';
      else if (type === "Rounding") body = '<div class="row"><input type="number" min="0" max="18" id="' + id + '" data-k="rscale" value="' + esc(v.scale) + '"><select data-k="rmode" aria-label="rounding mode">' + ["half-even", "half-up", "down", "up"].map(function (m) { return "<option" + (m === v.mode ? " selected" : "") + ">" + m + "</option>"; }).join("") + "</select></div>";
      else if (/^"on-ack"/.test(type)) body = '<select id="' + id + '" data-k="effective"><option value="on-ack"' + (v === "on-ack" ? " selected" : "") + '>on acknowledgment</option><option value="month"' + (v !== "on-ack" && v.next.unit === "month" ? " selected" : "") + '>start of next month</option><option value="quarter"' + (v !== "on-ack" && v.next.unit === "quarter" ? " selected" : "") + ">start of next quarter</option></select>";
      else if (/^"document"/.test(type)) body = '<select id="' + id + '" data-k="enum">' + ["document", "this-record"].map(function (x) { return "<option" + (x === v ? " selected" : "") + ">" + x + "</option>"; }).join("") + "</select>";
      else if (type === "Rate" || type === "Decimal" || type === "string" || type === "Name" || type === "Hash" || type === "ChainId") body = '<input type="text" id="' + id + '" data-k="' + (type === "Rate" || type === "Decimal" ? "dec" : "str") + '" value="' + esc(v) + '" spellcheck="false">';
      else body = '<textarea id="' + id + '" data-k="json" spellcheck="false">' + esc(JSON.stringify(v, null, 1)) + "</textarea>";
      return '<div class="field" data-ci="' + ci + '" data-p="' + esc(p) + '">' + head + body + '<span class="errmsg" hidden></span></div>';
    }
    // ---- the simple panel: the few things a visitor is likely to try
    function clauseOf(term) { return st.clauses.filter(function (c) { return c.term === term; })[0]; }
    function termClause() { return clauseOf("UP:Fixed-Term") || clauseOf("UP:Renewing-Term"); }
    function years(c) { return c && c.params.start && c.params.end ? Number(c.params.end.slice(0, 4)) - Number(c.params.start.slice(0, 4)) : null; }
    function drawSimple() {
      var fee = clauseOf("UP:Admin-Fee"), term = termClause(), y = years(term), cur = Object.keys(PRESETS).filter(function (k) { return PRESETS[k].label === st.label; })[0];
      var rate = fee && !isNaN(Number(fee.params.rate)) ? Number(fee.params.rate) : null;
      var html = '<div class="ctl"><span class="lab">Start from</span><div class="seg" role="group" aria-label="Example agreement">' +
        Object.keys(PRESETS).map(function (k) { return '<button type="button" data-preset="' + k + '" aria-pressed="' + (k === cur) + '">' + esc({ master: "Master", participation: "Participation", overlay: "Overlay" }[k]) + "</button>"; }).join("") + "</div></div>";
      if (fee) html += '<div class="ctl"><label for="s-rate">Administrative fee <output id="s-rate-out">' + (rate == null ? "—" : fmtPct(rate)) + "</output></label>" +
        '<input type="range" id="s-rate" min="0.005" max="0.05" step="0.0025" value="' + (rate == null ? 0.02 : rate) + '"><span class="hint">Share of reported net sales the supplier pays the aggregator each month.</span></div>';
      if (term && y != null) html += '<div class="ctl"><span class="lab">Length of the agreement <span class="val" id="s-years-out">' + y + " year" + (y === 1 ? "" : "s") + '</span></span><div class="seg" role="group" aria-label="Length in years">' +
        [1, 2, 3, 5].map(function (n) { return '<button type="button" data-years="' + n + '" aria-pressed="' + (n === y) + '">' + n + " yr</button>"; }).join("") + "</div></div>";
      html += '<div class="ctl"><label for="s-sup">Supplier’s name</label><input type="text" id="s-sup" value="' + esc(st.parties.supplier.name) + '" spellcheck="false"><span class="hint">A party’s name derives its example key, so a new name means a new party.</span></div>';
      if (fee) html += '<label class="switch"><input type="checkbox" id="s-seal"' + (fee.sealed.rate ? " checked" : "") + '> Keep the fee rate confidential (sealed)</label><span class="hint" style="margin-top:-10px">Only its hash goes into the agreement. Tick “View as an outsider” to see what others see.</span>';
      $("pg-simple").innerHTML = html;
    }
    function fmtPct(r) { return (Math.round(r * 10000) / 100).toString() + "%"; }
    var simple = $("pg-simple");
    simple.addEventListener("click", function (e) {
      var t = e.target.closest("button"); if (!t) return;
      if (t.dataset.preset) { preset(t.dataset.preset); return; }
      if (t.dataset.years) { var c = termClause(); c.params.end = UP.addPeriod(c.params.start, { unit: "year", count: Number(t.dataset.years) }); afterSimple(); }
    });
    simple.addEventListener("input", function (e) {
      var t = e.target;
      if (t.id === "s-rate") { var f = clauseOf("UP:Admin-Fee"), v = String(Math.round(Number(t.value) * 10000) / 10000); f.params.rate = v; $("s-rate-out").textContent = fmtPct(Number(v)); afterSimple(true); }
      else if (t.id === "s-sup") { st.parties.supplier.name = t.value; afterSimple(true); }
    });
    simple.addEventListener("change", function (e) {
      if (e.target.id === "s-seal") { var f = clauseOf("UP:Admin-Fee"); f.sealed.rate = e.target.checked; afterSimple(true); }
    });
    function afterSimple(keepSimple) { drawEditor(); update(); if (!keepSimple) drawSimple(); }

    function drawEditor() {
      var html = '<div class="card">' +
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
    ed.addEventListener("change", function () { drawSimple(); });
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
        else if (k === "pcount" || k === "punit") { var cnt = Number(f.querySelector('[data-k="pcount"]').value); if (!(cnt >= 1 && cnt <= 10000 && Number.isInteger(cnt))) throw new Error("Use a whole number from 1 to 10,000."); v = { unit: f.querySelector('[data-k="punit"]').value, count: cnt }; }
        else if (k === "role" || k === "enum") v = t.value;
        else if (k === "roles") v = Array.prototype.filter.call(f.querySelectorAll('[data-k="roles"]'), function (x) { return x.checked; }).map(function (x) { return x.value; });
        else if (k === "int") { var n = Number(t.value); if (!Number.isInteger(n)) throw new Error("Use a whole number."); v = n; }
        else if (k === "rscale" || k === "rmode") { var sc = Number(f.querySelector('[data-k="rscale"]').value); if (!Number.isInteger(sc) || sc < 0 || sc > 18) throw new Error("Use 0 to 18 places."); v = { scale: sc, mode: f.querySelector('[data-k="rmode"]').value }; }
        else if (k === "effective") v = t.value === "on-ack" ? "on-ack" : { next: { unit: t.value, count: 1 } };
        else if (k === "dec") { if (!/^-?(0|[1-9][0-9]*)(\.[0-9]+)?$/.test(t.value)) throw new Error("Write a decimal such as 0.02, with no % sign."); v = t.value; }
        else if (k === "str") v = t.value;
        else if (k === "json") { v = JSON.parse(t.value); UP.jcsString(v); }
      } catch (ex) { err = ex instanceof SyntaxError ? "That is not valid JSON yet." : ex.message; }
      f.classList.toggle("err", !!err);
      var em = f.querySelector(".errmsg"); em.hidden = !err; em.textContent = err;
      if (!err) { c.params[p] = v; update(); }
    }

    // ---- rendering helpers
    function inline(s) {
      return esc(s).replace(/\[sealed (sha256:[0-9a-f]{64})\]/g, '<span class="sealed">sealed $1</span>')
        .replace(/(^|[^>a-z0-9])((?:sha256|ed25519):[0-9a-f]{64})/g, function (m, pre, h, off, str) { return /sealed $/.test(str.slice(0, off + pre.length)) ? m : pre + "<code>" + h + "</code>"; });
    }
    function mdToHTML(md) {
      var out = [], inList = false;
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
    function sentenceOf(b, c) { try { return UP.renderTemplate(b, TERMS[c.term].render, c.params); } catch (e) { return "(this clause’s values are incomplete)"; } }

    // ---- main update
    var cur = null;
    function update() {
      var built = build(), ag = built.ag, h = ch(ag), b = bundleFor(built.discs);
      cur = { ag: ag, discs: built.discs, h: h, b: b };
      var issues = UP.agreementIssues(b, ag);
      cur.issues = issues;
      var changed = st.prevHash && st.prevHash !== h;
      $("pg-fp").innerHTML = fpHTML(h, st.prevHash, "Agreement fingerprint" + (changed ? " · changed" : ""));
      $("pg-fpmini").innerHTML = fpHTML(h, st.prevHash, "");
      if (changed) flash($("pg-fp"));
      st.prevHash = h;
      $("pg-valid").innerHTML = issues.length ? '<span class="pill bad">' + issues.length + " problem" + (issues.length === 1 ? "" : "s") + "</span>" : '<span class="pill ok">Valid under A1, A6, A10, A13</span>';
      if (st.tab === "write") drawWrite(); else if (st.tab === "compare") drawCompare(); else drawHistory();
      $("pg-json").textContent = (function () { try { return UP.jcsString(ag); } catch (e) { return e.message; } })();
    }
    function sigsHTML() {
      if (!st.sigs) return '<span style="color:var(--paper-muted)">Not signed yet. Press “Sign as every party”.</span>';
      var now = cur.ag.parties.map(function (p) { return p.party.key; });
      var html = st.sigs.map(function (s) {
        var ok = UP.verifySig(s.key, s.sig, cur.ag) && now.indexOf(s.key) >= 0;
        return '<div class="s"><span style="color:' + (ok ? "#17804f" : "#c43535") + '">' + (ok ? "✓" : "✗") + "</span><span>" + esc(s.name) + " · " + (ok ? "verifies over " + short(cur.h) + "…" : "signed " + short(st.signedHash) + "…, which is no longer this agreement") + "</span></div>";
      }).join("");
      if (st.signedHash !== cur.h) html += '<p style="color:#c43535;font-size:0.85rem;margin-top:0.3rem">The agreement changed after signing, so these signatures no longer verify. See the Compare tab for exactly what changed.</p>';
      return html;
    }
    function drawWrite() {
      var ag = cur.ag, b = cur.b, issues = cur.issues, text;
      try { text = UP.renderAgreement(b, ag); } catch (e) { text = "# " + (ag.label || "Agreement") + "\n\nThe text cannot be generated until the problems on the cover sheet are fixed (" + e.message + ")."; }
      $("pg-contract").innerHTML = mdToHTML(text);
      var termsHtml = ag.clauses.map(function (c) {
        var t = TERMS[c.term], line = sentenceOf(b, c), m = line.match(/^[\s\S]*?[.!?](\s|$)/);
        return "<li><b>" + esc(t.title) + " · “" + esc(c.n) + "”</b>" + inline(m ? m[0] : line) + "</li>";
      }).join("");
      $("pg-cover").innerHTML = '<h5 style="margin-top:0">Cover sheet</h5><h4>' + esc(ag.label || "Untitled agreement") + "</h4>" +
        '<dl><dt>Fingerprint</dt><dd class="meta">' + esc(cur.h) + "</dd><dt>Spec</dt><dd>" + esc(UP.SPEC) + "</dd>" +
        ag.parties.map(function (p) { return "<dt>" + esc(p.role) + "</dt><dd>" + esc(p.party.name) + '<div class="meta">' + esc(p.party.key.slice(0, 24)) + "…</div></dd>"; }).join("") +
        "<dt>Status</dt><dd>" + (issues.length ? '<ul class="issues">' + issues.map(function (x) { return "<li>" + esc(x[0]) + " " + esc(RULES[x[0]] || "") + ": " + esc(x[1]) + "</li>"; }).join("") + "</ul>" : "Valid: built only from defined Terms, every value typed and supplied by the parties, conflicts resolved.") + "</dd>" +
        (cur.discs.length ? "<dt>Sealed</dt><dd>" + cur.discs.length + " value" + (cur.discs.length === 1 ? "" : "s") + (st.observer ? ", hidden from you as an outsider" : ", visible to you as a party") + "</dd>" : "") +
        '</dl><ul class="terms">' + (termsHtml || '<li style="color:var(--paper-muted)">No Terms yet. Add one from the library.</li>') + '</ul><h5>Signatures</h5><div class="sigs">' + sigsHTML() + "</div>";
    }

    // ---- compare
    function words(s) { return s.split(/(\s+)/).filter(function (x) { return x.length; }); }
    function wordDiff(a, b) {
      var A = words(a), B = words(b), n = A.length, m = B.length, dp = [], i, j;
      for (i = 0; i <= n; i++) { dp.push(new Array(m + 1).fill(0)); }
      for (i = n - 1; i >= 0; i--) for (j = m - 1; j >= 0; j--) dp[i][j] = A[i] === B[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
      var out = ""; i = 0; j = 0;
      while (i < n || j < m) {
        if (i < n && j < m && A[i] === B[j]) { out += inline(A[i]); i++; j++; }
        else if (j < m && (i >= n || dp[i][j + 1] >= dp[i + 1][j])) { out += "<ins>" + inline(B[j]) + "</ins>"; j++; }
        else { out += "<del>" + inline(A[i]) + "</del>"; i++; }
      }
      return out.replace(/<\/ins>(\s*)<ins>/g, "$1").replace(/<\/del>(\s*)<del>/g, "$1");
    }
    function drawCompare() {
      if (!st.base) { $("cmp-out").innerHTML = "<p>Load an example first.</p>"; return; }
      var A = st.base.ag, B = cur.ag, hA = ch(A), hB = cur.h;
      var b = bundleFor(st.base.discs.concat(cur.discs));
      $("cmp-basenote").textContent = "Version A is " + st.base.note + ".";
      var html = '<h5 style="margin-top:0">Compare versions</h5><div class="cmp-fps"><div class="cmp-row"><b>Version A</b><span>' + esc(hA) + '</span></div><div class="cmp-row"><b>Version B</b><span>' + fpHTML(hB, hA, "").replace(/class="flip"/g, 'style="background:#f6ead0;color:#6b4a06"') + "</span></div></div>";
      if (hA === hB) html += "<p style=\"margin-top:0.8rem\">The two versions are identical, so they have the same fingerprint. Change anything in the editor to see the difference here.</p>";
      else {
        var changes = 0, body = "";
        ["aggregator", "member", "supplier"].forEach(function (r) {
          var pa = A.parties.filter(function (p) { return p.role === r; })[0], pb = B.parties.filter(function (p) { return p.role === r; })[0];
          if (pa && !pb) { changes++; body += '<div class="cmp-clause"><b>Party: ' + r + '</b><span class="st removed">removed</span><p>' + esc(pa.party.name) + "</p></div>"; }
          else if (!pa && pb) { changes++; body += '<div class="cmp-clause"><b>Party: ' + r + '</b><span class="st added">added</span><p>' + esc(pb.party.name) + "</p></div>"; }
          else if (pa && pb && pa.party.key !== pb.party.key) { changes++; body += '<div class="cmp-clause"><b>Party: ' + r + '</b><span class="st changed">changed</span><p>' + wordDiff(pa.party.name, pb.party.name) + ' <span class="meta">(a different key)</span></p></div>'; }
        });
        if ((A.label || "") !== (B.label || "")) { changes++; body += '<div class="cmp-clause"><b>Label</b><span class="st changed">changed</span><p>' + wordDiff(A.label || "", B.label || "") + "</p></div>"; }
        var names = B.clauses.map(function (c) { return c.n; }); A.clauses.forEach(function (c) { if (names.indexOf(c.n) < 0) names.push(c.n); });
        names.forEach(function (n) {
          var ca = A.clauses.filter(function (c) { return c.n === n; })[0], cb = B.clauses.filter(function (c) { return c.n === n; })[0];
          var title = esc(TERMS[(cb || ca).term].title) + " · “" + esc(n) + "”";
          if (ca && !cb) { changes++; body += '<div class="cmp-clause"><b>' + title + '</b><span class="st removed">removed</span><p><del>' + inline(sentenceOf(b, ca)) + "</del></p></div>"; return; }
          if (!ca && cb) { changes++; body += '<div class="cmp-clause"><b>' + title + '</b><span class="st added">added</span><p><ins>' + inline(sentenceOf(b, cb)) + "</ins></p></div>"; return; }
          if (UP.canonKey(ca) === UP.canonKey(cb)) return;
          changes++;
          var ps = [];
          Object.keys(Object.assign({}, ca.params, cb.params)).forEach(function (p) {
            if (UP.canonKey(ca.params[p]) !== UP.canonKey(cb.params[p])) ps.push('<span>' + esc(p) + ": <del>" + esc(JSON.stringify(ca.params[p])) + "</del> → <ins>" + esc(JSON.stringify(cb.params[p])) + "</ins></span>");
          });
          if (ca.term !== cb.term) ps.push("<span>Term: <del>" + esc(ca.term) + "</del> → <ins>" + esc(cb.term) + "</ins></span>");
          if (UP.canonKey(ca.over || []) !== UP.canonKey(cb.over || [])) ps.push("<span>precedence: <del>" + esc((ca.over || []).join(", ") || "none") + "</del> → <ins>" + esc((cb.over || []).join(", ") || "none") + "</ins></span>");
          body += '<div class="cmp-clause"><b>' + title + '</b><span class="st changed">changed</span><div class="cmp-params">' + ps.join("") + "</div><p>" + wordDiff(sentenceOf(b, ca), sentenceOf(b, cb)) + "</p></div>";
        });
        html += '<p style="margin-top:0.8rem"><b>' + changes + " change" + (changes === 1 ? "" : "s") + "</b> between A and B. Clauses are matched by name, values compared after canonical encoding, and the text below is generated from each version.</p>";
        if (st.sigs && st.signedHash === hA) html += '<p style="color:#c43535">The signatures you made cover version A only. Version B needs every party to sign again.</p>';
        html += body;
      }
      $("cmp-out").innerHTML = html;
    }
    $("cmp-base").addEventListener("click", function () { st.base = Object.assign(build(), { note: "the version you set at " + new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) }); update(); });
    $("cmp-amend").addEventListener("click", function () {
      var did = false;
      st.clauses.forEach(function (c) {
        if (c.term === "UP:Admin-Fee" && /^0\.\d+$/.test(c.params.rate)) { c.params.rate = String(Math.round((Number(c.params.rate) + 0.005) * 10000) / 10000); did = true; }
        if ((c.term === "UP:Fixed-Term" || c.term === "UP:Renewing-Term") && c.params.end) { c.params.end = UP.addPeriod(c.params.end, { unit: "year", count: 1 }); did = true; }
      });
      if (!did) st.clauses.push(newClause("UP:Notices"));
      drawEditor(); drawSimple(); update();
    });

    // ---- history
    var histCache = { key: null, h: null };
    function history() {
      var key = cur.h + JSON.stringify(st.hist) + (st.observer ? "o" : "");
      if (histCache.key === key) return histCache.h;
      var built = build();
      // The parties hold the disclosures, so the history is signed with them. An outsider sees the same chain without them.
      var h = UP.play.history(built.ag, TERM_LIST, function (pub) { return keyByPub[pub]; }, Object.assign({ disclosures: built.discs }, st.hist));
      if (!h.issues.length && st.observer && built.discs.length) { h.data = Object.assign({}, h.data, { disclosures: [] }); h.ev = new UP.Evaluator(new UP.Bundle(h.data)); }
      histCache = { key: key, h: h };
      return h;
    }
    function dayStr(t) { return t ? t.slice(0, 10) : "open-ended"; }
    function drawHistory() {
      var h = history(), out = $("hist-out");
      if (h.issues.length) { out.innerHTML = "<h3>History</h3><p class=\"muted\" style=\"margin-top:0.4rem\">Fix the problems on the cover sheet first. An invalid agreement cannot be signed, so it has no history.</p>"; return; }
      var g0 = h.ev.run(h.cid)[0];
      if (!g0.accepted) { out.innerHTML = '<h3>History</h3><p style="margin-top:0.4rem">Every party signs on ' + dayStr(h.signAt) + ', but the engine rejects the signed agreement:</p><p style="color:var(--bad);margin-top:0.3rem">' + esc(g0.reason) + '</p><p class="muted" style="margin-top:0.4rem;font-size:0.88rem">A participation needs its parent agreement in the same bundle, which the Playground does not have. Try the master agreement or the overlay.</p>'; return; }
      var t0 = UP.parseTime(h.signAt).getTime(), t1 = UP.parseTime(UP.addPeriod(h.horizon, { unit: "day", count: 60 })).getTime(), days = Math.round((t1 - t0) / 86400000);
      if (st.asOf == null || st.asOf > days) st.asOf = Math.min(days, Math.round((UP.parseTime(UP.addPeriod(h.start, { unit: "month", count: 4 })).getTime() - t0) / 86400000));
      var html = '<div class="clause-head"><h3>History</h3><span class="muted" style="font-size:0.82rem">Signed by every party on ' + dayStr(h.signAt) + " · chain " + esc(short(h.cid)) + "…</span></div>" +
        '<div class="slider" style="margin:0.8rem 0"><label for="hist-at" class="muted" style="font-size:0.85rem">As of</label><input type="range" id="hist-at" min="0" max="' + days + '" value="' + st.asOf + '"><b class="mono" id="hist-date"></b></div>' +
        '<div id="hist-asof"></div>';
      if (h.reportClause) {
        html += '<h3 style="margin-top:1.2rem;font-size:0.95rem">Sales reported under “' + esc(h.reportClause) + "”" + (h.feeClause ? " and the fee under “" + esc(h.feeClause) + "”" : "") + '</h3><p class="muted" style="font-size:0.84rem;margin:0.2rem 0 0.5rem">Type a period’s net sales. The supplier signs a report two days after the period ends. ' + (h.feeClause ? "The fee is computed by the engine from your rate and rounding. Tick “paid” and the supplier pays it three days before it is due, acknowledged by the aggregator." : "") + '</p><div class="periods" id="hist-periods"></div>';
      } else html += '<p class="muted" style="margin-top:1rem;font-size:0.88rem">This agreement has no Sales-Reporting clause, so there are no reports to enter. Its term and other duties still play out above.</p>';
      if (h.notes.length) html += '<p style="color:var(--bad);font-size:0.85rem;margin-top:0.5rem">' + h.notes.map(esc).join(" ") + "</p>";
      html += '<h3 style="margin-top:1.2rem;font-size:0.95rem">Signed events</h3><div id="hist-log" style="display:grid;gap:0.3rem;margin-top:0.4rem"></div>';
      out.innerHTML = html;
      drawAsOf(h, t0);
      if (h.reportClause) drawPeriods(h);
      $("hist-log").innerHTML = ['<div class="mono" style="font-size:0.8rem">' + dayStr(h.signAt) + " · ✓ every party signs the agreement · " + esc(short(h.cid)) + "…</div>"].concat(h.log.map(function (l) {
        return '<div class="mono" style="font-size:0.8rem;color:' + (l.accepted ? "inherit" : "var(--bad)") + '">' + dayStr(l.at) + " · " + (l.accepted ? "✓ " : "✗ ") + esc(l.what) + " · " + esc(short(l.hash)) + "…" + (l.accepted ? "" : " · " + esc(l.reason)) + "</div>";
      })).join("");
    }
    function drawAsOf(h, t0) {
      var t = UP.fmtTime(new Date(t0 + st.asOf * 86400000));
      $("hist-date").textContent = dayStr(t);
      var status = h.ev.status(h.cid, t), w = h.ev.window(h.cid, t);
      var all = h.ev.obligations(h.cid, h.horizon), now = h.ev.obligations(h.cid, t), byKey = {};
      now.forEach(function (o) { byKey[o.clause + o.period.start + (o.trigger || "")] = o; });
      var clauses = []; all.forEach(function (o) { if (clauses.indexOf(o.clause) < 0) clauses.push(o.clause); });
      var html = '<div class="controls" style="margin-bottom:0.7rem"><span class="pill ' + (status === "active" ? "ok" : "") + '">' + esc(status) + '</span><span class="muted" style="font-size:0.85rem">In force ' + dayStr(w[0]) + " to " + dayStr(w[1]) + "</span></div>";
      html += '<div class="tl">' + (clauses.length ? clauses.map(function (cn) {
        var ps = all.filter(function (o) { return o.clause === cn; });
        return '<div class="tl-row"><span>' + esc(cn) + ' <span class="muted mono" style="font-size:0.72rem">' + esc(ps[0].duty) + '</span></span><div class="tl-bar">' + ps.map(function (o) {
          var n = byKey[o.clause + o.period.start + (o.trigger || "")], cls = n ? n.status : "future";
          var amt = n && typeof n.amount === "object" ? " · " + n.amount.currency + " " + n.amount.value : "";
          return '<span class="' + cls + '" title="' + esc(dayStr(o.period.start) + " to " + dayStr(o.period.end) + ", due " + dayStr(o.due) + ": " + (n ? n.status + (n.late ? " (late)" : "") : "not yet arisen") + amt) + '"></span>';
        }).join("") + "</div></div>";
      }).join("") : '<p class="muted" style="font-size:0.88rem">No periodic duties in this agreement.</p>') + "</div>";
      html += '<div class="legend" style="margin-top:0.6rem"><span><i style="background:color-mix(in srgb, var(--ok) 55%, var(--panel))"></i>discharged</span><span><i style="background:color-mix(in srgb, var(--accent) 25%, var(--panel))"></i>open</span><span><i style="background:color-mix(in srgb, var(--bad) 45%, var(--panel))"></i>overdue</span><span><i style="opacity:0.35"></i>not yet arisen</span><span>One block per period. Hover for dates and amounts.</span></div>';
      $("hist-asof").innerHTML = html;
    }
    function drawPeriods(h) {
      var fees = {}; if (h.feeClause) h.ev.obligations(h.cid, h.horizon).forEach(function (o) { if (o.clause === h.feeClause) fees[o.period.start] = o; });
      var shown = st.histAll ? h.reportPeriods : h.reportPeriods.slice(0, 12);
      $("hist-periods").innerHTML = shown.map(function (pd) {
        var f = fees[pd.start], v = st.hist.reports[pd.start] || "", bad = v && UP.play.money(v) === null;
        var owed = f ? (typeof f.amount === "object" ? f.amount.currency + " " + f.amount.value : f.amount === "sealed" ? "sealed" : "—") : "—";
        return '<div class="period"><span class="mono">' + dayStr(pd.start) + '</span><input type="text" inputmode="decimal" data-rep="' + esc(pd.start) + '" value="' + esc(v) + '" placeholder="net sales, USD" aria-label="Net sales for the period starting ' + dayStr(pd.start) + '"' + (bad ? ' style="border-color:var(--bad)"' : "") + ">" +
          '<span class="num">' + (h.feeClause ? "fee " + esc(owed) + (f && f.status === "discharged" ? ' <span class="pill ok">paid' + (f.late ? " late" : "") + "</span>" : "") : "") + "</span>" +
          (h.feeClause ? '<label class="muted" style="font-size:0.82rem;display:flex;gap:0.3rem;align-items:center"><input type="checkbox" data-paid="' + esc(pd.start) + '"' + (st.hist.paid[pd.start] ? " checked" : "") + (f && typeof f.amount === "object" ? "" : " disabled") + "> paid</label>" : "<span></span>") + "</div>";
      }).join("") + (h.reportPeriods.length > 12 ? '<button class="btn small" type="button" id="hist-more" style="justify-self:start;margin-top:0.4rem">' + (st.histAll ? "Show the first 12 periods" : "Show all " + h.reportPeriods.length + " periods") + "</button>" : "") || '<p class="muted">No reporting periods.</p>';
    }
    $("hist-out").addEventListener("input", function (e) {
      if (e.target.id === "hist-at") { st.asOf = Number(e.target.value); drawAsOf(history(), UP.parseTime(history().signAt).getTime()); }
    });
    $("hist-out").addEventListener("click", function (e) { if (e.target.id === "hist-more") { st.histAll = !st.histAll; drawPeriods(history()); } });
    $("hist-out").addEventListener("change", function (e) {
      var t = e.target;
      if (t.dataset.rep) { st.hist.reports[t.dataset.rep] = t.value; drawHistory(); }
      else if (t.dataset.paid) { st.hist.paid[t.dataset.paid] = t.checked; drawHistory(); }
    });

    // ---- tabs and actions
    var tabs = ["write", "compare", "history"];
    function setTab(name) {
      st.tab = name;
      tabs.forEach(function (n) { $("tab-" + n).setAttribute("aria-selected", String(n === name)); $("panel-" + n).hidden = n !== name; });
      update();
    }
    tabs.forEach(function (n) { $("tab-" + n).addEventListener("click", function () { setTab(n); }); });
    document.querySelector('[role="tablist"]').addEventListener("keydown", function (e) {
      var i = tabs.indexOf(st.tab);
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") { var n = tabs[(i + (e.key === "ArrowRight" ? 1 : 2)) % 3]; setTab(n); $("tab-" + n).focus(); e.preventDefault(); }
    });
    $("pg-sign").addEventListener("click", function () {
      var built = build(), ag = built.ag;
      st.sigs = ag.parties.map(function (p) { var k = keyFor(p.role, p.party.name), s = k.signObj(ag); s.name = p.party.name; return s; });
      st.signedHash = ch(ag);
      st.base = Object.assign(built, { note: "the version you signed" });
      update();
    });
    $("pg-observer").addEventListener("change", function () { st.observer = this.checked; update(); });
    preset("master");
  })();

  // ======================================================================== Conformance
  (function () {
    if (CONF) {
      var tiles = [
        ["Tests passing", CONF.pytest ? fmtN(CONF.pytest.passed) : "—", CONF.pytest ? "of " + fmtN(CONF.pytest.passed + CONF.pytest.failed) + " in the suite, run " + CONF.run : "no recorded run", CONF.pytest && !CONF.pytest.failed],
        ["Engines agree", CONF.js ? CONF.js.passed + " / " + CONF.js.total : "—", "Python and JavaScript, every trace, check, and rendering", CONF.js && CONF.js.passed === CONF.js.total],
        ["Random seeds in CI", CONF.lab ? fmtN(CONF.lab.runs) : "—", CONF.lab ? CONF.lab.failures + " failures across eight invariants" : "", CONF.lab && !CONF.lab.failures],
        ["Audit findings fixed", fmtN(CONF.audit.length), CONF.audit.filter(function (a) { return a.sev === "High"; }).length + " high severity, each with a regression test", true]
      ];
      $("cf-tiles").innerHTML = tiles.map(function (t) { return '<div class="tile' + (t[3] ? " good" : "") + '"><span class="eyebrow">' + esc(t[0]) + '</span><span class="v">' + esc(t[1]) + '</span><span class="s">' + esc(t[2]) + "</span></div>"; }).join("");
      $("cf-files").innerHTML = CONF.files.map(function (f) { return "<tr><td><span class=\"mono\">" + esc(f.file) + '</span><div class="muted" style="font-size:0.78rem">' + esc(f.about || "") + '</div></td><td class="num">' + fmtN(f.tests) + "</td></tr>"; }).join("");
      $("cf-audit").innerHTML = CONF.audit.map(function (a) { return '<tr><td class="mono">' + esc(a.id) + '</td><td><span class="sev ' + esc(a.sev) + '">' + esc(a.sev) + "</span></td><td>" + esc(a.title) + "</td></tr>"; }).join("");
      $("cf-open").textContent = "Known limits: " + CONF.open + " items remain open in the audit, most importantly that both engines and the audit come from one team, so an independent review is still needed before 1.0. The JavaScript Ed25519 used on this page is not constant-time and signs only with public example seeds.";
    }
    // in-browser lab
    var prefix = Math.random().toString(36).slice(2, 6), worker = null, running = false, mode = "idle";
    var S = { runs: 0, events: 0, attacks: 0, caught: 0, invOk: 0, invBad: 0, inv: {}, att: {} }, fails = store("up-playground-failures") || [];
    var INV = UP.lab.INVARIANTS;
    Object.keys(INV).forEach(function (k) { S.inv[k] = { ok: 0, bad: 0 }; });
    Object.keys(UP.lab.ATTACKS).forEach(function (k) { S.att[k] = { n: 0, caught: 0, rules: {} }; });
    var WORKER_MAIN = "var running=false,terms=null,prefix='',n=0;" +
      "function strip(a){return a.map(function(x){var o={};for(var k in x)if(k!=='_data')o[k]=x[k];return o;});}" +
      "function summ(r){return {seed:r.seed,cfg:r.cfg,invariants:r.invariants,attacks:strip(r.attacks),events:r.events,sigs:r.sigs,ms:r.ms};}" +
      "function loop(){if(!running)return;var seed=prefix+'-'+(n++);var r;try{r=summ(UP.lab.runOne(seed,terms));}catch(e){r={seed:seed,invariants:[{id:'generator',ok:false,detail:String(e&&e.message)}],attacks:[],events:0,sigs:0,ms:0};}postMessage({type:'result',res:r});setTimeout(loop,0);}" +
      "onmessage=function(e){var m=e.data;if(m.type==='init'){terms={};m.terms.forEach(function(t){terms[t.id]=t;});prefix=m.prefix;}" +
      "if(m.type==='start'&&!running){running=true;loop();}if(m.type==='pause')running=false;};";
    function startWorker() {
      try {
        var src = ["src-crypto", "src-engine", "src-lab"].map(function (id) { return $(id).textContent; }).join("\n;\n") + "\n" + WORKER_MAIN;
        worker = new Worker(URL.createObjectURL(new Blob([src], { type: "text/javascript" })));
        worker.onmessage = function (e) { if (e.data.type === "result") { mode = "worker"; onResult(e.data.res); } };
        worker.onerror = function () { fallback(); };
        worker.postMessage({ type: "init", terms: TERM_LIST, prefix: prefix });
        worker.postMessage({ type: "start" });
        mode = "starting";
        setTimeout(function () { if (mode === "starting") fallback(); }, 8000);
      } catch (e) { fallback(); }
    }
    var n = 0, timer = null;
    function fallback() { if (worker) { try { worker.terminate(); } catch (e) { /* ignore */ } worker = null; } mode = "main"; mainLoop(); }
    function mainLoop() {
      clearTimeout(timer);
      if (!running || mode !== "main") return;
      var r = UP.lab.runOne(prefix + "-" + (n++), TERMS);
      onResult({ seed: r.seed, invariants: r.invariants, attacks: r.attacks, events: r.events });
      timer = setTimeout(mainLoop, 120);
    }
    function onResult(r) {
      S.runs++; S.events += r.events;
      r.invariants.forEach(function (x) { if (!S.inv[x.id]) S.inv[x.id] = { ok: 0, bad: 0 }; S.inv[x.id][x.ok ? "ok" : "bad"]++; S[x.ok ? "invOk" : "invBad"]++; });
      r.attacks.forEach(function (a) { var s = S.att[a.attack]; s.n++; S.attacks++; if (a.detected) { s.caught++; S.caught++; s.rules[a.rule] = (s.rules[a.rule] || 0) + 1; } });
      var bad = r.invariants.filter(function (x) { return !x.ok; });
      if (bad.length) { fails.unshift({ seed: r.seed, failed: bad.map(function (b) { return b.id + ": " + b.detail; }) }); fails = fails.slice(0, 30); store("up-playground-failures", fails); }
      paint();
    }
    function paint() {
      $("lab-status").textContent = running ? "Running in your browser" + (mode === "main" ? " (on the page)" : "") : S.runs ? "Paused" : "Not running";
      $("lab-status").classList.toggle("running", running);
      $("lab-tiles").innerHTML = [["Runs", fmtN(S.runs), fmtN(S.events) + " events validated", false], ["Attacks caught", fmtN(S.caught), "of " + fmtN(S.attacks) + " attempted", S.attacks && S.caught === S.attacks],
        ["Invariant checks", fmtN(S.invOk), "passed", S.invOk > 0], ["Failures", fmtN(S.invBad), "kept with their seeds", !S.invBad && S.runs > 0]].map(function (t, i) {
        return '<div class="tile' + (i === 3 && S.invBad ? " alarm" : t[3] ? " good" : "") + '"><span class="eyebrow">' + t[0] + '</span><span class="v">' + t[1] + '</span><span class="s">' + t[2] + "</span></div>";
      }).join("");
      $("lab-inv").innerHTML = Object.keys(INV).map(function (k) { var s = S.inv[k]; return "<tr><td>" + esc(INV[k]) + '</td><td class="num">' + fmtN(s.ok) + '</td><td class="num" style="color:' + (s.bad ? "var(--bad)" : "inherit") + '">' + fmtN(s.bad) + "</td></tr>"; }).join("");
      $("lab-att").innerHTML = Object.keys(S.att).map(function (k) {
        var s = S.att[k], rules = Object.keys(s.rules).map(function (r) { return '<span class="pill">' + esc(ruleName(r)) + "</span>"; }).join(" ");
        return "<tr><td>" + esc(UP.lab.ATTACKS[k].label) + '</td><td class="num">' + fmtN(s.caught) + " / " + fmtN(s.n) + "</td><td>" + (rules || '<span class="muted">—</span>') + "</td></tr>";
      }).join("");
      $("lab-fails").innerHTML = fails.length ? '<h3 style="margin-top:1rem;font-size:0.95rem;color:var(--bad)">Failures kept on this device</h3>' + fails.map(function (f) { return '<p class="mono" style="font-size:0.8rem;margin-top:0.3rem">seed ' + esc(f.seed) + ": " + f.failed.map(esc).join("; ") + "</p>"; }).join("") : "";
    }
    $("lab-toggle").addEventListener("click", function () {
      running = !running;
      this.textContent = running ? "Pause" : "Resume";
      if (running && mode === "idle") startWorker();
      else if (mode === "worker" && worker) worker.postMessage({ type: running ? "start" : "pause" });
      else if (mode === "main") mainLoop();
      paint();
    });
    paint();
  })();
})();
