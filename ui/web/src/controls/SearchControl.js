/**
 * SearchControl — horizontal toolbar widget for bilingual gazetteer search.
 * NOT an ol.control.Control — renders directly into the toolbar div.
 * Queries /map/api/gazetteer?q=...
 */
class SearchControl {
  /**
   * @param {HTMLElement} toolbar  — the shared .tsird-phase3-toolbar div
   * @param {ol.Map}      map
   */
  constructor(toolbar, map) {
    this._map = map;
    this._results = [];
    this._activeIdx = -1;
    this._debounceTimer = null;

    // Widget container
    var widget = document.createElement('div');
    widget.className = 'tsird-search-widget';

    var input = document.createElement('input');
    input.type = 'text';
    input.placeholder = 'Search Woreda or Tabia…';
    input.className = 'tsird-search-input';
    input.setAttribute('autocomplete', 'off');

    var dropdown = document.createElement('div');
    dropdown.className = 'tsird-search-results';
    dropdown.style.display = 'none';

    widget.appendChild(input);
    widget.appendChild(dropdown);
    toolbar.appendChild(widget);

    this._input = input;
    this._dropdown = dropdown;

    var self = this;

    input.addEventListener('input', function() {
      clearTimeout(self._debounceTimer);
      var q = input.value.trim();
      if (!q) {
        self._close();
        HighlightOverlay.clear();
        return;
      }
      self._debounceTimer = setTimeout(function() {
        self._search(q);
      }, 200);
    });

    input.addEventListener('keydown', function(e) {
      if (e.key === 'ArrowDown') {
        self._activeIdx = Math.min(self._activeIdx + 1, self._results.length - 1);
        self._render(); e.preventDefault();
      } else if (e.key === 'ArrowUp') {
        self._activeIdx = Math.max(self._activeIdx - 1, 0);
        self._render(); e.preventDefault();
      } else if (e.key === 'Enter') {
        if (self._results[self._activeIdx]) self._select(self._results[self._activeIdx]);
      } else if (e.key === 'Escape') {
        self._close();
        HighlightOverlay.clear();
      }
    });

    document.addEventListener('click', function(e) {
      if (!widget.contains(e.target)) {
        self._close();
      }
    });
  }

  async _search(query) {
    try {
      var resp = await fetch('/map/api/gazetteer?q=' + encodeURIComponent(query));
      if (!resp.ok) throw new Error('API ' + resp.status);
      this._results = await resp.json();
      this._activeIdx = -1;
      this._render();
    } catch (err) {
      console.warn('[SearchControl] Search failed:', err.message);
      this._results = [];
      this._render();
    }
  }

  _render() {
    var dropdown = this._dropdown;
    dropdown.innerHTML = '';
    if (!this._results.length) {
      dropdown.style.display = 'block';
      var noMatch = document.createElement('div');
      noMatch.className = 'item';
      noMatch.style.color = '#999';
      noMatch.textContent = 'No matches';
      dropdown.appendChild(noMatch);
      return;
    }
    var self = this;
    this._results.forEach(function(r, i) {
      var item = document.createElement('div');
      item.className = 'item' + (i === self._activeIdx ? ' active' : '');
      var typeLabel = r.type === 'woreda' ? 'Woreda' : 'Tabia';
      item.textContent = r.name_en + ' (' + r.name_ti + ') \u2014 ' + typeLabel;
      item.addEventListener('mousedown', function(e) {
        e.preventDefault();
        self._select(r);
      });
      dropdown.appendChild(item);
    });
    dropdown.style.display = 'block';
  }

  _select(record) {
    var typeLabel = record.type === 'woreda' ? 'Woreda' : 'Tabia';
    this._input.value = record.name_en + ' (' + record.name_ti + ') \u2014 ' + typeLabel;
    // Clear previous highlight before drawing new one
    HighlightOverlay.clear();
    this._close();
    if (!record.bbox) return;
    var extent3857 = ol.proj.transformExtent(record.bbox, 'EPSG:4326', 'EPSG:3857');
    // Tabias are small — use more padding and cap zoom so context remains visible
    var fitOptions = record.type === 'tabia'
      ? { padding: [80, 80, 80, 80], maxZoom: 12, duration: 400 }
      : { padding: [40, 40, 40, 40], duration: 400 };
    this._map.getView().fit(extent3857, fitOptions);
    HighlightOverlay.show(record.bbox);
    // Keep other tools decoupled from the search widget while letting them
    // consume the canonical gazetteer identity.  In particular, the drought
    // evidence-history view uses a Tabia's stable TSIRD ID rather than a name.
    window.dispatchEvent(new CustomEvent('tsird:boundary-selected', {
      detail: {
        type: record.type,
        id: record.id,
        name_en: record.name_en || '',
        name_ti: record.name_ti || ''
      }
    }));
  }

  _close() {
    this._dropdown.style.display = 'none';
    this._dropdown.innerHTML = '';
    this._results = [];
    this._activeIdx = -1;
  }
}
