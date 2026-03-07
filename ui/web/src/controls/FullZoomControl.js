/**
 * FullZoomControl — compact toolbar button that fits the map to the full Tigray extent.
 * NOT an ol.control.Control — renders directly into the toolbar div.
 */
class FullZoomControl {
  /**
   * @param {HTMLElement} toolbar  — the shared .tsird-phase3-toolbar div
   * @param {ol.Map}      map
   */
  constructor(toolbar, map) {
    this._map = map;

    var btn = document.createElement('button');
    btn.className = 'tsird-toolbar-btn';
    btn.title = 'Zoom to full Tigray extent';
    btn.textContent = '⛶ Full';

    toolbar.appendChild(btn);

    var self = this;
    btn.addEventListener('click', function() {
      var extent3857 = ol.proj.transformExtent(
        TSIRD_FULL_EXTENT_4326, 'EPSG:4326', 'EPSG:3857'
      );
      self._map.getView().fit(extent3857, { padding: [40, 40, 40, 40], duration: 400 });
      HighlightOverlay.clear();
    });
  }
}
