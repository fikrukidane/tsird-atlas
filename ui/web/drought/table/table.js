(function () {
  'use strict';
  const API_ROOT = '../../api/drought/public/dashboard';
  const MODES = {
    observed: { endpoint: 'observed', historyKey: 'rainfall', label: 'Final rainfall (CHIRPS)', field: 'rainfall_mm', unit: ' mm', digits: 1 },
    rapid: { endpoint: 'rapid', historyKey: 'rapid', label: 'Rapid rainfall (CHIRPS preliminary)', field: 'rainfall_mm', unit: ' mm', digits: 1 },
    vegetation: { endpoint: 'vegetation', historyKey: 'ndvi', label: 'Vegetation (NDVI)', field: 'ndvi_mean', unit: '', digits: 3 },
    soil_water: { endpoint: 'soil_water', historyKey: 'swi', label: 'Soil water (SWI-040)', field: 'swi040_mean', unit: '%', digits: 1 },
    thermal: { endpoint: 'thermal', historyKey: 'lst', label: 'Thermal (land-surface temperature)', field: 'lst_c_mean', unit: ' °C', digits: 1 },
    water_use: { endpoint: 'water_use', historyKey: 'wapor', label: 'Crop water use (WaPOR transpiration)', field: 'transpiration_mm', unit: ' mm/day', digits: 3 }
  };
  const params = new URLSearchParams(window.location.search);
  let indicator = MODES[params.get('indicator')] ? params.get('indicator') : 'observed';
  let rows = [];
  let sort = { key: 'name', direction: 1 };
  const status = document.getElementById('drought-table-status');
  const release = document.getElementById('drought-table-release');
  const select = document.getElementById('drought-table-indicator');
  const filter = document.getElementById('drought-table-filter');
  const body = document.querySelector('#drought-table tbody');
  const esc = value => String(value == null ? '' : value).replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[char]);
  const finite = value => Number.isFinite(Number(value));
  const tableParams = row => {
    const next = new URLSearchParams();
    next.set('indicator', indicator); next.set('month', params.get('month') || 'latest'); next.set('tabia', row.tsird_tabia_id); if (params.get('release')) next.set('release', params.get('release'));
    return next.toString();
  };
  function writeUrl() { const url = new URL(window.location.href); url.searchParams.set('indicator', indicator); history.replaceState({ tsirdDroughtTable: true }, '', `${url.pathname}?${url.searchParams}`); document.getElementById('map-view-link').href = `../?${url.searchParams}`; }
  function value(row) { return Number(row[MODES[indicator].field]); }
  function render() {
    const needle = filter.value.trim().toLowerCase();
    const visible = rows.filter(row => !needle || `${row.tabia_name_en || ''} ${row.tabia_name_ti || ''} ${row.woreda_name_en || ''}`.toLowerCase().includes(needle));
    visible.sort((left, right) => {
      const values = { name: [left.tabia_name_en || '', right.tabia_name_en || ''], woreda: [left.woreda_name_en || '', right.woreda_name_en || ''], value: [value(left), value(right)], coverage: [Number(left.coverage_pct), Number(right.coverage_pct)], quality: [left.quality_status || '', right.quality_status || ''] };
      const [a, b] = values[sort.key]; return (typeof a === 'number' ? (a - b) : String(a).localeCompare(String(b))) * sort.direction;
    });
    body.innerHTML = visible.map(row => {
      const mode = MODES[indicator]; const unavailable = row.quality_status !== 'ok' || !finite(row[mode.field]);
      const label = `${esc(row.tabia_name_en || 'Unnamed Tabia')}${row.tabia_name_ti ? `<span class="ti-name" lang="ti">${esc(row.tabia_name_ti)}</span>` : ''}`;
      const display = unavailable ? 'Insufficient evidence' : `${value(row).toFixed(mode.digits)}${mode.unit}`;
      const selected = row.tsird_tabia_id === params.get('tabia');
      const classes = [unavailable ? 'quality-insufficient' : '', selected ? 'is-selected' : ''].filter(Boolean).join(' ');
      return `<tr${classes ? ` class="${classes}"` : ''}${selected ? ' aria-current="true"' : ''}><td><a href="../?${tableParams(row)}">${label}</a></td><td>${esc(row.woreda_name_en || 'Not recorded')}</td><td>${display}</td><td>${finite(row.coverage_pct) ? `${Number(row.coverage_pct).toFixed(0)}%` : 'Not recorded'}</td><td>${esc(String(row.quality_status || 'not recorded').replaceAll('_', ' '))}</td></tr>`;
    }).join('');
    document.querySelectorAll('[data-sort]').forEach(button => {
      const heading = button.closest('th');
      if (heading) heading.setAttribute('aria-sort', button.dataset.sort === sort.key ? (sort.direction > 0 ? 'ascending' : 'descending') : 'none');
    });
    const selected = params.get('tabia');
    status.textContent = `${visible.length} of ${rows.length} Tabias shown for ${MODES[indicator].label}.${selected ? ` Selected Tabia: ${selected}.` : ''} Use a column heading to sort, or open a Tabia link to view it on the map.`;
  }
  async function load() {
    select.innerHTML = Object.entries(MODES).map(([key, item]) => `<option value="${key}"${key === indicator ? ' selected' : ''}>${item.label}</option>`).join('');
    writeUrl();
    const requestedRelease = params.get('release'); const requestedMonth = params.get('month');
    try {
      const overviewResponse = await fetch(`${API_ROOT}/overview`);
      if (!overviewResponse.ok) throw new Error('The approved release overview is unavailable.');
      const overview = await overviewResponse.json();
      const currentRelease = overview.indicator_release && overview.indicator_release.release_id;
      if (requestedRelease && requestedRelease !== currentRelease) {
        release.className = 'drought-table-release is-warning';
        release.textContent = `This link refers to release ${requestedRelease}, which has been superseded by ${currentRelease || 'an unavailable release'}. It deliberately does not substitute current values under the old link.`;
        status.textContent = 'Superseded release: no values displayed.'; return;
      }
      release.className = 'drought-table-release';
      const isHistorical = requestedMonth && requestedMonth !== 'latest';
      release.textContent = `${isHistorical ? `Retained historical snapshot ${requestedMonth}` : `Approved indicator release ${currentRelease || 'not recorded'} · activated ${String(overview.indicator_release && overview.indicator_release.activated_at || 'not recorded').slice(0, 10)}`}.`;
      const source = isHistorical
        ? `${API_ROOT}/evidence/${MODES[indicator].historyKey}/runs/${encodeURIComponent(requestedMonth)}/summary`
        : `${API_ROOT}/indicator/${MODES[indicator].endpoint}`;
      const response = await fetch(source);
      const payload = await response.json();
      const summaries = payload.summaries || payload.conditions;
      if (!response.ok || !Array.isArray(summaries)) throw new Error(isHistorical ? 'Requested historical snapshot is unavailable in this approved release.' : 'Indicator table is unavailable.');
      rows = summaries; render();
    } catch (error) { status.textContent = error.message || 'The evidence table is unavailable.'; }
  }
  select.addEventListener('change', () => { indicator = select.value; params.set('indicator', indicator); load(); });
  filter.addEventListener('input', render);
  document.querySelectorAll('[data-sort]').forEach(button => button.addEventListener('click', () => { const key = button.dataset.sort; sort = { key, direction: sort.key === key ? sort.direction * -1 : 1 }; render(); }));
  load();
}());
