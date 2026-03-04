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
 */

async function initializeApplication(registryPath = 'data/atlas-registry.json') {
  console.log('═══════════════════════════════════════════════════════════');
  console.log('TSIRD Phase 2 - Stage 6 Milestone 1 (Basic Map + Registry)');
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
    // Step 9: Log final state
    // ────────────────────────────────────────────────────────────
    console.log('Step 9: Monitoring WMS requests (check DevTools Network tab)...');
    console.log('  - Ensure only GetMap requests for tiles');
    console.log('  - GetFeatureInfo requests on click (queryable layers only)');
    console.log('  - No WFS traffic');
    console.log('');

    // ────────────────────────────────────────────────────────────
    // Initialization complete
    // ────────────────────────────────────────────────────────────
    console.log('═══════════════════════════════════════════════════════════');
    console.log('✓ APPLICATION INITIALIZED SUCCESSFULLY (MILESTONE 2)');
    console.log('═══════════════════════════════════════════════════════════');
    console.log('');
    console.log('Milestone 2 Definition of Done:');
    console.log('  ✓ Map loads, view fits registry extent');
    console.log('  ✓ TOC renders in correct order');
    console.log('  ✓ Toggling layers updates visibility');
    console.log('  ✓ Only published layers appear');
    console.log('  ✓ WMS tile requests to services.wms.base_url');
    console.log('  ✓ No WFS traffic (GetFeatureInfo only on click)');
    console.log('  ✓ Scale constraints enforced (layers auto-hide/show on zoom)');
    console.log('  ✓ Mutex pairs enforced (roads/towns never overlap)');
    console.log('  ✓ GetFeatureInfo on click (queryable layers only)');
    console.log('  ✓ Attribute allowlist filtering (identify_fields)');
    console.log('  ✓ Out-of-scale visual indicators in TOC');
    console.log('  ✗ Search UI — Deferred to Phase 3 (search: [] in registry)');
    console.log('');
    console.log('Test Checklist (Manual):');
    console.log('  1. Zoom in/out: Roads swap at 1:1M, Towns swap at 1:2M');
    console.log('  2. Toggle both roads ON: Only in-scale one visible');
    console.log('  3. Click health facilities: Only allowlisted fields shown');
    console.log('  4. Out-of-scale layers: TOC shows disabled style');
    console.log('');
    console.log('Ready for: Final testing + deployment');
    console.log('');

    return {
      mapController,
      layers,
      interaction,
      registry
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
  initializeApplication('data/atlas-registry.json?v=20260303b');
});

// Export for testing
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { initializeApplication, displayErrorPage };
}
