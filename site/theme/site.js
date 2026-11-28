/* Universal Paper site script (v7 design): art fields, nav, search, TOC, copy buttons, tabs, rails, reveals. */
(() => {
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

/* seeded random, shared with the Term thumbnails on the home page */
function seeded(str) { let h = 2166136261; for (const ch of str) { h ^= ch.charCodeAt(0); h = Math.imul(h, 16777619); } return () => ((h = Math.imul(h ^ (h >>> 15), 2246822507) ^ Math.imul(h ^ (h >>> 13), 3266489909)) >>> 0) / 4294967296; }
const PAL = ['#FF6A4A','#CDBEFF','#FFD873','#BDEFD6','#A9D7FF','#8C7CF0','#FF9C7A','#5B4FD9'];
function thumb(id) {
  const r = seeded(id), c = () => PAL[Math.floor(r() * PAL.length)];
  const blobs = Array.from({ length: 4 }, () => `radial-gradient(${40 + r() * 50}% ${40 + r() * 50}% at ${r() * 100}% ${r() * 100}%, ${c()} 0%, transparent 70%)`);
  return `${blobs.join(',')}, conic-gradient(from ${r() * 360}deg at ${30 + r() * 40}% ${30 + r() * 40}%, ${c()}, ${c()}, ${c()}, ${c()})`;
}
$$('[data-thumb]').forEach(el => { el.style.background = thumb(el.dataset.thumb); });

/* ── Generative field (same engine as the home page) ── */
const GLOWSETS = [
  [[.92,.3,.55,'rgba(227,169,72,.85)'],[.1,.92,.55,'rgba(157,197,165,.8)']],
  [[.85,.85,.6,'rgba(239,111,79,.9)'],[.3,.1,.5,'rgba(201,189,245,.7)']],
  [[.95,.15,.5,'rgba(239,111,79,.85)'],[.6,.95,.55,'rgba(227,169,72,.8)']],
  [[.15,.85,.55,'rgba(201,189,245,.75)'],[.9,.5,.5,'rgba(157,197,165,.8)']],
  [[.8,.2,.55,'rgba(157,197,165,.85)'],[.4,.95,.55,'rgba(239,111,79,.8)']]
];
const TONES = {
  warm:  { pal: ['#19173F', '#E3A948', '#EF6F4F', '#9DC5A5', '#C9BDF5', '#F1E6D0'] },
  coral: { pal: ['#19173F', '#EF6F4F', '#FF9C7A', '#F1E6D0', '#E3A948', '#6B3A4E'], base: ['#19173F', '#6B3A4E', '#E0785A'], glows: [[.88,.85,.6,'rgba(255,106,74,.9)'],[.2,.15,.45,'rgba(255,216,115,.55)']] },
  mint:  { pal: ['#14233A', '#9DC5A5', '#BDEFD6', '#F1E6D0', '#A9D7FF', '#E3A948'], base: ['#14233A', '#3F5E5A', '#9DC5A5'], glows: [[.85,.25,.55,'rgba(189,239,214,.8)'],[.15,.9,.5,'rgba(169,215,255,.6)']] },
  lilac: { pal: ['#19173F', '#C9BDF5', '#8C7CF0', '#F1E6D0', '#A9D7FF', '#EF6F4F'], base: ['#19173F', '#4B3F86', '#9C8CE0'], glows: [[.9,.3,.55,'rgba(205,190,255,.85)'],[.2,.9,.45,'rgba(255,106,74,.45)']] }
};
function Field(canvas, opts = {}) {
  const ctx = canvas.getContext('2d');
  const pal = opts.palette || ['#19173F', '#E3A948', '#EF6F4F', '#9DC5A5', '#C9BDF5', '#F1E6D0'];
  let w, h, dpr, parts = [], t = Math.random() * 100, running = false, raf, visible = true, paused = false;
  const pointer = { x: -1e4, y: -1e4 };
  const base = document.createElement('canvas');
  function paintBase() {
    base.width = Math.max(1, Math.round(w / 2)); base.height = Math.max(1, Math.round(h / 2));
    const b = base.getContext('2d'), W = base.width, H = base.height, R = Math.max(W, H);
    const bs = opts.base || ['#19173F', '#5A4A6E', '#B98A6A']; const lg = b.createLinearGradient(0, 0, W, H); lg.addColorStop(0, bs[0]); lg.addColorStop(.45, bs[1]); lg.addColorStop(1, bs[2]); b.fillStyle = lg; b.fillRect(0, 0, W, H);
    for (const [x, y, r, c] of (opts.glows || GLOWSETS[0])) { const g = b.createRadialGradient(x * W, y * H, 0, x * W, y * H, r * R); g.addColorStop(0, c); g.addColorStop(1, 'rgba(20,18,58,0)'); b.fillStyle = g; b.fillRect(0, 0, W, H); }
  }
  function colorAt(x, y) { const v = (Math.sin(x * .0013 + y * .0007) + Math.cos(y * .0017 - x * .0005) + 2) / 4; return Math.min(pal.length - 1, Math.floor(v * pal.length)); }
  function spawn() { const x = Math.random() * w, y = Math.random() * h; return { x, y, life: 80 + Math.random() * 200, ci: colorAt(x, y) }; }
  function angle(x, y) {
    let a = Math.sin(x * .0026 + t * .12) * 1.7 + Math.cos(y * .0031 - t * .08) * 1.5 + Math.sin((x + y) * .0012 + t * .05) + (opts.twist || 0);
    const dx = x - pointer.x, dy = y - pointer.y, d2 = dx * dx + dy * dy;
    if (d2 < 52000) a += Math.atan2(dy, dx) + Math.PI / 2 * (1 - d2 / 52000);
    return a;
  }
  function step() {
    ctx.globalAlpha = .01; ctx.drawImage(base, 0, 0, w, h);
    ctx.lineWidth = 2.6; ctx.globalAlpha = .8;
    for (let ci = 0; ci < pal.length; ci++) {
      ctx.strokeStyle = pal[ci]; ctx.beginPath();
      for (const p of parts) {
        if (p.ci !== ci) continue;
        const a = angle(p.x, p.y), nx = p.x + Math.cos(a) * 2.4, ny = p.y + Math.sin(a) * 2.4;
        ctx.moveTo(p.x, p.y); ctx.lineTo(nx, ny); p.x = nx; p.y = ny; p.life--;
        if (p.life < 0 || nx < 0 || nx > w || ny < 0 || ny > h) Object.assign(p, spawn());
      }
      ctx.stroke();
    }
    ctx.globalAlpha = 1; t += .016;
  }
  function resize() {
    dpr = Math.min(devicePixelRatio || 1, 1.5);
    const r = canvas.getBoundingClientRect(); w = r.width; h = r.height; if (!w || !h) return;
    canvas.width = w * dpr; canvas.height = h * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    paintBase(); ctx.globalAlpha = 1; ctx.drawImage(base, 0, 0, w, h);
    parts = Array.from({ length: Math.round(Math.min(5200, w * h / 120) * (opts.density || 1)) }, spawn);
    if (!running) for (let i = 0; i < (reduce ? 320 : 170); i++) step();
  }
  function loop() { if (!running) return; step(); raf = requestAnimationFrame(loop); }
  function sync() { const want = visible && !paused && !reduce && !document.hidden; if (want && !running) { running = true; loop(); } else if (!want && running) { running = false; cancelAnimationFrame(raf); } }
  new ResizeObserver(resize).observe(canvas);
  new IntersectionObserver(([e]) => { visible = e.isIntersecting; sync(); }).observe(canvas);
  document.addEventListener('visibilitychange', sync);
  const host = canvas.parentElement;
  host.addEventListener('pointermove', e => { const r = canvas.getBoundingClientRect(); pointer.x = e.clientX - r.left; pointer.y = e.clientY - r.top; });
  host.addEventListener('pointerleave', () => { pointer.x = pointer.y = -1e4; });
  return { setPaused(v) { paused = v; sync(); } };
}
window.UPField = Field;
$$('canvas[data-field]').forEach(c => {
  const r = seeded(c.dataset.field || 'up');
const T = TONES[c.dataset.tone] || TONES.warm;
Field(c, { palette: T.pal, base: T.base, glows: T.glows || GLOWSETS[Math.floor(r() * GLOWSETS.length)], twist: r() * 2, density: +(c.dataset.density || 1) });
});

/* ── Nav ── */
const nav = $('#nav');
if (nav) addEventListener('scroll', () => nav.classList.toggle('scrolled', scrollY > 8), { passive: true });
const mb = $('#menuBtn'), sheet = $('#menu');
if (mb && sheet) {
  const set = open => { mb.setAttribute('aria-expanded', open); sheet.hidden = !open; mb.innerHTML = `<svg class="ico"><use href="#i-${open ? 'x' : 'menu'}"/></svg>`; };
  mb.addEventListener('click', () => set(sheet.hidden));
  addEventListener('keydown', e => { if (e.key === 'Escape' && !sheet.hidden) { set(false); mb.focus(); } });
  matchMedia("(min-width: 1101px)").addEventListener('change', e => e.matches && set(false));
}

/* ── Search (⌘K) ── */
const sd = $('#search'), si = $('#searchInput'), sl = $('#searchList');
if (sd && si && sl && window.UP_SEARCH) {
  const KIND = { spec: ['SPEC', '#EEE9FF', '#2F2275'], term: ['TERM', '#FFE1D8', '#7A1E0C'], page: ['PAGE', '#DDF5E8', '#0F4D33'], integration: ['INT', '#FFF1C7', '#5C3D00'], research: ['RES', '#EEE9FF', '#2F2275'] };
  const docs = []; for (const p of window.UP_SEARCH) { docs.push({ t: p.t, sub: p.s, u: p.u, k: p.k, w: 3 }); for (const [hid, ht] of p.h || []) docs.push({ t: ht, sub: p.t, u: p.u + '#' + hid, k: p.k, w: 1 }); }
  let sel = 0, results = [];
  const esc = s => s.replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  function render() {
    const q = si.value.trim().toLowerCase();
    if (!q) results = window.UP_SEARCH.slice(0, 8).map(p => ({ t: p.t, sub: p.s, u: p.u, k: p.k }));
    else {
      const terms = q.split(/\s+/);
      results = docs.map(d => { const hay = (d.t + ' ' + d.sub).toLowerCase(); if (!terms.every(x => hay.includes(x))) return null; const s = d.w * 10 + (d.t.toLowerCase().startsWith(q) ? 20 : 0) + (d.t.toLowerCase().includes(q) ? 8 : 0) - d.t.length / 40; return { ...d, s }; }).filter(Boolean).sort((a, b) => b.s - a.s).slice(0, 12);
    }
    sel = 0;
    sl.innerHTML = results.length ? results.map((r, i) => { const [lab, bg, fg] = KIND[r.k] || KIND.page; return `<li role="option" id="sr${i}"><a href="${r.u}" aria-selected="${i === sel}"><span class="k" style="background:${bg};color:${fg}">${lab}</span><span style="min-width:0"><b>${esc(r.t)}</b><small>${esc(r.sub)}</small></span><em>↵</em></a></li>`; }).join('') : `<li class="empty">No pages match “${esc(si.value)}”.</li>`;
  }
  function move(d) { const as = $$('a', sl); if (!as.length) return; as[sel]?.setAttribute('aria-selected', 'false'); sel = (sel + d + as.length) % as.length; as[sel].setAttribute('aria-selected', 'true'); as[sel].scrollIntoView({ block: 'nearest' }); }
  function open() { if (sd.open) return; sd.showModal(); si.value = ''; render(); si.focus(); }
  $$('[data-search]').forEach(b => b.addEventListener('click', open));
  addEventListener('keydown', e => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); open(); } else if (e.key === '/' && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName) && !sd.open) { e.preventDefault(); open(); } });
  si.addEventListener('input', render);
  si.addEventListener('keydown', e => { if (e.key === 'ArrowDown') { e.preventDefault(); move(1); } else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); } else if (e.key === 'Enter') { e.preventDefault(); const a = $$('a', sl)[sel]; if (a) { sd.close(); location.href = a.href; } } });
  sd.addEventListener('click', e => { if (e.target === sd) sd.close(); });
}

/* ── TOC scrollspy ── */
const toc = $$('.toc a');
if (toc.length) {
  const map = new Map(toc.map(a => [decodeURIComponent(a.hash.slice(1)), a]));
  const heads = [...map.keys()].map(id => document.getElementById(id)).filter(Boolean);
  const spy = () => { let cur = heads[0]; for (const h of heads) if (h.getBoundingClientRect().top < 140) cur = h; toc.forEach(a => a.classList.remove('on')); if (cur) map.get(cur.id)?.classList.add('on'); };
  addEventListener('scroll', spy, { passive: true }); spy();
}

/* ── Copy buttons ── */
$$('[data-copy]').forEach(b => b.addEventListener('click', async () => {
  const src = b.dataset.copy.startsWith('#') ? $(b.dataset.copy)?.innerText : b.dataset.copy;
  try { await navigator.clipboard.writeText(src || ''); const t = b.innerHTML; b.classList.add('done'); b.textContent = 'Copied'; setTimeout(() => { b.classList.remove('done'); b.innerHTML = t; }, 1600); } catch { b.textContent = 'Press ⌘C'; }
}));

/* ── Tabs ── */
$$('[role=tablist]').forEach(list => {
  const tabs = $$('[role=tab]', list);
  const pick = t => { tabs.forEach(x => { const on = x === t; x.setAttribute('aria-selected', on); x.tabIndex = on ? 0 : -1; const p = document.getElementById(x.getAttribute('aria-controls')); if (p) p.hidden = !on; }); };
  tabs.forEach((t, i) => { t.addEventListener('click', () => pick(t)); t.addEventListener('keydown', e => { const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0; if (d) { const n = tabs[(i + d + tabs.length) % tabs.length]; pick(n); n.focus(); } }); });
});

/* ── Rails ── */
$$('[data-rail]').forEach(ctl => { const rail = document.getElementById(ctl.dataset.rail); if (!rail) return; const by = d => rail.scrollBy({ left: d * rail.clientWidth * .8, behavior: reduce ? 'auto' : 'smooth' }); $('[data-prev]', ctl)?.addEventListener('click', () => by(-1)); $('[data-next]', ctl)?.addEventListener('click', () => by(1)); });

/* ── Reveal + counters ── */
const io = new IntersectionObserver(es => es.forEach(e => {
  if (!e.isIntersecting) return; e.target.classList.add('in'); io.unobserve(e.target);
  e.target.querySelectorAll('[data-count]').forEach(n => { const to = +n.dataset.count; if (reduce) { n.textContent = to; return; } const t0 = performance.now(); const tick = now => { const k = Math.min(1, (now - t0) / 1400); n.textContent = Math.round(to * (1 - Math.pow(1 - k, 3))); if (k < 1) requestAnimationFrame(tick); }; requestAnimationFrame(tick); });
}), { threshold: .12 });
$$('.rv').forEach(n => io.observe(n));
})();

/* Header dropdowns: click or hover to open, Escape or click outside to close, arrow down to enter a panel. */
(function () {
  var nav = document.getElementById('nav');
  if (!nav) return;
  var btns = Array.prototype.slice.call(nav.querySelectorAll('.nx-btn'));
  if (!btns.length) return;
  var open = null, timer = 0, byHover = false; // byHover: the open panel was opened by hovering, not by a click
  function panel(b) { return document.getElementById(b.getAttribute('aria-controls')); }
  function hide() {
    clearTimeout(timer);
    if (!open) return;
    open.setAttribute('aria-expanded', 'false');
    panel(open).hidden = true;
    open = null;
  }
  function show(b) {
    clearTimeout(timer);
    if (open === b) return;
    hide();
    open = b;
    b.setAttribute('aria-expanded', 'true');
    panel(b).hidden = false;
  }
  var hover = window.matchMedia && matchMedia('(hover: hover) and (pointer: fine)').matches;
  btns.forEach(function (b) {
    // A click on a panel that hovering just opened keeps it open; otherwise a click toggles it.
    b.addEventListener('click', function () { if (open === b && !byHover) hide(); else show(b); byHover = false; });
    b.addEventListener('keydown', function (e) {
      if (e.key !== 'ArrowDown') return;
      e.preventDefault();
      show(b);
      var first = panel(b).querySelector('a');
      if (first) first.focus();
    });
    if (hover) b.addEventListener('mouseenter', function () { clearTimeout(timer); timer = setTimeout(function () { if (open !== b) { show(b); byHover = true; } }, open ? 0 : 90); });
  });
  if (hover) {
    nav.addEventListener('mouseleave', function () { clearTimeout(timer); timer = setTimeout(hide, 220); });
    nav.addEventListener('mouseenter', function () { if (open) clearTimeout(timer); });
  }
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape' || !open) return;
    var b = open;
    hide();
    b.focus();
  });
  document.addEventListener('click', function (e) { if (open && !nav.contains(e.target)) hide(); });
  document.addEventListener('focusin', function (e) { if (open && !nav.contains(e.target)) hide(); });
})();
