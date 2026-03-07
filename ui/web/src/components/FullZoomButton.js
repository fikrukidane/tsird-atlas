/**
 * FullZoomButton.js — Fit map to TSIRD full extent
 */

const FullZoomButton = {
  _button: null,

  /**
   * Create and attach the Full Zoom button.
   * 
   * @param {ol.Map} map - OpenLayers map instance
   * @param {string} [containerId] - Container element ID
   */
  create(map, containerId) {
    if (!map) {
      console.error('[FullZoomButton] Map instance required');
      return;
    }

    // Create button element
    const button = document.createElement('button');
    button.innerHTML = '🔲';
    button.title = 'Fit to Full Extent';
    button.className = 'phase3-tool-btn full-zoom-btn';
    button.type = 'button';

    button.addEventListener('click', () => {
      this._zoomToFullExtent(map);
    });

    // Find or create container
    let container = containerId ? document.getElementById(containerId) : null;
    if (!container) {
      container = document.createElement('div');
      container.className = 'phase3-tools-container';
      const mapEl = document.getElementById('map');
      if (mapEl && mapEl.parentNode) {
        mapEl.parentNode.appendChild(container);
      } else {
        document.body.appendChild(container);
      }
    }

    container.appendChild(button);
    this._button = button;

    console.log('[FullZoomButton] Created');
  },

  /**
   * Zoom to TSIRD full extent.
   */
  _zoomToFullExtent(map) {
    const view = map.getView();
    const projection = view.getProjection().getCode();
    const extent = Extents.getFullExtent(projection);

    view.fit(extent, {
      padding: [30, 30, 30, 30],
      duration: 500
    });

    console.log('[FullZoomButton] Zoomed to full extent');
  }
};

// Export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = FullZoomButton;
} else if (typeof window !== 'undefined') {
  window.FullZoomButton = FullZoomButton;
}
