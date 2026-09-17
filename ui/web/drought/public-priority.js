(function () {
  'use strict';

  const API = '../../api/drought/public/release';
  const panel = document.getElementById('public-drought-panel');
  const codes = { C1: '#b91c1c', C2: '#ea580c', C3: '#f59e0b', C4: '#eab308', 'insufficient-evidence': '#64748b' };
  const fewsColours = { 1: '#64748b', 2: '#facc15', 3: '#f97316', 4: '#e11d48', 5: '#7f1d1d' };
  const fewsNames = { 1: 'Minimal', 2: 'Stressed', 3: 'Crisis', 4: 'Emergency', 5: 'Catastrophe' };
  const map = new ol.Map({ target: 'public-drought-map', layers: [new ol.layer.Tile({ source: new ol.source.OSM() })], view: new ol.View({ center: ol.proj.fromLonLat([39.5, 13.7]), zoom: 7 }) });
  const replayLayer = new ol.layer.Vector({ source: new ol.source.Vector(), zIndex: 20, style: feature => new ol.style.Style({ fill: new ol.style.Fill({ color: `${codes[feature.get('retrospective_draft_code')] || '#64748b'}b0` }), stroke: new ol.style.Stroke({ color: '#ffffff', width: .55 }) }) });
  const fewsLayer = new ol.layer.Vector({ source: new ol.source.Vector(), zIndex: 30, style: feature => new ol.style.Style({ fill: new ol.style.Fill({ color: 'rgba(0,0,0,0)' }), stroke: new ol.style.Stroke({ color: fewsColours[feature.get('value')] || '#d1d5db', width: 2.5, lineDash: [7, 5] }) }) });
  map.addLayer(replayLayer); map.addLayer(fewsLayer);
  let release, assets, replays = [], issues = [], replayId, issueId, display = 'replay';

  function esc(value) { return String(value == null ? '—' : value).replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[char]); }
  function selectedReplay() { return replays.find(item => item.snapshot_id === replayId); }
  function selectedIssue() { return issues.find(item => item.run_id === issueId); }
  function visibility() { replayLayer.setVisible(display !== 'fews'); fewsLayer.setVisible(display !== 'replay'); }
  function assetFor(id) { return assets.get(id); }
  async function loadLayer(layer, assetId) {
    const asset = assetFor(assetId);
    if (!asset) throw new Error('The selected approved map asset is unavailable.');
    const response = await fetch(asset.url, { cache: 'no-store' });
    if (!response.ok) throw new Error(`The selected map asset returned ${response.status}.`);
    const payload = await response.json();
    layer.getSource().clear();
    layer.getSource().addFeatures(new ol.format.GeoJSON().readFeatures(payload, { featureProjection: 'EPSG:3857' }));
  }
  async function selectReplay(id) {
    replayId = id;
    const item = selectedReplay();
    await loadLayer(replayLayer, item.asset_id);
    const extent = replayLayer.getSource().getExtent();
    if (!ol.extent.isEmpty(extent)) map.getView().fit(extent, { padding: [30, 30, 30, 30], maxZoom: 10 });
  }
  async function selectIssue(id) { issueId = id; await loadLayer(fewsLayer, selectedIssue().asset_id); }
  function detailAt(coordinate) {
    const replay = replayLayer.getSource().getFeaturesAtCoordinate(coordinate)[0];
    const fews = fewsLayer.getSource().getFeaturesAtCoordinate(coordinate)[0];
    const target = panel.querySelector('[data-detail]');
    if (!target) return;
    if (!replay && !fews) { target.textContent = 'Select a Tabia or provider area to read retained context.'; return; }
    const rows = [];
    if (replay) rows.push(`<div><strong>TSIRD retained replay</strong><p><b>${esc(replay.get('retrospective_draft_code'))}</b> neutral stored draft code · ${esc(replay.get('tabia_name_en'))} — ${esc(replay.get('woreda_name_en'))}</p><dl><dt>Rainfall</dt><dd>${esc(replay.get('rainfall_mm'))} mm</dd><dt>Percentile</dt><dd>${esc(replay.get('rainfall_percentile'))}</dd><dt>Evidence state</dt><dd>${esc(replay.get('evidence_state'))}</dd></dl></div>`);
    if (fews) { const value = Number(fews.get('value')); rows.push(`<div><strong>FEWS NET provider context</strong><p><b>${esc(fewsNames[value] || 'Other provider feature')}</b></p><dl><dt>Scenario</dt><dd>${esc(fews.get('scenario'))}</dd><dt>Issue date</dt><dd>${esc(fews.get('reporting_date'))}</dd><dt>Validity</dt><dd>${esc(fews.get('projection_start'))} to ${esc(fews.get('projection_end'))}</dd></dl></div>`); }
    target.innerHTML = `<strong>Side-by-side retained context</strong>${rows.join('<hr>')}<p class="public-drought-meta">The layers remain separate: provider geography does not change the TSIRD draft code.</p>`;
  }
  function render() {
    const replayOptions = replays.map(item => `<option value="${esc(item.snapshot_id)}" ${item.snapshot_id === replayId ? 'selected' : ''}>${esc(String(item.source_latest_month || item.snapshot_id).slice(0, 10))} · ${esc(item.tabias)} Tabias</option>`).join('');
    const issueOptions = issues.map(item => `<option value="${esc(item.run_id)}" ${item.run_id === issueId ? 'selected' : ''}>${esc(String(item.issued_at || item.run_id).slice(0, 10))} · ${esc(item.feature_count)} provider areas</option>`).join('');
    panel.innerHTML = `<h1>Retrospective Evidence Replay</h1><div class="public-drought-banner">Approved public release <b>${esc(release.release_id)}</b><br><small>${esc(release.public_scope)}</small></div><h2>Review controls</h2><div class="public-drought-select"><label>Review month <select data-replay>${replayOptions}</select></label><small>Select an approved retained replay. It is historical evidence, not a forecast or decision.</small></div><div class="public-drought-select"><label>FEWS NET issue <select data-issue>${issueOptions}</select></label><small>Provider-native Food Security Classification context; no class is transferred to a Tabia.</small></div><div class="public-drought-select"><span>Map display</span><div class="public-drought-modes"><button type="button" data-display="replay" class="${display === 'replay' ? 'is-active' : ''}">Evidence replay</button><button type="button" data-display="fews" class="${display === 'fews' ? 'is-active' : ''}">FEWS NET context</button><button type="button" data-display="compare" class="${display === 'compare' ? 'is-active' : ''}">Compare</button></div><small>Compare uses dashed provider boundaries only; colours do not blend with replay codes.</small></div><div class="public-drought-detail" data-detail>Select a Tabia or provider area to read retained context.</div><h2>Legend</h2><ul class="public-drought-legend">${Object.entries(codes).map(([code, colour]) => `<li><i class="public-drought-swatch" style="background:${colour}"></i>${code} replay code</li>`).join('')}${Object.entries(fewsNames).map(([value, name]) => `<li><i class="public-drought-swatch" style="border-color:${fewsColours[value]}; background:transparent"></i>${name} · FEWS NET</li>`).join('')}</ul><p class="public-drought-footnote">Experimental retained evidence only. This page has no model configuration, scoring, allocation, forecast, or operational-decision function.</p>`;
    panel.querySelector('[data-replay]').addEventListener('change', async event => { try { await selectReplay(event.target.value); render(); } catch (error) { panel.querySelector('[data-detail]').textContent = error.message; } });
    panel.querySelector('[data-issue]').addEventListener('change', async event => { try { await selectIssue(event.target.value); render(); } catch (error) { panel.querySelector('[data-detail]').textContent = error.message; } });
    panel.querySelectorAll('[data-display]').forEach(button => button.addEventListener('click', () => { display = button.dataset.display; visibility(); render(); }));
  }
  async function load() {
    try {
      const response = await fetch(API, { cache: 'no-store' });
      if (response.status === 404) throw new Error('No approved public release is available yet.');
      if (!response.ok) throw new Error(`Release metadata returned ${response.status}.`);
      release = await response.json(); assets = new Map(release.assets.map(asset => [asset.asset_id, asset]));
      const replayIndex = assetFor('priority-replay-summary'); const fewsIndex = assetFor('fews-net-context-index');
      if (!replayIndex || !fewsIndex) throw new Error('The approved release lacks required replay context indexes.');
      const [replayPayload, fewsPayload] = await Promise.all([fetch(replayIndex.url, { cache: 'no-store' }), fetch(fewsIndex.url, { cache: 'no-store' })]);
      if (!replayPayload.ok || !fewsPayload.ok) throw new Error('The replay context indexes are unavailable.');
      const replayData = await replayPayload.json(); const fewsData = await fewsPayload.json();
      replays = (replayData.replays || []).map((item, index) => ({ ...item, asset_id: item.asset_id || (index === 0 ? 'priority-replay-latest' : null) })).filter(item => item.asset_id && assetFor(item.asset_id));
      issues = (fewsData.runs || []).map((item, index) => ({ ...item, asset_id: item.asset_id || (index === 0 ? 'fews-net-context-latest' : null) })).filter(item => item.asset_id && assetFor(item.asset_id));
      if (!replays.length || !issues.length) throw new Error('No approved replay or provider context assets are available.');
      replayId = replays[0].snapshot_id; issueId = issues[0].run_id;
      await Promise.all([selectReplay(replayId), selectIssue(issueId)]); visibility(); render();
      map.on('singleclick', event => detailAt(event.coordinate));
    } catch (error) { panel.innerHTML = `<h1>Retrospective Evidence Replay</h1><div class="public-drought-banner warning">${esc(error.message)}</div><p>This route never falls back to development evidence.</p>`; }
  }
  load();
}());
