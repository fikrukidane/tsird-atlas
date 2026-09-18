(function () {
  'use strict';

  const page = document.body.dataset.tsirdPage || 'drought';
  const api = page === 'priority' ? '../../api/drought/public/release' : '../api/drought/public/release';
  const indicatorApi = '../api/drought/public/indicators';
  const releaseHref = page === 'priority' ? '../release/' : 'release/';
  const panel = document.getElementById('public-drought-panel');
  const map = new ol.Map({
    target: 'public-drought-map',
    layers: [new ol.layer.Tile({ source: new ol.source.OSM() })],
    view: new ol.View({ center: ol.proj.fromLonLat([39.5, 13.7]), zoom: 7 })
  });
  const tabiaLayer = new ol.layer.Vector({ source: new ol.source.Vector(), zIndex: 20 });
  map.addLayer(tabiaLayer);
  const mapTools = document.createElement('div');
  mapTools.className = 'public-drought-map-tools';
  mapTools.innerHTML = '<label for="public-drought-search">Find a Woreda or Tabia</label><input id="public-drought-search" type="search" autocomplete="off" placeholder="Type at least two letters…" /><div class="public-drought-search-results" aria-live="polite"></div>';
  document.getElementById('public-drought-map').appendChild(mapTools);
  const searchInput = mapTools.querySelector('input');
  const searchResults = mapTools.querySelector('.public-drought-search-results');

  const MODES = {
    observed: { label: 'Latest', indicator: 'observed', value: 'rainfall_mm', unit: 'mm', note: 'Final retained CHIRPS rainfall evidence, shown as Tabia summaries.' },
    rapid: { label: 'Rapid rain', indicator: 'rapid', value: 'rainfall_mm', unit: 'mm', note: 'Preliminary CHIRPS rainfall evidence. It is not a final classification.' },
    vegetation: { label: 'Vegetation', indicator: 'vegetation', value: 'ndvi_mean', unit: '', note: 'Copernicus NDVI retained as contextual vegetation evidence.' },
    soil_water: { label: 'Soil water', indicator: 'soil_water', value: 'swi040_mean', unit: '%', note: 'Coarse Copernicus soil-water context; it is not a Tabia-scale observation.' },
    thermal: { label: 'Thermal', indicator: 'thermal', value: 'lst_c_mean', unit: '°C', note: 'Land-surface-temperature context, not measured air temperature.' },
    water_use: { label: 'Crop water use', indicator: 'water_use', value: 'transpiration_mm', unit: 'mm', note: 'FAO WaPOR transpiration context, not crop extent, yield, or drought severity.' },
    history: { label: 'History', unavailable: 'The approved package includes month-by-month retrospective replay, available through Priority planning. Individual raw observation traces are not published in the public release.' },
    outlook: { label: 'Outlook', unavailable: 'No reviewed provider outlook is included in this approved public release.' },
    exposure: { label: 'Exposure', exposure: true, value: 'population_decile', unit: ' decile', note: 'Static exposure context is shown separately; it is not a composite risk score.' },
    priority: { label: 'Evidence replay', priority: true, value: 'retrospective_draft_code', unit: '', note: 'Neutral C1–C4 retrospective draft codes from retained evidence only; not an instruction or operational decision.' }
  };
  const colours = ['#e8eef4', '#f9d56e', '#f9a65a', '#e76f51', '#9b4d47', '#543b3b'];
  const priorityColours = { C1: '#b91c1c', C2: '#ea580c', C3: '#f59e0b', C4: '#eab308', 'insufficient-evidence': '#64748b' };
  let records = new Map();
  let featureIndex = new Map();
  let activeMode = page === 'priority' ? 'priority' : 'observed';
  let activeAssetNames = new Set();

  function esc(value) { return String(value == null ? '—' : value).replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[c]); }
  function number(value, digits) { return Number.isFinite(Number(value)) ? Number(value).toFixed(digits == null ? 1 : digits) : 'Not available'; }
  function modeRecord(feature) { return records.get(feature.get('tsird_tabia_id')) || {}; }
  function quantileColour(value, values) {
    if (!Number.isFinite(Number(value))) return '#64748b';
    const usable = values.filter(Number.isFinite).sort((a, b) => a - b);
    if (!usable.length) return '#64748b';
    const position = usable.findIndex(item => item >= Number(value));
    return colours[Math.max(0, Math.min(colours.length - 1, Math.floor((position < 0 ? usable.length - 1 : position) * colours.length / usable.length)))];
  }
  function currentValues() {
    const mode = MODES[activeMode];
    return Array.from(records.values()).map(record => Number(record[mode.value])).filter(Number.isFinite);
  }
  function tabiaStyle(feature) {
    const mode = MODES[activeMode];
    const record = modeRecord(feature);
    const fill = mode.unavailable ? '#64748b' : (mode.priority ? (priorityColours[record.retrospective_draft_code] || '#64748b') : quantileColour(record[mode.value], currentValues()));
    return new ol.style.Style({ fill: new ol.style.Fill({ color: `${fill}b8` }), stroke: new ol.style.Stroke({ color: '#ffffff', width: .55 }) });
  }
  tabiaLayer.setStyle(tabiaStyle);

  function latestRunText(workspace, indicator) {
    const run = workspace.indicators[indicator] && workspace.indicators[indicator].run;
    if (!run) return 'No retained source summary in this release.';
    const date = run.source_period_end || run.observation_end || run.period_end || run.source_latest_month || 'date not recorded';
    return `${esc(run.source_product || 'Retained source')} · ${esc(String(date).slice(0, 10))} · ${esc(run.status || 'retained')}`;
  }
  function indicatorCard(workspace, key, mode) {
    if (mode.unavailable) return '';
    const run = workspace.indicators[key] && workspace.indicators[key].run;
    if (!run) return '';
    const date = run.source_period_end || run.observation_end || run.period_end || run.source_latest_month || 'date not recorded';
    return `<div class="public-drought-run-card"><b>${esc(mode.label)}</b>${esc(run.source_product || 'Retained source')} · ${esc(String(date).slice(0, 10))}<br>${esc(run.status || 'retained evidence')}</div>`;
  }
  function renderPanel(release, workspace) {
    const mode = MODES[activeMode];
    const controls = Object.entries(MODES).filter(([key]) => page !== 'priority' || key === 'priority').map(([key, item]) => `<button type="button" data-mode="${key}" class="${key === activeMode ? 'is-active' : ''}">${item.label}</button>`).join('');
    const sourceText = mode.unavailable ? mode.unavailable : (mode.priority ? 'The approved replay geometry is shown separately from FEWS NET provider-native context.' : latestRunText(workspace, mode.indicator));
    const sourceCards = Object.entries(MODES).filter(([key, item]) => ['observed', 'rapid', 'vegetation', 'soil_water', 'thermal', 'water_use'].includes(key)).map(([key, item]) => indicatorCard(workspace, key, item)).join('');
    const historyNotice = activeMode === 'history' ? `<p><a class="public-drought-link" href="priority/">Open retained January–August replay and provider context</a>.</p>` : '';
    const releaseLabel = release.schema_version === 'tsird-drought-public-indicator-release.v1' ? 'Automatically validated indicator release' : 'Approved public release';
    panel.innerHTML = `<h1>${page === 'priority' ? 'Retrospective Evidence Replay' : 'Drought intelligence'}</h1><div class="public-drought-banner">${releaseLabel} <b>${esc(release.release_id)}</b><br><small>${esc(release.public_scope)}</small></div><div class="public-drought-evidence-note">This is the public evidence workspace. It exposes retained Tabia summaries after source-specific technical checks; it does not calculate a forecast, publish a priority decision, or change the model.</div><div class="public-drought-modes">${controls}</div><h2>${esc(mode.label)}</h2><p class="public-drought-meta">${sourceText}</p><p>${esc(mode.note || '')}</p><div class="public-drought-detail" data-detail>${mode.unavailable ? `<strong>Not included as a raw public data stream</strong><p>${esc(mode.unavailable)}</p>${historyNotice}` : 'Select a coloured Tabia, or use the map search, to read the retained evidence summary.'}</div><h2>Current evidence in this release</h2><div class="public-drought-release-status"><b>Current Tabia evidence streams</b><span>Final rainfall, rapid rainfall, vegetation, soil-water, thermal and crop water-use context are available here as retained summaries.</span></div>${sourceCards}<h2>Map key</h2><ul class="public-drought-legend">${mode.priority ? Object.entries(priorityColours).map(([key, colour]) => `<li><i class="public-drought-swatch" style="background:${colour}"></i>${key} retrospective draft code</li>`).join('') : `<li><i class="public-drought-swatch" style="background:${colours[0]}"></i>lower retained value</li><li><i class="public-drought-swatch" style="background:${colours[colours.length - 1]}"></i>higher retained value</li><li><i class="public-drought-swatch" style="background:#64748b"></i>insufficient evidence</li>`}</ul><p class="public-drought-footnote">The release uses retained summaries—not raw grids or a live development API. <a href="${releaseHref}">Open the dedicated evidence replay and FEWS NET context</a>.</p>`;
    panel.querySelectorAll('[data-mode]').forEach(button => button.addEventListener('click', () => { activeMode = button.dataset.mode; tabiaLayer.changed(); renderPanel(release, workspace); }));
  }
  function setDetail(feature, workspace) {
    const target = panel.querySelector('[data-detail]');
    const mode = MODES[activeMode];
    const record = modeRecord(feature);
    if (!target || mode.unavailable) return;
    let rows;
    if (mode.priority) rows = [['Stored draft code', record.retrospective_draft_code], ['Rainfall', `${number(record.rainfall_mm)} mm`], ['Rainfall percentile', record.rainfall_percentile], ['Evidence state', record.evidence_state]];
    else if (mode.exposure) rows = [['Population context', record.population_decile], ['Cropland context', record.cropland_decile], ['Accessibility context', record.accessibility_context]];
    else rows = [[mode.label, `${number(record[mode.value], mode.indicator === 'vegetation' ? 3 : 1)}${mode.unit}`], ['Coverage', `${number(record.coverage_pct)}%`], ['Quality', record.quality_status]];
    target.innerHTML = `<strong>${esc(record.tabia_name_en || feature.get('tabia_name_en'))} — ${esc(record.woreda_name_en || feature.get('woreda_name_en'))}</strong><dl>${rows.map(([label, value]) => `<dt>${esc(label)}</dt><dd>${esc(value)}</dd>`).join('')}</dl><p><a class="public-drought-link" href="priority/">Inspect retained month replay and FEWS NET context for this area</a></p>`;
  }
  function showFeature(feature, workspace) {
    if (!feature) return;
    const geometry = feature.getGeometry();
    if (geometry) map.getView().fit(geometry.getExtent(), { padding: [60, 40, 60, 40], maxZoom: 11, duration: 250 });
    setDetail(feature, workspace);
  }
  function bindSearch(workspace) {
    searchInput.addEventListener('input', () => {
      const query = searchInput.value.trim().toLowerCase();
      if (query.length < 2) { searchResults.innerHTML = ''; return; }
      const matches = Array.from(featureIndex.values()).filter(feature => {
        const record = modeRecord(feature);
        return `${record.tabia_name_en || ''} ${record.woreda_name_en || ''}`.toLowerCase().includes(query);
      }).slice(0, 8);
      searchResults.innerHTML = matches.length ? matches.map(feature => {
        const record = modeRecord(feature);
        return `<button type="button" data-tabia-id="${esc(feature.get('tsird_tabia_id'))}">${esc(record.tabia_name_en || 'Unnamed Tabia')} <small>· ${esc(record.woreda_name_en || '')}</small></button>`;
      }).join('') : '<span class="public-drought-meta">No matching approved Tabia summary.</span>';
      searchResults.querySelectorAll('[data-tabia-id]').forEach(button => button.addEventListener('click', () => { showFeature(featureIndex.get(button.dataset.tabiaId), workspace); searchResults.innerHTML = ''; }));
    });
  }
  async function load() {
    let release;
    try { const response = await fetch(api, { cache: 'no-store' }); if (response.status === 404) throw new Error('No approved public evidence release is available yet.'); if (!response.ok) throw new Error(`Release metadata returned ${response.status}`); release = await response.json(); }
    catch (error) { panel.innerHTML = `<h1>Drought intelligence</h1><div class="public-drought-banner warning">${esc(error.message)}</div><p>This route never displays development data. Use the release process to publish an approved compact evidence package.</p>`; return; }
    let workspaceRelease = release;
    if (page !== 'priority') {
      try {
        const indicatorResponse = await fetch(indicatorApi, { cache: 'no-store' });
        if (indicatorResponse.ok) workspaceRelease = await indicatorResponse.json();
        else if (indicatorResponse.status !== 404) throw new Error(`Indicator release metadata returned ${indicatorResponse.status}`);
      } catch (error) {
        panel.innerHTML = `<h1>Drought intelligence</h1><div class="public-drought-banner warning">${esc(error.message)}</div><p>The previously approved indicator evidence remains available only when a separate validated indicator package has not been published.</p>`;
        return;
      }
    }
    const assets = new Map(workspaceRelease.assets.map(asset => [asset.asset_id, asset]));
    const reviewedAssets = new Map(release.assets.map(asset => [asset.asset_id, asset]));
    const workspaceAsset = assets.get('drought-workspace-latest');
    const replayAsset = reviewedAssets.get('priority-replay-latest');
    if (!workspaceAsset || !replayAsset) { panel.innerHTML = `<h1>Drought intelligence</h1><div class="public-drought-banner warning">This approved release predates the public workspace payload.</div><p>The dedicated <a href="release/">retrospective evidence replay</a> remains available. A later approved package is required before this familiar conditions workspace can be populated.</p>`; return; }
    try {
      const [workspaceResponse, replayResponse] = await Promise.all([fetch(workspaceAsset.url, { cache: 'no-store' }), fetch(replayAsset.url, { cache: 'no-store' })]);
      if (!workspaceResponse.ok || !replayResponse.ok) throw new Error('Required public workspace assets are unavailable.');
      const workspace = await workspaceResponse.json();
      const replay = await replayResponse.json();
      Object.entries(workspace.indicators || {}).forEach(([indicator, payload]) => (payload.summaries || []).forEach(summary => {
        const id = summary.tsird_tabia_id;
        if (!id) return;
        const record = records.get(id) || {};
        Object.assign(record, summary);
        records.set(id, record);
      }));
      const features = new ol.format.GeoJSON().readFeatures(replay, { featureProjection: 'EPSG:3857' });
      features.forEach(feature => { const id = feature.get('tsird_tabia_id'); const record = records.get(id) || {}; Object.assign(record, feature.getProperties()); records.set(id, record); featureIndex.set(id, feature); });
      tabiaLayer.getSource().addFeatures(features);
      if (!tabiaLayer.getSource().isEmpty()) map.getView().fit(tabiaLayer.getSource().getExtent(), { padding: [30, 30, 30, 30], maxZoom: 10 });
      renderPanel(workspaceRelease, workspace);
      bindSearch(workspace);
      map.on('singleclick', event => { const feature = map.forEachFeatureAtPixel(event.pixel, candidate => candidate); if (feature) showFeature(feature, workspace); });
    } catch (error) { panel.innerHTML = `<h1>Drought intelligence</h1><div class="public-drought-banner warning">${esc(error.message)}</div>`; }
  }
  load();
}());
