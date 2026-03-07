/**
 * NavigatorMap.js — Overview mini map (top-right inset)
 */

const NavigatorMap = {
  _control: null,

  /**
   * Add overview map control to the map.
   * 
   * @param {ol.Map} map - OpenLayers map instance
   * @param {Object} [options] - Options
   * @param {boolean} [options.collapsed=false] - Start collapsed
   */
  add(map, options = {}) {
    if (!map) {
      console.error('[NavigatorMap] Map instance required');
      return;
    }

    const collapsed = options.collapsed === true;

    // Create overview map with OSM layer
    this._control = new ol.control.OverviewMap({
      className: 'ol-overviewmap phase3-overview',
      collapsed: collapsed,
      collapsible: true,
      tipLabel: 'Navigator Map',
      layers: [
        new ol.layer.Tile({
          source: new ol.source.OSM()
        })
      ],
      view: new ol.View({
        projection: map.getView().getProjection()
      })
    });

    map.addControl(this._control);
    console.log('[NavigatorMap] Added overview map control');
  },

  /**
   * Get the overview map control.
   */
  getControl() {
    return this._control;
  },

  /**
   * Expand the overview map.
   */
  expand() {
    if (this._control) {
      this._control.setCollapsed(false);
    }
  },

  /**
   * Collapse the overview map.
   */
  collapse() {
    if (this._control) {
      this._control.setCollapsed(true);
    }
  }
};

// Export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = NavigatorMap;
} else if (typeof window !== 'undefined') {
  window.NavigatorMap = NavigatorMap;
}
