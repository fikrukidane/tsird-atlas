/**
 * MeasureTool.js — Distance and area measurement
 */

const MeasureTool = {
  _layer: null,
  _source: null,
  _draw: null,
  _mode: 'none', // 'none' | 'distance' | 'area'
  _map: null,
  _lastMeasurement: null,
  _onMeasureCallback: null,

  /**
   * Initialize the measurement tool.
   * 
   * @param {ol.Map} map - OpenLayers map instance
   * @param {Function} [onMeasure] - Callback when measurement completes
   */
  init(map, onMeasure) {
    if (!map) {
      console.error('[MeasureTool] Map instance required');
      return;
    }

    this._map = map;
    this._onMeasureCallback = onMeasure;

    // Create vector source and layer
    this._source = new ol.source.Vector();
    this._layer = new ol.layer.Vector({
      source: this._source,
      style: new ol.style.Style({
        fill: new ol.style.Fill({
          color: 'rgba(66, 133, 244, 0.2)'
        }),
        stroke: new ol.style.Stroke({
          color: '#4285f4',
          width: 2
        }),
        image: new ol.style.Circle({
          radius: 5,
          fill: new ol.style.Fill({
            color: '#4285f4'
          })
        })
      }),
      zIndex: 1001
    });

    this._layer.set('name', 'measure-layer');
    map.addLayer(this._layer);

    console.log('[MeasureTool] Initialized');
  },

  /**
   * Get the measurement layer.
   */
  getLayer() {
    return this._layer;
  },

  /**
   * Set measurement mode.
   * 
   * @param {'none' | 'distance' | 'area'} mode
   */
  setMode(mode) {
    // Remove existing draw interaction
    if (this._draw) {
      this._map.removeInteraction(this._draw);
      this._draw = null;
    }

    this._mode = mode;

    if (mode === 'none') {
      console.log('[MeasureTool] Mode: none');
      return;
    }

    // Create draw interaction
    const type = mode === 'distance' ? 'LineString' : 'Polygon';

    this._draw = new ol.interaction.Draw({
      source: this._source,
      type: type,
      style: new ol.style.Style({
        fill: new ol.style.Fill({
          color: 'rgba(66, 133, 244, 0.2)'
        }),
        stroke: new ol.style.Stroke({
          color: '#4285f4',
          width: 2,
          lineDash: [5, 5]
        }),
        image: new ol.style.Circle({
          radius: 5,
          fill: new ol.style.Fill({
            color: '#4285f4'
          })
        })
      })
    });

    this._draw.on('drawend', (event) => {
      this._handleDrawEnd(event);
    });

    this._map.addInteraction(this._draw);
    console.log(`[MeasureTool] Mode: ${mode}`);
  },

  /**
   * Handle draw end event.
   */
  _handleDrawEnd(event) {
    const geom = event.feature.getGeometry();
    let measurement;

    if (this._mode === 'distance') {
      // Geodesic length
      const length = ol.sphere.getLength(geom, { projection: 'EPSG:3857' });
      measurement = {
        type: 'distance',
        value: length,
        formatted: this._formatLength(length)
      };
    } else if (this._mode === 'area') {
      // Geodesic area
      const area = ol.sphere.getArea(geom, { projection: 'EPSG:3857' });
      measurement = {
        type: 'area',
        value: area,
        formatted: this._formatArea(area)
      };
    }

    this._lastMeasurement = measurement;
    console.log('[MeasureTool] Measurement:', measurement.formatted);

    if (this._onMeasureCallback) {
      this._onMeasureCallback(measurement);
    }
  },

  /**
   * Format length for display.
   */
  _formatLength(length) {
    if (length > 1000) {
      return (length / 1000).toFixed(2) + ' km';
    }
    return length.toFixed(0) + ' m';
  },

  /**
   * Format area for display.
   */
  _formatArea(area) {
    if (area > 1000000) {
      return (area / 1000000).toFixed(2) + ' km²';
    } else if (area > 10000) {
      return (area / 10000).toFixed(2) + ' ha';
    }
    return area.toFixed(0) + ' m²';
  },

  /**
   * Clear all measurements.
   */
  clear() {
    if (this._source) {
      this._source.clear();
    }
    this._lastMeasurement = null;
    console.log('[MeasureTool] Cleared');
    
    if (this._onMeasureCallback) {
      this._onMeasureCallback(null);
    }
  },

  /**
   * Get current mode.
   */
  getMode() {
    return this._mode;
  },

  /**
   * Get last measurement.
   */
  getLastMeasurement() {
    return this._lastMeasurement;
  }
};

// Export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = MeasureTool;
} else if (typeof window !== 'undefined') {
  window.MeasureTool = MeasureTool;
}
