/**
 * Development drought-intelligence dashboard.
 *
 * Indicators remain separate. Every selected record has an explicit
 * administrative geography: observed/exposure fixtures use a Tabia and the
 * intentionally coarse outlook fixture uses its Woreda. The API supplies the
 * actual geometry for a fit and outline; no town point is used as a proxy.
 */
class DroughtDashboard {
  constructor(map, options = {}) {
    this.map = map;
    this.dataUrl = options.dataUrl || 'data/drought-intelligence.dev.json';
    this.observedUrl = options.observedUrl || 'api/drought/development/observed-rainfall/latest?limit=100';
    this.observedRunsUrl = options.observedRunsUrl || 'api/drought/development/observed-rainfall/runs?limit=36';
    this.observedRunBaseUrl = options.observedRunBaseUrl || 'api/drought/development/observed-rainfall/runs';
    this.preliminaryUrl = options.preliminaryUrl || 'api/drought/development/preliminary-rainfall/latest?limit=748';
    this.ndviUrl = options.ndviUrl || 'api/drought/development/ndvi/latest?limit=748';
    this.swiUrl = options.swiUrl || 'api/drought/development/swi/latest?limit=748';
    this.lstUrl = options.lstUrl || 'api/drought/development/lst/latest?limit=748';
    this.waporUrl = options.waporUrl || 'api/drought/development/wapor/latest?limit=748';
    // DroughtDashboard is also mounted under /map/drought/, so its fallback
    // must resolve through the parent /map/api/ route even if an older caller
    // has not yet supplied the explicit workspace URL.
    this.outlookUrl = options.outlookUrl || '../api/drought/development/seasonal-outlook';
    this.priorityConfigurationUrl = options.priorityConfigurationUrl || '../api/drought/development/priority/model-configuration';
    this.priorityPreviewsUrl = options.priorityPreviewsUrl || '../api/drought/development/priority/calibration-previews';
    this.priorityReplaysUrl = options.priorityReplaysUrl || '../api/drought/development/priority/historical-replays';
    this.fewsNetRunsUrl = options.fewsNetRunsUrl || '../api/drought/development/fews-net-context/runs';
    this.fewsNetRunBaseUrl = options.fewsNetRunBaseUrl || '../api/drought/development/fews-net-context/runs';
    this.modelReadinessUrl = options.modelReadinessUrl || '../api/drought/development/model-readiness';
    this.historyUrl = options.historyUrl || 'api/drought/development/history';
    this.evidenceBaseUrl = options.evidenceBaseUrl || 'api/drought/development/evidence';
    this.boundaryUrl = options.boundaryUrl || 'api/boundaries';
    this.containerId = options.containerId || 'drought-dashboard';
    this.priorityOnly = Boolean(options.priorityOnly);
    this.mode = this.priorityOnly ? 'priority' : 'observed';
    this.data = null;
    this.boundaryLayer = null;
    this.fixtureLayer = null;
    this.fixtureRenderToken = 0;
    this.selectedId = null;
    this.observedArtifact = null;
    this.observedRuns = [];
    this.observedSnapshotId = 'latest';
    this.preliminaryArtifact = null;
    this.ndviArtifact = null;
    this.swiArtifact = null;
    this.lstArtifact = null;
    this.waporArtifact = null;
    this.outlookArtifact = null;
    this.outlookRuns = [];
    this.priorityConfiguration = null;
    this.priorityPreviews = [];
    this.priorityReplays = [];
    this.priorityPreviewSnapshot = null;
    this.priorityPreviewLayer = null;
    this.fewsNetRuns = [];
    this.fewsNetRunId = null;
    this.fewsNetDisplay = 'priority';
    this.fewsNetLayer = null;
    this.modelReadiness = null;
    this.outlookRunId = 'active';
    this.outlookRepresentation = 'native_grid';
    this.historyIndicator = 'ndvi';
    this.historyTabiaId = null;
    this.historyTabiaLabel = '';
    this.historyMapSnapshot = 'latest';
    this.historyCompareSnapshot = 'off';
    this.historyDisplay = 'value';
    this.historyRuns = { rainfall: [], rapid: [], ndvi: [], swi: [], lst: [], wapor: [] };
    this.historyMapToken = 0;
    this.historyComparisonLayer = null;
    this.exposureMeasure = 'population';
    this.spatialViews = { observed: 'tabia', rapid: 'raw', vegetation: 'tabia', soilWater: 'tabia', thermal: 'tabia', waterUse: 'tabia' };
    this.onEnsureContextLayers = options.onEnsureContextLayers || null;
    this.onSetEvidenceLayer = options.onSetEvidenceLayer || null;
  }

  async initialize() {
    const response = await fetch(this.dataUrl, { cache: 'no-store' });
    if (!response.ok) throw new Error(`Drought data unavailable (${response.status})`);
    this.data = await response.json();
    this._validateData();
    await this._loadObservedArtifact();
    await this._loadObservedRuns();
    await this._loadPreliminaryArtifact();
    await this._loadNdviArtifact();
    await this._loadSwiArtifact();
    await this._loadLstArtifact();
    await this._loadWaporArtifact();
    await this._loadOutlookArtifact();
    await this._loadPriorityFoundation();
    await this._loadFewsNetContext();
    await this._loadHistoryRuns();
    this._createBoundaryLayer();
    this._renderShell();
    this._renderMode();
    window.addEventListener('tsird:boundary-selected', event => this._handleBoundarySelection(event));
    return this;
  }

  async _loadPriorityFoundation() {
    const [configurationResult, readinessResult, previewsResult, replaysResult] = await Promise.allSettled([
      fetch(this.priorityConfigurationUrl, { cache: 'no-store' }),
      fetch(this.modelReadinessUrl, { cache: 'no-store' }),
      fetch(this.priorityPreviewsUrl, { cache: 'no-store' }),
      fetch(this.priorityReplaysUrl, { cache: 'no-store' })
    ]);
    try {
      if (configurationResult.status !== 'fulfilled' || !configurationResult.value.ok) throw new Error('configuration unavailable');
      const payload = await configurationResult.value.json();
      if (!payload || !payload.configuration) throw new Error('invalid configuration');
      this.priorityConfiguration = payload;
    } catch (error) {
      console.error('[DroughtDashboard] Priority model configuration unavailable:', error);
      this.priorityConfiguration = { unavailable: true, message: 'Priority model definition is unavailable.' };
    }
    try {
      if (readinessResult.status !== 'fulfilled' || !readinessResult.value.ok) throw new Error('readiness unavailable');
      this.modelReadiness = await readinessResult.value.json();
    } catch (error) {
      console.error('[DroughtDashboard] Priority model readiness unavailable:', error);
      this.modelReadiness = { status: 'unavailable', reason: 'Priority evidence-readiness inspection is unavailable.' };
    }
    try {
      if (previewsResult.status !== 'fulfilled' || !previewsResult.value.ok) throw new Error('previews unavailable');
      const payload = await previewsResult.value.json();
      this.priorityPreviews = Array.isArray(payload.previews) ? payload.previews : [];
      if (!this.priorityPreviewSnapshot && this.priorityPreviews.length) this.priorityPreviewSnapshot = this.priorityPreviews[0].snapshot_id;
    } catch (error) {
      console.error('[DroughtDashboard] Priority calibration previews unavailable:', error);
      this.priorityPreviews = [];
    }
    try {
      if (replaysResult.status !== 'fulfilled' || !replaysResult.value.ok) throw new Error('replays unavailable');
      const payload = await replaysResult.value.json();
      this.priorityReplays = Array.isArray(payload.replays) ? payload.replays : [];
      if (this.priorityReplays.length) this.priorityPreviewSnapshot = this.priorityReplays[0].snapshot_id;
    } catch (error) {
      console.error('[DroughtDashboard] Priority historical replays unavailable:', error);
      this.priorityReplays = [];
    }
  }

  async _loadFewsNetContext() {
    try {
      const response = await fetch(this.fewsNetRunsUrl, { cache: 'no-store' });
      const payload = await response.json();
      if (!response.ok || !Array.isArray(payload.runs)) throw new Error('invalid provider context');
      this.fewsNetRuns = payload.runs;
      if (!this.fewsNetRunId && this.fewsNetRuns.length) this.fewsNetRunId = this.fewsNetRuns[0].run_id;
    } catch (error) {
      console.error('[DroughtDashboard] FEWS NET provider context unavailable:', error);
      this.fewsNetRuns = [];
    }
  }

  async _loadNdviArtifact() {
    try { const response = await fetch(this.ndviUrl, { cache: 'no-store' }); const artifact = await response.json(); if (!response.ok || !artifact.run || !Array.isArray(artifact.summaries)) throw new Error('invalid NDVI artifact'); this.ndviArtifact = artifact; }
    catch (error) { console.error('[DroughtDashboard] NDVI unavailable:', error); this.ndviArtifact = { unavailable: true, message: 'Vegetation-condition artifact is unavailable.' }; }
  }

  async _loadSwiArtifact() {
    try {
      const response = await fetch(this.swiUrl, { cache: 'no-store' });
      const artifact = await response.json();
      if (!response.ok || !artifact.run || !Array.isArray(artifact.summaries)) throw new Error('invalid SWI artifact');
      this.swiArtifact = artifact;
    } catch (error) {
      console.error('[DroughtDashboard] SWI unavailable:', error);
      this.swiArtifact = { unavailable: true, message: 'Soil-water context artifact is unavailable.' };
    }
  }

  async _loadLstArtifact() {
    try {
      const response = await fetch(this.lstUrl, { cache: 'no-store' }); const artifact = await response.json();
      if (!response.ok || !artifact.run || !Array.isArray(artifact.summaries)) throw new Error('invalid LST artifact');
      this.lstArtifact = artifact;
    } catch (error) {
      console.error('[DroughtDashboard] LST unavailable:', error);
      this.lstArtifact = { unavailable: true, message: 'Thermal-context artifact is unavailable.' };
    }
  }

  async _loadWaporArtifact() {
    try {
      const response = await fetch(this.waporUrl, { cache: 'no-store' }); const artifact = await response.json();
      if (!response.ok || !artifact.run || !Array.isArray(artifact.summaries)) throw new Error('invalid WaPOR artifact');
      this.waporArtifact = artifact;
    } catch (error) {
      console.error('[DroughtDashboard] WaPOR unavailable:', error);
      this.waporArtifact = { unavailable: true, message: 'Agricultural water-use artifact is unavailable.' };
    }
  }

  async _loadOutlookArtifact(runId = 'active') {
    try {
      const [activeResponse, runsResponse] = await Promise.all([
        fetch(`${this.outlookUrl}/active?variable=seasonal_rainfall`, { cache: 'no-store' }),
        fetch(`${this.outlookUrl}/runs?variable=seasonal_rainfall`, { cache: 'no-store' })
      ]);
      const active = await activeResponse.json();
      const runs = await runsResponse.json();
      if (!activeResponse.ok || !runsResponse.ok || !Array.isArray(runs.runs)) throw new Error('invalid seasonal-outlook response');
      this.outlookRuns = runs.runs;
      const selected = runId === 'active' ? active.run : this.outlookRuns.find(candidate => candidate.run_id === runId);
      this.outlookRunId = runId;
      this.outlookArtifact = selected && (runId !== 'active' || active.available !== false)
        ? { available: true, run: selected }
        : { available: false, reason: active.reason || 'No reviewed active or upcoming provider outlook is loaded.' };
    } catch (error) {
      console.error('[DroughtDashboard] seasonal outlook unavailable:', error);
      this.outlookRuns = [];
      this.outlookArtifact = { available: false, reason: 'Seasonal outlook service is unavailable.' };
    }
  }

  async _loadPreliminaryArtifact() {
    try {
      const response = await fetch(this.preliminaryUrl, { cache: 'no-store' });
      if (!response.ok) throw new Error(`preliminary artifact returned ${response.status}`);
      const artifact = await response.json();
      if (!Array.isArray(artifact.summaries) || !artifact.run) throw new Error('invalid preliminary artifact schema');
      this.preliminaryArtifact = artifact;
    } catch (error) {
      console.error('[DroughtDashboard] Preliminary artifact unavailable:', error);
      this.preliminaryArtifact = { unavailable: true, message: 'Rapid preliminary rainfall is unavailable.' };
    }
  }

  async _loadObservedArtifact(runId = 'latest') {
    try {
      const url = runId === 'latest'
        ? this.observedUrl
        : `${this.observedRunBaseUrl}/${encodeURIComponent(runId)}?limit=748`;
      const response = await fetch(url, { cache: 'no-store' });
      if (!response.ok) throw new Error(`observed artifact returned ${response.status}`);
      const artifact = await response.json();
      if (!Array.isArray(artifact.conditions) || !artifact.run) throw new Error('invalid observed artifact schema');
      this.observedArtifact = artifact;
    } catch (error) {
      console.error('[DroughtDashboard] Observed artifact unavailable:', error);
      this.observedArtifact = { unavailable: true, message: 'Current development rainfall artifact is unavailable.' };
    }
  }

  async _loadObservedRuns() {
    try {
      const response = await fetch(this.observedRunsUrl, { cache: 'no-store' });
      const payload = await response.json();
      if (!response.ok || !Array.isArray(payload.runs)) throw new Error('invalid observed-rainfall run list');
      this.observedRuns = payload.runs;
    } catch (error) {
      console.error('[DroughtDashboard] Historical rainfall snapshots unavailable:', error);
      this.observedRuns = [];
    }
  }

  async _loadHistoryRuns() {
    const kinds = ['rainfall', 'rapid', 'ndvi', 'swi', 'lst', 'wapor'];
    await Promise.all(kinds.map(async kind => {
      try {
        const response = await fetch(`${this.evidenceBaseUrl}/${kind}/runs`, { cache: 'no-store' });
        const payload = await response.json();
        if (!response.ok || !Array.isArray(payload.runs)) throw new Error('invalid evidence run list');
        this.historyRuns[kind] = payload.runs;
      } catch (error) {
        console.error(`[DroughtDashboard] ${kind} evidence snapshots unavailable:`, error);
        this.historyRuns[kind] = [];
      }
    }));
  }

  _validateData() {
    if (!this.data || !Array.isArray(this.data.areas) || !Array.isArray(this.data.sources)) {
      throw new Error('Invalid drought intelligence schema');
    }
    this.data.areas.forEach(area => {
      if (!area.id || !area.name_en) throw new Error('Drought fixture contains an invalid area record');
      ['observed', 'vulnerability'].forEach(mode => {
        const boundary = area[mode] && area[mode].boundary;
        if (!boundary || !['tabia', 'woreda'].includes(boundary.type) || typeof boundary.id !== 'string' || !boundary.id) {
          throw new Error(`Drought fixture has no valid ${mode} boundary for ${area.id}`);
        }
      });
    });
  }

  _createBoundaryLayer() {
    this.outlookLayer = new ol.layer.Vector({
      source: new ol.source.Vector(),
      zIndex: 998,
      style: feature => this._outlookFeatureStyle(feature)
    });
    this.outlookLayer.setVisible(false);
    this.map.addLayer(this.outlookLayer);
    this.historyComparisonLayer = new ol.layer.Vector({
      source: new ol.source.Vector(),
      zIndex: 999,
      style: feature => this._historyMapStyle(feature)
    });
    this.historyComparisonLayer.setVisible(false);
    this.map.addLayer(this.historyComparisonLayer);
    this.priorityPreviewLayer = new ol.layer.Vector({
      source: new ol.source.Vector(), zIndex: 999,
      style: feature => this._priorityPreviewStyle(feature)
    });
    this.priorityPreviewLayer.setVisible(false);
    this.map.addLayer(this.priorityPreviewLayer);
    this.fewsNetLayer = new ol.layer.Vector({
      source: new ol.source.Vector(), zIndex: 1000,
      style: feature => this._fewsNetStyle(feature)
    });
    this.fewsNetLayer.setVisible(false);
    this.map.addLayer(this.fewsNetLayer);
    this.fixtureLayer = new ol.layer.Vector({
      source: new ol.source.Vector(),
      zIndex: 1000,
      style: feature => this._fixtureStyle(feature)
    });
    this.map.addLayer(this.fixtureLayer);
    this.boundaryLayer = new ol.layer.Vector({
      source: new ol.source.Vector(),
      style: new ol.style.Style({
        stroke: new ol.style.Stroke({ color: '#7c2d12', width: 3 }),
        fill: new ol.style.Fill({ color: 'rgba(251, 146, 60, 0.18)' })
      }),
      zIndex: 1001
    });
    this.map.addLayer(this.boundaryLayer);
    this.map.on('singleclick', event => this._handleFixtureMapClick(event));
  }

  _setBoundaryHighlightStyle(historySelection) {
    if (!this.boundaryLayer) return;
    this.boundaryLayer.setStyle(new ol.style.Style({
      stroke: new ol.style.Stroke({ color: historySelection ? '#facc15' : '#7c2d12', width: historySelection ? 4 : 3 }),
      fill: new ol.style.Fill({ color: historySelection ? 'rgba(250, 204, 21, 0.28)' : 'rgba(251, 146, 60, 0.18)' })
    }));
  }

  _renderShell() {
    const root = document.getElementById(this.containerId);
    if (!root) throw new Error(`#${this.containerId} not found`);
    root.innerHTML = '';
    const heading = document.createElement('div');
    heading.className = 'drought-heading';
    heading.innerHTML = this.priorityOnly
      ? `<div><strong>Retrospective Evidence Replay</strong><span>Tigray · ${this.priorityReplays.length ? 'retained draft evidence' : 'retrospective calibration review'}</span></div>`
      : '<div><strong>Drought intelligence</strong><span>Tigray · development view</span></div>';
    const close = document.createElement('button');
    close.className = 'drought-close';
    close.type = 'button';
    close.textContent = '×';
    close.title = 'Hide drought intelligence';
    close.addEventListener('click', () => root.classList.toggle('is-hidden'));
    heading.appendChild(close);
    root.appendChild(heading);

    const notice = document.createElement('div');
    notice.className = 'drought-notice';
    notice.textContent = this.data.geographic_note;
    this.notice = notice;
    root.appendChild(notice);

    const controls = document.createElement('div');
    controls.className = 'drought-mode-controls';
    const modeItems = this.priorityOnly
      ? []
      : [['observed', 'Latest'], ['rapid', 'Rapid rain'], ['vegetation', 'Vegetation'], ['soilWater', 'Soil water'], ['thermal', 'Thermal'], ['waterUse', 'Crop water use'], ['history', 'History'], ['outlook', 'Outlook'], ['vulnerability', 'Exposure']];
    modeItems.forEach(([mode, label]) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.dataset.mode = mode;
      button.textContent = label;
      button.addEventListener('click', () => {
        this.mode = mode;
        this._renderMode();
      });
      controls.appendChild(button);
    });
    root.appendChild(controls);
    this.content = document.createElement('div');
    this.content.className = 'drought-content';
    root.appendChild(this.content);
    this.legend = document.createElement('section');
    this.legend.className = 'drought-legend';
    this.legend.setAttribute('aria-label', 'Active drought intelligence legend');
    root.appendChild(this.legend);
    const footer = document.createElement('div');
    footer.className = 'drought-footer';
    footer.textContent = this.priorityOnly
      ? (this.priorityReplays.length ? 'Development retrospective replay · draft only; no forecast or publication' : 'Development retrospective calibration review · no priority score or forecast')
      : 'Development workspace · no composite risk score';
    root.appendChild(footer);
  }

  _renderMode() {
    document.body.dataset.tsirdDroughtMode = this.mode;
    document.querySelectorAll('#drought-dashboard [data-mode]').forEach(button => {
      button.classList.toggle('is-active', button.dataset.mode === this.mode);
    });
    if (this.mode !== 'vulnerability') this._clearFixtureMap();
    if (this.mode !== 'outlook' && this.outlookLayer) {
      this.outlookLayer.setVisible(false);
      this.outlookLayer.getSource().clear();
    }
    if (this.mode !== 'history' && this.historyComparisonLayer) {
      this.historyComparisonLayer.setVisible(false);
      this.historyComparisonLayer.getSource().clear();
    }
    if (this.mode !== 'priority' && this.priorityPreviewLayer) {
      this.priorityPreviewLayer.setVisible(false);
      this.priorityPreviewLayer.getSource().clear();
    }
    if (this.mode !== 'priority' && this.fewsNetLayer) {
      this.fewsNetLayer.setVisible(false);
      this.fewsNetLayer.getSource().clear();
    }
    if (!['history', 'priority'].includes(this.mode) && this.boundaryLayer) {
      this.boundaryLayer.getSource().clear();
    }
    if (this.mode === 'observed') {
      const historical = this.observedSnapshotId !== 'latest';
      this._setEvidenceLayer(historical ? null : this._evidenceLayerForMode());
      this.notice.textContent = historical
        ? 'Historical evidence snapshot: this Tabia-only map shows an archived CHIRPS observation period. It is not an as-issued forecast or a model backtest, and no historical native raster is implied.'
        : this.spatialViews.observed === 'raw'
        ? 'Latest available analysis is a development CHIRPS native-grid rainfall total. Its ten bands show measured totals only—not drought priority. Select Tabia class for the baseline-relative Tabia interpretation.'
        : 'Latest available analysis is a development CHIRPS Tabia summary. Click a coloured Tabia on the map for its evidence; areas without sufficient grid coverage are not classified.';
      this._renderObservedArtifact();
      if (historical) this._showHistoricalObservedMap(); else this._renderSpatialControl();
      this._renderLegend();
      return;
    }
    if (this.mode === 'rapid') {
      this._setEvidenceLayer(this._evidenceLayerForMode());
      this.notice.textContent = 'Rapid monitoring uses six completed CHIRPS preliminary pentads. Choose the native grid or Tabia zonal average; it is an observed rainfall total, not a drought class or food-security prediction.';
      this._renderPreliminaryArtifact();
      this._renderSpatialControl();
      this._renderLegend();
      return;
    }
    if (this.mode === 'vegetation') { this._setEvidenceLayer(this._evidenceLayerForMode()); this.notice.textContent = 'Vegetation condition can be shown as the retained Copernicus native raster or a Tabia zonal mean. It is not a drought or food-security classification.'; this._renderNdviArtifact(); this._renderSpatialControl(); this._renderLegend(); return; }
    if (this.mode === 'soilWater') { this._setEvidenceLayer(this._evidenceLayerForMode()); this.notice.textContent = 'Soil water can be shown as the coarse Copernicus native grid or a Tabia zonal mean. It is context, not a Tabia-scale observation, drought class, or food-security prediction.'; this._renderSwiArtifact(); this._renderSpatialControl(); this._renderLegend(); return; }
    if (this.mode === 'thermal') { this._setEvidenceLayer(this._evidenceLayerForMode()); this.notice.textContent = 'Land-surface temperature can be shown as the retained native raster or a Tabia zonal mean. It is not measured air temperature, a drought class, or a food-security prediction.'; this._renderLstArtifact(); this._renderSpatialControl(); this._renderLegend(); return; }
    if (this.mode === 'waterUse') { this._setEvidenceLayer(this._evidenceLayerForMode()); this.notice.textContent = 'Crop water use shows FAO WaPOR transpiration—a vegetation water-use measure—alongside actual evapotranspiration context. It is not current crop extent, yield, drought severity, food-security, or a priority classification.'; this._renderWaporArtifact(); this._renderSpatialControl(); this._renderLegend(); return; }
    if (this.mode === 'history') {
      this._setEvidenceLayer(this._historyEvidenceLayer());
      this._ensureContextLayersVisible('tabia');
      this.notice.textContent = 'History keeps the latest selected indicator visible as map context. Select a Tabia to plot its retained observations; the chart does not interpolate gaps or combine indicators into a risk score.';
      this._renderHistory();
      this._renderHistoryMap();
      this._renderLegend();
      return;
    }
    if (this.mode === 'outlook') {
      this._setEvidenceLayer(null);
      this._ensureContextLayersVisible('woreda');
      this.notice.textContent = 'Seasonal rainfall outlook uses the provider’s native probability geography. Woreda is available only as a labelled contextual summary; no Tabia forecast is created.';
      this._renderOutlookMap();
      this._showOutlookMap();
      this._renderLegend();
      return;
    }
    if (this.mode === 'priority') {
      this._setEvidenceLayer(null);
      this._ensureContextLayersVisible('tabia');
      this.notice.textContent = this.priorityReplays.length
        ? 'Retrospective draft replay only. It displays a retained draft snapshot and its evidence; it is not a forecast, current operational priority, or published decision. FEWS NET can be displayed separately as provider-issued food-security context.'
        : 'Retrospective calibration review only. It shows observed rainfall relative to normal; it is not a forecast or a published priority ranking.';
      this._renderPriorityWorkspace();
      this._showPriorityPreviewMap();
      this._renderLegend();
      return;
    }
    if (this.mode === 'vulnerability') {
      const roadView = this.exposureMeasure === 'road';
      const populationView = this.exposureMeasure === 'population';
      const croplandView = this.exposureMeasure === 'cropland';
      this._setEvidenceLayer(roadView ? 'tigray_drought_road_accessibility_dev' : (populationView ? 'tigray_drought_population_dev' : (croplandView ? 'tigray_drought_cropland_dev' : null)));
      this._ensureContextLayersVisible('tabia');
      this.notice.textContent = populationView
        ? 'Population baseline maps a WorldPop 2025 100 m constrained population estimate summarized to Tabias. It is an alpha modeled estimate, not an official census or a drought-exposure count.'
        : croplandView
        ? 'Cropland share maps the ESA WorldCover 2021 10 m cropland class summarized to Tabias. It is a reference land-cover baseline—not current cultivation, crop production, food insecurity, or a response-priority score.'
        : roadView
        ? 'Road proximity is a full Tabia baseline to mapped Federal (ERA) and Regional (TRRA) Tigray Roads 2006 features. It is straight-line distance from a representative Tabia point—not travel time, road condition, seasonal passability, humanitarian access, or a risk score.'
        : 'Exposure is a Tabia reporting map. It shows available development population or cropland records separately; it is not a composite risk, food-security, aid-access, or road-accessibility score.';
      this._renderExposureMap();
      if (roadView || populationView || croplandView) this._clearFixtureMap(); else this._showFixtureMap('vulnerability');
      this._renderLegend();
    }
  }

  _renderPriorityWorkspace() {
    const model = this.priorityConfiguration;
    const readiness = this.modelReadiness || {};
    if (!model || model.unavailable || !model.configuration) {
      this.content.innerHTML = `<div class="drought-mode-title"><strong>Retrospective Evidence Replay</strong><span>Model definition unavailable</span></div><div class="drought-period-stamp"><strong>Replay unavailable</strong><span>${model && model.message ? model.message : 'Loading the local model definition.'}</span><small>No score or planning map is drawn.</small></div>`;
      return;
    }
    const config = model.configuration;
    const settings = config.configuration || {};
    const observed = settings.observed_stress || {};
    const exposure = settings.exposure || {};
    const decision = readiness.decision || {};
    const gateStatus = readiness.status === 'unavailable' ? 'unavailable' : (decision.status || 'not evaluated');
    const gateBlocked = String(gateStatus).toLowerCase().replace(/_/g, '-') === 'not-ready';
    const configuredFactors = (settings.factors || []).filter(item => item.enabled).map(item => item.name);
    const disabledFactors = (settings.factors || []).filter(item => !item.enabled).map(item => item.name);
    const factorTrace = `<div class="drought-map-instruction"><strong>Active model trace</strong><span>Enabled in the active draft: ${configuredFactors.length ? configuredFactors.join(', ') : 'none stated'}. Disabled: ${disabledFactors.length ? disabledFactors.join(', ') : 'none stated'}.</span><small>Retained replay snapshots are read as retrospective calibration evidence. The selected Tabia shows the stored text trace available in that snapshot; snapshot-level configuration version and full factor provenance are not yet displayed. No live configuration is retroactively applied to a past snapshot.</small></div>`;
    const gateBanner = gateBlocked ? `<div class="drought-readiness-warning"><strong>Gate NOT READY — retrospective replay only.</strong><span>The displayed replay flags can be above the current observed-stress ceiling. They must not be used for operational priority, allocation, or a published map until evidence readiness is resolved.</span></div>` : '';
    const replays = this.priorityReplays.length > 0;
    const reviews = replays ? this.priorityReplays : this.priorityPreviews;
    const prioritySelectionInstruction = this.fewsNetDisplay === 'fews'
      ? 'Priority replay is hidden. Switch to Priority replay or Compare to select a Tabia and see its draft planning explanation.'
      : 'Select a Tabia to see the explanation.';
    const previewSummary = reviews.length
      ? `<div class="drought-history-controls"><label>Review month <select data-priority-preview>${reviews.map(item => `<option value="${item.snapshot_id}" ${item.snapshot_id === this.priorityPreviewSnapshot ? 'selected' : ''}>${String(item.source_latest_month).slice(0, 10)}</option>`).join('')}</select></label><small>Click a coloured Tabia to see its stored replay trace and neutral replay flag.</small></div><div class="drought-map-selection" data-priority-preview-selection>${prioritySelectionInstruction}</div>`
      : '<div class="drought-map-selection"><strong>No retrospective review is available yet.</strong></div>';
    const fewsSelectionInstruction = this.fewsNetDisplay === 'fews'
      ? 'Click a FEWS NET provider area to see its classification, scenario, and validity period.'
      : 'Select a Tabia on the priority map to check intersecting provider context.';
    const fewsSummary = this.fewsNetRuns.length
      ? `<div class="drought-history-controls"><label>FEWS NET issue <select data-fews-net-run>${this.fewsNetRuns.map(item => `<option value="${item.run_id}" ${item.run_id === this.fewsNetRunId ? 'selected' : ''}>${String(item.issued_at).slice(0, 10)} · ${item.feature_count} provider areas</option>`).join('')}</select></label><small>Native Food Security Classification geography. It is external context, not a Tabia classification.</small></div><div class="drought-spatial-control"><span>Map display</span><div><button type="button" data-fews-net-display="priority" class="${this.fewsNetDisplay === 'priority' ? 'is-active' : ''}">Priority replay</button><button type="button" data-fews-net-display="fews" class="${this.fewsNetDisplay === 'fews' ? 'is-active' : ''}">FEWS NET context</button><button type="button" data-fews-net-display="compare" class="${this.fewsNetDisplay === 'compare' ? 'is-active' : ''}">Compare</button></div><small>Compare draws FEWS NET as dashed provider boundaries only, so its colours never blend with the local replay.</small></div><div class="drought-map-selection" data-fews-net-selection>${fewsSelectionInstruction}</div>`
      : '<div class="drought-map-instruction">FEWS NET retained provider context is not available from this local development service.</div>';
    this.content.innerHTML = replays
      ? `<div class="drought-mode-title"><strong>Retrospective review replay</strong><span>Draft model · v${config.version}</span></div>${gateBanner}<div class="drought-period-stamp"><strong>What this map shows</strong><span>Draft, explainable replay flags from retained rainfall and static exposure evidence.</span><small>This is a retrospective plausibility replay—not an as-issued forecast, published decision, allocation, IPC phase, or food-security classification.</small></div><div class="drought-source-meta"><span>Tabia level</span><span>CHIRPS 1991–2020 reference</span><span>Gate: ${gateStatus}</span></div>${previewSummary}${fewsSummary}${factorTrace}`
      : `<div class="drought-mode-title"><strong>Historical agricultural-stress review</strong><span>Draft calibration · v${config.version}</span></div><div class="drought-period-stamp"><strong>What this map shows</strong><span>Observed monthly rainfall compared with the Tabia’s normal rainfall for the same month.</span><small>Dark red means unusually low rainfall. This supports review of the draft thresholds; it is not a forecast or a priority ranking.</small></div><div class="drought-source-meta"><span>Tabia level</span><span>CHIRPS 1991–2020 reference</span><span>Gate: ${gateStatus}</span></div>${previewSummary}<div class="drought-map-instruction">People, cropland, and road context appear only after you select a Tabia. They are not combined into a score in this review.</div>`;
    const previewSelector = this.content.querySelector('[data-priority-preview]');
    if (previewSelector) previewSelector.addEventListener('change', event => {
      this.priorityPreviewSnapshot = event.target.value;
      this._renderMode();
    });
    const fewsSelector = this.content.querySelector('[data-fews-net-run]');
    if (fewsSelector) fewsSelector.addEventListener('change', event => { this.fewsNetRunId = event.target.value; this._renderMode(); });
    this.content.querySelectorAll('[data-fews-net-display]').forEach(button => button.addEventListener('click', () => { this.fewsNetDisplay = button.dataset.fewsNetDisplay; this._renderMode(); }));
  }

  _fewsNetStyle(feature) {
    const properties = feature.getProperties();
    const raw = String(properties.phase || properties.ipc_phase || properties.ml1 || properties.value || properties.classification || '').toLowerCase();
    const colour = raw.includes('5') || raw.includes('catastroph') ? '#7f1d1d' : raw.includes('4') || raw.includes('emergency') ? '#dc2626' : raw.includes('3') || raw.includes('crisis') ? '#f97316' : raw.includes('2') || raw.includes('stress') ? '#facc15' : '#64748b';
    const compare = this.fewsNetDisplay === 'compare';
    return new ol.style.Style({ fill: new ol.style.Fill({ color: compare ? 'rgba(0,0,0,0)' : `${colour}44` }), stroke: new ol.style.Stroke({ color: colour, width: compare ? 3 : 2, lineDash: [6, 4] }) });
  }

  _fewsNetClassification(properties) {
    const raw = properties.phase || properties.ipc_phase || properties.ml1 || properties.value || properties.classification;
    const value = String(raw == null ? '' : raw).trim();
    const labels = { '1': 'Minimal', '2': 'Stressed', '3': 'Crisis', '4': 'Emergency', '5': 'Catastrophe' };
    return {
      value,
      label: labels[value] || (value ? 'Provider classification' : 'Classification not supplied'),
      display: labels[value] || (value || 'Not supplied')
    };
  }

  _fewsNetScenario(properties) {
    const scenario = String(properties.scenario || properties.scenario_name || '').trim();
    if (scenario === 'ML1') return 'Current assessment';
    if (scenario === 'ML2') return 'Projected assessment';
    return scenario || 'Assessment type not supplied';
  }

  _fewsNetPeriod(properties) {
    const start = properties.projection_start || properties.valid_from || properties.start_date;
    const end = properties.projection_end || properties.valid_to || properties.end_date;
    if (!start && !end) return 'Period not supplied';
    const monthLabel = value => {
      const match = String(value || '').match(/^(\d{4})-(\d{2})/);
      if (!match) return String(value || 'unspecified');
      return `${['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][Number(match[2]) - 1]} ${match[1]}`;
    };
    const startLabel = monthLabel(start);
    const endLabel = monthLabel(end);
    const startYear = String(start || '').slice(0, 4);
    const endYear = String(end || '').slice(0, 4);
    return startYear && startYear === endYear && startLabel !== endLabel
      ? `${startLabel.replace(` ${startYear}`, '')}–${endLabel}`
      : startLabel === endLabel ? startLabel : `${startLabel}–${endLabel}`;
  }

  _priorityPreviewStyle(feature) {
    if (feature.get('priority_class')) {
      const priorityColours = { critical: '#4c1d95', high: '#6d28d9', moderate: '#2563eb', watch: '#bfdbfe', insufficient_evidence: '#94a3b8' };
      const colour = priorityColours[feature.get('priority_class')] || priorityColours.insufficient_evidence;
      return new ol.style.Style({ fill: new ol.style.Fill({ color: `${colour}cc` }), stroke: new ol.style.Stroke({ color: '#7c2d12', width: 0.6 }) });
    }
    const colours = { very_low: '#7f1d1d', low: '#dc2626', watch: '#fb923c', no_signal: '#fef3c7', unavailable: '#94a3b8' };
    const state = feature.get('evidence_state');
    const colour = state === 'eligible_for_review' ? (colours[feature.get('rainfall_band')] || colours.unavailable) : colours.unavailable;
    return new ol.style.Style({ fill: new ol.style.Fill({ color: `${colour}${state === 'eligible_for_review' ? 'cc' : '66'}` }), stroke: new ol.style.Stroke({ color: '#7c2d12', width: 0.6 }) });
  }

  _priorityReplayCode(priorityClass) {
    return { critical: 'C1', high: 'C2', moderate: 'C3', watch: 'C4', insufficient_evidence: 'Evidence gap' }[priorityClass] || 'Unspecified';
  }

  _neutralReplayRule(rule) {
    return String(rule || '').replace(/^(critical|high|moderate|watch):/i, value => ({ critical: 'C1:', high: 'C2:', moderate: 'C3:', watch: 'C4:' }[value.slice(0, -1).toLowerCase()]));
  }

  _highlightPriorityFeature(feature) {
    if (!this.boundaryLayer || !feature) return;
    const highlight = feature.clone();
    highlight.setStyle(new ol.style.Style({
      stroke: new ol.style.Stroke({ color: '#facc15', width: 4 }),
      fill: new ol.style.Fill({ color: 'rgba(250, 204, 21, 0.20)' })
    }));
    this.boundaryLayer.getSource().clear();
    this.boundaryLayer.getSource().addFeature(highlight);
  }

  async _showPriorityPreviewMap() {
    const layer = this.priorityPreviewLayer;
    if (!layer || !this.priorityPreviewSnapshot) return;
    layer.getSource().clear();
    layer.setVisible(false);
    try {
      const baseUrl = this.priorityReplays.some(item => item.snapshot_id === this.priorityPreviewSnapshot) ? this.priorityReplaysUrl : this.priorityPreviewsUrl;
      const response = await fetch(`${baseUrl}/${encodeURIComponent(this.priorityPreviewSnapshot)}/features`, { cache: 'no-store' });
      const collection = await response.json();
      if (!response.ok || !Array.isArray(collection.features) || this.mode !== 'priority') throw new Error('preview unavailable');
      const features = new ol.format.GeoJSON().readFeatures(collection, { dataProjection: 'EPSG:4326', featureProjection: this.map.getView().getProjection() });
      layer.getSource().addFeatures(features);
      layer.setVisible(this.fewsNetDisplay !== 'fews');
      await this._showFewsNetContext();
    } catch (error) {
      console.error('[DroughtDashboard] Priority calibration preview unavailable:', error);
    }
  }

  async _showFewsNetContext() {
    const layer = this.fewsNetLayer;
    if (!layer) return;
    layer.getSource().clear();
    layer.setVisible(false);
    if (!this.fewsNetRunId || this.fewsNetDisplay === 'priority' || this.mode !== 'priority') return;
    try {
      const response = await fetch(`${this.fewsNetRunBaseUrl}/${encodeURIComponent(this.fewsNetRunId)}/features`, { cache: 'no-store' });
      const collection = await response.json();
      if (!response.ok || !Array.isArray(collection.features) || this.mode !== 'priority') throw new Error('provider context unavailable');
      const features = new ol.format.GeoJSON().readFeatures(collection, { dataProjection: 'EPSG:4326', featureProjection: this.map.getView().getProjection() });
      layer.getSource().addFeatures(features);
      layer.setVisible(true);
    } catch (error) { console.error('[DroughtDashboard] FEWS NET map unavailable:', error); }
  }

  _renderOutlookMap() {
    const artifact = this.outlookArtifact;
    if (!artifact || !artifact.available) {
      this.content.innerHTML = `<div class="drought-mode-title"><strong>Seasonal rainfall outlook</strong><span>No active provider release</span></div><div class="drought-period-stamp"><strong>Outlook unavailable</strong><span>${artifact ? artifact.reason : 'Loading outlook status.'}</span><small>No map is drawn until a reviewed provider-issued forecast with issue and validity dates is loaded.</small></div><div class="drought-map-instruction">The old illustrative Outlook fixture has been removed. This workspace will show only a provider-native forecast grid or a transparent Woreda contextual summary.</div>`;
      return;
    }
    const run = artifact.run;
    const lifecycle = run.lifecycle === 'active' ? 'ACTIVE' : 'UPCOMING';
    const releaseOptions = this.outlookRuns.map(candidate => {
      const label = `${candidate.valid_from} to ${candidate.valid_to} · ${candidate.lifecycle}`;
      return `<option value="${candidate.run_id}" ${candidate.run_id === run.run_id ? 'selected' : ''}>${label}</option>`;
    }).join('');
    this.content.innerHTML = `<div class="drought-mode-title"><strong>Seasonal rainfall outlook</strong><span>${run.source_product}</span></div><div class="drought-period-stamp"><strong>${lifecycle} · valid ${run.valid_from} to ${run.valid_to}</strong><span>Issued ${String(run.issued_at).slice(0, 10)} · Lead: ${run.lead_start_months}–${run.lead_end_months} months</span><small>Provider geography: ${run.geography_scope} · Native resolution: ${run.native_resolution}</small></div><div class="drought-history-controls"><label>Forecast release <select data-outlook-release>${releaseOptions}</select></label><small>Archived releases are for reference only and are never selected as the default outlook.</small></div><div class="drought-spatial-control"><span>Map display</span><div><button type="button" data-outlook-representation="native_grid" class="${this.outlookRepresentation === 'native_grid' ? 'is-active' : ''}">Native forecast grid</button><button type="button" data-outlook-representation="woreda_context" class="${this.outlookRepresentation === 'woreda_context' ? 'is-active' : ''}">Woreda context</button></div><small>Woreda context is a transparent summary of provider grid cells—not a Tabia prediction.</small></div><div class="drought-map-instruction">Colours indicate the most-likely seasonal rainfall category; opacity represents its probability. Click a feature to inspect all below-, near-, and above-normal probabilities.</div><div class="drought-map-selection" data-outlook-selection>Select a forecast feature on the map to inspect its probabilities.</div>`;
    this.content.querySelector('[data-outlook-release]').addEventListener('change', async event => {
      await this._loadOutlookArtifact(event.target.value);
      if (this.mode === 'outlook') this._renderMode();
    });
    this.content.querySelectorAll('[data-outlook-representation]').forEach(button => button.addEventListener('click', () => {
      this.outlookRepresentation = button.dataset.outlookRepresentation;
      this._renderMode();
    }));
  }

  _renderExposureMap() {
    if (this.exposureMeasure === 'population') {
      this.content.innerHTML = `<div class="drought-mode-title"><strong>Population baseline</strong><span>WorldPop 2025 · development</span></div><div class="drought-source-meta"><span>Scope: all 748 Tabias</span><span>Native source: ~100 m</span><span>Status: R2025A v1 alpha</span></div><div class="drought-spatial-control"><span>Display measure</span><div><button type="button" data-exposure-measure="population" class="is-active">People</button><button type="button" data-exposure-measure="cropland">Cropland</button><button type="button" data-exposure-measure="road">Road proximity</button></div><small>Population totals are modeled people-per-pixel estimates summarized to Tabias; they are not an official census or a drought-exposure count.</small></div><div class="drought-map-instruction">Every coloured Tabia has a validated WorldPop population total and coverage record. Click a Tabia with the normal map information tool to inspect its value.</div>`;
      this.content.querySelectorAll('[data-exposure-measure]').forEach(button => button.addEventListener('click', () => { this.exposureMeasure = button.dataset.exposureMeasure; this._renderMode(); }));
      return;
    }
    if (this.exposureMeasure === 'road') {
      this.content.innerHTML = `<div class="drought-mode-title"><strong>Federal and Regional road proximity</strong><span>ERA + TRRA · development</span></div><div class="drought-source-meta"><span>Scope: all 748 Tabias</span><span>Source: 65 mapped ERA/TRRA features</span><span>Method: point-to-nearest-network distance</span></div><div class="drought-spatial-control"><span>Display measure</span><div><button type="button" data-exposure-measure="population">People</button><button type="button" data-exposure-measure="cropland">Cropland</button><button type="button" data-exposure-measure="road" class="is-active">Road proximity</button></div><small>This is a transparent baseline, not a travel-time or humanitarian-access model.</small></div><div class="drought-map-instruction">Every Tabia is classified by straight-line distance from its representative point to the nearest mapped ERA or TRRA feature in Tigray Roads 2006. Click a Tabia with the normal map information tool to inspect its value.</div>`;
      this.content.querySelectorAll('[data-exposure-measure]').forEach(button => button.addEventListener('click', () => { this.exposureMeasure = button.dataset.exposureMeasure; this._renderMode(); }));
      return;
    }
    if (this.exposureMeasure === 'cropland') {
      this.content.innerHTML = `<div class="drought-mode-title"><strong>Cropland baseline</strong><span>ESA WorldCover 2021 · development</span></div><div class="drought-source-meta"><span>Scope: all 748 Tabias</span><span>Native source: 10 m</span><span>Class: cropland (40)</span></div><div class="drought-spatial-control"><span>Display measure</span><div><button type="button" data-exposure-measure="population">People</button><button type="button" data-exposure-measure="cropland" class="is-active">Cropland</button><button type="button" data-exposure-measure="road">Road proximity</button></div><small>This is a 2021 land-cover reference baseline, not a current crop or food-security measure.</small></div><div class="drought-map-instruction">Every coloured Tabia has a valid 2021 cropland-share and cropland-area summary. Click a Tabia with the normal map information tool to inspect its values.</div>`;
      this.content.querySelectorAll('[data-exposure-measure]').forEach(button => button.addEventListener('click', () => { this.exposureMeasure = button.dataset.exposureMeasure; this._renderMode(); }));
      return;
    }
    const source = this.data.sources.find(item => item.role === 'vulnerability');
    const count = new Set(this.data.areas.map(area => area.vulnerability.boundary.id)).size;
    this.content.innerHTML = `<div class="drought-mode-title"><strong>Tabia exposure map</strong><span>${source ? source.provider : 'Unknown source'}</span></div><div class="drought-source-meta"><span>Scope: Tabia reporting</span><span>Records mapped: ${count}</span><span>Updated: ${source ? source.updated : 'unknown'}</span></div><div class="drought-spatial-control"><span>Display measure</span><div><button type="button" data-exposure-measure="population" class="${this.exposureMeasure === 'population' ? 'is-active' : ''}">People</button><button type="button" data-exposure-measure="cropland" class="${this.exposureMeasure === 'cropland' ? 'is-active' : ''}">Cropland</button><button type="button" data-exposure-measure="road">Road proximity</button></div><small>Each measure is mapped separately; neither is a risk score.</small></div><div class="drought-map-instruction">Click a coloured Tabia for its available exposure record. Uncoloured Tabias have no record in this development fixture.</div><div class="drought-map-selection" data-fixture-selection>Select a coloured Tabia on the map to inspect its available exposure record.</div>`;
    this.content.querySelectorAll('[data-exposure-measure]').forEach(button => button.addEventListener('click', () => {
      this.exposureMeasure = button.dataset.exposureMeasure;
      this._renderMode();
    }));
  }

  _evidenceLayerForMode() {
    const layers = {
      observed: { tabia: 'tigray_drought_chirps_dev', raw: 'tigray_drought_chirps_raw_dev' },
      rapid: { tabia: 'tigray_drought_chirps_rapid_tabia_dev', raw: 'tigray_drought_chirps_rapid_raw_dev' },
      vegetation: { tabia: 'tigray_drought_ndvi_dev', raw: 'tigray_drought_ndvi_raw_dev' },
      soilWater: { tabia: 'tigray_drought_swi_dev', raw: 'tigray_drought_swi_raw_dev' },
      thermal: { tabia: 'tigray_drought_lst_dev', raw: 'tigray_drought_lst_raw_dev' },
      waterUse: { tabia: 'tigray_drought_wapor_dev', raw: 'tigray_drought_wapor_raw_dev' }
    };
    return layers[this.mode] && layers[this.mode][this.spatialViews[this.mode]];
  }

  _historyEvidenceLayer() {
    const modeByIndicator = { rainfall: 'observed', rapid: 'rapid', ndvi: 'vegetation', swi: 'soilWater', lst: 'thermal', wapor: 'waterUse' };
    const mode = modeByIndicator[this.historyIndicator] || 'vegetation';
    const layers = {
      observed: { tabia: 'tigray_drought_chirps_dev', raw: 'tigray_drought_chirps_raw_dev' },
      rapid: { tabia: 'tigray_drought_chirps_rapid_tabia_dev', raw: 'tigray_drought_chirps_rapid_raw_dev' },
      vegetation: { tabia: 'tigray_drought_ndvi_dev', raw: 'tigray_drought_ndvi_raw_dev' },
      soilWater: { tabia: 'tigray_drought_swi_dev', raw: 'tigray_drought_swi_raw_dev' },
      thermal: { tabia: 'tigray_drought_lst_dev', raw: 'tigray_drought_lst_raw_dev' },
      waterUse: { tabia: 'tigray_drought_wapor_dev', raw: 'tigray_drought_wapor_raw_dev' }
    };
    // History defaults to its latest Tabia-average context.  This keeps the
    // map interpretable while the chart remains a dated evidence timeline.
    return layers[mode].tabia;
  }

  _renderSpatialControl() {
    if (!this.spatialViews[this.mode]) return;
    const modeNames = { observed: 'Latest rainfall', rapid: 'Rapid rainfall', vegetation: 'Vegetation', soilWater: 'Soil water', thermal: 'Thermal context', waterUse: 'Agricultural water use' };
    const labels = this.mode === 'observed' ? { tabia: 'Tabia average', raw: 'Native rainfall grid' } : { tabia: 'Tabia average', raw: 'Native raster' };
    const control = document.createElement('div');
    control.className = 'drought-spatial-control';
    control.innerHTML = `<span>${modeNames[this.mode]} display</span><div><button type="button" data-spatial-view="raw" class="${this.spatialViews[this.mode] === 'raw' ? 'is-active' : ''}">${labels.raw}</button><button type="button" data-spatial-view="tabia" class="${this.spatialViews[this.mode] === 'tabia' ? 'is-active' : ''}">${labels.tabia}</button></div><small>${this.spatialViews[this.mode] === 'raw' ? 'Native source grid; no Tabia resampling.' : 'One zonal statistic or class per Tabia boundary.'}</small>`;
    control.querySelectorAll('[data-spatial-view]').forEach(button => button.addEventListener('click', () => {
      this.spatialViews[this.mode] = button.dataset.spatialView;
      this._renderMode();
    }));
    this.content.prepend(control);
  }

  _clearFixtureMap() {
    this.fixtureRenderToken += 1;
    if (this.fixtureLayer) this.fixtureLayer.getSource().clear();
  }

  _outlookStyle(value) {
    const colourByCategory = { 'Drier than normal': '#b45309', 'Near normal': '#64748b', 'Wetter than normal': '#2563eb' };
    const probability = Number(value.probability) || 0;
    const opacity = probability < 0.40 ? 0.32 : probability < 0.50 ? 0.48 : probability < 0.60 ? 0.65 : probability < 0.70 ? 0.80 : 0.92;
    return { colour: colourByCategory[value.category] || '#64748b', opacity };
  }

  _outlookCategory(properties) {
    const values = [
      ['Below normal', Number(properties.below_normal_probability)],
      ['Near normal', Number(properties.near_normal_probability)],
      ['Above normal', Number(properties.above_normal_probability)]
    ].filter(([, value]) => Number.isFinite(value));
    if (!values.length) return { category: 'Unavailable', probability: 0 };
    return values.reduce((highest, candidate) => candidate[1] > highest[1] ? candidate : highest)
      .reduce((category, probability) => ({ category, probability }));
  }

  _outlookFeatureStyle(feature) {
    const properties = feature.getProperties();
    const { category, probability } = this._outlookCategory(properties);
    const colour = { 'Below normal': '#b45309', 'Near normal': '#64748b', 'Above normal': '#2563eb' }[category] || '#94a3b8';
    const opacity = probability < 0.40 ? 0.32 : probability < 0.50 ? 0.48 : probability < 0.60 ? 0.65 : probability < 0.70 ? 0.80 : 0.92;
    return new ol.style.Style({
      fill: new ol.style.Fill({ color: `${colour}${Math.round(opacity * 255).toString(16).padStart(2, '0')}` }),
      stroke: new ol.style.Stroke({ color: '#334155', width: 0.8 })
    });
  }

  async _showOutlookMap() {
    const layer = this.outlookLayer;
    const artifact = this.outlookArtifact;
    if (!layer || !artifact || !artifact.available) return;
    layer.getSource().clear();
    layer.setVisible(false);
    try {
      const response = await fetch(`${this.outlookUrl}/runs/${encodeURIComponent(artifact.run.run_id)}/features?representation=${encodeURIComponent(this.outlookRepresentation)}`, { cache: 'no-store' });
      const collection = await response.json();
      if (!response.ok || !Array.isArray(collection.features)) throw new Error('outlook representation unavailable');
      if (this.mode !== 'outlook' || this.outlookArtifact.run.run_id !== artifact.run.run_id) return;
      const features = new ol.format.GeoJSON().readFeatures(collection, {
        dataProjection: 'EPSG:4326', featureProjection: this.map.getView().getProjection()
      });
      layer.getSource().addFeatures(features);
      layer.setVisible(true);
    } catch (error) {
      console.error('[DroughtDashboard] seasonal outlook map unavailable:', error);
      const target = this.content && this.content.querySelector('[data-outlook-selection]');
      if (target) target.textContent = this.outlookRepresentation === 'native_grid'
        ? 'The reviewed release has no retained native-grid map yet.'
        : 'The reviewed release has no retained Woreda contextual summary yet.';
    }
  }

  _exposureStyle(value) {
    const population = Number(value.population_exposed) || 0;
    const cropland = Number(value.cropland_exposed_pct) || 0;
    if (this.exposureMeasure === 'cropland') {
      const palette = ['#fff7bc', '#fee391', '#fec44f', '#fe9929', '#cc4c02'];
      const index = cropland < 20 ? 0 : cropland < 40 ? 1 : cropland < 60 ? 2 : cropland < 80 ? 3 : 4;
      return { colour: palette[index], opacity: 0.76 };
    }
    const palette = ['#eff3ff', '#bdd7e7', '#6baed6', '#3182bd', '#08519c'];
    const index = population < 10000 ? 0 : population < 25000 ? 1 : population < 50000 ? 2 : population < 100000 ? 3 : 4;
    return { colour: palette[index], opacity: 0.76 };
  }

  _fixtureStyle(feature) {
    const colour = feature.get('droughtColour') || '#94a3b8';
    const opacity = Number(feature.get('droughtOpacity')) || 0.5;
    return new ol.style.Style({
      fill: new ol.style.Fill({ color: `${colour}${Math.round(opacity * 255).toString(16).padStart(2, '0')}` }),
      stroke: new ol.style.Stroke({ color: '#334155', width: 1.4 })
    });
  }

  async _showFixtureMap(mode) {
    if (!this.fixtureLayer) return;
    const token = ++this.fixtureRenderToken;
    const source = this.fixtureLayer.getSource();
    source.clear();
    const fixtures = [];
    const seen = new Set();
    this.data.areas.forEach(area => {
      const value = area[mode];
      const boundary = value && value.boundary;
      if (!boundary || seen.has(boundary.id)) return;
      seen.add(boundary.id);
      fixtures.push({ area, value, boundary });
    });
    const records = await Promise.all(fixtures.map(async fixture => {
      try {
        const response = await fetch(`${this.boundaryUrl}/${fixture.boundary.type}/${fixture.boundary.id}`, { cache: 'no-store' });
        if (!response.ok) throw new Error(`boundary lookup returned ${response.status}`);
        return { ...fixture, boundaryRecord: await response.json() };
      } catch (error) {
        console.error('[DroughtDashboard] Fixture boundary unavailable:', error);
        return null;
      }
    }));
    if (token !== this.fixtureRenderToken || this.mode !== mode) return;
    records.filter(Boolean).forEach(record => {
      const feature = new ol.format.GeoJSON().readFeature(record.boundaryRecord.geometry, {
        dataProjection: 'EPSG:4326', featureProjection: this.map.getView().getProjection()
      });
      const style = mode === 'outlook' ? this._outlookStyle(record.value) : this._exposureStyle(record.value);
      feature.setProperties({
        droughtFixture: true, droughtMode: mode, droughtArea: record.area, droughtValue: record.value,
        droughtBoundary: record.boundary, droughtColour: style.colour, droughtOpacity: style.opacity
      });
      source.addFeature(feature);
    });
  }

  _handleFixtureMapClick(event) {
    const historicalObserved = this.mode === 'observed' && this.observedSnapshotId !== 'latest';
    if (this.mode === 'priority' && this.fewsNetDisplay === 'fews' && this.fewsNetLayer && this.fewsNetLayer.getVisible()) {
      const feature = this.map.forEachFeatureAtPixel(event.pixel, candidate => candidate, { layerFilter: layer => layer === this.fewsNetLayer });
      if (feature) this._showFewsNetFeatureContext(feature);
      return;
    }
    if (this.mode === 'priority' && this.priorityPreviewLayer && this.priorityPreviewLayer.getVisible()) {
      const feature = this.map.forEachFeatureAtPixel(event.pixel, candidate => candidate, { layerFilter: layer => layer === this.priorityPreviewLayer });
      const target = this.content && this.content.querySelector('[data-priority-preview-selection]');
      if (!feature || !target) return;
      this._highlightPriorityFeature(feature);
      const p = feature.getProperties();
      if (p.priority_class) {
        const rules = Array.isArray(p.triggered_rules) ? p.triggered_rules.map(rule => this._neutralReplayRule(rule)).join(' · ') : 'No rule explanation retained';
        const replayCode = this._priorityReplayCode(p.priority_class);
        target.innerHTML = `<strong>${p.tabia_name_en || 'Selected Tabia'}${p.woreda_name_en ? ` — ${p.woreda_name_en}` : ''}</strong><span>Retrospective replay flag: ${replayCode}</span><small>Stored local draft code: ${replayCode}. Local verification is required before considering any response; no operational action is recommended by this replay. Why: ${rules}. Rainfall ${p.rainfall_mm == null ? 'unavailable' : Number(p.rainfall_mm).toFixed(1)} mm against same-month median ${p.baseline_median_mm == null ? 'unavailable' : Number(p.baseline_median_mm).toFixed(1)} mm (CHIRPS 1991–2020 percentile ${p.rainfall_percentile == null ? 'unavailable' : Number(p.rainfall_percentile).toFixed(1)}); people decile ${p.population_decile || 'unavailable'}; cropland decile ${p.cropland_decile || 'unavailable'}; accessibility context ${p.accessibility_context || 'unavailable'}. Retrospective draft replay only—not a forecast, allocation, IPC phase, or food-security classification.</small>`;
        this._showFewsNetTabiaContext(p.tsird_tabia_id, {
          priorityClass: replayCode,
          tabiaName: p.tabia_name_en || 'Selected Tabia',
          woredaName: p.woreda_name_en || ''
        });
        return;
      }
      const eligible = p.evidence_state === 'eligible_for_review';
      target.innerHTML = `<strong>${p.tabia_name_en || 'Selected Tabia'}${p.woreda_name_en ? ` — ${p.woreda_name_en}` : ''}</strong><span>Rainfall band: ${String(p.rainfall_band || 'unavailable').replace('_', ' ')} · percentile: ${p.rainfall_percentile == null ? 'unavailable' : Number(p.rainfall_percentile).toFixed(1)}</span><small>Rainfall ${p.rainfall_mm == null ? 'unavailable' : Number(p.rainfall_mm).toFixed(1)} mm · same-month median ${p.baseline_median_mm == null ? 'unavailable' : Number(p.baseline_median_mm).toFixed(1)} mm · people decile ${p.population_decile || 'unavailable'} · cropland decile ${p.cropland_decile || 'unavailable'} · road context ${p.road_context || 'unavailable'} · ${eligible ? 'eligible for threshold review' : 'not eligible: insufficient rainfall coverage'}. This is not a priority score or forecast.</small>`;
      return;
    }
    if (this.mode === 'outlook' && this.outlookLayer && this.outlookLayer.getVisible()) {
      const feature = this.map.forEachFeatureAtPixel(event.pixel, candidate => candidate, {
        layerFilter: layer => layer === this.outlookLayer
      });
      const target = this.content && this.content.querySelector('[data-outlook-selection]');
      if (!feature || !target) return;
      const properties = feature.getProperties();
      const category = this._outlookCategory(properties);
      const asPercent = value => Number.isFinite(Number(value)) ? `${(Number(value) * 100).toFixed(0)}%` : 'not supplied';
      const label = properties.woreda_gid ? `Woreda context ${properties.woreda_gid}` : (properties.provider_area_id || 'Provider forecast cell');
      target.innerHTML = `<strong>${label}</strong><span>Most likely: ${category.category} (${(category.probability * 100).toFixed(0)}%)</span><small>Below normal ${asPercent(properties.below_normal_probability)} · Near normal ${asPercent(properties.near_normal_probability)} · Above normal ${asPercent(properties.above_normal_probability)}${Number.isFinite(Number(properties.coverage_pct)) ? ` · coverage ${Number(properties.coverage_pct).toFixed(0)}%` : ''}. Climate probability only—not a Tabia forecast or priority score.</small>`;
      return;
    }
    if (this.mode === 'history' && this.historyComparisonLayer && this.historyComparisonLayer.getVisible()) {
      const historicalFeature = this.map.forEachFeatureAtPixel(event.pixel, candidate => candidate, { layerFilter: layer => layer === this.historyComparisonLayer });
      if (historicalFeature && historicalFeature.get('tsird_tabia_id')) {
        this._handleBoundarySelection({ detail: { type: 'tabia', id: historicalFeature.get('tsird_tabia_id') } });
      }
      return;
    }
    if (!(['outlook', 'vulnerability'].includes(this.mode) || historicalObserved) || !this.fixtureLayer) return;
    const feature = this.map.forEachFeatureAtPixel(event.pixel, candidate => (candidate.get('droughtFixture') || candidate.get('droughtHistoricalObserved')) ? candidate : null, {
      layerFilter: layer => layer === this.fixtureLayer
    });
    if (!feature) return;
    if (historicalObserved) {
      const value = feature.getProperties();
      const target = this.content && this.content.querySelector('[data-historical-selection]');
      if (target) {
        const rainfall = Number(value.rainfall_mm);
        const baseline = Number(value.baseline_median_mm);
        const percentile = Number(value.percentile);
        target.innerHTML = `<strong>${value.tabia_name_en || 'Selected Tabia'} · ${value.woreda_name_en || ''}</strong><span>${Number.isFinite(rainfall) ? `${rainfall.toFixed(1)} mm` : 'No usable rainfall value'}${Number.isFinite(baseline) ? ` · baseline median ${baseline.toFixed(1)} mm` : ''}${Number.isFinite(percentile) ? ` · ${percentile.toFixed(1)}th percentile` : ''}</span><small>${value.quality_status === 'ok' ? `Coverage ${Number(value.coverage_pct).toFixed(0)}% · archived observation evidence only.` : 'Insufficient grid coverage; not classified.'}</small>`;
      }
      return;
    }
    const value = feature.get('droughtValue');
    const boundary = feature.get('droughtBoundary');
    const target = this.content && this.content.querySelector('[data-fixture-selection]');
    if (!target) return;
    if (this.mode === 'outlook') {
      target.innerHTML = `<strong>${boundary.label}</strong><span>${value.category}: ${(Number(value.probability) * 100).toFixed(0)}% probability, ${value.lead}.</span><small>Woreda-scale probability; not a Tabia prediction.</small>`;
    } else {
      target.innerHTML = `<strong>${boundary.label}</strong><span>${Number(value.population_exposed).toLocaleString()} people · ${value.cropland_exposed_pct}% cropland.</span><small>${value.access_note || 'No access assessment available.'}</small>`;
    }
  }

  async _showFewsNetTabiaContext(tabiaId, priorityContext) {
    const target = this.content && this.content.querySelector('[data-fews-net-selection]');
    if (!target || !tabiaId || !this.fewsNetRunId) return;
    target.textContent = 'Checking intersecting FEWS NET provider geography…';
    try {
      const response = await fetch(`${this.fewsNetRunBaseUrl}/${encodeURIComponent(this.fewsNetRunId)}/tabias/${encodeURIComponent(tabiaId)}`, { cache: 'no-store' });
      const payload = await response.json();
      if (!response.ok || !Array.isArray(payload.features)) throw new Error('provider comparison unavailable');
      const labels = payload.features.map(feature => {
        const props = typeof feature.properties === 'string' ? JSON.parse(feature.properties) : feature.properties || {};
        const classification = this._fewsNetClassification(props);
        const scenario = this._fewsNetScenario(props);
        const period = this._fewsNetPeriod(props);
        return { classification, scenario, period };
      });
      const tabiaName = payload.tabia.tabia_name_en || (priorityContext && priorityContext.tabiaName) || 'Selected Tabia';
      const woredaName = payload.tabia.woreda_name_en || (priorityContext && priorityContext.woredaName) || '';
      if (this.fewsNetDisplay === 'compare' && priorityContext) {
        const fewsCell = labels.length
          ? labels.map(item => `<div><strong>${item.classification.display}</strong><span>${item.scenario} · ${item.period}</span></div>`).join('')
          : '<div><strong>No intersecting provider area</strong><span>No FEWS NET context for this retained issue.</span></div>';
        target.innerHTML = `<strong>Side-by-side context · ${tabiaName}${woredaName ? ` — ${woredaName}` : ''}</strong><table class="drought-context-table"><thead><tr><th>TSIRD draft priority</th><th>FEWS NET context</th></tr></thead><tbody><tr><td><strong>${priorityContext.priorityClass}</strong><span>Retained local draft class</span></td><td>${fewsCell}</td></tr></tbody></table><small>Read these in parallel: they are not equivalent categories and no FEWS NET classification is transferred to this Tabia or used to alter its TSIRD class. ${payload.selection_note}</small>`;
        return;
      }
      target.innerHTML = `<strong>FEWS NET context · ${tabiaName}${woredaName ? ` — ${woredaName}` : ''}</strong><span>${labels.length ? `Intersecting provider area${labels.length === 1 ? '' : 's'}: ${labels.map(item => `${item.classification.display} · ${item.scenario} · ${item.period}`).join(' · ')}` : 'No intersecting provider area in this retained issue.'}</span><small>${payload.selection_note}</small>`;
    } catch (error) {
      console.error('[DroughtDashboard] FEWS NET Tabia comparison unavailable:', error);
      target.textContent = 'FEWS NET provider comparison is unavailable for this selection.';
    }
  }

  _showFewsNetFeatureContext(feature) {
    const target = this.content && this.content.querySelector('[data-fews-net-selection]');
    if (!target) return;
    const props = feature.getProperties();
    const classification = this._fewsNetClassification(props);
    const scenario = this._fewsNetScenario(props);
    const period = this._fewsNetPeriod(props);
    const reported = props.reporting_date || props.report_date || props.issued_at;
    target.innerHTML = `<strong>FEWS NET provider area</strong><span>Classification: ${classification.display} · ${scenario}</span><small>Assessment period: ${period}${reported ? ` · reported ${reported}` : ''}. This is FEWS NET’s native geography and classification, shown as external context; it is not a Tabia classification or a TSIRD priority.</small>`;
  }

  _renderLegend() {
    if (!this.legend) return;
    const swatch = (color, label, detail = '') => `<li><i class="drought-legend-swatch" style="--legend-colour:${color}"></i><span><strong>${label}</strong>${detail ? `<small>${detail}</small>` : ''}</span></li>`;
    const outlined = (label, detail) => `<li><i class="drought-legend-outline"></i><span><strong>${label}</strong><small>${detail}</small></span></li>`;
    const legendGroup = (title, detail, items) => `<section class="drought-legend-group"><h4>${title}<small>${detail}</small></h4><ul>${items.join('')}</ul></section>`;
    const rainfallBands = [
      swatch('#fee08b', 'Below 25 mm', 'lower preliminary total'),
      swatch('#a6d96a', '25–75 mm', 'preliminary total'),
      swatch('#66bd63', '75–150 mm', 'preliminary total'),
      swatch('#1a9850', 'At least 150 mm', 'higher preliminary total')
    ];
    const seasonalRainfallBands = [
      swatch('#fee08b', 'Below 100 mm', 'lower seasonal total'),
      swatch('#a6d96a', '100–200 mm', 'seasonal total'),
      swatch('#66bd63', '200–300 mm', 'seasonal total'),
      swatch('#1a9850', 'At least 300 mm', 'higher seasonal total')
    ];
    const fineBands = (prefix, thresholds, colors, unit, detail) => [
      swatch(colors[0], `${prefix} below ${thresholds[0]}${unit}`.trim(), detail),
      ...thresholds.slice(0, -1).map((threshold, index) => swatch(colors[index + 1], `${prefix} ${threshold}–${thresholds[index + 1]}${unit}`.trim(), detail)),
      swatch(colors[colors.length - 1], `${prefix} at least ${thresholds[thresholds.length - 1]}${unit}`.trim(), detail)
    ];
    const fineRainColors = ['#fff7bc', '#fee391', '#fec44f', '#fe9929', '#ec7014', '#cc4c02', '#993404', '#662506', '#471908', '#2d1208'];
    const fineNdviColors = ['#a50026', '#d73027', '#f46d43', '#fdae61', '#fee08b', '#d9ef8b', '#a6d96a', '#66bd63', '#1a9850', '#006837'];
    const fineSwiColors = ['#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#f7f7f7', '#d1e5f0', '#92c5de', '#4393c3', '#2166ac', '#053061'];
    const fineLstColors = ['#053061', '#2166ac', '#4393c3', '#92c5de', '#d1e5f0', '#fee08b', '#fdae61', '#f46d43', '#d6302b', '#a50026'];
    const fineSeasonalRainfallBands = fineBands('', [50, 100, 150, 200, 250, 300, 350, 400, 450], fineRainColors, ' mm', 'native seasonal total');
    const fineRapidRainfallBands = fineBands('', [50, 100, 150, 200, 250, 300, 350, 400, 450], fineRainColors, ' mm', 'native preliminary total');
    const fineNdviBands = fineBands('NDVI', [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90], fineNdviColors, '', 'native grid value');
    const fineSwiBands = fineBands('SWI-040', [10, 20, 30, 40, 50, 60, 70, 80, 90], fineSwiColors, '%', 'native grid value');
    const fineLstBands = fineBands('LST', [15, 20, 25, 30, 35, 40, 45, 50, 55], fineLstColors, ' °C', 'native grid value');
    const historyIndicatorBands = {
      rainfall: fineSeasonalRainfallBands.map(item => item.replace('native seasonal total', 'Tabia-average rainfall total')),
      rapid: fineRapidRainfallBands.map(item => item.replace('native preliminary total', 'Tabia-average rainfall total')),
      ndvi: fineBands('NDVI', [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90], fineNdviColors, '', 'Tabia-average value'),
      swi: fineBands('SWI-040', [10, 20, 30, 40, 50, 60, 70, 80, 90], fineSwiColors, '%', 'Tabia-average value'),
      lst: fineBands('LST', [15, 20, 25, 30, 35, 40, 45, 50, 55], fineLstColors, ' °C', 'Tabia-average value'),
      wapor: fineBands('T', [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 5], fineRainColors, ' mm/day', 'Tabia-average magnitude')
    };
    const priorityReplayItems = this.priorityReplays && this.priorityReplays.length ? [
      swatch('#4c1d95', 'Replay flag C1', 'stored local draft code'),
      swatch('#6d28d9', 'Replay flag C2', 'stored local draft code'),
      swatch('#2563eb', 'Replay flag C3', 'stored local draft code'),
      swatch('#bfdbfe', 'Replay flag C4', 'stored local draft code'),
      swatch('#94a3b8', 'Insufficient evidence', 'do not rank; resolve the evidence gap')
    ] : [
      swatch('#7f1d1d', 'Very low rainfall', 'same-month CHIRPS percentile ≤10'),
      swatch('#dc2626', 'Low rainfall', 'percentile >10–20'),
      swatch('#fb923c', 'Watch rainfall', 'percentile >20–33'),
      swatch('#fef3c7', 'No rainfall signal', 'percentile >33'),
      swatch('#94a3b8', 'Not eligible', 'insufficient coverage or unavailable')
    ];
    const fewsNetItems = [
      swatch('#64748b', 'Minimal', 'FEWS NET classification'),
      swatch('#facc15', 'Stressed', 'FEWS NET classification'),
      swatch('#f97316', 'Crisis', 'FEWS NET classification'),
      swatch('#dc2626', 'Emergency', 'FEWS NET classification'),
      swatch('#7f1d1d', 'Catastrophe', 'FEWS NET classification'),
      outlined('Other FEWS NET feature', 'no mapped classification code')
    ];
    const definitions = {
      observed: {
        title: this.observedSnapshotId === 'latest' ? 'Map legend · latest rainfall total' : 'Map legend · historical rainfall evidence',
        note: this.observedSnapshotId !== 'latest'
          ? 'Archived CHIRPS Tabia zonal means for the selected observation period. The ten bands preserve total magnitude; this is not a reconstructed native raster, a forecast, or a decision-product backtest.'
          : this.spatialViews.observed === 'raw'
          ? 'CHIRPS monthly rainfall summed over the selected season. Ten fixed total bands preserve the native 0.05° grid; they distinguish rainfall totals, not drought priority.'
          : 'CHIRPS zonal mean seasonal rainfall. It uses exactly the same ten millimetre bands and colours as the native 0.05° grid; baseline percentile remains available in Tabia details.',
        items: fineSeasonalRainfallBands
      },
      rapid: {
        title: 'Legend · rapid rainfall monitoring',
        note: `Six completed preliminary CHIRPS pentads summed in millimetres. ${this.spatialViews.rapid === 'raw' ? 'Ten fixed total bands preserve the native 0.05° grid.' : 'The Tabia zonal mean uses exactly the same ten total bands and colours.'} These are not drought or food-security classes.`,
        items: fineRapidRainfallBands
      },
      vegetation: {
        title: 'Map legend · vegetation condition',
        note: this.spatialViews.vegetation === 'raw' ? 'Ten fixed NDVI bands preserve the retained 300 m grid. They indicate greenness values, not drought severity or priority.' : 'Copernicus NDVI v3 mean, zonally summarized from the retained 300 m raster. It uses the same ten fixed NDVI bands and colours as the native grid.',
        items: fineNdviBands
      },
      soilWater: {
        title: 'Map legend · soil-water context',
        note: this.spatialViews.soilWater === 'raw' ? 'Ten fixed SWI-040 bands preserve the roughly 12.5 km grid. They indicate index values, not drought priority.' : 'Copernicus SWI-040 mean, zonally summarized from a roughly 12.5 km grid. It uses the same ten SWI-040 bands and colours as the native grid, but remains coarse context.',
        items: fineSwiBands
      },
      thermal: {
        title: 'Map legend · thermal context',
        note: this.spatialViews.thermal === 'raw' ? 'Ten fixed land-surface-temperature bands preserve the approximately 5 km grid. They are not air temperature or a drought-priority scale.' : 'Copernicus land-surface-temperature mean, summarized from an approximately 5 km raster. It uses the same ten temperature bands and colours as the native grid; it is not air temperature or a drought class.',
        items: fineLstBands
      },
      waterUse: {
        title: 'Map legend · agricultural water use',
        note: this.spatialViews.waterUse === 'raw' ? 'FAO WaPOR v3 Level 2 dekadal transpiration, retained at its approximately 100 m native grid. The composite is expressed as a daily mean (mm/day). Ten fixed magnitude bands do not represent crop yield, drought severity, food insecurity, or priority.' : 'FAO WaPOR v3 Level 2 dekadal transpiration daily mean, summarized per Tabia from the approximately 100 m retained raster. It uses the same ten fixed mm/day bands as the native grid. AETI is available as supporting detail and includes evaporation/interception.',
        items: fineBands('T', [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 5], fineRainColors, ' mm/day', 'vegetation water-use magnitude')
      },
      history: {
        title: this.historyCompareSnapshot !== 'off' ? 'Map legend · measured change between snapshots' : 'Map legend · history map context',
        note: this.historyCompareSnapshot !== 'off'
          ? 'Green means a higher value in the selected snapshot than the comparison date; red means lower. This is a measured indicator difference, not a drought-priority score.'
          : 'The map uses the selected retained Tabia-average snapshot. The chart contains only actual source timestamps and does not interpolate missing periods.',
        items: this.historyCompareSnapshot !== 'off'
          ? [swatch('#b91c1c', 'Lower than comparison', 'larger negative change'), swatch('#fca5a5', 'Slightly lower', 'small negative change'), swatch('#f8fafc', 'Little change', 'near zero'), swatch('#86efac', 'Slightly higher', 'small positive change'), swatch('#15803d', 'Higher than comparison', 'larger positive change')]
          : historyIndicatorBands[this.historyIndicator]
      },
      outlook: {
        title: 'Legend · seasonal outlook',
        note: this.outlookArtifact && this.outlookArtifact.available
          ? 'Colour is the provider’s most-likely rainfall category; opacity is its stated probability. Native grid is the source-faithful display; Woreda context is not a Tabia prediction.'
          : 'No active or upcoming reviewed provider release is loaded. No seasonal outlook map is drawn.',
        items: [
          swatch('#b45309', 'Drier than normal', 'most-likely category'),
          swatch('#64748b', 'Near normal', 'most-likely category'),
          swatch('#2563eb', 'Wetter than normal', 'most-likely category'),
          swatch('#94a3b8', 'Probability strength', '33–39 weak · 40–49 modest · 50–59 elevated · 60–69 strong · ≥70 very strong'),
          swatch('#ffffff', 'No record', 'no provider forecast data')
        ]
      },
      priority: {
        title: this.fewsNetDisplay === 'fews' ? 'Legend · FEWS NET provider context' : this.fewsNetDisplay === 'compare' ? 'Legend · priority replay and FEWS NET context' : 'Legend · retrospective review replay',
        note: this.fewsNetDisplay === 'fews'
          ? 'Provider-issued native Food Security Classification geography. Each area can be clicked to see its classification, scenario, and validity period. These are not TSIRD classes, Tabia classifications, or priority inputs.'
          : this.fewsNetDisplay === 'compare'
          ? 'TSIRD uses blue–purple retrospective replay flags; FEWS NET is shown as dashed provider boundaries only in Compare mode, so the two palettes do not blend. The layers are deliberately non-equivalent: no FEWS NET classification changes a TSIRD replay flag.'
          : this.priorityReplays && this.priorityReplays.length
          ? 'Blue–purple replay flags are draft retrospective plausibility evidence from retained rainfall plus static exposure. They are not a forecast, operational priority, or published decision.'
          : 'The map shows draft retrospective rainfall-percentile calibration bands, not priority classes. A combined priority score remains unavailable pending calibrated core evidence, an approved outlook, and review.',
        items: priorityReplayItems,
        groups: this.fewsNetDisplay === 'fews'
          ? [legendGroup('FEWS NET classification', 'provider-native areas', fewsNetItems)]
          : this.fewsNetDisplay === 'compare'
          ? [legendGroup('TSIRD retained evidence replay', 'solid filled Tabias', priorityReplayItems), legendGroup('FEWS NET classification context', 'dashed provider boundaries only; no fill', fewsNetItems)]
          : [legendGroup('TSIRD retained evidence replay', 'solid filled Tabias', priorityReplayItems)]
      },
      vulnerability: {
        title: 'Legend · vulnerability / exposure',
        note: this.exposureMeasure === 'population'
          ? 'WorldPop 2025 constrained population estimates at about 100 m, summarized to Tabias. The ten decile bands are local distribution bands, not a priority scale, an official census, or a count of people currently exposed to drought.'
          : this.exposureMeasure === 'road'
          ? 'Straight-line distance from a Tabia representative point to the nearest mapped ERA or TRRA feature in Tigray Roads 2006. Distance bands describe this local dataset distribution; they are not priority, travel-time, road-condition, seasonal-passability, or humanitarian-access classes.'
          : 'ESA WorldCover 2021 cropland class at 10 m, summarized to Tabias. The ten decile bands are local distribution bands, not current cultivation, crop production, food insecurity, or a priority scale.',
        items: this.exposureMeasure === 'population' ? [
          swatch('#f7fbff', 'Below 4,015 people', 'WorldPop modeled total per Tabia'),
          swatch('#deebf7', '4,015–5,257 people', 'WorldPop modeled total per Tabia'),
          swatch('#c6dbef', '5,257–6,093 people', 'WorldPop modeled total per Tabia'),
          swatch('#9ecae1', '6,093–6,964 people', 'WorldPop modeled total per Tabia'),
          swatch('#6baed6', '6,964–7,955 people', 'WorldPop modeled total per Tabia'),
          swatch('#4292c6', '7,955–9,114 people', 'WorldPop modeled total per Tabia'),
          swatch('#2171b5', '9,114–10,753 people', 'WorldPop modeled total per Tabia'),
          swatch('#08519c', '10,753–13,253 people', 'WorldPop modeled total per Tabia'),
          swatch('#08306b', '13,253–18,451 people', 'WorldPop modeled total per Tabia'),
          swatch('#041f4a', '18,451 people or more', 'WorldPop modeled total per Tabia'),
          swatch('#ffffff', 'No record', 'uncoloured Tabia; unavailable or insufficient coverage')
        ] : this.exposureMeasure === 'road' ? [
          swatch('#1a9850', 'Within 0.9 km', 'nearest ERA/TRRA feature'), swatch('#a6d96a', '0.9–2.7 km', 'nearest ERA/TRRA feature'),
          swatch('#fee08b', '2.7–5.5 km', 'nearest ERA/TRRA feature'), swatch('#fc8d59', '5.5–10 km', 'nearest ERA/TRRA feature'),
          swatch('#d73027', '10 km or farther', 'nearest ERA/TRRA feature')
        ] : [
          swatch('#ffffe5', 'Below 7.9% cropland', 'WorldCover 2021 class 40 share'), swatch('#fff7bc', '7.9–15.5% cropland', 'WorldCover 2021 class 40 share'),
          swatch('#fee391', '15.5–21.9% cropland', 'WorldCover 2021 class 40 share'), swatch('#fec44f', '21.9–27.5% cropland', 'WorldCover 2021 class 40 share'),
          swatch('#fe9929', '27.5–32.8% cropland', 'WorldCover 2021 class 40 share'), swatch('#ec7014', '32.8–38.6% cropland', 'WorldCover 2021 class 40 share'),
          swatch('#cc4c02', '38.6–45.1% cropland', 'WorldCover 2021 class 40 share'), swatch('#993404', '45.1–52.8% cropland', 'WorldCover 2021 class 40 share'),
          swatch('#662506', '52.8–63.5% cropland', 'WorldCover 2021 class 40 share'), swatch('#451908', '63.5% cropland or more', 'WorldCover 2021 class 40 share'),
          swatch('#ffffff', 'No record', 'uncoloured Tabia; unavailable or insufficient coverage')
        ]
      }
    };
    const legend = definitions[this.mode] || definitions.observed;
    const legendBody = legend.groups ? legend.groups.join('') : `<ul>${legend.items.join('')}</ul>`;
    this.legend.innerHTML = `<div class="drought-legend-heading"><strong>${legend.title}</strong><span>source-specific</span></div>${legendBody}<p>${legend.note}</p>`;
  }

  _renderPreliminaryArtifact() {
    const artifact = this.preliminaryArtifact;
    if (!artifact || artifact.unavailable) {
      this.content.innerHTML = `<div class="drought-mode-title"><strong>Rapid rainfall</strong><span>Unavailable</span></div><p class="drought-empty">${artifact ? artifact.message : 'Loading artifact.'}</p>`;
      return;
    }
    const run = artifact.run;
    const usable = artifact.summaries.filter(item => item.quality_status === 'ok');
    const comparable = usable.filter(item => item.provisional_percentile !== null && item.provisional_percentile !== undefined);
    const rainfall = usable.map(item => Number(item.rainfall_mm)).filter(Number.isFinite);
    const range = rainfall.length ? `${Math.min(...rainfall).toFixed(1)}–${Math.max(...rainfall).toFixed(1)} mm` : 'no usable totals';
    const baselineState = comparable.length
      ? `${comparable.length} provisional final-history comparisons available`
      : 'Historical comparison is building locally';
    this.content.innerHTML = `<div class="drought-mode-title"><strong>Rapid observed rainfall</strong><span>CHIRPS preliminary · development</span></div><div class="drought-source-meta"><span>Period: ${run.period_start} to ${run.period_end}</span><span>${run.pentad_count} completed pentads</span><span>Usable: ${usable.length}/${artifact.summaries.length}</span><span>Tabia total range: ${range}</span></div><div class="drought-map-instruction">${baselineState}. Select Native raster to see the retained 0.05° preliminary-grid total, or Tabia average for its zonal mean. Preliminary and final source maturity remain distinct.</div>`;
  }

  _renderNdviArtifact() {
    const artifact = this.ndviArtifact;
    if (!artifact || artifact.unavailable) { this.content.innerHTML = `<p class="drought-empty">${artifact ? artifact.message : 'Loading artifact.'}</p>`; return; }
    const run = artifact.run, usable = artifact.summaries.filter(item => item.quality_status === 'ok' && Number.isFinite(Number(item.ndvi_mean)));
    const values = usable.map(item => Number(item.ndvi_mean)); const range = values.length ? `${Math.min(...values).toFixed(3)}–${Math.max(...values).toFixed(3)}` : 'no usable values';
    this.content.innerHTML = `<div class="drought-mode-title"><strong>Vegetation condition</strong><span>Copernicus NDVI v3 · ${run.status}</span></div><div class="drought-source-meta"><span>Native resolution: ${run.native_resolution}</span><span>Observation: ${run.observation_start}</span><span>Usable: ${usable.length}/${artifact.summaries.length}</span><span>NDVI mean range: ${range}</span></div><div class="drought-map-instruction">${run.status === 'degraded' ? 'Degraded freshness — do not treat as current. ' : ''}Use Native raster for the retained 300 m grid; Tabia average is its zonal summary.</div>`;
  }

  _renderSwiArtifact() {
    const artifact = this.swiArtifact;
    if (!artifact || artifact.unavailable) { this.content.innerHTML = `<p class="drought-empty">${artifact ? artifact.message : 'Loading artifact.'}</p>`; return; }
    const run = artifact.run, usable = artifact.summaries.filter(item => item.quality_status === 'ok' && Number.isFinite(Number(item.swi040_mean)));
    const values = usable.map(item => Number(item.swi040_mean)); const range = values.length ? `${Math.min(...values).toFixed(1)}–${Math.max(...values).toFixed(1)}%` : 'no usable values';
    this.content.innerHTML = `<div class="drought-mode-title"><strong>Soil-water context</strong><span>Copernicus SWI v4 · ${run.status}</span></div><div class="drought-source-meta"><span>Native resolution: ${run.native_resolution}</span><span>Observation: ${run.observation_start}</span><span>Usable: ${usable.length}/${artifact.summaries.length}</span><span>SWI-040 mean range: ${range}</span></div><div class="drought-map-instruction">${run.status === 'degraded' ? 'Degraded freshness — do not treat as current. ' : ''}Use Native raster for the retained ~12.5 km grid; Tabia average is a zonal summary and adds no spatial precision.</div>`;
  }

  _renderLstArtifact() {
    const artifact = this.lstArtifact;
    if (!artifact || artifact.unavailable) { this.content.innerHTML = `<p class="drought-empty">${artifact ? artifact.message : 'Loading artifact.'}</p>`; return; }
    const run = artifact.run, usable = artifact.summaries.filter(item => item.quality_status === 'ok' && Number.isFinite(Number(item.lst_c_mean)));
    const values = usable.map(item => Number(item.lst_c_mean)); const range = values.length ? `${Math.min(...values).toFixed(1)}–${Math.max(...values).toFixed(1)}°C` : 'no usable values';
    this.content.innerHTML = `<div class="drought-mode-title"><strong>Thermal context</strong><span>Copernicus LST v2 · ${run.status}</span></div><div class="drought-source-meta"><span>Native resolution: ${run.native_resolution}</span><span>Observation: ${run.observation_start}</span><span>Usable: ${usable.length}/${artifact.summaries.length}</span><span>LST mean range: ${range}</span></div><div class="drought-map-instruction">${run.status === 'degraded' ? 'Degraded freshness — do not treat as current. ' : ''}Use Native raster for the retained ~5 km grid; Tabia average is a zonal summary. Neither is an air-temperature observation.</div>`;
  }

  _renderWaporArtifact() {
    const artifact = this.waporArtifact;
    if (!artifact || artifact.unavailable) { this.content.innerHTML = `<p class="drought-empty">${artifact ? artifact.message : 'Loading artifact.'}</p>`; return; }
    const run = artifact.run, usable = artifact.summaries.filter(item => item.quality_status === 'ok' && Number.isFinite(Number(item.transpiration_mm)));
    const transpiration = usable.map(item => Number(item.transpiration_mm));
    const aeti = usable.map(item => Number(item.aeti_mm)).filter(Number.isFinite);
    const tRange = transpiration.length ? `${Math.min(...transpiration).toFixed(1)}–${Math.max(...transpiration).toFixed(1)} mm/day` : 'no usable values';
    const aetiRange = aeti.length ? `${Math.min(...aeti).toFixed(1)}–${Math.max(...aeti).toFixed(1)} mm/day` : 'no usable values';
    this.content.innerHTML = `<div class="drought-mode-title"><strong>Current agricultural water use</strong><span>FAO WaPOR v3 · ${run.status}</span></div><div class="drought-source-meta"><span>Native resolution: ${run.native_resolution}</span><span>Period: ${run.source_period_start} to ${run.source_period_end}</span><span>Unit: daily mean within dekadal composite</span><span>Usable: ${usable.length}/${artifact.summaries.length}</span><span>T mean range: ${tRange}</span><span>AETI range: ${aetiRange}</span></div><div class="drought-map-instruction">${run.status === 'degraded' ? 'Degraded freshness — do not treat as current. ' : ''}Transpiration is vegetation water-use context. Use Native raster for the retained provider grid; Tabia average is a zonal summary. AETI includes evaporation and interception, and neither measure identifies current crop extent or yield.</div>`;
  }

  _historyArtifact(indicator) {
    return { rainfall: this.observedArtifact, rapid: this.preliminaryArtifact, ndvi: this.ndviArtifact, swi: this.swiArtifact, lst: this.lstArtifact, wapor: this.waporArtifact }[indicator];
  }

  _renderHistory() {
    const selected = this.historyTabiaId
      ? `<div class="drought-history-selection"><strong>${this.historyTabiaLabel || 'Selected Tabia'}</strong><span>Selected from the map or Search</span></div>`
      : '<div class="drought-map-instruction">Select a Tabia boundary on the map or use Search to view this indicator’s retained Tabia zonal-mean history.</div>';
    const runs = this.historyRuns[this.historyIndicator] || [];
    const snapshotOptions = runs.map(run => `<option value="${run.run_id}" ${this.historyMapSnapshot === run.run_id ? 'selected' : ''}>${String(run.observation_start).slice(0, 10)}</option>`).join('');
    const compareOptions = runs.filter(run => run.run_id !== this.historyMapSnapshot).map(run => `<option value="${run.run_id}" ${this.historyCompareSnapshot === run.run_id ? 'selected' : ''}>${String(run.observation_start).slice(0, 10)}</option>`).join('');
    const relativeAvailable = ['rainfall', 'ndvi', 'wapor'].includes(this.historyIndicator);
    const referenceExplanation = this.historyIndicator === 'rainfall'
      ? 'Relative to normal compares each monthly total with that Tabia’s CHIRPS 1991–2020 median for the same calendar month. '
      : ['ndvi', 'wapor'].includes(this.historyIndicator)
        ? 'Relative to reference compares the observed value with the candidate 2018–2025 same-calendar-month reference when enough quality-approved years are retained. Historical candidate years exclude themselves from their seven-year comparison. '
        : 'A like-for-like seasonal baseline is not yet loaded for this indicator; the chart intentionally retains observed values only. ';
    this.content.innerHTML = `<div class="drought-mode-title"><strong>Evidence history</strong><span>retained observations only</span></div><div class="drought-history-controls"><label>Indicator <select data-history-indicator><option value="rainfall" ${this.historyIndicator === 'rainfall' ? 'selected' : ''}>Final rainfall (CHIRPS)</option><option value="rapid" ${this.historyIndicator === 'rapid' ? 'selected' : ''}>Rapid rain (CHIRPS preliminary)</option><option value="ndvi" ${this.historyIndicator === 'ndvi' ? 'selected' : ''}>Vegetation (NDVI)</option><option value="swi" ${this.historyIndicator === 'swi' ? 'selected' : ''}>Soil water (SWI-040)</option><option value="lst" ${this.historyIndicator === 'lst' ? 'selected' : ''}>Thermal (LST)</option><option value="wapor" ${this.historyIndicator === 'wapor' ? 'selected' : ''}>Crop water use (WaPOR T)</option></select></label><label>Chart view <select data-history-display><option value="value" ${this.historyDisplay === 'value' ? 'selected' : ''}>Observed value</option><option value="relative" ${this.historyDisplay === 'relative' ? 'selected' : ''} ${relativeAvailable ? '' : 'disabled'}>Relative to reference</option></select></label><label>Map snapshot <select data-history-snapshot><option value="latest" ${this.historyMapSnapshot === 'latest' ? 'selected' : ''}>Latest retained</option>${snapshotOptions}</select></label><label>Compare with <select data-history-compare><option value="off" ${this.historyCompareSnapshot === 'off' ? 'selected' : ''}>Off</option>${compareOptions}</select></label><small>${referenceExplanation}Choose a dated Tabia-average snapshot, or compare two dates as a measured change map. Candidate-reference runs are shown as Tabia summaries; they are not a raster publication, forecast, or priority output.</small></div>${selected}<div class="drought-history-result">${this.historyTabiaId ? 'Loading retained observations…' : ''}</div>`;
    this.content.querySelector('[data-history-indicator]').addEventListener('change', event => {
      this.historyIndicator = event.target.value;
      this.historyDisplay = 'value';
      this.historyMapSnapshot = 'latest';
      this.historyCompareSnapshot = 'off';
      this._renderMode();
    });
    this.content.querySelector('[data-history-display]').addEventListener('change', event => {
      this.historyDisplay = event.target.value;
      if (this.historyTabiaId) this._loadHistory();
    });
    this.content.querySelector('[data-history-snapshot]').addEventListener('change', event => {
      this.historyMapSnapshot = event.target.value;
      if (this.historyCompareSnapshot === this.historyMapSnapshot) this.historyCompareSnapshot = 'off';
      this._renderMode();
    });
    this.content.querySelector('[data-history-compare]').addEventListener('change', event => {
      this.historyCompareSnapshot = event.target.value;
      this._renderMode();
    });
    if (this.historyTabiaId) this._loadHistory();
  }

  _historyMapStyle(feature) {
    const quality = feature.get('quality_status');
    const delta = feature.get('historyDelta');
    let colour = '#94a3b8';
    if (Number.isFinite(Number(delta))) {
      const magnitude = Math.abs(Number(delta));
      const thresholds = feature.get('historyReference') ? [10, 30] : {
        rainfall: [25, 75],
        rapid: [25, 75],
        ndvi: [0.03, 0.10],
        swi: [5, 15],
        lst: [1, 3],
        wapor: [0.25, 0.75]
      }[this.historyIndicator] || [0.1, 0.3];
      colour = magnitude < thresholds[0] ? '#f8fafc' : Number(delta) < 0 ? (magnitude < thresholds[1] ? '#fca5a5' : '#b91c1c') : (magnitude < thresholds[1] ? '#86efac' : '#15803d');
    } else if (quality === 'ok' && Number.isFinite(Number(feature.get('value')))) {
      const value = Number(feature.get('value'));
      const config = {
        rainfall: [[50, '#fff7bc'], [100, '#fee391'], [150, '#fec44f'], [200, '#fe9929'], [250, '#ec7014'], [300, '#cc4c02'], [350, '#993404'], [400, '#662506'], [450, '#471908'], [Infinity, '#2d1208']],
        rapid: [[50, '#fff7bc'], [100, '#fee391'], [150, '#fec44f'], [200, '#fe9929'], [250, '#ec7014'], [300, '#cc4c02'], [350, '#993404'], [400, '#662506'], [450, '#471908'], [Infinity, '#2d1208']],
        ndvi: [[0.1, '#a50026'], [0.2, '#d73027'], [0.3, '#f46d43'], [0.4, '#fdae61'], [0.5, '#fee08b'], [0.6, '#d9ef8b'], [0.7, '#a6d96a'], [0.8, '#66bd63'], [0.9, '#1a9850'], [Infinity, '#006837']],
        swi: [[10, '#b2182b'], [20, '#d6604d'], [30, '#f4a582'], [40, '#fddbc7'], [50, '#f7f7f7'], [60, '#d1e5f0'], [70, '#92c5de'], [80, '#4393c3'], [90, '#2166ac'], [Infinity, '#053061']],
        lst: [[15, '#053061'], [20, '#2166ac'], [25, '#4393c3'], [30, '#92c5de'], [35, '#d1e5f0'], [40, '#fee08b'], [45, '#fdae61'], [50, '#f46d43'], [55, '#d6302b'], [Infinity, '#a50026']],
        wapor: [[0.5, '#ffffe5'], [1, '#fff7bc'], [1.5, '#fee391'], [2, '#fec44f'], [2.5, '#fe9929'], [3, '#ec7014'], [3.5, '#cc4c02'], [4, '#993404'], [5, '#662506'], [Infinity, '#3f1b00']]
      }[this.historyIndicator];
      colour = config.find(item => value < item[0])[1];
    }
    return new ol.style.Style({ fill: new ol.style.Fill({ color: quality === 'ok' ? `${colour}cc` : '#94a3b855' }), stroke: new ol.style.Stroke({ color: '#475569', width: 0.7 }) });
  }

  async _renderHistoryMap() {
    const layer = this.historyComparisonLayer;
    if (!layer) return;
    const token = ++this.historyMapToken;
    const runs = this.historyRuns[this.historyIndicator] || [];
    const primary = this.historyMapSnapshot === 'latest' ? runs[0] : runs.find(run => run.run_id === this.historyMapSnapshot);
    const comparison = this.historyCompareSnapshot === 'off' ? null : runs.find(run => run.run_id === this.historyCompareSnapshot);
    if (!primary) {
      layer.setVisible(false); layer.getSource().clear();
      return;
    }
    try {
      const fetchFeatures = async run => {
        const response = await fetch(`${this.evidenceBaseUrl}/${this.historyIndicator}/runs/${encodeURIComponent(run.run_id)}/features`, { cache: 'no-store' });
        if (!response.ok) throw new Error(`snapshot returned ${response.status}`);
        return response.json();
      };
      const [primaryData, comparisonData] = await Promise.all([fetchFeatures(primary), comparison ? fetchFeatures(comparison) : Promise.resolve(null)]);
      if (token !== this.historyMapToken || this.mode !== 'history') return;
      const comparisonValues = new Map((comparisonData ? comparisonData.features : []).map(feature => [feature.properties.tsird_tabia_id, Number(feature.properties.value)]));
      const features = new ol.format.GeoJSON().readFeatures(primaryData, { dataProjection: 'EPSG:4326', featureProjection: this.map.getView().getProjection() });
      features.forEach(feature => {
        const referenceDeviation = Number(feature.get('reference_deviation_pct'));
        if (this.historyDisplay === 'relative' && ['ndvi', 'wapor'].includes(this.historyIndicator) && Number.isFinite(referenceDeviation)) {
          feature.setProperties({ historyDelta: referenceDeviation, historyReference: true });
        } else if (comparison) {
          feature.set('historyDelta', Number(feature.get('value')) - comparisonValues.get(feature.get('tsird_tabia_id')));
        }
      });
      layer.getSource().clear(); layer.getSource().addFeatures(features); layer.setVisible(true);
      this._setEvidenceLayer(null);
    } catch (error) {
      console.error('[DroughtDashboard] historical map comparison unavailable:', error);
      if (token === this.historyMapToken) { layer.setVisible(false); layer.getSource().clear(); }
    }
  }

  _handleBoundarySelection(event) {
    const selection = event && event.detail;
    if (!selection || selection.type !== 'tabia' || !selection.id) return;
    this.historyTabiaId = selection.id;
    this.historyTabiaLabel = [selection.name_en, selection.parent_name_en].filter(Boolean).join(' — ') || 'Selected Tabia';
    if (this.mode === 'history') {
      this._renderHistory();
      this._highlightHistoryTabia(selection);
    }
  }

  async _highlightHistoryTabia(selection) {
    try {
      const response = await fetch(`${this.boundaryUrl}/tabia/${encodeURIComponent(selection.id)}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`boundary lookup returned ${response.status}`);
      if (this.mode === 'history' && this.historyTabiaId === selection.id) this._showBoundary(await response.json(), 'tabia', { fit: false });
    } catch (error) {
      console.error('[DroughtDashboard] History boundary highlight failed:', error);
    }
  }

  async _loadHistory() {
    const target = this.content.querySelector('.drought-history-result');
    try {
      const response = await fetch(`${this.historyUrl}/${this.historyIndicator}/${encodeURIComponent(this.historyTabiaId)}`, { cache: 'no-store' });
      const history = await response.json();
      if (!response.ok || !Array.isArray(history.points)) throw new Error('invalid evidence history');
      const relativeToNormal = this.historyDisplay === 'relative' && ['rainfall', 'ndvi', 'wapor'].includes(this.historyIndicator);
      const rawValues = history.points.map(point => Number(point.value)).filter(Number.isFinite);
      const values = relativeToNormal
        ? history.points.map(point => Number(point.expected_median) > 0 ? (100 * (Number(point.value) - Number(point.expected_median)) / Number(point.expected_median)) : NaN).filter(Number.isFinite)
        : rawValues;
      const label = relativeToNormal
        ? `${history.metadata.label} deviation from reference (%)`
        : `${history.metadata.label} (${history.metadata.unit})`;
      if (!values.length) { target.textContent = `No quality-approved ${label} observations are retained for this Tabia.`; return; }
      const selectedRun = this.historyMapSnapshot === 'latest'
        ? (this.historyRuns[this.historyIndicator] || [])[0]
        : (this.historyRuns[this.historyIndicator] || []).find(run => run.run_id === this.historyMapSnapshot);
      const selectedPoint = selectedRun && history.points.find(point => point.run_id === selectedRun.run_id);
      const expected = Number(selectedPoint && selectedPoint.expected_median);
      const anomaly = expected > 0 && selectedPoint ? 100 * (Number(selectedPoint.value) - expected) / expected : NaN;
      const hasReference = selectedPoint && selectedPoint.baseline_status !== 'unavailable' && Number.isFinite(expected);
      const selectedTable = selectedPoint
        ? `<table class="drought-history-value-table"><caption>Selected indicator snapshot</caption><tbody><tr><th>Indicator</th><td>${history.metadata.label} (${history.metadata.unit})</td></tr><tr><th>Observation</th><td>${String(selectedPoint.observation_at).slice(0, 10)}</td></tr><tr><th>Observed value</th><td>${Number(selectedPoint.value).toFixed(2)} ${history.metadata.unit}</td>${hasReference ? `<tr><th>Reference median</th><td>${expected.toFixed(2)} ${history.metadata.unit}</td></tr><tr><th>Deviation from reference</th><td>${Number.isFinite(anomaly) ? `${anomaly >= 0 ? '+' : ''}${anomaly.toFixed(1)}% · ${Number(selectedPoint.percentile).toFixed(1)}th percentile` : 'Not available'}</td></tr><tr><th>Reference status</th><td>${selectedPoint.baseline_status.replaceAll('_', ' ')}</td></tr><tr><th>Reference</th><td>${selectedPoint.baseline_label}</td></tr>` : ''}<tr><th>Quality</th><td>${selectedPoint.quality_status}</td></tr><tr><th>Native source grid</th><td>${selectedPoint.native_resolution}</td></tr></tbody></table>`
        : '<p class="drought-map-instruction">No retained value is available for the selected map snapshot.</p>';
      const expectedValues = relativeToNormal ? history.points.map(() => 0) : history.points.map(point => Number(point.expected_median)).filter(Number.isFinite);
      const domainValues = values.concat(expectedValues);
      const width = 300, height = 88, min = Math.min(...domainValues), max = Math.max(...domainValues), spread = max - min || 1;
      const displayedValue = point => relativeToNormal ? (Number(point.expected_median) > 0 ? 100 * (Number(point.value) - Number(point.expected_median)) / Number(point.expected_median) : NaN) : Number(point.value);
      const pointPosition = (value, index) => `${10 + (history.points.length === 1 ? width / 2 : index * (width - 20) / (history.points.length - 1))},${height - 12 - ((value - min) / spread) * (height - 28)}`;
      const points = history.points.map((point, index) => pointPosition(displayedValue(point), index)).join(' ');
      const expectedPoints = history.points.map((point, index) => pointPosition(relativeToNormal ? 0 : Number(point.expected_median), index)).join(' ');
      const stale = history.points.filter(point => point.status === 'degraded').length;
      const coordinates = history.points.map((point, index) => ({ point, x: 10 + (history.points.length === 1 ? width / 2 : index * (width - 20) / (history.points.length - 1)), y: height - 12 - ((displayedValue(point) - min) / spread) * (height - 28) }));
      const trace = history.points.length > 1 ? `<polyline points="${points}" fill="none" stroke="#0f766e" stroke-width="3"/>` : '';
      const expectedTrace = relativeToNormal || expectedValues.length === history.points.length ? `<polyline points="${expectedPoints}" fill="none" stroke="#64748b" stroke-width="2" stroke-dasharray="5 4"/>` : '';
      const markers = coordinates.map(({ point, x, y }) => `<circle cx="${x}" cy="${y}" r="5" fill="${point.status === 'degraded' ? '#f59e0b' : '#0f766e'}" stroke="white" stroke-width="2"><title>${String(point.observation_at).slice(0, 10)}: ${displayedValue(point).toFixed(2)}${relativeToNormal ? '%' : ''}</title></circle>`).join('');
      const firstDate = String(history.points[0].observation_at).slice(0, 10);
      const lastDate = String(history.points[history.points.length - 1].observation_at).slice(0, 10);
      target.innerHTML = `<div class="drought-source-meta"><span>${history.tabia.tabia_name_en} · ${history.tabia.woreda_name_en}</span><span>${history.points.length} retained observation${history.points.length === 1 ? '' : 's'}</span></div>${selectedTable}<svg class="drought-history-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${label} retained-observation chart"><line x1="10" y1="${height - 12}" x2="${width - 10}" y2="${height - 12}" stroke="#94a3b8"/>${expectedTrace}${trace}${markers}<text x="10" y="12">${max.toFixed(2)}${relativeToNormal ? '%' : ''}</text><text x="10" y="${height - 16}">${min.toFixed(2)}${relativeToNormal ? '%' : ''}</text><text x="10" y="${height - 2}">${firstDate}</text>${history.points.length > 1 ? `<text x="${width - 80}" y="${height - 2}">${lastDate}</text>` : ''}</svg><div class="drought-map-instruction">${relativeToNormal ? `Teal is the observed deviation from its Tabia-specific same-calendar-month reference; the dashed line is 0%. ${this.historyIndicator === 'rainfall' ? 'Above zero is wetter than its usual month; below zero is drier. ' : 'This is observed contextual evidence only, not a drought classification or priority. '}` : expectedValues.length === history.points.length ? 'Teal is observed value; the dashed line is the available expected median. ' : ''}${history.points.length === 1 ? `Only one retained source observation is available (${firstDate}); later refreshes append points. ` : ''}${stale ? `${stale} retained point${stale === 1 ? ' is' : 's are'} degraded; ` : ''}Points are source timestamps only—gaps are not interpolated.</div>`;
    } catch (error) {
      console.error('[DroughtDashboard] evidence history unavailable:', error);
      target.textContent = 'Evidence history is unavailable.';
    }
  }

  _historicalRainfallColour(value, qualityStatus) {
    if (qualityStatus !== 'ok' || !Number.isFinite(Number(value))) return '#cbd5e1';
    const colors = ['#fff7bc', '#fee391', '#fec44f', '#fe9929', '#ec7014', '#cc4c02', '#993404', '#662506', '#471908', '#2d1208'];
    const thresholds = [50, 100, 150, 200, 250, 300, 350, 400, 450];
    const index = thresholds.findIndex(threshold => Number(value) < threshold);
    return colors[index === -1 ? colors.length - 1 : index];
  }

  async _selectObservedSnapshot(runId) {
    this.observedSnapshotId = runId;
    if (runId !== 'latest') this.spatialViews.observed = 'tabia';
    await this._loadObservedArtifact(runId);
    if (this.mode === 'observed') this._renderMode();
  }

  async _showHistoricalObservedMap() {
    if (!this.fixtureLayer || this.observedSnapshotId === 'latest') return;
    const runId = this.observedSnapshotId;
    const token = ++this.fixtureRenderToken;
    try {
      const response = await fetch(`${this.observedRunBaseUrl}/${encodeURIComponent(runId)}/features`, { cache: 'no-store' });
      const featureCollection = await response.json();
      if (!response.ok || !Array.isArray(featureCollection.features)) throw new Error('invalid historical rainfall GeoJSON');
      if (token !== this.fixtureRenderToken || this.mode !== 'observed' || this.observedSnapshotId !== runId) return;
      const features = new ol.format.GeoJSON().readFeatures(featureCollection, {
        dataProjection: 'EPSG:4326', featureProjection: this.map.getView().getProjection()
      });
      features.forEach(feature => {
        const properties = feature.getProperties();
        feature.setProperties({
          droughtHistoricalObserved: true,
          droughtColour: this._historicalRainfallColour(properties.rainfall_mm, properties.quality_status),
          droughtOpacity: properties.quality_status === 'ok' ? 0.78 : 0.38
        });
      });
      const source = this.fixtureLayer.getSource();
      source.clear();
      source.addFeatures(features);
    } catch (error) {
      console.error('[DroughtDashboard] Historical rainfall map unavailable:', error);
    }
  }

  _renderObservedArtifact() {
    const artifact = this.observedArtifact;
    if (!artifact || artifact.unavailable) {
      this.content.innerHTML = `<div class="drought-mode-title"><strong>Observed condition</strong><span>Unavailable</span></div><p class="drought-empty">${artifact ? artifact.message : 'Loading artifact.'}</p>`;
      return;
    }
    const run = artifact.run;
    const rawQuality = artifact.artifact && artifact.artifact.quality_summary;
    let quality = rawQuality;
    if (typeof rawQuality === 'string') {
      try { quality = JSON.parse(rawQuality); } catch (error) { quality = null; }
    }
    const counts = quality && quality.quality_counts ? Object.entries(quality.quality_counts).map(([key, value]) => `${value} ${key}`).join(' · ') : 'quality summary unavailable';
    const classCounts = quality && quality.class_counts ? quality.class_counts : {};
    const classLabels = {
      exceptionally_dry: 'Exceptionally dry', drier_than_typical: 'Drier than typical',
      typical_range: 'Typical range', wetter_than_typical: 'Wetter than typical',
      exceptionally_wet: 'Exceptionally wet', unavailable: 'Insufficient coverage'
    };
    const summaries = Object.entries(classLabels).map(([key, label]) =>
      `<div class="drought-class drought-class-${key}"><strong>${classCounts[key] || 0}</strong><span>${label}</span></div>`
    ).join('');
    const usable = artifact.conditions.filter(item => item.quality_status === 'ok' && Number.isFinite(Number(item.rainfall_mm)));
    const totals = usable.map(item => Number(item.rainfall_mm));
    const range = totals.length ? `${Math.min(...totals).toFixed(1)}–${Math.max(...totals).toFixed(1)} mm` : 'no usable totals';
    const tabiaView = this.spatialViews.observed === 'tabia';
    const monthName = month => new Intl.DateTimeFormat('en', { month: 'long', timeZone: 'UTC' }).format(new Date(Date.UTC(run.analysis_year, Number(month) - 1, 1)));
    const months = (run.season_months || []).map(Number).filter(Number.isFinite);
    const analysisPeriod = months.length
      ? `${monthName(months[0])}${months.length > 1 ? `–${monthName(months[months.length - 1])}` : ''} ${run.analysis_year}`
      : `analysis year ${run.analysis_year}`;
    const accumulationLabel = months.length > 1
      ? `Cumulative rainfall total: ${analysisPeriod} (${months.length} completed calendar months)`
      : `Rainfall total: ${analysisPeriod} (one completed calendar month)`;
    const latest = run.source_latest_month ? new Intl.DateTimeFormat('en', { month: 'long', year: 'numeric', timeZone: 'UTC' }).format(new Date(`${run.source_latest_month}T00:00:00Z`)) : 'not recorded';
    const historical = this.observedSnapshotId !== 'latest';
    const snapshotOptions = this.observedRuns
      .filter(candidate => candidate.run_id !== run.run_id)
      .map(candidate => {
        const monthsForRun = (candidate.season_months || []).map(Number).filter(Number.isFinite);
        const label = monthsForRun.length
          ? `${monthsForRun.map(monthName).join('–')} ${candidate.analysis_year}`
          : candidate.run_id;
        return `<option value="${candidate.run_id}" ${this.observedSnapshotId === candidate.run_id ? 'selected' : ''}>Historical evidence: ${label}</option>`;
      }).join('');
    const snapshotControl = snapshotOptions
      ? `<div class="drought-history-controls"><label>Rainfall snapshot <select data-observed-snapshot><option value="latest" ${historical ? '' : 'selected'}>Latest seasonal analysis</option>${snapshotOptions}</select></label><small>${historical ? 'Historical selections are Tabia summaries only; native raster display is reserved for the latest retained analysis.' : 'Historical selections are archived observations, not forecasts or model backtests.'}</small></div>`
      : '';
    const title = historical ? 'Historical rainfall evidence' : (tabiaView ? 'Latest rainfall total' : 'Latest rainfall condition');
    this.content.innerHTML = `<div class="drought-mode-title"><strong>${title}</strong><span>CHIRPS v3 · development</span></div>${snapshotControl}<div class="drought-period-stamp"><strong>${accumulationLabel}</strong><span>Newest source month included: ${latest} · Baseline comparison: ${run.baseline_year_start}–${run.baseline_year_end}</span><small>${historical ? 'Archived observed rainfall accumulation; provider archive retrieval time is not proof of historical decision-time availability.' : '“Latest” is the latest retained analysis, not a July-only total, daily value, or real-time rainfall.'}</small></div><div class="drought-source-meta"><span>Native grid: ${artifact.artifact ? artifact.artifact.native_resolution : '0.05 degree'}</span><span>${tabiaView ? `Tabia mean range: ${range}` : counts}</span></div>${tabiaView ? '' : `<div class="drought-class-grid">${summaries}</div>`}<div class="drought-map-instruction">${historical ? 'The map is a Tabia zonal-mean historical evidence layer using the same ten rainfall-total bands as the native grid. It does not reconstruct a historical native raster or a past decision product.' : tabiaView ? 'The Tabia zonal-mean map uses the same ten rainfall-total bands as the native grid. Select a Tabia to inspect its rainfall, baseline percentile, coverage, and source details.' : 'The native map preserves the source grid. Select Tabia average for an aggregated display using the same millimetre classes.'}</div>${historical ? '<div class="drought-map-selection" data-historical-selection>Select a coloured Tabia to inspect this archived rainfall evidence.</div>' : ''}`;
    const snapshotSelector = this.content.querySelector('[data-observed-snapshot]');
    if (snapshotSelector) snapshotSelector.addEventListener('change', event => this._selectObservedSnapshot(event.target.value));
  }

  async selectArea(id) {
    const area = this.data.areas.find(item => item.id === id);
    if (!area) return;
    this.selectBoundary(area[this.mode].boundary);
  }

  async selectBoundary(boundary) {
    this.selectedId = boundary.id;
    if (boundary.type === 'tabia') {
      this.historyTabiaId = boundary.id;
      this.historyTabiaLabel = boundary.label || 'Selected Tabia';
      if (this.mode === 'history') this._renderHistory();
    }
    this._ensureContextLayersVisible(boundary.type);
    this.content.querySelectorAll('.drought-row').forEach(row => {
      const rowId = row.dataset.artifactTabiaId || row.dataset.areaId;
      row.classList.toggle('is-selected', rowId === boundary.id);
    });
    try {
      const response = await fetch(`${this.boundaryUrl}/${boundary.type}/${boundary.id}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`boundary lookup returned ${response.status}`);
      this._showBoundary(await response.json(), boundary.type);
    } catch (error) {
      console.error('[DroughtDashboard] Boundary selection failed:', error);
      this._showSelectionError(`Boundary unavailable for ${boundary.label}.`);
    }
  }

  _showBoundary(record, boundaryType, options = {}) {
    const source = this.boundaryLayer.getSource();
    source.clear();
    this._setBoundaryHighlightStyle(this.mode === 'history' && boundaryType === 'tabia');
    const feature = new ol.format.GeoJSON().readFeature(record.geometry, {
      dataProjection: 'EPSG:4326', featureProjection: this.map.getView().getProjection()
    });
    source.addFeature(feature);
    if (options.fit !== false) {
      this.map.getView().fit(feature.getGeometry().getExtent(), {
        padding: [45, 420, 45, 45], maxZoom: boundaryType === 'tabia' ? 12 : 10, duration: 400
      });
    }
  }

  _ensureContextLayersVisible(boundaryType) {
    const contextIds = boundaryType === 'tabia'
      ? ['tigray_woredas_ti_en_pg', 'tigray_tabias_ti_en_pg']
      : ['tigray_woredas_ti_en_pg'];
    if (this.onEnsureContextLayers) {
      this.onEnsureContextLayers(contextIds);
      return;
    }
    this.map.getLayers().getArray().forEach(layer => {
      if (contextIds.includes(layer.layerId)) layer.setVisible(true);
    });
  }

  _setEvidenceLayer(activeLayerId) {
    const ids = ['tigray_drought_chirps_dev', 'tigray_drought_chirps_raw_dev', 'tigray_drought_chirps_rapid_raw_dev', 'tigray_drought_chirps_rapid_tabia_dev', 'tigray_drought_ndvi_dev', 'tigray_drought_ndvi_raw_dev', 'tigray_drought_swi_dev', 'tigray_drought_swi_raw_dev', 'tigray_drought_lst_dev', 'tigray_drought_lst_raw_dev', 'tigray_drought_wapor_dev', 'tigray_drought_wapor_raw_dev', 'tigray_drought_road_accessibility_dev', 'tigray_drought_population_dev', 'tigray_drought_cropland_dev'];
    if (this.onSetEvidenceLayer) {
      this.onSetEvidenceLayer(activeLayerId);
      return;
    }
    this.map.getLayers().getArray().forEach(layer => {
      if (ids.includes(layer.layerId)) layer.setVisible(layer.layerId === activeLayerId);
    });
  }

  _showSelectionError(message) {
    const notice = document.querySelector('#drought-dashboard .drought-notice');
    if (notice) notice.textContent = message;
  }
}
