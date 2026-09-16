/**
 * InteractionController — Manage user interactions
 * 
 * Milestone 1: TOC rendering + per-layer toggle
 * Milestone 2: Scale enforcement + mutex pairs + GetFeatureInfo
 * 
 * Responsibilities:
 *   - Render TOC from tocModel hierarchy
 *   - Implement layer toggle (checkbox → visibility)
 *   - Apply default visibility from registry (at startup)
 *   - Implement group toggle (optional)
 *   - Enforce scale-dependent visibility (Milestone 2)
 *   - Enforce mutex pairs (roads/towns) (Milestone 2)
 *   - Handle GetFeatureInfo on map click (Milestone 2)
 */

class InteractionController {
  constructor(tocContainerId, layers, tocModel, layerDefs, mapController, scaleMutexPairs = []) {
    this.tocContainerId = tocContainerId;
    this.layers = layers;  // Array of ol.layer.Tile objects
    this.olLayers = layers;  // Alias for opacity updates
    this.tocModel = tocModel;  // Hierarchy: categories → groups → layers
    this.layerDefs = layerDefs;  // Metadata: { [id]: { ... } }
    this.mapController = mapController;  // MapController instance (Milestone 2)
    this.scaleMutexPairs = scaleMutexPairs;  // Scale mutex pairs from registry (Milestone 2)
    
    // Map layer ID to ol.Layer for quick lookup
    this.layerMap = {};
    layers.forEach(layer => {
      this.layerMap[layer.layerId] = layer;
    });

    this.tocElement = null;
    
    // Track user-requested visibility state (separate from scale/mutex constraints)
    this.userVisibilityState = {};  // { layerId: boolean }
    layers.forEach(layer => {
      this.userVisibilityState[layer.layerId] = layer.layerDef.default_visible || false;
    });

    this.defaultGroupIds = new Set([
      'grp_tigrai_tabias_new',
      'grp_towns',
      'grp_tigray_roads_2006',
      'grp_sample_grid',
      'grp_credits'
    ]);

    this.creditsPanel = null;
    this.creditsBody = null;
    this.creditsList = null;

    // Temporal (time-series) state tracking
    // Stores current year for each temporal layer: { layerId: year }
    this.temporalYearState = {};
    // Stores current date for each date-mode temporal layer: { layerId: "YYYY-MM-DD" }
    this.temporalDateState = {};
    // Legend cache by (layerId, year): { "layerId:year": HTMLElement }
    this.legendCache = {};

    // Global temporal control (new unified model)
    // globalDate: shared date for all time_enabled layers in 'global' mode
    this.globalDate = this._initGlobalDate();
    // Tracks per-layer time_mode overrides: { layerId: 'global' | 'local' }
    this.layerTimeMode = {};
    // Tracks per-layer local dates: { layerId: 'YYYY-MM-DD' }
    this.layerLocalDate = {};
    this._loadTimeSettings();

    // TOC density: compact (11px), normal (12px), comfortable (13px)
    this.density = localStorage.getItem('tsird_toc_density') || 'compact';
  }

  /**
   * Initialize global date from localStorage or default to yesterday (GIBS lag).
   * @private
   */
  _initGlobalDate() {
    const saved = localStorage.getItem('tsird:globalDate');
    if (saved && /^\d{4}-\d{2}-\d{2}$/.test(saved)) {
      return saved;
    }
    // Default to yesterday (GIBS data lag)
    const d = new Date();
    d.setDate(d.getDate() - 1);
    return this._formatDate(d);
  }

  /**
   * Format Date to YYYY-MM-DD string.
   * @private
   */
  _formatDate(date) {
    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const dd = String(date.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
  }

  /**
   * Load per-layer time settings from localStorage.
   * @private
   */
  _loadTimeSettings() {
    // Load per-layer time modes
    const modes = localStorage.getItem('tsird:layerTimeModes');
    if (modes) {
      try {
        this.layerTimeMode = JSON.parse(modes);
      } catch (e) {
        this.layerTimeMode = {};
      }
    }
    // Load per-layer local dates
    const dates = localStorage.getItem('tsird:layerLocalDates');
    if (dates) {
      try {
        this.layerLocalDate = JSON.parse(dates);
      } catch (e) {
        this.layerLocalDate = {};
      }
    }
  }

  /**
   * Save time settings to localStorage.
   * @private
   */
  _saveTimeSettings() {
    localStorage.setItem('tsird:globalDate', this.globalDate);
    localStorage.setItem('tsird:layerTimeModes', JSON.stringify(this.layerTimeMode));
    localStorage.setItem('tsird:layerLocalDates', JSON.stringify(this.layerLocalDate));
  }

  /**
   * Get effective date for a time-enabled layer.
   * Returns global date if layer follows global, otherwise local date.
   * @param {string} layerId
   * @returns {string} ISO date string
   */
  getEffectiveDate(layerId) {
    const layerDef = this.layerDefs[layerId];
    if (!layerDef || !layerDef.time_enabled) {
      return null;
    }
    const mode = this.layerTimeMode[layerId] || layerDef.time_mode || 'global';
    if (mode === 'local') {
      return this.layerLocalDate[layerId] || layerDef.time_default || this.globalDate;
    }
    return this.globalDate;
  }

  /**
   * Render TOC from registry order and attach event handlers.
   */
  renderTOC() {
    console.log('[InteractionController] Rendering TOC...');

    const container = document.getElementById(this.tocContainerId);
    if (!container) {
      throw new Error(`TOC container not found: #${this.tocContainerId}`);
    }

    // Clear existing content
    container.innerHTML = '';

    // Apply density attribute on TOC root
    this._applyDensity(this.density);

    // ── Build two-panel sidebar: sticky header + scrollable body ──
    const settingsPanel = document.createElement('div');
    settingsPanel.id = 'display-settings-container';
    settingsPanel.className = 'toc-settings-panel';

    const scrollPanel = document.createElement('div');
    scrollPanel.id = 'toc-scroll-container';
    scrollPanel.className = 'toc-scroll-panel';

    container.appendChild(settingsPanel);
    container.appendChild(scrollPanel);

    // Render Display Settings panel (global boundary opacity) into sticky header
    this._renderDisplaySettings(settingsPanel);

    // Render categories into scrollable body
    for (const category of this.tocModel) {
      const categoryElement = this._renderCategory(category);
      scrollPanel.appendChild(categoryElement);
    }

    // Credits panel (UI-only)
    this._renderCreditsPanel(scrollPanel);

    // Update display settings visibility based on raster/basemap state
    this._updateDisplaySettingsVisibility();

    console.log('[InteractionController] TOC rendered successfully');
  }

  /**
   * Render a single category with its groups and layers.
   * @private
   */
  _renderCategory(category) {
    const categoryDiv = document.createElement('div');
    categoryDiv.className = 'toc-category';
    categoryDiv.setAttribute('data-category-id', category.id);

    // Category header
    const headerDiv = document.createElement('div');
    headerDiv.className = 'toc-category-header';

    const toggle = document.createElement('span');
    toggle.className = 'toc-toggle';
    const isCollapsed = category.closed === true;
    toggle.textContent = isCollapsed ? '+' : '-';

    const categoryLabel = document.createElement('h3');
    categoryLabel.className = 'toc-category-label';
    categoryLabel.textContent = category.label;

    headerDiv.appendChild(toggle);
    headerDiv.appendChild(categoryLabel);
    categoryDiv.appendChild(headerDiv);

    // Groups
    const groupsDiv = document.createElement('div');
    groupsDiv.className = 'toc-groups';

    if (isCollapsed) {
      categoryDiv.classList.add('is-collapsed');
      groupsDiv.style.display = 'none';
    }

    for (const group of category.groups) {
      const groupElement = this._renderGroup(group);
      groupsDiv.appendChild(groupElement);
    }

    if (category.groups.length === 0) {
      const emptyNote = document.createElement('div');
      emptyNote.className = 'toc-empty-note';
      emptyNote.textContent = '(coming later)';
      groupsDiv.appendChild(emptyNote);
    }

    headerDiv.addEventListener('click', () => {
      const collapsed = categoryDiv.classList.toggle('is-collapsed');
      groupsDiv.style.display = collapsed ? 'none' : 'block';
      toggle.textContent = collapsed ? '+' : '-';
    });

    categoryDiv.appendChild(groupsDiv);
    return categoryDiv;
  }

  /**
   * Render a single group with its layers.
   * @private
   */
  _renderGroup(group) {
    const groupDiv = document.createElement('div');
    groupDiv.className = 'toc-group';
    groupDiv.setAttribute('data-group-id', group.id);

    const groupHasLayers = group.layers.length > 0;
    const groupHasDefaultVisible = this._groupHasDefaultVisible(group);
    const isDefaultGroup = groupHasDefaultVisible || this._isDefaultGroup(group);

    if (!isDefaultGroup) {
      groupDiv.classList.add('is-muted');
    }

    if (!groupHasLayers) {
      groupDiv.classList.add('toc-group-empty');
    }

    // Group header
    const headerDiv = document.createElement('div');
    headerDiv.className = 'toc-group-header';

    let toggle = null;
    if (groupHasLayers) {
      toggle = document.createElement('span');
      toggle.className = 'toc-toggle';
      headerDiv.appendChild(toggle);
    }

    if (groupHasLayers) {
      const groupCheckbox = document.createElement('input');
      groupCheckbox.type = 'checkbox';
      groupCheckbox.className = 'toc-group-checkbox';
      groupCheckbox.checked = false;
      groupCheckbox.addEventListener('change', (e) => {
        this._onGroupToggle(group.id, e.target.checked);
      });
      groupCheckbox.addEventListener('click', (e) => e.stopPropagation());
      headerDiv.appendChild(groupCheckbox);
    }

    const groupLabel = document.createElement('label');
    groupLabel.className = 'toc-group-label';
    groupLabel.textContent = groupHasLayers ? group.label : `${group.label} (coming later)`;
    headerDiv.appendChild(groupLabel);
    groupDiv.appendChild(headerDiv);

    // Layers
    const layersDiv = document.createElement('div');
    layersDiv.className = 'toc-layers';

    for (const layerRef of group.layers) {
      const layerElement = this._renderLayer(layerRef, group.id);
      layersDiv.appendChild(layerElement);
    }

    if (groupHasLayers) {
      const defaultOpen = group.closed === true ? false : group.closed === false ? true : isDefaultGroup;
      const isCollapsed = !defaultOpen;

      if (toggle) {
        toggle.textContent = isCollapsed ? '+' : '-';
      }

      if (isCollapsed) {
        groupDiv.classList.add('is-collapsed');
        layersDiv.style.display = 'none';
      }

      headerDiv.addEventListener('click', () => {
        const collapsed = groupDiv.classList.toggle('is-collapsed');
        layersDiv.style.display = collapsed ? 'none' : 'block';
        if (toggle) {
          toggle.textContent = collapsed ? '+' : '-';
        }
      });
    }

    groupDiv.appendChild(layersDiv);
    return groupDiv;
  }

  /**
   * Render a single layer with checkbox and legend toggle.
   * @private
   */
  _renderLayer(layerRef, groupId) {
    const layerId = layerRef.id;
    const layerDef = this.layerDefs[layerId];
    // Step 1: Debug log for legend_mode propagation
    console.log('[LegendGate]', layerId, layerDef.wms_name, layerDef.source_type, layerDef.legend_mode, layerDef.legend);

    const layerDiv = document.createElement('div');
    layerDiv.className = 'toc-layer';
    layerDiv.setAttribute('data-layer-id', layerId);

    if (!layerDef.default_visible) {
      layerDiv.classList.add('is-muted');
    }

    // Layer row (checkbox + label + legend toggle)
    const layerRow = document.createElement('div');
    layerRow.className = 'toc-layer-row';

    // Layer checkbox
    const layerCheckbox = document.createElement('input');
    layerCheckbox.type = 'checkbox';
    layerCheckbox.id = `layer-${layerId}`;
    layerCheckbox.className = 'toc-layer-checkbox';
    layerCheckbox.checked = layerDef.default_visible || false;
    layerCheckbox.addEventListener('change', (e) => {
      this._onLayerToggle(layerId, e.target.checked);
    });

    // Layer label
    const layerLabel = document.createElement('label');
    layerLabel.htmlFor = `layer-${layerId}`;
    layerLabel.className = 'toc-layer-label';
    layerLabel.textContent = layerRef.label;

    layerRow.appendChild(layerCheckbox);
    layerRow.appendChild(layerLabel);

    // Legend toggle button: show if (legend_mode: full OR legend_url present) and not base_layer, hide if legend === false
    const showLegendToggle = !layerDef.base_layer && 
                              layerDef.legend !== false && 
                              (layerDef.legend_mode === 'full' || layerDef.legend_url);
    if (showLegendToggle) {
      const legendToggle = document.createElement('button');
      legendToggle.className = 'toc-legend-toggle';
      legendToggle.title = 'Show/hide legend';
      legendToggle.innerHTML = '<span class="legend-icon">◧</span>';
      legendToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        this._toggleLegend(layerId, layerDef.wms_name, layerDiv, legendToggle);
      });
      layerRow.appendChild(legendToggle);
    }

    layerDiv.appendChild(layerRow);

    // Legend container (hidden by default) - must be AFTER layerRow for proper layout
    if (showLegendToggle) {
      const legendContainer = document.createElement('div');
      legendContainer.className = 'toc-legend-container';
      legendContainer.id = `legend-${layerId}`;
      legendContainer.style.display = 'none';
      layerDiv.appendChild(legendContainer);
    }

    // Temporal (time-series) control: year dropdown + slider (mode: year)
    if (layerDef.temporal && layerDef.temporal.mode === 'year' && Array.isArray(layerDef.temporal.years) && layerDef.temporal.years.length > 0) {
      const temporalRow = this._renderTemporalControl(layerId, layerDef);
      layerDiv.appendChild(temporalRow);
    }

    // Global temporal control: time_enabled layers get Follow Global toggle + optional local date
    if (layerDef.time_enabled) {
      const timeControlRow = this._renderTimeEnabledControl(layerId, layerDef);
      layerDiv.appendChild(timeControlRow);
    }
    // Legacy: Temporal (time-series) control: date dropdown + slider (mode: date) - only if NOT time_enabled
    else if (layerDef.temporal && layerDef.temporal.mode === 'date') {
      const dateRow = this._renderDateTemporalControl(layerId, layerDef);
      layerDiv.appendChild(dateRow);
    }

    return layerDiv;
  }

  /**
   * Render temporal (year) control: dropdown + slider synced together.
   * @private
   */
  _renderTemporalControl(layerId, layerDef) {
    const temporal = layerDef.temporal;
    const years = temporal.years.slice().sort((a, b) => a - b);
    const minYear = years[0];
    const maxYear = years[years.length - 1];

    // Load persisted year from localStorage or default to max year
    const storageKey = `tsird:year:${layerId}`;
    let currentYear = parseInt(localStorage.getItem(storageKey), 10);
    if (isNaN(currentYear) || !years.includes(currentYear)) {
      currentYear = maxYear;
    }
    this.temporalYearState[layerId] = currentYear;

    // Apply initial WMS params for the temporal layer
    this._applyTemporalYear(layerId, currentYear, false);

    const controlRow = document.createElement('div');
    controlRow.className = 'toc-temporal-control';
    controlRow.setAttribute('data-layer-id', layerId);

    // Year label
    const yearLabel = document.createElement('span');
    yearLabel.className = 'toc-temporal-label';
    yearLabel.textContent = 'Year:';

    // Dropdown (select)
    const dropdown = document.createElement('select');
    dropdown.className = 'toc-temporal-dropdown';
    dropdown.id = `temporal-dropdown-${layerId}`;
    years.forEach(y => {
      const opt = document.createElement('option');
      opt.value = y;
      opt.textContent = y;
      if (y === currentYear) opt.selected = true;
      dropdown.appendChild(opt);
    });

    // Slider (range)
    const slider = document.createElement('input');
    slider.type = 'range';
    slider.className = 'toc-temporal-slider';
    slider.id = `temporal-slider-${layerId}`;
    slider.min = minYear;
    slider.max = maxYear;
    slider.step = 1;
    slider.value = currentYear;

    // Sync dropdown -> slider and apply year change
    dropdown.addEventListener('change', () => {
      const newYear = parseInt(dropdown.value, 10);
      slider.value = newYear;
      this._onTemporalYearChange(layerId, newYear);
    });

    // Sync slider -> dropdown and apply year change
    slider.addEventListener('input', () => {
      const newYear = parseInt(slider.value, 10);
      // Snap to nearest available year if not contiguous
      const closestYear = years.reduce((prev, curr) =>
        Math.abs(curr - newYear) < Math.abs(prev - newYear) ? curr : prev
      );
      dropdown.value = closestYear;
      slider.value = closestYear;
      this._onTemporalYearChange(layerId, closestYear);
    });

    controlRow.appendChild(yearLabel);
    controlRow.appendChild(dropdown);
    controlRow.appendChild(slider);

    return controlRow;
  }

  /**
   * Handle temporal year change: update WMS params and persist.
   * @private
   */
  _onTemporalYearChange(layerId, newYear) {
    const oldYear = this.temporalYearState[layerId];
    if (oldYear === newYear) return;

    this.temporalYearState[layerId] = newYear;
    localStorage.setItem(`tsird:year:${layerId}`, newYear);

    this._applyTemporalYear(layerId, newYear, true);

    // Invalidate legend cache for this layer (if year changed)
    this._invalidateLegendForTemporalLayer(layerId);

    console.log(`[Temporal] Layer ${layerId}: year changed ${oldYear} → ${newYear}`);
  }

  /**
   * Apply temporal year to the OL layer's WMS params.
   * @private
   */
  _applyTemporalYear(layerId, year, forceRefresh = false) {
    const layer = this.layerMap[layerId];
    if (!layer) return;

    const layerDef = this.layerDefs[layerId];
    const temporal = layerDef.temporal;
    if (!temporal) return;

    const source = layer.getSource();
    if (!source || typeof source.updateParams !== 'function') {
      console.warn(`[Temporal] Layer ${layerId} source does not support updateParams`);
      return;
    }

    const params = {};

    if (temporal.time_param && temporal.time_param.enabled) {
      // TIME parameter mode: set TIME, keep LAYERS unchanged
      const format = temporal.time_param.format || '{year}-01-01';
      params.TIME = format.replace('{year}', year);
    } else if (temporal.layer_by_year) {
      // Layer-by-year mode: change LAYERS, no TIME
      const yearStr = String(year);
      const mappedLayer = temporal.layer_by_year[yearStr];
      if (mappedLayer) {
        params.LAYERS = mappedLayer;
      } else {
        console.warn(`[Temporal] Layer ${layerId}: no mapping for year ${year}`);
      }
    }

    // Add cache buster if force refresh
    if (forceRefresh) {
      params._ts = Date.now();
    }

    source.updateParams(params);
  }

  /**
   * Invalidate and clear legend for a temporal layer when year changes.
   * @private
   */
  _invalidateLegendForTemporalLayer(layerId) {
    const legendContainer = document.getElementById(`legend-${layerId}`);
    if (legendContainer && legendContainer.dataset.loaded) {
      // Clear loaded state to force reload on next toggle
      delete legendContainer.dataset.loaded;
      legendContainer.innerHTML = '';
    }
  }

  /**
   * Generate an array of date strings (YYYY-MM-DD) for the last N days.
   * @private
   */
  _generateDateRange(rangeDays) {
    const dates = [];
    const today = new Date();
    for (let i = 0; i < rangeDays; i++) {
      const d = new Date(today);
      d.setDate(today.getDate() - i);
      const yyyy = d.getFullYear();
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      const dd = String(d.getDate()).padStart(2, '0');
      dates.push(`${yyyy}-${mm}-${dd}`);
    }
    return dates; // Most recent first
  }

  /**
   * Render temporal control for date mode (daily TIME slider for GIBS etc).
   * @private
   */
  _renderDateTemporalControl(layerId, layerDef) {
    const temporal = layerDef.temporal;
    const rangeDays = temporal.range_days || 30;
    // Handle negative offset (YAML style: -1 = yesterday) or positive (index style: 1 = yesterday)
    const rawOffset = temporal.default_offset_days || 1;
    const offsetDays = Math.abs(rawOffset);

    const dates = this._generateDateRange(rangeDays);
    const defaultDate = dates[Math.min(offsetDays, dates.length - 1)];

    // Load persisted date from localStorage or default
    const storageKey = `tsird:date:${layerId}`;
    let currentDate = localStorage.getItem(storageKey);
    if (!currentDate || !dates.includes(currentDate)) {
      currentDate = defaultDate;
    }
    this.temporalDateState = this.temporalDateState || {};
    this.temporalDateState[layerId] = currentDate;

    // Apply initial WMS params for the temporal layer
    this._applyTemporalDate(layerId, currentDate, false);

    const controlRow = document.createElement('div');
    controlRow.className = 'toc-temporal-control';
    controlRow.setAttribute('data-layer-id', layerId);

    // Date label
    const dateLabel = document.createElement('span');
    dateLabel.className = 'toc-temporal-label';
    dateLabel.textContent = 'Date:';

    // Dropdown (select)
    const dropdown = document.createElement('select');
    dropdown.className = 'toc-temporal-dropdown';
    dropdown.id = `temporal-date-dropdown-${layerId}`;
    dates.forEach(d => {
      const opt = document.createElement('option');
      opt.value = d;
      // Format display as "Feb 24" for better readability
      const dateObj = new Date(d + 'T00:00:00');
      const monthName = dateObj.toLocaleString('en', { month: 'short' });
      const day = dateObj.getDate();
      opt.textContent = `${monthName} ${day}`;
      if (d === currentDate) opt.selected = true;
      dropdown.appendChild(opt);
    });

    // Slider (range) - index based (0 = most recent, rangeDays-1 = oldest)
    const slider = document.createElement('input');
    slider.type = 'range';
    slider.className = 'toc-temporal-slider';
    slider.id = `temporal-date-slider-${layerId}`;
    slider.min = 0;
    slider.max = rangeDays - 1;
    slider.step = 1;
    slider.value = dates.indexOf(currentDate);

    // Sync dropdown -> slider and apply date change
    dropdown.addEventListener('change', () => {
      const newDate = dropdown.value;
      slider.value = dates.indexOf(newDate);
      this._onTemporalDateChange(layerId, newDate);
    });

    // Sync slider -> dropdown and apply date change
    slider.addEventListener('input', () => {
      const idx = parseInt(slider.value, 10);
      const newDate = dates[idx];
      dropdown.value = newDate;
      this._onTemporalDateChange(layerId, newDate);
    });

    controlRow.appendChild(dateLabel);
    controlRow.appendChild(dropdown);
    controlRow.appendChild(slider);

    return controlRow;
  }

  /**
   * Handle temporal date change: update WMS params and persist.
   * @private
   */
  _onTemporalDateChange(layerId, newDate) {
    this.temporalDateState = this.temporalDateState || {};
    const oldDate = this.temporalDateState[layerId];
    if (oldDate === newDate) return;

    this.temporalDateState[layerId] = newDate;
    localStorage.setItem(`tsird:date:${layerId}`, newDate);

    this._applyTemporalDate(layerId, newDate, true);

    // Invalidate legend cache for this layer
    this._invalidateLegendForTemporalLayer(layerId);

    console.log(`[Temporal] Layer ${layerId}: date changed ${oldDate} → ${newDate}`);
  }

  /**
   * Apply temporal date to the OL layer's WMS params.
   * @private
   */
  _applyTemporalDate(layerId, date, forceRefresh = false) {
    const layer = this.layerMap[layerId];
    if (!layer) return;

    const layerDef = this.layerDefs[layerId];
    const temporal = layerDef.temporal;
    if (!temporal) return;

    const source = layer.getSource();
    if (!source || typeof source.updateParams !== 'function') {
      console.warn(`[Temporal] Layer ${layerId} source does not support updateParams`);
      return;
    }

    const params = {};

    // Apply TIME parameter
    if (temporal.time_param && temporal.time_param.enabled) {
      params.TIME = date; // ISO8601 date format YYYY-MM-DD
    }

    // Add cache buster if force refresh
    if (forceRefresh) {
      params._ts = Date.now();
    }

    source.updateParams(params);
  }

  /**
   * Render time-enabled layer control with Follow Global toggle and optional local date.
   * @private
   */
  _renderTimeEnabledControl(layerId, layerDef) {
    const controlRow = document.createElement('div');
    controlRow.className = 'toc-temporal-control toc-time-enabled-control';
    controlRow.setAttribute('data-layer-id', layerId);

    // Determine current mode (global or local)
    const savedMode = this.layerTimeMode[layerId] || layerDef.time_mode || 'global';
    const isGlobal = savedMode === 'global';

    // Follow Global toggle (checkbox style)
    const toggleLabel = document.createElement('label');
    toggleLabel.className = 'toc-follow-global-label';

    const toggleCheckbox = document.createElement('input');
    toggleCheckbox.type = 'checkbox';
    toggleCheckbox.className = 'toc-follow-global-checkbox';
    toggleCheckbox.id = `follow-global-${layerId}`;
    toggleCheckbox.checked = isGlobal;

    const toggleText = document.createElement('span');
    toggleText.textContent = 'Follow Global';
    toggleText.className = 'toc-follow-global-text';

    toggleLabel.appendChild(toggleCheckbox);
    toggleLabel.appendChild(toggleText);

    // Local date controls container (hidden when following global)
    const localDateContainer = document.createElement('div');
    localDateContainer.className = 'toc-local-date-container';
    localDateContainer.id = `local-date-container-${layerId}`;
    localDateContainer.style.display = isGlobal ? 'none' : 'flex';

    // Local date input
    const localDateInput = document.createElement('input');
    localDateInput.type = 'date';
    localDateInput.className = 'toc-local-date-input';
    localDateInput.id = `local-date-${layerId}`;
    // Initialize to saved local date or current effective date
    localDateInput.value = this.layerLocalDate[layerId] || layerDef.time_default || this.globalDate;

    // Date limits
    const today = new Date();
    const minDate = new Date(today);
    minDate.setDate(today.getDate() - 90);
    localDateInput.max = this._formatDate(today);
    localDateInput.min = this._formatDate(minDate);

    localDateInput.addEventListener('change', (e) => {
      this._setLayerLocalDate(layerId, e.target.value);
    });

    localDateContainer.appendChild(localDateInput);

    // Toggle behavior
    toggleCheckbox.addEventListener('change', () => {
      const newMode = toggleCheckbox.checked ? 'global' : 'local';
      this.layerTimeMode[layerId] = newMode;
      this._saveTimeSettings();

      if (newMode === 'global') {
        localDateContainer.style.display = 'none';
        // Re-apply global date
        this._applyTimeParam(layerId);
      } else {
        localDateContainer.style.display = 'flex';
        // Apply local date
        const localDate = this.layerLocalDate[layerId] || this.globalDate;
        localDateInput.value = localDate;
        this._setLayerLocalDate(layerId, localDate);
      }

      console.log(`[Temporal] Layer ${layerId}: mode changed to ${newMode}`);
    });

    controlRow.appendChild(toggleLabel);
    controlRow.appendChild(localDateContainer);

    // Apply initial TIME param
    this._applyTimeParam(layerId);

    return controlRow;
  }

  /**
   * Set local date for a layer and refresh it.
   * @private
   */
  _setLayerLocalDate(layerId, dateStr) {
    this.layerLocalDate[layerId] = dateStr;
    this._saveTimeSettings();
    this._applyTimeParam(layerId);
    console.log(`[Temporal] Layer ${layerId}: local date set to ${dateStr}`);
  }

  /**
   * Toggle legend visibility for a layer.
   * @private
   */
  _toggleLegend(layerId, wmsName, layerDiv, toggleButton) {
    const legendContainer = document.getElementById(`legend-${layerId}`);
    if (!legendContainer) return;

    const isVisible = legendContainer.style.display !== 'none';
    
    if (isVisible) {
      // Hide legend
      legendContainer.style.display = 'none';
      toggleButton.innerHTML = '<span class="legend-icon">◧</span>';
      toggleButton.classList.remove('is-expanded');
    } else {
      // Show legend - load if not already loaded
      legendContainer.style.display = 'block';
      toggleButton.innerHTML = '<span class="legend-icon">◨</span>';
      toggleButton.classList.add('is-expanded');
      
      if (!legendContainer.dataset.loaded) {
        this._loadLegend(layerId, wmsName, legendContainer, toggleButton);
      }
    }
  }

  /**
   * Load legend image via WMS GetLegendGraphic or static URL.
   * Handles temporal layers by using current year's WMS params.
   * Supports legend_url for external WMS that don't support GetLegendGraphic.
   * @private
   */
  _loadLegend(layerId, wmsName, container, toggleButton) {
    const layerDef = this.layerDefs[layerId];
    
    // Check for static legend URL first (for external WMS that don't support GetLegendGraphic)
    if (layerDef.legend_url) {
      this._loadStaticLegend(layerDef.legend_url, container, toggleButton);
      return;
    }
    
    // Determine WMS base URL (external or local MapServer)
    let wmsBaseUrl;
    if (layerDef.source_type === 'wms_external' && layerDef.wms_base_url) {
      wmsBaseUrl = layerDef.wms_base_url;
    } else {
      wmsBaseUrl = this.mapController.wmsBaseUrl;
    }

    // Determine layer name and TIME param for temporal layers
    let effectiveLayerName = wmsName;
    let timeParam = '';

    if (layerDef.temporal && layerDef.temporal.mode === 'year') {
      const currentYear = this.temporalYearState[layerId];
      const temporal = layerDef.temporal;

      if (temporal.layer_by_year && currentYear) {
        // Use year-specific layer name
        const yearStr = String(currentYear);
        effectiveLayerName = temporal.layer_by_year[yearStr] || wmsName;
      } else if (temporal.time_param && temporal.time_param.enabled && currentYear) {
        // Keep wmsName but add TIME param
        const format = temporal.time_param.format || '{year}-01-01';
        timeParam = `&TIME=${encodeURIComponent(format.replace('{year}', currentYear))}`;
      }
    }

    const legendUrl = `${wmsBaseUrl}?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetLegendGraphic&LAYER=${encodeURIComponent(effectiveLayerName)}&FORMAT=image/png&SLD_VERSION=1.1.0${timeParam}`;
    
    // Show loading state
    container.innerHTML = '<div class="toc-legend-header">Legend</div><span class="toc-legend-loading">Loading...</span>';
    
    const img = document.createElement('img');
    img.className = 'toc-legend-image';
    img.alt = `Legend for ${effectiveLayerName}`;
    img.crossOrigin = 'anonymous';  // For external WMS CORS
    
    img.onload = () => {
      // Fallback: check if legend image is too small (likely blank/empty)
      // Typical "empty" legends are ~20x15 or smaller
      if (img.naturalWidth < 25 && img.naturalHeight < 20) {
        container.innerHTML = '<div class="toc-legend-header">Legend</div><span class="toc-legend-error">Legend unavailable</span>';
        container.dataset.loaded = 'empty';
        return;
      }
      container.innerHTML = '<div class="toc-legend-header">Legend</div>';
      container.appendChild(img);
      container.dataset.loaded = 'true';
    };
    
    img.onerror = () => {
      container.innerHTML = '<div class="toc-legend-header">Legend</div><span class="toc-legend-error">Legend unavailable</span>';
      container.dataset.loaded = 'error';
    };
    
    img.src = legendUrl;
  }

  /**
   * Load a static legend image from a direct URL.
   * Used for external WMS services that don't support GetLegendGraphic.
   * @private
   */
  _loadStaticLegend(legendUrl, container, toggleButton) {
    container.innerHTML = '<div class="toc-legend-header">Legend</div><span class="toc-legend-loading">Loading...</span>';
    
    const img = document.createElement('img');
    img.className = 'toc-legend-image';
    img.alt = 'Legend';
    img.crossOrigin = 'anonymous';
    
    img.onload = () => {
      container.innerHTML = '<div class="toc-legend-header">Legend</div>';
      container.appendChild(img);
      container.dataset.loaded = 'true';
    };
    
    img.onerror = () => {
      container.innerHTML = '<div class="toc-legend-header">Legend</div><span class="toc-legend-error">Legend unavailable</span>';
      container.dataset.loaded = 'error';
    };
    
    img.src = legendUrl;
  }

  _groupHasDefaultVisible(group) {
    return group.layers.some(layerRef => {
      const layerDef = this.layerDefs[layerRef.id];
      return layerDef?.default_visible === true;
    });
  }

  _isDefaultGroup(group) {
    return this.defaultGroupIds.has(group.id);
  }

  _renderCreditsPanel(container) {
    const panel = document.createElement('div');
    panel.className = 'toc-credits';

    const header = document.createElement('div');
    header.className = 'toc-credits-header';

    const toggle = document.createElement('span');
    toggle.className = 'toc-toggle';
    toggle.textContent = '-';

    const label = document.createElement('span');
    label.className = 'toc-credits-label';
    label.textContent = 'Credits';

    header.appendChild(toggle);
    header.appendChild(label);
    panel.appendChild(header);

    const body = document.createElement('div');
    body.className = 'toc-credits-body';

    const list = document.createElement('ul');
    list.className = 'toc-credits-list';
    body.appendChild(list);

    header.addEventListener('click', () => {
      const collapsed = panel.classList.toggle('is-collapsed');
      body.style.display = collapsed ? 'none' : 'block';
      toggle.textContent = collapsed ? '+' : '-';
    });

    panel.appendChild(body);
    container.appendChild(panel);

    this.creditsPanel = panel;
    this.creditsBody = body;
    this.creditsList = list;

    this._refreshCreditsPanel();
  }

  _refreshCreditsPanel() {
    if (!this.creditsList) return;

    const attributions = new Set();
    this.layers.forEach(layer => {
      if (layer.getVisible() && layer.layerDef?.attribution) {
        attributions.add(layer.layerDef.attribution);
      }
    });

    this.creditsList.innerHTML = '';

    if (attributions.size === 0) {
      const emptyItem = document.createElement('li');
      emptyItem.className = 'toc-credits-empty';
      emptyItem.textContent = 'No attributions provided.';
      this.creditsList.appendChild(emptyItem);
      return;
    }

    for (const item of attributions) {
      const li = document.createElement('li');
      li.textContent = item;
      this.creditsList.appendChild(li);
    }
  }

  /**
   * Boundary layer IDs that are controlled by the global opacity slider.
   * @private
   */
  _getBoundaryLayerIds() {
    return [
      'ethiopia_zones', 'ethiopia_woredas', 'ethiopia_admin', 'ethiopia_aoi',
      'tigray_woreda', 'tigray_tabias',
      'ethiopia_boundary_level1', 'ethiopia_boundary_level2', 'ethiopia_boundary_level3'
    ];
  }

  /**
   * Render Display Settings panel with global boundary opacity slider and density control.
   * @private
   */
  _renderDisplaySettings(container) {
    const panel = document.createElement('div');
    panel.className = 'toc-display-settings';
    panel.id = 'display-settings-panel';

    const header = document.createElement('div');
    header.className = 'toc-display-settings-header';
    header.textContent = 'Display Settings';

    // --- Boundary Opacity Row ---
    const row = document.createElement('div');
    row.className = 'toc-display-settings-row';

    const label = document.createElement('span');
    label.className = 'toc-display-settings-label';
    label.textContent = 'Boundary Opacity:';

    // Load from localStorage or default to 50%
    const savedOpacity = localStorage.getItem('atlas_boundary_opacity');
    const initialValue = savedOpacity !== null ? parseInt(savedOpacity) : 50;

    const slider = document.createElement('input');
    slider.type = 'range';
    slider.className = 'toc-display-settings-slider';
    slider.id = 'boundary-opacity-slider';
    slider.min = '0';
    slider.max = '100';
    slider.value = String(initialValue);
    slider.title = 'Adjust boundary layer transparency';

    const valueLabel = document.createElement('span');
    valueLabel.className = 'toc-display-settings-value';
    valueLabel.id = 'boundary-opacity-value';
    valueLabel.textContent = `${initialValue}%`;

    slider.addEventListener('input', (e) => {
      const value = parseInt(e.target.value);
      valueLabel.textContent = `${value}%`;
      this._applyBoundaryOpacity(value / 100);
      localStorage.setItem('atlas_boundary_opacity', String(value));
    });

    row.appendChild(label);
    row.appendChild(slider);
    row.appendChild(valueLabel);

    // --- Density Control Row ---
    const densityRow = document.createElement('div');
    densityRow.className = 'toc-display-settings-row toc-density-row';

    const densityLabel = document.createElement('span');
    densityLabel.className = 'toc-display-settings-label';
    densityLabel.textContent = 'Density:';

    // Segmented control for density
    const densityControl = document.createElement('div');
    densityControl.className = 'toc-density-control';

    const densities = [
      { id: 'compact', label: 'Compact' },
      { id: 'normal', label: 'Normal' },
      { id: 'comfortable', label: 'Comfortable' }
    ];

    densities.forEach(d => {
      const btn = document.createElement('button');
      btn.className = 'toc-density-btn';
      btn.dataset.density = d.id;
      btn.textContent = d.label;
      btn.title = `${d.label} density`;
      if (this.density === d.id) {
        btn.classList.add('is-active');
      }
      btn.addEventListener('click', () => {
        this._setDensity(d.id, densityControl);
      });
      densityControl.appendChild(btn);
    });

    densityRow.appendChild(densityLabel);
    densityRow.appendChild(densityControl);

    // --- Global Date Control Row ---
    const globalDateRow = this._createGlobalDateControl();

    panel.appendChild(header);
    panel.appendChild(row);
    panel.appendChild(densityRow);
    panel.appendChild(globalDateRow);
    container.appendChild(panel);

    // Apply initial boundary opacity
    this._applyBoundaryOpacity(initialValue / 100);
  }

  /**
   * Set TOC density and persist to localStorage.
   * @private
   */
  _setDensity(density, controlEl) {
    this.density = density;
    localStorage.setItem('tsird_toc_density', density);
    this._applyDensity(density);

    // Update active state on buttons
    const buttons = controlEl.querySelectorAll('.toc-density-btn');
    buttons.forEach(btn => {
      btn.classList.toggle('is-active', btn.dataset.density === density);
    });
    console.log(`[InteractionController] TOC density set to: ${density}`);
  }

  /**
   * Apply density attribute to TOC container.
   * @private
   */
  _applyDensity(density) {
    const container = document.getElementById(this.tocContainerId);
    if (container) {
      container.dataset.density = density;
    }
  }

  /**
   * Create the Global Date control row for Display Settings.
   * @private
   * @returns {HTMLElement}
   */
  _createGlobalDateControl() {
    const row = document.createElement('div');
    row.className = 'toc-display-settings-row toc-global-date-row';

    const label = document.createElement('span');
    label.className = 'toc-display-settings-label';
    label.textContent = 'Global Date:';

    // Date input (type="date" for native picker)
    const dateInput = document.createElement('input');
    dateInput.type = 'date';
    dateInput.className = 'toc-global-date-input';
    dateInput.id = 'global-date-input';
    dateInput.value = this.globalDate;
    // Limit to reasonable range (last 90 days to today)
    const today = new Date();
    const minDate = new Date(today);
    minDate.setDate(today.getDate() - 90);
    dateInput.max = this._formatDate(today);
    dateInput.min = this._formatDate(minDate);

    dateInput.addEventListener('change', (e) => {
      this._setGlobalDate(e.target.value);
    });

    // Reset button (set to yesterday)
    const resetBtn = document.createElement('button');
    resetBtn.className = 'toc-global-date-reset';
    resetBtn.textContent = 'Reset';
    resetBtn.title = 'Reset to yesterday';
    resetBtn.addEventListener('click', () => {
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);
      const dateStr = this._formatDate(yesterday);
      dateInput.value = dateStr;
      this._setGlobalDate(dateStr);
    });

    row.appendChild(label);
    row.appendChild(dateInput);
    row.appendChild(resetBtn);

    return row;
  }

  /**
   * Set the global date and refresh all time-enabled layers following global.
   * @private
   */
  _setGlobalDate(dateStr) {
    if (this.globalDate === dateStr) return;

    const oldDate = this.globalDate;
    this.globalDate = dateStr;
    this._saveTimeSettings();

    console.log(`[InteractionController] Global date changed: ${oldDate} → ${dateStr}`);

    // Refresh all time-enabled layers that follow global
    this._refreshGlobalTimeLayers();
  }

  /**
   * Refresh WMS params for all time-enabled layers following global date.
   * @private
   */
  _refreshGlobalTimeLayers() {
    for (const [layerId, layerDef] of Object.entries(this.layerDefs)) {
      if (!layerDef.time_enabled) continue;

      const mode = this.layerTimeMode[layerId] || layerDef.time_mode || 'global';
      if (mode !== 'global') continue;

      this._applyTimeParam(layerId);
    }
  }

  /**
   * Apply TIME param to a layer's WMS source.
   * @private
   */
  _applyTimeParam(layerId) {
    const layer = this.layerMap[layerId];
    if (!layer) return;

    const layerDef = this.layerDefs[layerId];
    if (!layerDef.time_enabled) return;

    const source = layer.getSource();
    if (!source || typeof source.updateParams !== 'function') {
      console.warn(`[Temporal] Layer ${layerId} source does not support updateParams`);
      return;
    }

    const effectiveDate = this.getEffectiveDate(layerId);
    const paramName = layerDef.time_param_name || 'TIME';

    const params = {};
    params[paramName] = effectiveDate;
    params._ts = Date.now();  // Cache buster

    source.updateParams(params);
    console.debug(`[Temporal] Layer ${layerId}: ${paramName}=${effectiveDate}`);

    // Invalidate legend cache
    this._invalidateLegendForTemporalLayer(layerId);
  }

  /**
   * Apply opacity to all boundary layers.
   * @private
   */
  _applyBoundaryOpacity(opacity) {
    const boundaryIds = this._getBoundaryLayerIds();
    for (const layerId of boundaryIds) {
      const layer = this.layerMap[layerId];
      if (layer) {
        layer.setOpacity(opacity);
      }
    }
    console.log(`[InteractionController] Boundary opacity set to ${Math.round(opacity * 100)}%`);
  }

  /**
   * Update display settings panel visibility.
   * Show only when a raster or basemap layer is visible.
   * @private
   */
  _updateDisplaySettingsVisibility() {
    // Display Settings is always visible — it is not conditional on layer state.
    // The panel is structurally sticky inside .toc-settings-panel and must never
    // be hidden by layer toggle events.
    const panel = document.getElementById('display-settings-panel');
    if (!panel) return;
    panel.style.display = 'block';
  }

  _updatePolygonOpacity() {
    // Deprecated: Now using global boundary opacity from Display Settings
    // This method is kept for backwards compatibility but defers to slider value
    this._updateDisplaySettingsVisibility();
  }

  /**
   * Initialize layer visibility based on default_visible.
   * Called after layers are added to map.
   * Milestone 2: Uses scale-aware visibility logic
   */
  initializeLayerVisibility() {
    console.log('[InteractionController] Initializing layer visibility...');

    for (const layer of this.layers) {
      const layerId = layer.layerId;
      const layerDef = layer.layerDef;
      const isVisible = layerDef.default_visible === true;

      // Set user-requested state
      this.userVisibilityState[layerId] = isVisible;

      // Apply visibility with scale/mutex constraints
      this._updateLayerVisibility(layerId);

      console.log(`[InteractionController] ${layerId}: default_visible=${isVisible}`);
    }

    this._updatePolygonOpacity();
  }

  /**
   * Handle layer toggle.
   * Milestone 2: Integrates scale constraints and mutex enforcement
   * Milestone 2.5: Basemap radio behavior (only one basemap visible at a time)
   * @private
   */
  _onLayerToggle(layerId, enabled) {
    const layer = this.layerMap[layerId];
    if (!layer) {
      console.warn(`[InteractionController] Layer not found: ${layerId}`);
      return;
    }

    const layerDef = this.layerDefs[layerId];

    // Basemap radio behavior: when turning ON a basemap, turn OFF all others
    if (enabled && layerDef && layerDef.base_layer) {
      this._enforceBasemapMutex(layerId);
    }

    // Update user-requested state
    this.userVisibilityState[layerId] = enabled;

    // Apply visibility with scale and mutex constraints
    this._updateLayerVisibility(layerId);

    console.log(`[InteractionController] Layer toggled: ${layerId} = ${enabled} (user request)`);
  }

  setLayerVisible(layerId, enabled) {
    this._onLayerToggle(layerId, enabled);
  }

  /**
   * Enforce basemap mutex: only one basemap visible at a time.
   * When a basemap is turned ON, all other basemaps are turned OFF.
   * @private
   */
  _enforceBasemapMutex(activeBasemapId) {
    // Find all basemap layers and turn them off (except the active one)
    for (const [layerId, layerDef] of Object.entries(this.layerDefs)) {
      if (layerDef.base_layer && layerId !== activeBasemapId) {
        // Turn off this basemap
        this.userVisibilityState[layerId] = false;
        
        const layer = this.layerMap[layerId];
        if (layer) {
          layer.setVisible(false);
        }
        
        // Update checkbox in UI
        const checkbox = document.getElementById(`layer-${layerId}`);
        if (checkbox) {
          checkbox.checked = false;
        }
        
        console.log(`[InteractionController] Basemap mutex: ${layerId} turned OFF (${activeBasemapId} is active)`);
      }
    }
  }

  /**
   * Handle opacity slider change for a layer.
   * @private
   */
  _onOpacityChange(layerId, opacity) {
    const layer = this.layerMap[layerId];
    if (!layer) {
      console.warn(`[InteractionController] Layer not found for opacity change: ${layerId}`);
      return;
    }

    layer.setOpacity(opacity);
    console.log(`[InteractionController] Layer opacity changed: ${layerId} = ${Math.round(opacity * 100)}%`);
  }

  /**
   * Update layer visibility based on user state, scale constraints, and mutex rules.
   * Milestone 2: Central visibility logic
   * @private
   */
  _updateLayerVisibility(layerId) {
    const layer = this.layerMap[layerId];
    const layerDef = this.layerDefs[layerId];
    const userWantsVisible = this.userVisibilityState[layerId];

    if (!layer || !layerDef) return;

    // Step 1: Check if user wants it visible
    if (!userWantsVisible) {
      layer.setVisible(false);
      this._updateLayerCheckboxState(layerId, false, null);
      this._refreshCreditsPanel();
      this._updatePolygonOpacity();
      return;
    }

    // Step 2: Check scale constraint
    const currentScale = ScaleEngine.getCurrentScale(this.mapController.getView());
    const inScale = ScaleEngine.isLayerInScale(layerDef, currentScale);

    if (!inScale) {
      layer.setVisible(false);
      this._updateLayerCheckboxState(layerId, false, 'out-of-scale');
      console.log(`[InteractionController] ${layerId}: OUT OF SCALE (${ScaleEngine.formatScale(currentScale)})`);
      this._refreshCreditsPanel();
      this._updatePolygonOpacity();
      return;
    }

    // Step 3: Check mutex constraints
    const mutexBlocker = this._getMutexBlocker(layerId);
    if (mutexBlocker) {
      layer.setVisible(false);
      this._updateLayerCheckboxState(layerId, false, 'mutex-suppressed');
      console.log(`[InteractionController] ${layerId}: SUPPRESSED by mutex pair with ${mutexBlocker}`);
      this._refreshCreditsPanel();
      this._updatePolygonOpacity();
      return;
    }

    // All constraints satisfied: show layer
    layer.setVisible(true);
    this._updateLayerCheckboxState(layerId, true, null);
    this._refreshCreditsPanel();
    this._updatePolygonOpacity();
    console.log(`[InteractionController] ${layerId}: VISIBLE`);
  }

  /**
   * Check if layer is blocked by a mutex pair.
   * Returns the ID of the blocking layer, or null if not blocked.
   * 
   * Mutex rule: If both layers in a pair are toggled ON by user,
   * only the one that is IN SCALE should be visible.
   * If both are in scale at the same time (shouldn't happen with proper ranges),
   * prefer the first one in the pair.
   * 
   * @private
   */
  _getMutexBlocker(layerId) {
    const layerDef = this.layerDefs[layerId];
    const currentScale = ScaleEngine.getCurrentScale(this.mapController.getView());
    const thisLayerInScale = ScaleEngine.isLayerInScale(layerDef, currentScale);

    // Find all mutex pairs containing this layer
    for (const pair of this.scaleMutexPairs) {
      if (!pair || pair.length !== 2) continue;

      const [layer1Id, layer2Id] = pair;
      const otherLayerId = (layerId === layer1Id) ? layer2Id : (layerId === layer2Id) ? layer1Id : null;

      if (!otherLayerId) continue;  // This layer not in this pair

      // Check if other layer is toggled ON by user
      const otherUserWantsVisible = this.userVisibilityState[otherLayerId];
      if (!otherUserWantsVisible) continue;  // Other layer not requested, no conflict

      // Check if other layer is in scale
      const otherLayerDef = this.layerDefs[otherLayerId];
      const otherLayerInScale = ScaleEngine.isLayerInScale(otherLayerDef, currentScale);

      // Mutex rule: If other layer is in scale, it takes priority
      if (otherLayerInScale && !thisLayerInScale) {
        return otherLayerId;  // This layer blocked
      }

      // If both are in scale (edge case), prefer first in pair
      if (thisLayerInScale && otherLayerInScale && layerId === layer2Id) {
        return layer1Id;  // This layer is second in pair, blocked by first
      }
    }

    return null;  // Not blocked
  }

  /**
   * Update checkbox and layer UI state (enabled/disabled, warnings).
   * @private
   */
  _updateLayerCheckboxState(layerId, visible, reason) {
    const checkbox = document.querySelector(`input#layer-${layerId}`);
    const layerDiv = document.querySelector(`div.toc-layer[data-layer-id="${layerId}"]`);

    if (checkbox) {
      checkbox.checked = this.userVisibilityState[layerId];

      // Add visual indicator for constraints
      if (reason === 'out-of-scale') {
        checkbox.disabled = false;  // Keep interactive so user can toggle off
        layerDiv?.classList.add('out-of-scale');
        layerDiv?.classList.remove('mutex-suppressed');
        checkbox.title = `Out of scale range (current: ${ScaleEngine.formatScale(ScaleEngine.getCurrentScale(this.mapController.getView()))})`;
      } else if (reason === 'mutex-suppressed') {
        checkbox.disabled = false;
        layerDiv?.classList.add('mutex-suppressed');
        layerDiv?.classList.remove('out-of-scale');
        checkbox.title = 'Suppressed by scale mutex (zoomed in/out for alternative layer)';
      } else {
        checkbox.disabled = false;
        layerDiv?.classList.remove('out-of-scale', 'mutex-suppressed');
        checkbox.title = '';
      }
    }
  }

  /**
   * Update all layer visibility based on current scale.
   * Called on zoom/pan changes.
   * Milestone 2
   */
  updateAllLayersForScale() {
    const currentScale = ScaleEngine.getCurrentScale(this.mapController.getView());
    console.log(`[InteractionController] Scale changed: ${ScaleEngine.formatScale(currentScale)}`);

    for (const layerId in this.layerMap) {
      if (this.userVisibilityState[layerId]) {
        this._updateLayerVisibility(layerId);
      }
    }
  }

  /**
   * Initialize scale-based visibility updates on map zoom/pan.
   * Call after map is initialized.
   * Milestone 2
   */
  initializeScaleMonitoring() {
    console.log('[InteractionController] Initializing scale monitoring...');

    this.mapController.getView().on('change:resolution', () => {
      this.updateAllLayersForScale();
    });

    console.log('[InteractionController] Scale monitoring active');
  }

  /**
   * Handle group toggle.
   * Toggle all child layers in the group, respecting their default_visible state.
   * @private
   */
  _onGroupToggle(groupId, enabled) {
    console.log(`[InteractionController] Group toggled: ${groupId} = ${enabled}`);

    // Find group in tocModel
    let targetGroup = null;
    for (const category of this.tocModel) {
      const found = category.groups.find(g => g.id === groupId);
      if (found) {
        targetGroup = found;
        break;
      }
    }

    if (!targetGroup) {
      console.warn(`[InteractionController] Group not found: ${groupId}`);
      return;
    }

    // Toggle all layers in group
    for (const layerRef of targetGroup.layers) {
      const layerId = layerRef.id;
      const layer = this.layerMap[layerId];
      if (!layer) continue;

      // If enabled, respect default_visible; if disabled, always turn off
      const shouldBeVisible = enabled && (this.layerDefs[layerId].default_visible === true);
      layer.setVisible(shouldBeVisible);

      // Update checkbox
      const checkbox = document.querySelector(`input#layer-${layerId}`);
      if (checkbox) {
        checkbox.checked = shouldBeVisible;
      }

      console.log(`[InteractionController]   └─ ${layerId}: ${shouldBeVisible}`);
    }

    this._updatePolygonOpacity();
  }

  /**
   * Get checkbox element for a layer.
   */
  getLayerCheckbox(layerId) {
    return document.querySelector(`input#layer-${layerId}`);
  }

  /**
   * Initialize GetFeatureInfo click handler.
   * Milestone 2.3
   */
  initializeGetFeatureInfo(wmsBaseUrl) {
    console.log('[InteractionController] Initializing GetFeatureInfo...');

    this.wmsBaseUrl = wmsBaseUrl;

    // Create popup overlay
    this._createPopupOverlay();

    // Add click handler to map
    this.mapController.getMap().on('singleclick', (evt) => {
      this._handleMapClick(evt);
    });

    console.log('[InteractionController] GetFeatureInfo enabled');
  }

  /**
   * Create popup overlay for feature info display.
   * @private
   */
  _createPopupOverlay() {
    // Create popup container
    const popupContainer = document.createElement('div');
    popupContainer.id = 'feature-info-popup';
    popupContainer.className = 'feature-info-popup';
    popupContainer.innerHTML = `
      <div class="popup-closer" id="popup-closer">&times;</div>
      <div class="popup-content" id="popup-content"></div>
    `;
    document.body.appendChild(popupContainer);

    // Create OpenLayers overlay
    this.popup = new ol.Overlay({
      element: popupContainer,
      autoPan: true,
      autoPanAnimation: {
        duration: 250
      }
    });

    this.mapController.getMap().addOverlay(this.popup);

    // Close button handler
    document.getElementById('popup-closer').onclick = () => {
      this.popup.setPosition(undefined);
      return false;
    };
  }

  /**
   * Handle map click for GetFeatureInfo.
   * @private
   */
  async _handleMapClick(evt) {
    // History owns its vector snapshot clicks so one click selects a Tabia
    // and updates the indicator table/chart, rather than opening the general
    // Atlas GetFeatureInfo popup as a competing interaction.
    if (['history', 'priority'].includes(document.body.dataset.tsirdDroughtMode)) {
      this.popup.setPosition(undefined);
      return;
    }
    const coordinate = evt.coordinate;
    const viewResolution = this.mapController.getView().getResolution();
    const projection = this.mapController.getView().getProjection();

    // Get all visible and queryable layers (in reverse order, topmost first)
    const queryableLayers = this.layers
      .filter(layer => layer.getVisible() && layer.layerDef.queryable)
      .reverse();

    if (queryableLayers.length === 0) {
      // No queryable layers visible
      this.popup.setPosition(undefined);
      return;
    }

    console.log(`[InteractionController] GetFeatureInfo: ${queryableLayers.length} queryable layers`);

    // Query each layer
    const results = [];
    for (const layer of queryableLayers) {
      try {
        const source = layer.getSource();
        const url = source.getFeatureInfoUrl(
          coordinate,
          viewResolution,
          projection,
          {
            'INFO_FORMAT': 'application/vnd.ogc.gml',  // MapServer GML format
            'FEATURE_COUNT': 10
          }
        );

        if (url) {
          const response = await fetch(url);
          if (response.ok) {
            const xmlText = await response.text();  // Changed from response.json()
            const features = this._parseGetFeatureInfoXML(xmlText);
            
            if (features && features.length > 0) {
              results.push({
                layerId: layer.layerId,
                layerLabel: layer.layerDef.label,
                layerDef: layer.layerDef,
                features: features
              });
            }
          }
        }
      } catch (error) {
        console.error(`[InteractionController] GetFeatureInfo failed for ${layer.layerId}:`, error);
      }
    }

    // Display results
    if (results.length > 0) {
      this._displayFeatureInfo(results, coordinate);
      this._emitSelectedTabia(results);
    } else {
      this.popup.setPosition(undefined);
    }
  }

  /**
   * Announce a Tabia selected through the standard GetFeatureInfo path.
   * Consumers receive the stable TSIRD identity, never a name-based match.
   * @private
   */
  _emitSelectedTabia(results) {
    const tabiaResult = results.find(result => result.layerId === 'tigray_tabias_ti_en_pg');
    const props = tabiaResult && tabiaResult.features && tabiaResult.features[0] && tabiaResult.features[0].properties;
    if (!props || !props.tsird_tabia_id) return;
    window.dispatchEvent(new CustomEvent('tsird:boundary-selected', {
      detail: {
        type: 'tabia',
        id: props.tsird_tabia_id,
        name_en: props.TABIA || '',
        parent_name_en: props.WEREDA || ''
      }
    }));
  }

  /**
   * Parse WMS GetFeatureInfo GML response from MapServer.
   * Uses namespace-safe element iteration (no CSS wildcard selectors).
   * @private
   */
  _parseGetFeatureInfoXML(xmlText) {
    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(xmlText, 'text/xml');
    
    // Check for XML parsing errors
    const parserError = xmlDoc.querySelector('parsererror');
    if (parserError) {
      console.error('[InteractionController] XML parsing error:', parserError.textContent);
      return [];
    }

    // Check for ServiceException (error response)
    const serviceException = xmlDoc.querySelector('ServiceException');
    if (serviceException) {
      console.error('[InteractionController] WMS ServiceException:', serviceException.textContent);
      return [];
    }

    const features = [];
    
    // MapServer GML format: find all elements ending with _feature
    // Use localName to be namespace-safe (no CSS wildcard selectors)
    const allElements = xmlDoc.getElementsByTagName('*');
    const featureNodes = [];
    
    for (const el of allElements) {
      const name = el.localName || el.tagName;
      if (name.endsWith('_feature')) {
        featureNodes.push(el);
      }
    }
    
    console.log(`[InteractionController] Found ${featureNodes.length} feature nodes in GML`);
    
    // Extract properties from each feature node
    for (const featureEl of featureNodes) {
      const properties = {};
      
      // Iterate through child elements (field nodes)
      for (const child of featureEl.children) {
        const key = child.localName || child.tagName;
        
        // Skip gml:boundedBy and similar metadata elements
        if (key === 'boundedBy' || key.startsWith('gml:')) {
          continue;
        }
        
        const value = child.textContent.trim();
        if (value) {
          properties[key] = value;
        }
      }
      
      if (Object.keys(properties).length > 0) {
        features.push({ properties });
      }
    }
    
    console.log(`[InteractionController] Parsed ${features.length} features with properties`);
    return features;
  }

  /**
   * Display GetFeatureInfo results in popup.
   * Filters attributes by identify_fields allowlist.
   * @private
   */
  _displayFeatureInfo(results, coordinate) {
    const popupContent = document.getElementById('popup-content');
    let html = '';

    for (const result of results) {
      html += `<div class="layer-results">`;
      html += `<h4>${result.layerLabel}</h4>`;

      for (const feature of result.features) {
        const props = feature.properties || {};
        const allowlist = result.layerDef.identify_fields || [];

        // Filter properties by allowlist
        const filteredProps = {};
        if (allowlist.length > 0) {
          for (const field of allowlist) {
            if (props.hasOwnProperty(field)) {
              filteredProps[field] = props[field];
            }
          }
        } else {
          // No allowlist: show all (fallback, shouldn't happen with proper registry)
          Object.assign(filteredProps, props);
        }

        // Render attributes
        html += `<div class="feature-attributes">`;
        for (const [key, value] of Object.entries(filteredProps)) {
          // Format numeric values to 2 decimal places
          let displayValue = value;
          if (value !== null && value !== '') {
            const numVal = parseFloat(value);
            if (!isNaN(numVal) && value.toString().includes('.')) {
              displayValue = numVal.toFixed(2);
            }
          }
          html += `<div class="attribute-row">`;
          html += `<span class="attribute-key">${key}:</span> `;
          html += `<span class="attribute-value">${displayValue !== null ? displayValue : 'N/A'}</span>`;
          html += `</div>`;
        }
        html += `</div>`;
      }

      html += `</div>`;
    }

    popupContent.innerHTML = html;
    this.popup.setPosition(coordinate);

    console.log(`[InteractionController] Displayed feature info: ${results.length} layers`);
  }
}

// Export for use in main.js
if (typeof module !== 'undefined' && module.exports) {
  module.exports = InteractionController;
}
