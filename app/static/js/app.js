/* Plainplan front-end: layered parallax, scroll reveal, dialogs, small ajax forms.
   No framework. Endpoints return HTML partials; checkout returns JSON {url}. */
(function () {
  'use strict';
  document.documentElement.classList.add('js');
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ---------- toast ---------- */
  var toastTimer;
  function toast(msg) {
    var t = $('#toast'); if (!t) return;
    t.textContent = msg; t.classList.add('show');
    clearTimeout(toastTimer); toastTimer = setTimeout(function () { t.classList.remove('show'); }, 3200);
  }

  /* ---------- scroll reveal (each block has its own delay via --d) ---------- */
  var io = 'IntersectionObserver' in window ? new IntersectionObserver(function (entries) {
    entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
  }, { threshold: 0.12, rootMargin: '0px 0px -6% 0px' }) : null;
  function observe(root) {
    $$('.reveal:not(.in)', root).forEach(function (el) { if (io) io.observe(el); else el.classList.add('in'); });
  }

  /* ---------- layered parallax ----------
     data-depth: 1 = moves with the page, 0 = stays put, >1 = moves faster (foreground).
     data-lag:   easing per layer (small = slow to catch up), so every layer has its own tempo. */
  var layers = [];
  function collect() {
    layers = $$('[data-depth]').map(function (el) {
      return { el: el, d: parseFloat(el.dataset.depth), lag: parseFloat(el.dataset.lag) || 0.08, y: null,
               fixed: !!el.closest('.bg'), fade: el.hasAttribute('data-fade') };
    });
  }
  function tick() {
    var sy = Math.min(window.scrollY || 0, 1400);
    for (var i = 0; i < layers.length; i++) {
      var L = layers[i];
      if (!L.el.offsetParent && !L.fixed) continue;
      if (L.y === null) L.y = sy;
      L.y += (sy - L.y) * L.lag;
      var t = L.fixed ? -L.y * L.d : L.y * (1 - L.d);
      L.el.style.transform = 'translate3d(0,' + t.toFixed(1) + 'px,0)';
      if (L.fade) L.el.style.opacity = Math.max(0, 1 - L.y / 520).toFixed(3);
    }
    requestAnimationFrame(tick);
  }

  /* Resolve "#id" relative to the page the element lives in (the prototype keeps several pages in one document). */
  function byRef(sel, from) {
    var sc = from && from.closest ? from.closest('[data-route]') : null;
    if (sc && sel.charAt(0) === '#') { var el = document.getElementById((sc.getAttribute('data-prefix') || '') + sel.slice(1)); if (el) return el; }
    return $(sel);
  }

  /* ---------- dialogs ---------- */
  function openDlg(id) { var d = document.getElementById(id); if (d && !d.open) d.showModal(); }
  function closeAll() { $$('dialog[open]').forEach(function (d) { d.close(); }); }
  function unlock() { try { sessionStorage.setItem('pp_unlocked', '1'); } catch (e) {} }

  /* ---------- ajax forms ---------- */
  function send(form) {
    var fd = new FormData(form), url = form.getAttribute('action');
    if (window.PP_STUB) return Promise.resolve(window.PP_STUB(url, fd, form));
    return fetch(url, { method: 'POST', body: fd, credentials: 'same-origin', headers: { 'X-Requested-With': 'fetch' } })
      .then(function (res) {
        var json = (res.headers.get('content-type') || '').indexOf('json') > -1;
        return (json ? res.json() : res.text()).then(function (b) { return { status: res.status, html: json ? null : b, json: json ? b : null }; });
      });
  }
  document.addEventListener('submit', function (e) {
    var form = e.target.closest ? e.target.closest('form[data-ajax], form[data-checkout]') : null;
    if (!form) return;
    e.preventDefault();
    var btn = form.querySelector('[type=submit]'); if (btn) btn.disabled = true;
    send(form).then(function (r) {
      if (r.status === 402) { openDlg('dlg-paywall'); return; }
      if (form.hasAttribute('data-checkout')) {
        if (r.json && r.json.url) {
          unlock(); closeAll(); toast('Plainplan Family is on. Your question is waiting for you.');
          if (!window.PP_PROTOTYPE) setTimeout(function () { location.href = r.json.url; }, 700);
        } else { toast('Checkout is not connected yet.'); }
        return;
      }
      var target = byRef(form.getAttribute('data-target'), form);
      if (target) { target.innerHTML = r.html || ''; observe(target); if (target.scrollIntoView) target.scrollIntoView({ behavior: 'smooth', block: 'nearest' }); }
      if (form.hasAttribute('data-reset')) form.reset();
    }).catch(function () { toast('Something went wrong. Please try again.'); })
      .then(function () { if (btn) btn.disabled = false; });
  });

  /* ---------- clicks ---------- */
  document.addEventListener('click', function (e) {
    var t = e.target.closest ? e.target.closest('[data-open],[data-close],[data-fill],[data-flip],[data-ics],dialog') : null;
    if (!t) return;
    if (t.matches('dialog')) { if (e.target === t) t.close(); return; }
    if (t.hasAttribute('data-open')) { openDlg(t.getAttribute('data-open')); return; }
    if (t.hasAttribute('data-close')) { var d = t.closest('dialog'); if (d) d.close(); return; }
    if (t.hasAttribute('data-fill')) {
      var inp = byRef(t.getAttribute('data-fill'), t); if (!inp) return;
      inp.value = t.getAttribute('data-text'); inp.focus();
      if (t.hasAttribute('data-submit') && inp.form) { inp.form.requestSubmit ? inp.form.requestSubmit() : inp.form.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true })); }
      return;
    }
    if (t.hasAttribute('data-flip')) { var on = t.classList.toggle('is-flipped'); t.setAttribute('aria-pressed', on); return; }
    if (t.hasAttribute('data-ics')) { if (window.PP_PROTOTYPE) e.preventDefault(); toast(window.PP_PROTOTYPE ? 'Calendar file downloaded (demo).' : 'Calendar file downloaded.'); }
  });
  document.addEventListener('change', function (e) {
    if (e.target && e.target.type === 'file' && e.target.form) { var n = e.target.form.querySelector('[data-file-name]'); if (n && e.target.files[0]) n.textContent = e.target.files[0].name; }
  });

  /* ---------- boot ---------- */
  function init() {
    observe(document); collect();
    if (!reduce && !window.__ppTick) { window.__ppTick = true; requestAnimationFrame(tick); }
    if (/[?&]unlocked=1/.test(location.search)) toast('Plainplan Family is on.');
  }
  window.PP = { observe: observe, collect: collect, openDlg: openDlg, toast: toast, init: init };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
