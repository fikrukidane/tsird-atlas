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
   * Create a single TileWMS layer.
   * 
   * @private
   */
  _createTileWMSLayer(layerId, layerDef) {
    // Create WMS source with stable parameters
    const source = new ol.source.TileWMS({
      url: this.wmsBaseUrl,
      params: {
        'LAYERS': layerDef.wms_name,
        'TILED': true,
        'TRANSPARENT': true,
        'FORMAT': 'image/png',  // Fixed format
        'STYLES': ''  // Default/empty
      },
      serverType: 'mapserver'  // MapServer-specific optimizations
    });

    // Create tile layer
    const layer = new ol.layer.Tile({
      source: source,
      title: layerDef.label,
      visible: false  // Will be set by InteractionController
    });

    // Attach metadata for later reference
    layer.layerId = layerId;
    layer.layerDef = layerDef;

    // Log WMS request parameters for debugging
    console.debug(`[LayerFactory] ${layerId}: WMS params = LAYERS:${layerDef.wms_name}, FORMAT:image/png, TRANSPARENT:true, TILED:true`);

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
