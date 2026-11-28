/* Research note: recompute each example trace's fingerprint in the browser. No network requests.
   The rule is the language's own: RFC 8785 canonical JSON (restricted to strings, integers, booleans,
   arrays and objects), then SHA-256, with a top-level `sigs` member left out. */
(function () {
  var holder = document.getElementById('rs-data');
  if (!holder) return;
  var items = JSON.parse(holder.textContent);
  // One value to change per trace, to show the fingerprint moving.
  var CHANGES = [
    { path: ['verdict', 'participations', 0, 'tier'], to: 'C', label: 'C', say: 'Tier changed from B to C.' },
    { path: ['verdict', 'obligations', 0, 'amount', 'value'], to: '21.98', label: '$21.98', say: 'Fee changed from $21.89 to $21.98.' },
    { path: ['verdict', 'accepted'], to: true, label: 'Accepted', say: 'Verdict changed from rejected to accepted.' }
  ];

  function jcs(v) {
    if (v === true) return 'true';
    if (v === false) return 'false';
    if (v === null || v === undefined) throw new Error('null is not allowed');
    if (typeof v === 'number') { if (!Number.isInteger(v)) throw new Error('use a Decimal string'); return String(v); }
    if (typeof v === 'string') return JSON.stringify(v);
    if (Array.isArray(v)) return '[' + v.map(jcs).join(',') + ']';
    return '{' + Object.keys(v).sort().map(function (k) { return JSON.stringify(k) + ':' + jcs(v[k]); }).join(',') + '}';
  }
  function fingerprint(o) {
    var copy = {};
    Object.keys(o).forEach(function (k) { if (k !== 'sigs') copy[k] = o[k]; });
    return crypto.subtle.digest('SHA-256', new TextEncoder().encode(jcs(copy))).then(function (buf) {
      return 'sha256:' + Array.prototype.map.call(new Uint8Array(buf), function (b) { return b.toString(16).padStart(2, '0'); }).join('');
    });
  }
  function esc(s) { return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  function highlight(text, marked) {
    return esc(text).replace(/"(?:[^"\\\n]|\\.)*"|[{}\[\],]|-?\b\d+\b|\btrue\b|\bfalse\b/g, function (t, at, all) {
      var cls = t[0] === '"' ? (/^\s*:/.test(all.slice(at + t.length)) ? 'k' : 's') : '{}[],'.indexOf(t) >= 0 ? 'p' : 'num';
      var out = '<span class="' + cls + '">' + t + '</span>';
      return marked && t === marked ? '<mark>' + out + '</mark>' : out;
    });
  }
  function setAt(o, path, value) {
    var x = o;
    for (var i = 0; i < path.length - 1; i++) x = x[path[i]];
    x[path[path.length - 1]] = value;
  }

  Array.prototype.forEach.call(document.querySelectorAll('.rs-panel'), function (panel) {
    var i = +panel.dataset.trace, item = items[i], change = CHANGES[i];
    var box = panel.querySelector('.rs-check'), got = box.querySelector('[data-got]'), chip = box.querySelector('[data-chip]');
    var btn = box.querySelector('[data-tamper]'), msg = box.querySelector('[data-msg]'), json = box.querySelector('[data-json]');
    var field = panel.querySelector('[data-rs-field]'), fieldHTML = field ? field.innerHTML : '', fieldClass = field ? field.className : '';
    var changed = false;

    function run() {
      var trace = JSON.parse(JSON.stringify(item.trace));
      if (changed) setAt(trace, change.path, change.to);
      json.innerHTML = highlight(JSON.stringify(trace, null, 2), changed ? JSON.stringify(change.to) : null);
      if (field) {
        if (changed) { field.textContent = change.label; field.className = (i === 2 ? 'vd ok ' : '') + 'rs-changed'; }
        else { field.innerHTML = fieldHTML; field.className = fieldClass; }
      }
      if (!(window.crypto && crypto.subtle)) {
        got.textContent = 'This browser cannot compute SHA-256 on this page.';
        return;
      }
      fingerprint(trace).then(function (fp) {
        var same = fp === item.fingerprint;
        got.textContent = fp;
        box.dataset.state = same ? 'match' : 'diff';
        chip.hidden = false;
        chip.className = 'vd sm ' + (same ? 'ok' : 'bad');
        chip.textContent = same ? 'Match' : 'No match';
        msg.textContent = changed ? change.say + ' The fingerprint no longer matches, so the two sides would know.' : '';
      });
    }
    btn.addEventListener('click', function () {
      changed = !changed;
      btn.setAttribute('aria-pressed', changed);
      btn.textContent = changed ? 'Put it back' : 'Change one value';
      run();
    });
    run();
  });
})();
