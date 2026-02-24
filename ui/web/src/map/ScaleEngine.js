/**
 * ScaleEngine — Cartographic scale calculations and layer visibility rules
 * 
 * Milestone 2.1: Foundation for scale-dependent rendering
 * 
 * Responsibilities:
 *   - Convert OpenLayers resolution to cartographic scale denominator
 *   - Determine if a layer should be visible at current scale
 *   - Use consistent scale approximation formula
 * 
 * Convention (frozen):
 *   - min_scale: Largest denominator (most zoomed out)
 *   - max_scale: Smallest denominator (most zoomed in)
 *   - Layer visible if: max_scale <= current_scale <= min_scale
 * 
 * Example:
 *   Layer with min_scale=10000000, max_scale=1000000
 *   - Visible from 1:10M (zoomed out) to 1:1M (zoomed in)
 *   - At 1:5M (current_scale=5000000): VISIBLE
 *   - At 1:500K (current_scale=500000): NOT VISIBLE (too zoomed in)
 *   - At 1:20M (current_scale=20000000): NOT VISIBLE (too zoomed out)
 */

class ScaleEngine {
  /**
   * Convert OpenLayers resolution to cartographic scale denominator.
   * 
   * Formula: scale = resolution * meters_per_pixel
   * Assumes 96 DPI (standard web browser default)
   * 
   * @param {number} resolution - OL resolution in meters per pixel
   * @returns {number} Cartographic scale denominator (e.g., 1000000 = 1:1M)
   */
  static getScaleDenominator(resolution) {
    // Dots per meter at 96 DPI: 96 / 0.0254 ≈ 3779.53
    const dotsPerMeter = 96 / 0.0254;
    return resolution * dotsPerMeter;
  }

  /**
   * Check if a layer should be visible at the current scale.
   * 
   * Uses frozen convention: max_scale <= current_scale <= min_scale
   * 
   * @param {Object} layerDef - Layer definition from registry (must have min_scale, max_scale)
   * @param {number} currentScale - Current cartographic scale denominator
   * @returns {boolean} True if layer should be visible at this scale
   */
  static isLayerInScale(layerDef, currentScale) {
    // If layer has no scale constraints, always visible
    if (!layerDef.min_scale || !layerDef.max_scale) {
      return true;
    }

    const minScale = layerDef.min_scale;  // Largest denominator (zoomed out)
    const maxScale = layerDef.max_scale;  // Smallest denominator (zoomed in)

    // Layer visible if scale is within bounds
    return currentScale >= maxScale && currentScale <= minScale;
  }

  /**
   * Get the current scale denominator from the map view.
   * 
   * @param {ol.View} view - OpenLayers View object
   * @returns {number} Current cartographic scale denominator
   */
  static getCurrentScale(view) {
    const resolution = view.getResolution();
    return ScaleEngine.getScaleDenominator(resolution);
  }

  /**
   * Check if a layer is in scale given the current view.
   * 
   * @param {Object} layerDef - Layer definition from registry
   * @param {ol.View} view - OpenLayers View object
   * @returns {boolean} True if layer should be visible at current scale
   */
  static isLayerInScaleForView(layerDef, view) {
    const currentScale = ScaleEngine.getCurrentScale(view);
    return ScaleEngine.isLayerInScale(layerDef, currentScale);
  }

  /**
   * Get human-readable scale string (e.g., "1:5,000,000")
   * 
   * @param {number} scale - Cartographic scale denominator
   * @returns {string} Formatted scale string
   */
  static formatScale(scale) {
    return `1:${Math.round(scale).toLocaleString()}`;
  }

  /**
   * Get scale range string for a layer (e.g., "1:10M - 1:1M")
   * 
   * @param {Object} layerDef - Layer definition with min_scale, max_scale
   * @returns {string} Human-readable scale range
   */
  static formatScaleRange(layerDef) {
    if (!layerDef.min_scale || !layerDef.max_scale) {
      return 'All scales';
    }

    const minScaleStr = ScaleEngine.formatScale(layerDef.min_scale);
    const maxScaleStr = ScaleEngine.formatScale(layerDef.max_scale);
    return `${maxScaleStr} - ${minScaleStr}`;
  }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
  module.exports = ScaleEngine;
}

