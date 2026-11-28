/* A thin progress line while reading a note. */
(function () {
  var bar = document.querySelector('.rs-progress'), art = document.querySelector('.rs-read .prose');
  if (!bar || !art) return;
  function set() {
    var r = art.getBoundingClientRect(), span = r.height - innerHeight * 0.6;
    bar.style.transform = 'scaleX(' + Math.max(0, Math.min(1, span > 0 ? -r.top / span : 0)).toFixed(4) + ')';
  }
  addEventListener('scroll', set, { passive: true });
  addEventListener('resize', set);
  set();
})();
