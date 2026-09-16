/**
 * main.js — TSIRD Atlas Application Orchestration (Phase 3)
 *
 * Plain browser global script. No ES module syntax.
 * All dependencies loaded as classic <script> tags before this file.
 *
 * Initialization sequence:
 *   1. Load and normalize registry
 *   2. Initialize map controller
 *   3. Create WMS layers
 *   4. Add layers to map
 *   5. Render TOC
 *   6. Initialize layer visibility
 *   7. Scale monitoring + GetFeatureInfo
 *   8. Phase 3: HighlightOverlay, SearchControl, FullZoomControl, MeasureControl, Navigator
 */
async function initializeApplication(registryPath, options) {
  options = options || {};
  registryPath = registryPath || 'data/atlas-registry.json';
  console.log('═══════════════════════════════════════════════════════════');
  console.log('TSIRD Phase 3 — Search, Navigator, Measure Tools');
  console.log('═══════════════════════════════════════════════════════════');

  try {
    // Step 1: Load registry
    console.log('Step 1: Loading registry...');
    const loader = new RegistryLoader(registryPath);
    const registry = await loader.load();
    console.log('✓ Registry loaded:', registry.atlasConfig.title);
    console.log('  WMS:', registry.wmsBaseUrl, '| Layers:', Object.keys(registry.layerDefs).length);

    // Step 2: Initialize map controller
    console.log('Step 2: Initializing map...');
    const mapController = new MapController('map', registry.atlasConfig, registry.wmsBaseUrl);
    mapController.initialize();
    console.log('✓ Map initialized, scale:', ScaleEngine.formatScale(mapController.getCurrentScaleDenominator()));

    // Step 3: Create WMS layers
    console.log('Step 3: Creating layers...');
    const layerFactory = new LayerFactory(registry.wmsBaseUrl, registry.layerDefs, registry.tocModel);
    const layers = layerFactory.createLayers();
    layerFactory.setAllLayers(layers);
    console.log('✓ Created', layers.length, 'layers');

    // Step 4: Add layers to map
    console.log('Step 4: Adding layers...');
    mapController.addLayers(layers);

    // Step 5 & 6: Render TOC + initialize visibility
    console.log('Step 5: Rendering TOC...');
    const interaction = new InteractionController(
      'toc-container', layers, registry.tocModel, registry.layerDefs,
      mapController, registry.scaleMutexPairs
    );
    interaction.renderTOC();
    interaction.initializeLayerVisibility();
    console.log('✓ TOC rendered');

    // Step 7: Scale monitoring + GetFeatureInfo
    console.log('Step 7: Scale monitoring + GetFeatureInfo...');
    interaction.initializeScaleMonitoring();
    interaction.initializeGetFeatureInfo(registry.wmsBaseUrl);
    console.log('✓ Scale monitoring active. Mutex pairs:', registry.scaleMutexPairs.length);

    let droughtDashboard = null;
    if (options.droughtWorkspace) {
      droughtDashboard = new DroughtDashboard(mapController.map, {
        priorityOnly: options.priorityOnly,
        dataUrl: options.droughtDataUrl,
        observedUrl: options.droughtObservedUrl,
        observedRunsUrl: options.droughtObservedRunsUrl,
        observedRunBaseUrl: options.droughtObservedRunBaseUrl,
        preliminaryUrl: options.droughtPreliminaryUrl,
        ndviUrl: options.droughtNdviUrl,
        swiUrl: options.droughtSwiUrl,
        lstUrl: options.droughtLstUrl,
        waporUrl: options.droughtWaporUrl,
        outlookUrl: options.droughtOutlookUrl,
        priorityConfigurationUrl: options.droughtPriorityConfigurationUrl,
        priorityPreviewsUrl: options.droughtPriorityPreviewsUrl,
        priorityReplaysUrl: options.droughtPriorityReplaysUrl,
        fewsNetRunsUrl: options.droughtFewsNetRunsUrl,
        fewsNetRunBaseUrl: options.droughtFewsNetRunBaseUrl,
        modelReadinessUrl: options.droughtModelReadinessUrl,
        historyUrl: options.droughtHistoryUrl,
        evidenceBaseUrl: options.droughtEvidenceBaseUrl,
        boundaryUrl: options.droughtBoundaryUrl,
        onEnsureContextLayers: layerIds => layerIds.forEach(layerId => interaction.setLayerVisible(layerId, true)),
        onSetEvidenceLayer: activeLayerId => {
          ['tigray_drought_chirps_dev', 'tigray_drought_chirps_raw_dev', 'tigray_drought_chirps_rapid_raw_dev',
           'tigray_drought_chirps_rapid_tabia_dev', 'tigray_drought_ndvi_dev', 'tigray_drought_ndvi_raw_dev',
           'tigray_drought_swi_dev', 'tigray_drought_swi_raw_dev', 'tigray_drought_lst_dev', 'tigray_drought_lst_raw_dev',
           'tigray_drought_wapor_dev', 'tigray_drought_wapor_raw_dev',
           'tigray_drought_road_accessibility_dev', 'tigray_drought_population_dev', 'tigray_drought_cropland_dev']
            .forEach(layerId => interaction.setLayerVisible(layerId, layerId === activeLayerId));
        }
      });
      await droughtDashboard.initialize();
      if (!options.priorityOnly) interaction.setLayerVisible('tigray_drought_chirps_dev', true);
      console.log('✓ Drought intelligence workspace initialized (development artifact)');
    }

    // Step 8: Phase 3 — Highlight + Toolbar + Navigator
    console.log('Step 8: Adding Phase 3 controls...');

    // 8.1 Highlight overlay
    HighlightOverlay.init(mapController.map);

    // 8.2 Build single horizontal toolbar div, appended directly to map viewport
    var mapViewport = mapController.map.getViewport();
    var toolbar = document.createElement('div');
    toolbar.className = 'tsird-phase3-toolbar';
    mapViewport.appendChild(toolbar);

    // 8.3 Populate toolbar (left to right)
    new SearchControl(toolbar, mapController.map);
    new FullZoomControl(toolbar, mapController.map);
    new MeasureControl(toolbar, mapController.map);

    // 8.4 Navigator Map (OverviewMap) — top-right via CSS
    var overviewMap = new ol.control.OverviewMap({
      className: 'ol-overviewmap ol-custom-overviewmap',
      layers: [ new ol.layer.Tile({ source: new ol.source.OSM() }) ],
      collapseLabel: '\u00BB',
      label: '\u00AB',
      collapsed: false
    });
    mapController.map.addControl(overviewMap);

    console.log('✓ Toolbar (Search, Full Zoom, Measure) + Navigator added');

    console.log('═══════════════════════════════════════════════════════════');
    console.log('✓ APPLICATION INITIALIZED SUCCESSFULLY (PHASE 3)');
    console.log('═══════════════════════════════════════════════════════════');

    return { mapController, layers, interaction, registry, droughtDashboard };

  } catch (error) {
    console.error('❌ APPLICATION INITIALIZATION FAILED:', error.message);
    console.error(error);
    displayErrorPage('Registry unavailable or application error. Please try again later.');
    throw error;
  }
}

function displayErrorPage(message) {
  var container = document.getElementById('map-container');
  if (!container) return;
  container.innerHTML =
    '<div style="display:flex;flex-direction:column;align-items:center;justify-content:center;width:100%;height:100%;background:#f5f5f5;color:#333;font-family:sans-serif;">' +
    '<h1>⚠️ TSIRD Atlas</h1>' +
    '<h2 style="color:#d32f2f;">' + message + '</h2>' +
    '<button onclick="location.reload()" style="padding:10px 20px;margin-top:20px;background:#1976d2;color:white;border:none;border-radius:4px;cursor:pointer;font-size:16px;">Retry</button>' +
    '</div>';
}

document.addEventListener('DOMContentLoaded', function() {
  // Purpose-built workspaces initialise themselves with their own relative
  // API/data paths. Only the main Atlas page uses this generic bootstrap.
  if (!document.body.dataset.tsirdPage) {
    initializeApplication('data/atlas-registry.json?v=20260306');
  }
});
