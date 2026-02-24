/**
 * LayerFactory — Create OpenLayers TileWMS layers from registry
 * 
 * Responsibilities:
 *   - Create TileWMS sources only (no WFS)
 *   - Use stable WMS parameters (FORMAT, TRANSPARENT, etc.)
 *   - Store layer metadata for later reference (GetFeatureInfo, scale rules, etc.)
 *   - Respect published flag (skip unpublished)
 *   - Maintain YAML order
 * 
 * Contract:
 *   - Returns array of ol.layer.Tile objects in YAML order
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
   * Create all TileWMS layers from registry.
   * Respects published flag and YAML order.
   * 
   * @returns {Array<ol.layer.Tile>} Ordered array of TileWMS layers
   */
  createLayers() {
    console.log('[LayerFactory] Creating TileWMS layers...');

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
            const layer = this._createTileWMSLayer(layerId, layerDef);
            layers.push(layer);
            layerCount++;

            console.log(`[LayerFactory] Created layer: ${layerId} (WMS: ${layerDef.wms_name})`);
          } catch (error) {
            console.error(`[LayerFactory] Failed to create layer ${layerId}:`, error.message);
          }
        }
      }
    }

    console.log(`[LayerFactory] Created ${layerCount} TileWMS layers`);
    return layers;
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
      ratio: 1  // Request image at exact viewport size (no over-request)
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
    const layer = new ol.layer.Image({
      source: source,
      title: layerDef.label,
      visible: false  // Will be set by InteractionController
    });

    // Attach metadata for later reference
    layer.layerId = layerId;
    layer.layerDef = layerDef;

    // Log WMS request parameters for debugging
    console.debug(`[LayerFactory] ${layerId}: WMS params = LAYERS:${layerDef.wms_name}, FORMAT:image/png, TRANSPARENT:true, ratio:1 (constrained to 4096px max)`);

    return layer;
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
