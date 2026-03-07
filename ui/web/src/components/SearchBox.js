/**
 * SearchBox.js — Autocomplete search for Woredas and Tabias
 */

const SearchBox = {
  _container: null,
  _input: null,
  _dropdown: null,
  _map: null,
  _highlightLayer: null,
  _debounceTimer: null,
  _selectedIndex: -1,
  _results: [],

  /**
   * Create the search box UI.
   * 
   * @param {ol.Map} map - OpenLayers map instance
   * @param {ol.layer.Vector} highlightLayer - Highlight layer for bbox
   * @param {string} [containerId] - Container element ID
   */
  create(map, highlightLayer, containerId) {
    if (!map) {
      console.error('[SearchBox] Map instance required');
      return;
    }

    this._map = map;
    this._highlightLayer = highlightLayer;

    // Create container
    const container = document.createElement('div');
    container.className = 'phase3-search-box';
    container.innerHTML = `
      <input type="text" 
             class="search-input" 
             placeholder="Search Woreda or Tabia…" 
             autocomplete="off" />
      <div class="search-dropdown hidden"></div>
    `;

    this._input = container.querySelector('.search-input');
    this._dropdown = container.querySelector('.search-dropdown');
    this._container = container;

    // Event listeners
    this._input.addEventListener('input', (e) => this._handleInput(e));
    this._input.addEventListener('keydown', (e) => this._handleKeydown(e));
    this._input.addEventListener('blur', () => {
      // Delay to allow click on dropdown
      setTimeout(() => this._hideDropdown(), 200);
    });
    this._input.addEventListener('focus', () => {
      if (this._results.length > 0) {
        this._showDropdown();
      }
    });

    // Find or create parent container
    let parent = containerId ? document.getElementById(containerId) : null;
    if (!parent) {
      parent = document.querySelector('.phase3-tools-container');
      if (!parent) {
        parent = document.createElement('div');
        parent.className = 'phase3-tools-container';
        const mapEl = document.getElementById('map');
        if (mapEl && mapEl.parentNode) {
          mapEl.parentNode.insertBefore(parent, mapEl);
        }
      }
    }

    // Insert search at the beginning
    parent.insertBefore(container, parent.firstChild);

    console.log('[SearchBox] Created');
  },

  /**
   * Handle input event with debounce.
   */
  _handleInput(e) {
    const query = e.target.value.trim();

    // Clear existing timer
    if (this._debounceTimer) {
      clearTimeout(this._debounceTimer);
    }

    // Debounce 200ms
    this._debounceTimer = setTimeout(() => {
      this._search(query);
    }, 200);
  },

  /**
   * Perform search.
   */
  _search(query) {
    if (query.length < 2) {
      this._hideDropdown();
      this._results = [];
      return;
    }

    const results = GazetteerSearchService.search(query, { limit: 10 });
    this._results = results;
    this._selectedIndex = -1;

    if (results.length === 0) {
      this._showNoResults();
    } else {
      this._renderResults(results);
    }
  },

  /**
   * Render search results.
   */
  _renderResults(results) {
    const html = results.map((r, idx) => {
      const typeLabel = r.type === 'woreda' ? 'Woreda' : 'Tabia';
      const parentInfo = r.type === 'tabia' && r.parent?.woreda_id 
        ? ` (${r.parent.woreda_id})` 
        : '';
      
      return `
        <div class="search-result" data-index="${idx}">
          <span class="result-name">${this._escapeHtml(r.name)}</span>
          <span class="result-type">${typeLabel}${parentInfo}</span>
        </div>
      `;
    }).join('');

    this._dropdown.innerHTML = html;
    this._showDropdown();

    // Add click handlers
    this._dropdown.querySelectorAll('.search-result').forEach(el => {
      el.addEventListener('click', () => {
        const idx = parseInt(el.dataset.index, 10);
        this._selectResult(this._results[idx]);
      });
    });
  },

  /**
   * Show "No matches" message.
   */
  _showNoResults() {
    this._dropdown.innerHTML = '<div class="search-no-results">No matches</div>';
    this._showDropdown();
  },

  /**
   * Handle keyboard navigation.
   */
  _handleKeydown(e) {
    if (this._results.length === 0) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        this._moveSelection(1);
        break;
      case 'ArrowUp':
        e.preventDefault();
        this._moveSelection(-1);
        break;
      case 'Enter':
        e.preventDefault();
        if (this._selectedIndex >= 0 && this._selectedIndex < this._results.length) {
          this._selectResult(this._results[this._selectedIndex]);
        }
        break;
      case 'Escape':
        this._hideDropdown();
        this._input.blur();
        break;
    }
  },

  /**
   * Move selection up/down.
   */
  _moveSelection(delta) {
    const items = this._dropdown.querySelectorAll('.search-result');
    if (items.length === 0) return;

    // Clear current selection
    items.forEach(el => el.classList.remove('selected'));

    // Calculate new index
    this._selectedIndex += delta;
    if (this._selectedIndex < 0) this._selectedIndex = items.length - 1;
    if (this._selectedIndex >= items.length) this._selectedIndex = 0;

    // Apply selection
    items[this._selectedIndex].classList.add('selected');
  },

  /**
   * Select a result and zoom.
   */
  _selectResult(result) {
    if (!result) return;

    console.log('[SearchBox] Selected:', result.name);

    // Clear input and dropdown
    this._input.value = result.name;
    this._hideDropdown();

    // Zoom to bbox
    if (result.bbox && result.bbox.length === 4) {
      const view = this._map.getView();
      const projection = view.getProjection().getCode();
      const extent = ol.proj.transformExtent(result.bbox, 'EPSG:4326', projection);

      view.fit(extent, {
        padding: [50, 50, 50, 50],
        duration: 500
      });

      // Highlight bbox
      if (this._highlightLayer) {
        HighlightOverlay.highlightBBox(this._highlightLayer, result.bbox, projection);
      }
    } else if (result.center && result.center.length === 2) {
      // Fallback to center point
      const view = this._map.getView();
      const center = ol.proj.fromLonLat(result.center);
      view.animate({
        center: center,
        zoom: 13,
        duration: 500
      });
    }
  },

  _showDropdown() {
    this._dropdown.classList.remove('hidden');
  },

  _hideDropdown() {
    this._dropdown.classList.add('hidden');
    this._selectedIndex = -1;
  },

  _escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
};

// Export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = SearchBox;
} else if (typeof window !== 'undefined') {
  window.SearchBox = SearchBox;
}
