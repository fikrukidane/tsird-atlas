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

    // Fit view to initial extent (Tigray) without constraining navigation
    // This focuses the initial view but allows zooming out to Ethiopia
    this.view.fit(extentEPSG3857, {
      padding: [20, 20, 20, 20],
      duration: 0,
      maxZoom: this.atlasConfig.zoom ?? 9
    });

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
