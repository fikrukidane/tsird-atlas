/**
 * HighlightOverlay — Draws a bbox highlight on the map.
 * Plain browser global. Uses global `ol`.
 */
var HighlightOverlay = (function() {
  var source = null;

  function init(map) {
    source = new ol.source.Vector();
    var layer = new ol.layer.Vector({
      source: source,
      style: new ol.style.Style({
        stroke: new ol.style.Stroke({ color: '#FF8C00', width: 3 }),
        fill: new ol.style.Fill({ color: 'rgba(255, 140, 0, 0.15)' })
      }),
      zIndex: 999
    });
    map.addLayer(layer);
  }

  function show(bbox) {
    if (!source) return;
    source.clear();
    var extent3857 = ol.proj.transformExtent(bbox, 'EPSG:4326', 'EPSG:3857');
    source.addFeature(new ol.Feature(ol.geom.Polygon.fromExtent(extent3857)));
  }

  function clear() { if (source) source.clear(); }

  return { init: init, show: show, clear: clear };
})();
