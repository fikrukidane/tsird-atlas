/**
 * extents.js — Geographic extent constants
 */

const Extents = {
  /**
   * TSIRD full extent in EPSG:4326 [minx, miny, maxx, maxy]
   * Covers Tigray region with buffer
   */
  TSIRD_FULL_EXTENT_4326: [36.3, 12.2, 40.3, 14.9],

  /**
   * Get full extent transformed to a target projection.
   * 
   * @param {string} targetProjection - e.g., 'EPSG:3857'
   * @returns {number[]} Transformed extent
   */
  getFullExtent(targetProjection) {
    return ol.proj.transformExtent(
      this.TSIRD_FULL_EXTENT_4326,
      'EPSG:4326',
      targetProjection
    );
  }
};

// Export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = Extents;
} else if (typeof window !== 'undefined') {
  window.Extents = Extents;
}
