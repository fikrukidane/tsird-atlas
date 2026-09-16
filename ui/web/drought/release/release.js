(function () {
  'use strict';

  const API = '../../api/drought/public/release';
  const panel = document.getElementById('release-panel');
  const codeColours = { C1: '#b91c1c', C2: '#ea580c', C3: '#f59e0b', C4: '#eab308', 'insufficient-evidence': '#64748b' };
  const fewsColours = { 1: '#64748b', 2: '#facc15', 3: '#f97316', 4: '#e11d48', 5: '#7f1d1d' };
  const fewsNames = { 1: 'Minimal', 2: 'Stressed', 3: 'Crisis', 4: 'Emergency', 5: 'Catastrophe' };
  const map = new ol.Map({
    target: 'release-map',
    layers: [new ol.layer.Tile({ source: new ol.source.OSM() })],
    view: new ol.View({ center: ol.proj.fromLonLat([39.5, 13.7]), zoom: 7 })
  });
  let replayLayer;
  let fewsLayer;
  let display = 'replay';

  function escape(text) {
    return String(text == null ? '—' : text).replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[char]);
  }

  function setLayerVisibility() {
    if (replayLayer) replayLayer.setVisible(display !== 'fews');
    if (fewsLayer) fewsLayer.setVisible(display !== 'replay');
  }

  function renderDetail(feature, kind) {
    const props = feature.getProperties();
    if (kind === 'replay') {
      panel.querySelector('[data-release-detail]').innerHTML = `<strong>${escape(props.tabia_name_en)} — ${escape(props.woreda_name_en)}</strong><p>Retrospective draft code <b>${escape(props.retrospective_draft_code)}</b>. This is a neutral stored code, not an instruction.</p><dl><dt>Rainfall</dt><dd>${escape(props.rainfall_mm)} mm</dd><dt>Percentile</dt><dd>${escape(props.rainfall_percentile)}</dd><dt>Evidence state</dt><dd>${escape(props.evidence_state)}</dd><dt>Note</dt><dd>${escape(props.interpretation_note)}</dd></dl>`;
    } else {
      const value = Number(props.value);
      panel.querySelector('[data-release-detail]').innerHTML = `<strong>FEWS NET provider-native context</strong><p><b>${escape(fewsNames[value] || 'Other provider feature')}</b>. This value remains in the provider's geography and is not transferred to a Tabia.</p><dl><dt>Scenario</dt><dd>${escape(props.scenario)}</dd><dt>Issue date</dt><dd>${escape(props.reporting_date)}</dd><dt>Validity</dt><dd>${escape(props.projection_start)} to ${escape(props.projection_end)}</dd><dt>Scale</dt><dd>${escape(props.classification_scale)}</dd></dl>`;
    }
  }

  function renderPanel(release) {
    const assets = new Map(release.assets.map(asset => [asset.asset_id, asset]));
    panel.innerHTML = `<h1>Retrospective Evidence Replay</h1><div class="release-state">Approved public release <b>${escape(release.release_id)}</b></div><p class="release-meta">Activated ${escape(release.activated_at || 'not recorded')} · ${escape(release.public_scope)}</p><div class="release-toggle"><button type="button" data-display="replay" class="is-active">Evidence replay</button><button type="button" data-display="fews">FEWS NET context</button><button type="button" data-display="compare">Compare</button></div><p class="release-meta">The replay and FEWS NET layers remain separate. FEWS NET uses provider-native boundaries and does not change TSIRD’s stored draft code.</p><h2>Legend</h2><ul class="release-key"><li><i class="release-swatch" style="background:${codeColours.C1}"></i>C1 retrospective draft code</li><li><i class="release-swatch" style="background:${codeColours.C2}"></i>C2 retrospective draft code</li><li><i class="release-swatch" style="background:${codeColours.C3}"></i>C3 retrospective draft code</li><li><i class="release-swatch" style="background:${codeColours.C4}"></i>C4 retrospective draft code</li><li><i class="release-swatch" style="background:${fewsColours[3]}"></i>FEWS NET provider-native outlines</li></ul><div class="release-detail" data-release-detail>Select a map area to read its retained evidence or provider context.</div><h2>Release assets</h2><ul class="release-assets">${release.assets.map(asset => `<li>${escape(asset.source)} · ${escape(asset.source_observation_start)} to ${escape(asset.source_observation_end)}</li>`).join('')}</ul>`;
    panel.querySelectorAll('[data-display]').forEach(button => button.addEventListener('click', function () {
      display = this.dataset.display;
      panel.querySelectorAll('[data-display]').forEach(item => item.classList.toggle('is-active', item === this));
      setLayerVisibility();
    }));
    return assets;
  }

  function asVectorLayer(collection, style) {
    const source = new ol.source.Vector({ features: new ol.format.GeoJSON().readFeatures(collection, { featureProjection: 'EPSG:3857' }) });
    return new ol.layer.Vector({ source, style });
  }

  async function load() {
    let release;
    try {
      const response = await fetch(API, { cache: 'no-store' });
      if (response.status === 404) {
        panel.innerHTML = '<h1>Retrospective Evidence Replay</h1><div class="release-state is-waiting">No approved public evidence release is available yet.</div><p>This page will show only an explicitly approved, compact release. It does not fall back to development data.</p>';
        return;
      }
      if (!response.ok) throw new Error(`release metadata returned ${response.status}`);
      release = await response.json();
    } catch (error) {
      panel.innerHTML = `<h1>Retrospective Evidence Replay</h1><div class="release-state is-error">The approved release cannot be read right now.</div><p>${escape(error.message)}</p>`;
      return;
    }
    const assets = renderPanel(release);
    const replay = assets.get('priority-replay-latest');
    const fews = assets.get('fews-net-context-latest');
    if (!replay || !fews) {
      panel.insertAdjacentHTML('afterbegin', '<div class="release-state is-error">This approved release is missing its required map assets.</div>');
      return;
    }
    try {
      const [replayPayload, fewsPayload] = await Promise.all([fetch(replay.url, { cache: 'no-store' }), fetch(fews.url, { cache: 'no-store' })]);
      if (!replayPayload.ok || !fewsPayload.ok) throw new Error('required release map asset is unavailable');
      replayLayer = asVectorLayer(await replayPayload.json(), feature => new ol.style.Style({ fill: new ol.style.Fill({ color: `${codeColours[feature.get('retrospective_draft_code')] || '#64748b'}99` }), stroke: new ol.style.Stroke({ color: '#ffffff', width: .5 }) }));
      fewsLayer = asVectorLayer(await fewsPayload.json(), feature => new ol.style.Style({ fill: new ol.style.Fill({ color: 'rgba(0,0,0,0)' }), stroke: new ol.style.Stroke({ color: fewsColours[feature.get('value')] || '#d1d5db', width: 2, lineDash: [7, 5] }) }));
      map.addLayer(replayLayer);
      map.addLayer(fewsLayer);
      fewsLayer.setVisible(false);
      map.getView().fit(replayLayer.getSource().getExtent(), { padding: [30, 30, 30, 30], maxZoom: 10 });
      map.on('singleclick', event => {
        const replayFeature = replayLayer.getSource().getFeaturesAtCoordinate(event.coordinate)[0];
        const fewsFeature = fewsLayer.getSource().getFeaturesAtCoordinate(event.coordinate)[0];
        if (display !== 'fews' && replayFeature) renderDetail(replayFeature, 'replay');
        else if (display !== 'replay' && fewsFeature) renderDetail(fewsFeature, 'fews');
      });
    } catch (error) {
      panel.insertAdjacentHTML('afterbegin', `<div class="release-state is-error">Map assets could not be displayed: ${escape(error.message)}</div>`);
    }
  }

  load();
}());
