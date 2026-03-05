/**
 * main.js — Application orchestration
 * 
 * Initialization sequence:
 * 1. Load and normalize registry
 * 2. Initialize map controller
 * 3. Create layers
 * 4. Add layers to map
 * 5. Render TOC
 * 6. Initialize layer visibility
 * 7. Set up interaction handlers
 * 8. Phase 3: Search, Navigator, Measure tools
 */

async function initializeApplication(registryPath = 'data/atlas-registry.json') {
  console.log('═══════════════════════════════════════════════════════════');
  console.log('TSIRD Phase 3 — Search, Navigator, Measure Tools');
  console.log('═══════════════════════════════════════════════════════════');
  console.log('Initializing application...\n');

  try {
    // ────────────────────────────────────────────────────────────
    // Step 1: Load registry
    // ────────────────────────────────────────────────────────────
    console.log('Step 1: Loading registry...');
    const loader = new RegistryLoader(registryPath);
    
    const registry = await loader.load();
    console.log('✓ Registry loaded and normalized');
    console.log(`  - Atlas: ${registry.atlasConfig.title}`);
    console.log(`  - Center: ${registry.atlasConfig.center}`);
    console.log(`  - Zoom: ${registry.atlasConfig.zoom}`);
    console.log(`  - WMS Base URL: ${registry.wmsBaseUrl}`);
    console.log(`  - Layers: ${Object.keys(registry.layerDefs).length} total`);
    console.log(`  - Published: ${Object.values(registry.layerDefs).filter(l => l.published).length}`);
    console.log(`  - Scale mutex pairs: ${registry.scaleMutexPairs.length}`);
    console.log('');

    // ────────────────────────────────────────────────────────────
    // Step 2: Initialize map controller
    // ────────────────────────────────────────────────────────────
    console.log('Step 2: Initializing map controller...');
    const mapController = new MapController(
      'map',  // Target the actual map div, not the container
      registry.atlasConfig,
      registry.wmsBaseUrl
    );
    mapController.initialize();
    console.log('✓ Map controller initialized');
    console.log(`  - Projection: ${registry.atlasConfig.view_crs}`);
    console.log(`  - Initial scale: ${mapController.getCurrentScaleDenominator().toFixed(0)}`);
    console.log('');

    // ────────────────────────────────────────────────────────────
    // Step 2.5: Auto-zoom DISABLED - let extent fit determine initial view
    // Scale-constrained layers will show/hide based on user's zoom level
    // ────────────────────────────────────────────────────────────
    console.log('Step 2.5: Auto-zoom disabled (extent fit determines initial view)');
    // mapController.autoZoomForDefaultLayers(registry.layerDefs, 11);
    const postAutoZoomScale = mapController.getCurrentScaleDenominator();
    console.log(`✓ Current scale: ${ScaleEngine.formatScale(postAutoZoomScale)}`);
    console.log('');

    // ────────────────────────────────────────────────────────────
    // Step 3: Create layers
    // ────────────────────────────────────────────────────────────
    console.log('Step 3: Creating WMS layers...');
    const layerFactory = new LayerFactory(
      registry.wmsBaseUrl,
      registry.layerDefs,
      registry.tocModel
    );
    const layers = layerFactory.createLayers();
    layerFactory.setAllLayers(layers);
    console.log(`✓ Created ${layers.length} WMS layers`);
    console.log('  WMS Request Sanity Check:');
    console.log('    - FORMAT: image/png (fixed)');
    console.log('    - TRANSPARENT: true (for overlays)');
    console.log('    - Source: ImageWMS (MapServer compatible)');
    console.log('    - No WFS calls (GetFeatureInfo deferred to Milestone 2)');
    console.log('');

    // ────────────────────────────────────────────────────────────
    // Step 4: Add layers to map
    // ────────────────────────────────────────────────────────────
    console.log('Step 4: Adding layers to map...');
    mapController.addLayers(layers);
    console.log(`✓ Added ${layers.length} layers to map`);
    console.log('');

    // ────────────────────────────────────────────────────────────
    // Step 5: Render TOC
    // ────────────────────────────────────────────────────────────
    console.log('Step 5: Rendering Table of Contents...');
    const interaction = new InteractionController(
      'toc-container',
      layers,
      registry.tocModel,
      registry.layerDefs,
      mapController,  // Milestone 2: needed for scale monitoring
      registry.scaleMutexPairs  // Milestone 2: mutex enforcement
    );
    interaction.renderTOC();
    console.log('✓ TOC rendered');
    console.log('');

    // ────────────────────────────────────────────────────────────
    // Step 6: Initialize layer visibility
    // ────────────────────────────────────────────────────────────
    console.log('Step 6: Initializing layer visibility...');
    interaction.initializeLayerVisibility();
    console.log('✓ Layer visibility initialized');
    console.log('');

    // ────────────────────────────────────────────────────────────
    // Step 7: Initialize scale monitoring (Milestone 2)
    // ────────────────────────────────────────────────────────────
    console.log('Step 7: Initializing scale monitoring...');
    interaction.initializeScaleMonitoring();
    console.log('✓ Scale monitoring active');
    console.log(`  - Mutex pairs: ${registry.scaleMutexPairs.length}`);
    console.log(`  - Scale engine: ${ScaleEngine.name || 'ScaleEngine'}`);
    console.log('');

    // ────────────────────────────────────────────────────────────
    // Step 8: Initialize GetFeatureInfo (Milestone 2)
    // ────────────────────────────────────────────────────────────
    console.log('Step 8: Initializing GetFeatureInfo...');
    interaction.initializeGetFeatureInfo(registry.wmsBaseUrl);
    console.log('✓ GetFeatureInfo enabled');
    console.log('  - Click queryable layers to view attributes');
    console.log('  - Attributes filtered by identify_fields allowlist');
    console.log('');

    // ────────────────────────────────────────────────────────────
    // Step 8.5: Load search index (Phase 3)
    // ────────────────────────────────────────────────────────────
    if (registry.atlasConfig.search && registry.atlasConfig.search.enabled) {
      console.log('Step 8.5: Loading search index...');
      try {
        await interaction.loadSearchIndex(registry.atlasConfig.search.index_url);
        console.log('✓ Search index loaded');
        console.log(`  - Index URL: ${registry.atlasConfig.search.index_url}`);
      } catch (err) {
        console.warn('⚠ Search index failed to load:', err.message);
        console.log('  - Search functionality will be disabled');
      }
      console.log('');
    }

    // ────────────────────────────────────────────────────────────
    // Step 9: Log final state
    // ────────────────────────────────────────────────────────────
    console.log('Step 9: Monitoring WMS requests (check DevTools Network tab)...');
    console.log('  - Ensure only GetMap requests for tiles');
    console.log('  - GetFeatureInfo requests on click (queryable layers only)');
    console.log('  - No WFS traffic');
    console.log('');

    // ────────────────────────────────────────────────────────────
    // Phase 3: Initialize Search, Navigator, Measure Tools
    // ────────────────────────────────────────────────────────────
    console.log('Step 10: Initializing Phase 3 tools...');
    
    // Create highlight layer and add to map
    const highlightLayer = HighlightOverlay.createHighlightLayer();
    mapController.map.addLayer(highlightLayer);
    console.log('  ✓ Highlight overlay layer added');
    
    // Add Navigator Map (OverviewMap)
    NavigatorMap.add(mapController.map);
    console.log('  ✓ Navigator map (overview) added');
    
    // Initialize Gazetteer Search Service
    try {
      await GazetteerSearchService.initGazetteerSearch();
      const status = GazetteerSearchService.getStatus();
      console.log(`  ✓ Gazetteer search: ${status.recordCount} records`);
    } catch (e) {
      console.warn('  ⚠ Gazetteer search init failed:', e.message);
    }
    
    // Create Phase 3 UI Components
    FullZoomButton.create(mapController.map);
    console.log('  ✓ Full Zoom button added');
    
    MeasurePanel.create(mapController.map);
    console.log('  ✓ Measure tools added');
    
    SearchBox.create(mapController.map, highlightLayer);
    console.log('  ✓ Search box added');
    
    console.log('');

    // ────────────────────────────────────────────────────────────
    // Initialization complete
    // ────────────────────────────────────────────────────────────
    console.log('═══════════════════════════════════════════════════════════');
    console.log('✓ APPLICATION INITIALIZED SUCCESSFULLY (PHASE 3)');
    console.log('═══════════════════════════════════════════════════════════');
    console.log('');
    console.log('Phase 3 Features:');
    console.log('  ✓ Search Woredas/Tabias (autocomplete)');
    console.log('  ✓ Navigator Map (overview inset)');
    console.log('  ✓ Full Zoom (fit to extent)');
    console.log('  ✓ Measure Distance/Area');
    console.log('  ✓ Highlight overlay on search selection');
    console.log('');
    console.log('Phase 2 Features (retained):');
    console.log('  ✓ Layer catalog with scale constraints');
    console.log('  ✓ GetFeatureInfo on click');
    console.log('  ✓ Mutex pairs enforcement');
    console.log('');

    return {
      mapController,
      layers,
      interaction,
      registry,
      highlightLayer
    };

  } catch (error) {
    console.error('═══════════════════════════════════════════════════════════');
    console.error('❌ APPLICATION INITIALIZATION FAILED');
    console.error('═══════════════════════════════════════════════════════════');
    console.error('Error:', error.message);
    console.error('');

    // Display error page to user
    displayErrorPage('Registry unavailable or application error. Please try again later.');
    throw error;
  }
}

/**
 * Display a user-friendly error page.
 */
function displayErrorPage(message) {
  const container = document.getElementById('map-container');
  if (!container) return;

  container.innerHTML = `
    <div style="
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      width: 100%;
      height: 100%;
      background: #f5f5f5;
      color: #333;
      font-family: sans-serif;
    ">
      <h1>⚠️ TSIRD Atlas</h1>
      <h2 style="color: #d32f2f;">${message}</h2>
      <button onclick="location.reload()" style="
        padding: 10px 20px;
        margin-top: 20px;
        background: #1976d2;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 16px;
      ">Retry</button>
    </div>
  `;
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  initializeApplication('data/atlas-registry.json?v=20260305');
});

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { initializeApplication, displayErrorPage };
}
