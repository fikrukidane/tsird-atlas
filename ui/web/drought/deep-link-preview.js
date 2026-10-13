/* Render one approved historical-rainfall finding before the map runtime loads.
 * This is deliberately narrow: it only serves a URL-pinned observed-rainfall
 * Tabia from the public API. The full workspace replaces it once OpenLayers
 * and the map controls are ready. */
(function () {
  'use strict';

  const params = new URLSearchParams(window.location.search);
  const indicator = params.get('indicator');
  const month = params.get('month');
  const tabiaId = params.get('tabia');
  if (!tabiaId || !month || month === 'latest' || !['observed', 'rainfall', 'latest'].includes(indicator || '')) return;

  const root = document.getElementById('drought-dashboard');
  if (!root) return;
  const escape = value => String(value == null ? '' : value).replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[character]);
  const number = (value, places = 1, suffix = '') => Number.isFinite(Number(value))
    ? `${Number(value).toFixed(places)}${suffix}` : 'not available';

  fetch(`../api/drought/public/dashboard/observed-rainfall/runs/${encodeURIComponent(month)}`, { cache: 'no-store' })
    .then(response => response.ok ? response.json() : Promise.reject(new Error(`snapshot ${response.status}`)))
    .then(payload => {
      const row = Array.isArray(payload.conditions) && payload.conditions.find(item => item && item.tsird_tabia_id === tabiaId);
      if (!row) return;
      const title = `${row.tabia_name_en || 'Selected Tabia'}${row.woreda_name_en ? ` — ${row.woreda_name_en}` : ''}`;
      const coverage = Number.isFinite(Number(row.coverage_pct)) ? `${Number(row.coverage_pct).toFixed(0)}%` : 'not recorded';
      const quality = String(row.quality_status || 'not recorded').replaceAll('_', ' ');
      root.dataset.tsirdDroughtPreview = 'ready';
      root.innerHTML = `<div class="drought-heading"><div><strong>Drought intelligence</strong><span>Tigray · approved retained evidence</span></div></div><div class="drought-notice">Opening the approved map workspace…</div><div class="drought-map-selection" data-public-evidence-selection data-selected-tabia="${escape(tabiaId)}"><strong>Tabia detail · ${escape(title)}</strong><span>Rainfall ${number(row.rainfall_mm, 1, ' mm')} · baseline median ${number(row.baseline_median_mm, 1, ' mm')} · ${number(row.percentile, 1)}th percentile</span><small>Coverage ${escape(coverage)} · quality ${escape(quality)}. Retained CHIRPS Tabia zonal mean; this is observed rainfall evidence, not a drought class or priority.</small></div>`;
      requestAnimationFrame(() => requestAnimationFrame(() => performance.mark('tsird-public-evidence-selection-ready')));
    })
    .catch(() => { /* The full workspace retains its own explicit error handling. */ });
}());
