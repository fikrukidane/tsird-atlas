/**
 * MeasureTool — Measurement interactions using global `ol`.
 * Plain browser global class.
 */
class MeasureTool {
  constructor(map) {
    this.map = map;
    this.draw = null;
    this.source = new ol.source.Vector();
    this.layer = new ol.layer.Vector({
      source: this.source,
      style: new ol.style.Style({
        stroke: new ol.style.Stroke({ color: '#3399CC', width: 2 }),
        fill: new ol.style.Fill({ color: 'rgba(51,153,204,0.2)' })
      }),
      zIndex: 998
    });
    map.addLayer(this.layer);
    var tooltipEl = document.createElement('div');
    tooltipEl.style.cssText = 'background:rgba(0,0,0,0.75);color:#fff;padding:3px 8px;border-radius:4px;font-size:12px;pointer-events:none;';
    this.tooltipOverlay = new ol.Overlay({ element: tooltipEl, offset: [0,-15], positioning: 'bottom-center' });
    map.addOverlay(this.tooltipOverlay);
    this.tooltipEl = tooltipEl;
  }

  activate(type) {
    this.deactivate();
    this.source.clear();
    this.draw = new ol.interaction.Draw({ source: this.source, type: type });
    var self = this;
    this.draw.on('drawstart', function(evt) {
      evt.feature.getGeometry().on('change', function(e) {
        var geom = e.target;
        var output = '', coord;
        if (geom instanceof ol.geom.Polygon) {
          output = self._fmtArea(geom);
          coord = geom.getInteriorPoint().getCoordinates();
        } else if (geom instanceof ol.geom.LineString) {
          output = self._fmtLen(geom);
          coord = geom.getLastCoordinate();
        }
        self.tooltipEl.textContent = output;
        self.tooltipOverlay.setPosition(coord);
      });
    });
    this.draw.on('drawend', function() { self.tooltipOverlay.setPosition(undefined); });
    this.map.addInteraction(this.draw);
  }

  deactivate() {
    if (this.draw) { this.map.removeInteraction(this.draw); this.draw = null; }
    this.tooltipOverlay.setPosition(undefined);
  }

  clear() { this.deactivate(); this.source.clear(); }

  _fmtLen(line) {
    var m = ol.sphere.getLength(line);
    return m > 1000 ? (Math.round(m/100)/10) + ' km' : Math.round(m) + ' m';
  }

  _fmtArea(polygon) {
    var a = ol.sphere.getArea(polygon);
    return a > 1000000 ? (Math.round(a/100000)/10) + ' km²' : Math.round(a) + ' m²';
  }
}
