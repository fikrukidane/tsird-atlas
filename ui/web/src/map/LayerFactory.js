/**
 * LayerFactory — Create OpenLayers layers from registry
 * 
 * Responsibilities:
 *   - Create TileWMS sources for thematic layers (no WFS)
 *   - Create XYZ sources for basemaps (base_layer: true)
 *   - Use stable WMS parameters (FORMAT, TRANSPARENT, etc.)
 *   - Store layer metadata for later reference (GetFeatureInfo, scale rules, etc.)
 *   - Respect published flag (skip unpublished)
 *   - Maintain YAML order
 *   - Basemaps always zIndex = 0 (behind all thematic layers)
 * 
 * Contract:
 *   - Returns array of ol.layer objects in YAML order
 *   - Each layer has attached layerDef and layerId properties
 *   - WMS requests are cache-friendly (stable params)
 */

class LayerFactory {
  constructor(wmsBaseUrl, layerDefs, tocModel) {
    this.wmsBaseUrl = wmsBaseUrl;
    this.layerDefs = layerDefs;
    this.tocModel = tocModel;
  }

  /**
   * Create all layers from registry.
   * Respects published flag and YAML order.
   * Handles both WMS (thematic) and XYZ (basemap) sources.
   * 
   * @returns {Array<ol.layer.Base>} Ordered array of layers
   */
  createLayers() {
    console.log('[LayerFactory] Creating layers...');

    const layers = [];
    let layerCount = 0;

    // Traverse tocModel to maintain YAML order
    // tocModel already filters published=true layers
    for (const category of this.tocModel) {
      for (const group of category.groups) {
        for (const layerRef of group.layers) {
          const layerId = layerRef.id;
          const layerDef = this.layerDefs[layerId];

          if (!layerDef) {
            console.warn(`[LayerFactory] Layer definition not found: ${layerId}`);
            continue;
          }

          try {
            let layer;
            
            // Check if this is a basemap (XYZ source)
            if (layerDef.base_layer && layerDef.source_type === 'xyz') {
              layer = this._createXYZLayer(layerId, layerDef);
              console.log(`[LayerFactory] Created XYZ basemap: ${layerId}`);
            } else if (layerDef.source_type === 'wms_external') {
              // External WMS source (e.g., NASA FIRMS)
              layer = this._createExternalWMSLayer(layerId, layerDef);
              console.log(`[LayerFactory] Created external WMS layer: ${layerId} (WMS: ${layerDef.wms_name})`);
            } else {
              layer = this._createTileWMSLayer(layerId, layerDef);
              console.log(`[LayerFactory] Created WMS layer: ${layerId} (WMS: ${layerDef.wms_name})`);
            }
            
            layers.push(layer);
            layerCount++;
          } catch (error) {
            console.error(`[LayerFactory] Failed to create layer ${layerId}:`, error.message);
          }
        }
      }
    }

    console.log(`[LayerFactory] Created ${layerCount} layers (WMS + XYZ)`);
    return layers;
  }

  /**
   * Create an XYZ tile layer for basemaps.
   * 
   * @private
   */
  _createXYZLayer(layerId, layerDef) {
    const source = new ol.source.XYZ({
      url: layerDef.url_template,
      attributions: layerDef.attribution || ''
    });

    const layer = new ol.layer.Tile({
      source: source,
      title: layerDef.label,
      visible: false,  // Will be set by InteractionController
      opacity: layerDef.opacity !== undefined ? layerDef.opacity : 1.0
    });

    // Basemaps always at zIndex 0 (behind all thematic layers)
    layer.setZIndex(0);

    // Attach metadata for later reference
    layer.layerId = layerId;
    layer.layerDef = layerDef;
    layer.set('layerId', layerId);
    layer.set('layerDef', layerDef);
    layer.set('isBasemap', true);

    console.debug(`[LayerFactory] ${layerId}: XYZ basemap, url=${layerDef.url_template}, opacity=${layerDef.opacity || 1.0}`);

    return layer;
  }

  /**
   * Create an external WMS layer (e.g., NASA FIRMS, ESA WorldCover).
   * Uses TileWMS with the layer's wms_base_url instead of the global MapServer URL.
   * Supports configurable WMS version (1.1.1 or 1.3.0).
   * 
   * @private
   */
  _createExternalWMSLayer(layerId, layerDef) {
    const wmsUrl = layerDef.wms_base_url;
    if (!wmsUrl) {
      throw new Error(`External WMS layer ${layerId} missing wms_base_url`);
    }

    // Default to WMS 1.1.1 for better compatibility with external services
    const wmsVersion = layerDef.wms_version || '1.1.1';
    
    // Build WMS params - use SRS for 1.1.1, CRS for 1.3.0
    const params = {
      'LAYERS': layerDef.wms_name,
      'TRANSPARENT': layerDef.transparent !== false,
      'FORMAT': layerDef.format || 'image/png',
      'VERSION': wmsVersion
    };
    
    // WMS 1.1.1 uses SRS, 1.3.0 uses CRS
    if (wmsVersion === '1.1.1') {
      params['SRS'] = 'EPSG:3857';
    } else {
      params['CRS'] = 'EPSG:3857';
    }

    // Apply initial TIME param for time_enabled layers
    // Default to yesterday if no specific time_default is set
    if (layerDef.time_enabled) {
      const paramName = layerDef.time_param_name || 'TIME';
      // Use time_default if set, otherwise use yesterday (GIBS lag)
      let initialDate = layerDef.time_default;
      if (!initialDate) {
        const d = new Date();
        d.setDate(d.getDate() - 1);
        const yyyy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        initialDate = `${yyyy}-${mm}-${dd}`;
      }
      params[paramName] = initialDate;
      console.debug(`[LayerFactory] ${layerId}: Initial TIME=${initialDate}`);
    }

    const source = new ol.source.TileWMS({
      url: wmsUrl,
      params: params,
      crossOrigin: 'anonymous',
      attributions: layerDef.attribution || ''
    });

    const opacity = layerDef.opacity !== undefined ? layerDef.opacity : 1.0;
    const layer = new ol.layer.Tile({
      source: source,
      title: layerDef.label,
      visible: false,  // Will be set by InteractionController
      opacity: opacity
    });

    const zIndex = this._getLayerZIndex(layerDef);
    layer.setZIndex(zIndex);

    // Attach metadata for later reference
    layer.layerId = layerId;
    layer.layerDef = layerDef;
    layer.set('layerId', layerId);
    layer.set('layerDef', layerDef);
    layer.set('isExternalWMS', true);

    console.debug(`[LayerFactory] ${layerId}: External WMS, url=${wmsUrl}, layer=${layerDef.wms_name}, zIndex=${zIndex}`);

    return layer;
  }

  /**
   * Create a single ImageWMS layer with MapServer-compatible sizing.
   * 
   * @private
   */
  _createTileWMSLayer(layerId, layerDef) {
    // Create WMS source with stable parameters
    // Use imageLoadFunction to constrain image dimensions to MapServer limits (1-4096px)
    const source = new ol.source.ImageWMS({
      url: this.wmsBaseUrl,
      params: {
        'LAYERS': layerDef.wms_name,
        'TRANSPARENT': true,
        'FORMAT': 'image/png',  // Fixed format
        'STYLES': ''  // Default/empty
      },
      serverType: 'mapserver',  // MapServer-specific optimizations
      ratio: 1,  // Request image at exact viewport size (no over-request)
      wmsVersion: '1.3.0'  // Enable proper EPSG:4326 axis order handling (lat,lon for geographic)
    });

    // Custom image load function to enforce MapServer dimension constraints
    const originalLoadFunction = source.getImageLoadFunction();
    source.setImageLoadFunction(function(image, src) {
      // Parse URL to extract WIDTH and HEIGHT parameters
      const url = new URL(src, window.location.href);
      let width = parseInt(url.searchParams.get('WIDTH')) || 256;
      let height = parseInt(url.searchParams.get('HEIGHT')) || 256;

      // Constrain to MapServer limits (1-4096 pixels)
      const MAX_SIZE = 4096;
      if (width > MAX_SIZE || height > MAX_SIZE) {
        // Scale down proportionally
        const scale = Math.min(MAX_SIZE / width, MAX_SIZE / height);
        width = Math.floor(width * scale);
        height = Math.floor(height * scale);
        
        // Reconstruct URL with constrained dimensions
        url.searchParams.set('WIDTH', width);
        url.searchParams.set('HEIGHT', height);
        src = url.toString();
        
        console.log(`[LayerFactory] Constrained image size: ${width}x${height}px (from WMS request)`);
      }

      // Call original load function with adjusted URL
      originalLoadFunction.call(this, image, src);
    });

    // Create image layer
    const opacity = layerDef.opacity !== undefined ? layerDef.opacity : 1.0;
    const layer = new ol.layer.Image({
      source: source,
      title: layerDef.label,
      visible: false,  // Will be set by InteractionController
      opacity: opacity
    });

    const zIndex = this._getLayerZIndex(layerDef);
    layer.setZIndex(zIndex);

    // Attach metadata for later reference
    layer.layerId = layerId;
    layer.layerDef = layerDef;
    layer.set('layerId', layerId);
    layer.set('layerDef', layerDef);

    // Log WMS request parameters for debugging
    console.debug(`[LayerFactory] ${layerId}: WMS params = LAYERS:${layerDef.wms_name}, FORMAT:image/png, TRANSPARENT:true, ratio:1 (constrained to 4096px max)`);

    return layer;
  }

  _getLayerZIndex(layerDef) {
    // Explicit z_index from registry takes priority
    if (typeof layerDef.z_index === 'number') {
      return layerDef.z_index;
    }

    // Basemaps always at bottom
    if (layerDef.base_layer) {
      return 0;
    }

    // External WMS overlays (e.g., NASA FIRMS)
    if (layerDef.source_type === 'wms_external') {
      return 5;
    }

    const layerType = (layerDef.type || '').toLowerCase();
    const geometryType = (layerDef.geometry_type || '').toLowerCase();

    // Rasters above basemaps (TSIRD rasters at 10)
    if (layerType === 'raster') {
      return 10;
    }

    // UI/overlay layers at top
    if (layerType === 'grid' || layerType === 'overlay' || layerType === 'ui') {
      return 45;
    }

    // Lines above polygons
    if (geometryType === 'linestring' || geometryType === 'line') {
      return 25;
    }

    // Points at top of thematic layers
    if (geometryType === 'point') {
      return 35;
    }

    // Polygons (default vector)
    return 15;
  }

  /**
   * Get all created layers (for testing/debugging).
   */
  getLayers() {
    return this._allLayers || [];
  }

  /**
   * Create and store reference to all layers.
   */
  setAllLayers(layers) {
    this._allLayers = layers;
  }
}

// Export for use in main.js
if (typeof module !== 'undefined' && module.exports) {
  module.exports = LayerFactory;
}
