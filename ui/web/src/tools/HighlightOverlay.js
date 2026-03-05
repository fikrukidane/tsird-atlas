/**
 * HighlightOverlay.js — Highlight bbox rectangle on map
 */

const HighlightOverlay = {
  /**
   * Create a vector layer for highlighting.
   * 
   * @returns {ol.layer.Vector} Highlight layer
   */
  createHighlightLayer() {
    const source = new ol.source.Vector();
    
    const layer = new ol.layer.Vector({
      source: source,
      style: new ol.style.Style({
        stroke: new ol.style.Stroke({
          color: 'rgba(255, 140, 0, 1)',
          width: 3
        }),
        fill: new ol.style.Fill({
          color: 'rgba(255, 165, 0, 0.2)'
        })
      }),
      zIndex: 1000 // Above other layers
    });

    layer.set('name', 'highlight-overlay');
    return layer;
  },

  /**
   * Highlight a bbox on the map.
   * 
   * @param {ol.layer.Vector} layer - Highlight layer
   * @param {number[]} bbox4326 - [minx, miny, maxx, maxy] in EPSG:4326
   * @param {string} mapProjection - Map projection (e.g., 'EPSG:3857')
   */
  highlightBBox(layer, bbox4326, mapProjection) {
    if (!layer || !bbox4326 || bbox4326.length !== 4) {
      console.warn('[HighlightOverlay] Invalid layer or bbox');
      return;
    }

    // Clear previous highlight
    this.clearHighlight(layer);

    // Transform extent to map projection
    const extent = ol.proj.transformExtent(
      bbox4326,
      'EPSG:4326',
      mapProjection
    );

    // Create polygon from extent
    const polygon = ol.geom.Polygon.fromExtent(extent);
    const feature = new ol.Feature({
      geometry: polygon,
      name: 'highlight'
    });

    layer.getSource().addFeature(feature);
    console.log('[HighlightOverlay] Highlighted bbox:', bbox4326);
  },

  /**
   * Clear all highlight features.
   * 
   * @param {ol.layer.Vector} layer - Highlight layer
   */
  clearHighlight(layer) {
    if (layer && layer.getSource()) {
      layer.getSource().clear();
    }
  }
};

// Export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = HighlightOverlay;
} else if (typeof window !== 'undefined') {
  window.HighlightOverlay = HighlightOverlay;
}
