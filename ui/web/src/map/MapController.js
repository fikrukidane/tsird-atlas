/**
 * MapController — Initialize OpenLayers map with CRS handling
 * 
 * Responsibilities:
 *   - Create OL map with view projection = view_crs (EPSG:3857)
 *   - Transform center from canonical_crs → view_crs
 *   - Transform extent and apply as view constraint
 *   - Provide resolution-to-scale conversion utility
 * 
 * Contract:
 *   - Map is initialized and ready for layer addition
 *   - View center/zoom/extent match registry values (after transformation)
 */

class MapController {
  constructor(mapTargetElementId, atlasConfig, wmsBaseUrl) {
    this.mapTargetId = mapTargetElementId;
    this.atlasConfig = atlasConfig;
    this.wmsBaseUrl = wmsBaseUrl;
    this.map = null;
    this.view = null;
    
    // Layer storage for later reference
    this.layers = [];
  }

  /**
   * Initialize the OpenLayers map.
   * Must be called after DOM is ready.
   */
  initialize() {
    console.log('[MapController] Initializing map...');

    // Check target element exists
    const target = document.getElementById(this.mapTargetId);
    if (!target) {
      const errorMsg = `Map target element not found: #${this.mapTargetId}`;
      console.error(`[MapController] ${errorMsg}`);
      this._showError(errorMsg);
      throw new Error(errorMsg);
    }

    // Hide loading message
    this._hideLoadingMessage();

    const canonicalCrs = this.atlasConfig.canonical_crs || 'EPSG:4326';
    const viewCrs = this.atlasConfig.view_crs || 'EPSG:3857';

    const centerEPSG4326 = this.atlasConfig.center;  // [lon, lat]
    const centerEPSG3857 = ol.proj.fromLonLat(centerEPSG4326);

    const extentEPSG4326 = this.atlasConfig.extent;  // [minx, miny, maxx, maxy]
    const extentEPSG3857 = ol.proj.transformExtent(
      extentEPSG4326,
      canonicalCrs,
      viewCrs
    );

    console.log(`[MapController] Center: ${centerEPSG4326} (EPSG:4326) → ${centerEPSG3857} (${viewCrs})`);
    console.log(`[MapController] Extent: ${extentEPSG4326} (${canonicalCrs}) → ${extentEPSG3857} (${viewCrs})`);

    // Create view WITHOUT extent constraint (allows zoom-out beyond initial bounds)
    this.view = new ol.View({
      projection: ol.proj.get(viewCrs),
      center: centerEPSG3857,
      zoom: this.atlasConfig.zoom
    });

    // Create map
    this.map = new ol.Map({
      target: this.mapTargetId,
      view: this.view,
      layers: [] // Will be populated by LayerFactory
    });

    console.log('[MapController] Map initialized successfully');

    // Fit view to initial extent (Tigray Tabias) 
    // Use constrainResolution: false to allow exact fit without snapping to zoom levels
    this.view.fit(extentEPSG3857, {
      padding: [20, 20, 20, 20],
      duration: 0,
      constrainResolution: false  // Allow fractional zoom to fit extent exactly
    });

    console.log(`[MapController] View fitted to extent, zoom: ${this.view.getZoom().toFixed(2)}`);

    // Register map render event to confirm tiles loading
    this.map.once('rendercomplete', () => {
      console.log('[MapController] First render complete');
    });
  }

  /**
   * Hide the loading message after map initialization.
   */
  _hideLoadingMessage() {
    const loadingEl = document.getElementById('map-loading');
    if (loadingEl) {
      loadingEl.style.display = 'none';
      console.log('[MapController] Loading message hidden');
    }
  }

  /**
   * Show error message if map cannot initialize.
   */
  _showError(message) {
    const container = document.getElementById('map-container');
    if (container) {
      const errorDiv = document.createElement('div');
      errorDiv.className = 'loading error';
      errorDiv.style.color = '#d32f2f';
      errorDiv.style.fontWeight = 'bold';
      errorDiv.textContent = `⚠️ ${message}`;
      container.appendChild(errorDiv);
    }
  }

  /**
   * Get the OpenLayers Map object.
   */
  getMap() {
    return this.map;
  }

  /**
   * Get the View object.
   */
  getView() {
    return this.view;
  }

  /**
   * Convert OpenLayers resolution to cartographic scale denominator.
   * 
   * Scale = resolution * dots_per_meter
   * Assumes 96 DPI (standard web)
   * 
   * @param {number} resolution - OL resolution (meters per pixel)
   * @returns {number} Cartographic scale denominator (e.g., 1000000 = 1:1M)
   */
  getScaleDenominator(resolution) {
    const dotsPerMeter = 96 / 0.0254;  // ~3779 dpi/meter at 96 DPI
    return resolution * dotsPerMeter;
  }

  /**
   * Get current scale denominator from map resolution.
   */
  getCurrentScaleDenominator() {
    const resolution = this.view.getResolution();
    return this.getScaleDenominator(resolution);
  }

  /**
   * Auto-adjust zoom on startup to satisfy default-visible layer scale ranges.
   * 
   * Algorithm:
   * - Collect default_visible layers with scale constraints
   * - Zoom in (incrementally by 1 level) until all are in-scale
   * - Stop at maxZoomCap to prevent excessive zoom
   * - Do not zoom out automatically
   * 
   * @param {Object} layerDefs - Layer definitions from registry (all layers)
   * @param {number} maxZoomCap - Maximum zoom level to prevent over-zoom (default 11)
   */
  autoZoomForDefaultLayers(layerDefs, maxZoomCap = 11) {
    console.log('[MapController] Auto-zooming to satisfy default-visible layer scale ranges...');
    
    // Collect default-visible layers with scale constraints
    const constrainedDefaultLayers = Object.entries(layerDefs)
      .filter(([key, def]) => {
        return def.published && 
               def.default_visible && 
               def.min_scale && 
               def.max_scale;
      })
      .map(([key, def]) => ({ wms_name: key, ...def }));

    if (constrainedDefaultLayers.length === 0) {
      console.log('[MapController] No default-visible layers with scale constraints. Skipping auto-zoom.');
      return;
    }

    console.log(`[MapController] Checking ${constrainedDefaultLayers.length} default-visible layers with scale constraints:`);
    constrainedDefaultLayers.forEach(layer => {
      console.log(`  - ${layer.wms_name}: ${layer.min_scale.toLocaleString()} - ${layer.max_scale.toLocaleString()}`);
    });

    // Auto-zoom: zoom in until all layers are in-scale or reach maxZoomCap
    let zoomAdjusted = false;
    let currentZoom = this.view.getZoom();
    const startZoom = currentZoom;

    while (currentZoom < maxZoomCap) {
      const currentScale = ScaleEngine.getCurrentScale(this.view);
      const anyOutOfScale = constrainedDefaultLayers.some(layer => 
        !ScaleEngine.isLayerInScale(layer, currentScale)
      );

      if (!anyOutOfScale) {
        // All layers are in-scale
        break;
      }

      // Zoom in by 1 level
      currentZoom = this.view.getZoom() + 1;
      this.view.setZoom(currentZoom);
      zoomAdjusted = true;
    }

    if (zoomAdjusted) {
      const finalZoom = this.view.getZoom();
      const finalScale = ScaleEngine.getCurrentScale(this.view);
      console.log(`[MapController] Auto-zoom complete: ${startZoom} → ${finalZoom} (scale: ${ScaleEngine.formatScale(finalScale)})`);
    } else {
      console.log('[MapController] All default-visible layers are already in-scale. No zoom adjustment needed.');
    }
  }

  /**
   * Add a layer to the map.
   */
  addLayer(layer) {
    this.map.addLayer(layer);
    this.layers.push(layer);
  }

  /**
   * Add multiple layers to the map.
   */
  addLayers(layersArray) {
    layersArray.forEach(layer => this.addLayer(layer));
  }

  /**
   * Listen for zoom/pan changes to enforce scale rules later.
   */
  onViewChange(callback) {
    this.view.on('change:resolution', callback);
  }
}

// Export for use in main.js
if (typeof module !== 'undefined' && module.exports) {
  module.exports = MapController;
}
