/**
 * MeasureControl — Distance and area measurement toolbar buttons.
 * NOT an ol.control.Control — renders directly into the toolbar div.
 */
class MeasureControl {
  /**
   * @param {HTMLElement} toolbar  — the shared .tsird-phase3-toolbar div
   * @param {ol.Map}      map
   */
  constructor(toolbar, map) {
    this._measureTool = new MeasureTool(map);

    var btnDist = document.createElement('button');
    btnDist.className = 'tsird-toolbar-btn';
    btnDist.textContent = '📏 Dist';
    btnDist.title = 'Measure distance';

    var btnArea = document.createElement('button');
    btnArea.className = 'tsird-toolbar-btn';
    btnArea.textContent = '▭ Area';
    btnArea.title = 'Measure area';

    var btnClear = document.createElement('button');
    btnClear.className = 'tsird-toolbar-btn';
    btnClear.textContent = '✕ Clear';
    btnClear.title = 'Clear measurements';

    toolbar.appendChild(btnDist);
    toolbar.appendChild(btnArea);
    toolbar.appendChild(btnClear);

    var self = this;
    btnDist.addEventListener('click', function() {
      btnDist.classList.add('active');
      btnArea.classList.remove('active');
      self._measureTool.activate('LineString');
    });
    btnArea.addEventListener('click', function() {
      btnArea.classList.add('active');
      btnDist.classList.remove('active');
      self._measureTool.activate('Polygon');
    });
    btnClear.addEventListener('click', function() {
      btnDist.classList.remove('active');
      btnArea.classList.remove('active');
      self._measureTool.clear();
    });
  }
}
