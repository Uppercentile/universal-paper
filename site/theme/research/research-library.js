/* Research library: search, facets, sort and paging over rows that are already in the page.
   State lives in the address (?q=&kind=&topic=&status=&impact=&year=&sort=), so any view can be shared. */
(function () {
  var list = document.getElementById('rs-list');
  if (!list) return;
  var PAGE = 30, FACETS = ['kind', 'topic', 'status', 'impact', 'year'];
  var rows = Array.prototype.slice.call(list.querySelectorAll('.rs-row'));
  var q = document.getElementById('rs-q'), sort = document.getElementById('rs-sort'), count = document.getElementById('rs-count');
  var chips = document.getElementById('rs-chips'), clear = document.getElementById('rs-clear'), empty = document.getElementById('rs-empty'), more = document.getElementById('rs-more');
  var buttons = Array.prototype.slice.call(document.querySelectorAll('.rs-f'));
  var state = { q: '', kind: '', topic: '', status: '', impact: '', year: '', sort: 'new' }, shown = PAGE;

  function has(row, facet, value) {
    if (!value) return true;
    return facet === 'topic' ? (' ' + row.dataset.topics + ' ').indexOf(' ' + value + ' ') >= 0 : row.dataset[facet] === value;
  }
  function matches(row, skip) {
    var words = state.q.toLowerCase().split(/\s+/).filter(Boolean);
    for (var i = 0; i < words.length; i++) if (row.dataset.text.indexOf(words[i]) < 0) return false;
    for (var f = 0; f < FACETS.length; f++) if (FACETS[f] !== skip && !has(row, FACETS[f], state[FACETS[f]])) return false;
    return true;
  }
  var order = {
    'new': function (a, b) { return b.dataset.date.localeCompare(a.dataset.date) || a.dataset.n - b.dataset.n; },
    old: function (a, b) { return a.dataset.date.localeCompare(b.dataset.date) || a.dataset.n - b.dataset.n; },
    az: function (a, b) { return a.dataset.title.localeCompare(b.dataset.title); },
    no: function (a, b) { return a.dataset.n - b.dataset.n; }
  };
  function label(b) { return b.querySelector('span').textContent; }

  function render() {
    var hit = rows.filter(function (r) { return matches(r); }).sort(order[state.sort] || order['new']);
    Array.prototype.forEach.call(list.querySelectorAll('.rs-year'), function (y) { y.remove(); });
    rows.forEach(function (r) { r.hidden = true; });
    var year = '', byDate = state.sort === 'new' || state.sort === 'old';
    hit.forEach(function (r, i) {
      if (i < shown) {
        if (byDate && r.dataset.year !== year) {
          year = r.dataset.year;
          var y = document.createElement('li');
          y.className = 'rs-year'; y.textContent = year; y.setAttribute('aria-hidden', 'true');
          list.appendChild(y);
        }
        r.hidden = false;
      }
      list.appendChild(r);
    });
    // Each facet's counts assume every other filter stays as it is.
    buttons.forEach(function (b) {
      var f = b.dataset.facet, v = b.dataset.value;
      var n = rows.filter(function (r) { return matches(r, f) && has(r, f, v); }).length;
      b.querySelector('i').textContent = n;
      b.setAttribute('aria-pressed', state[f] === v);
      b.disabled = n === 0 && state[f] !== v;
    });
    var active = FACETS.filter(function (f) { return state[f]; });
    count.textContent = hit.length + (hit.length === 1 ? ' entry' : ' entries') + (hit.length < rows.length ? ' of ' + rows.length : '');
    chips.innerHTML = '';
    active.forEach(function (f) {
      var b = buttons.filter(function (x) { return x.dataset.facet === f && x.dataset.value === state[f]; })[0];
      var c = document.createElement('button');
      c.type = 'button'; c.className = 'rs-chip'; c.textContent = b ? label(b) : state[f];
      c.setAttribute('aria-label', 'Remove filter: ' + c.textContent);
      c.addEventListener('click', function () { state[f] = ''; shown = PAGE; push(); render(); });
      chips.appendChild(c);
    });
    clear.hidden = !(active.length || state.q);
    empty.hidden = hit.length > 0;
    more.hidden = hit.length <= shown;
    more.textContent = 'Show ' + Math.min(PAGE, hit.length - shown) + ' more';
  }
  function push() {
    var p = new URLSearchParams();
    Object.keys(state).forEach(function (k) { if (state[k] && !(k === 'sort' && state[k] === 'new')) p.set(k, state[k]); });
    var s = p.toString();
    history.replaceState(null, '', location.pathname + (s ? '?' + s : '') + location.hash);
  }
  function read() {
    var p = new URLSearchParams(location.search);
    Object.keys(state).forEach(function (k) { if (p.get(k)) state[k] = p.get(k); });
    q.value = state.q;
    sort.value = order[state.sort] ? state.sort : 'new';
  }

  buttons.forEach(function (b) {
    b.addEventListener('click', function () {
      var f = b.dataset.facet;
      state[f] = state[f] === b.dataset.value ? '' : b.dataset.value;
      shown = PAGE; push(); render();
    });
  });
  q.addEventListener('input', function () { state.q = q.value.trim(); shown = PAGE; push(); render(); });
  sort.addEventListener('change', function () { state.sort = sort.value; shown = PAGE; push(); render(); });
  more.addEventListener('click', function () { shown += PAGE; render(); });
  clear.addEventListener('click', function () { FACETS.forEach(function (f) { state[f] = ''; }); state.q = ''; q.value = ''; shown = PAGE; push(); render(); });
  // Kind and topic cards lower on the page filter in place instead of reloading.
  Array.prototype.forEach.call(document.querySelectorAll('a[data-set]'), function (a) {
    a.addEventListener('click', function (e) {
      e.preventDefault();
      state[a.dataset.set] = a.dataset.value; shown = PAGE; push(); render();
      document.getElementById('library').scrollIntoView();
    });
  });
  document.addEventListener('keydown', function (e) {
    var t = e.target.tagName;
    if (e.key === '/' && !e.metaKey && !e.ctrlKey && t !== 'INPUT' && t !== 'TEXTAREA' && t !== 'SELECT') { e.preventDefault(); q.focus(); }
  });
  // On phones the filters start closed. They reopen if the window grows.
  var fd = document.querySelector('.rs-fd');
  if (fd && window.matchMedia) {
    var narrow = matchMedia('(max-width: 900px)');
    var sync = function () { fd.open = !narrow.matches; };
    sync();
    if (narrow.addEventListener) narrow.addEventListener('change', sync);
  }
  read(); render();
})();
