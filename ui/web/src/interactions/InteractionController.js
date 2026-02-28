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

    // Render Display Settings panel (global boundary opacity)
    this._renderDisplaySettings(container);

    // Render categories
    for (const category of this.tocModel) {
      const categoryElement = this._renderCategory(category);
      container.appendChild(categoryElement);
    }

    // Credits panel (UI-only)
    this._renderCreditsPanel(container);

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

    // Legend toggle button (only for WMS layers, not basemaps)
    if (!layerDef.base_layer) {
      const legendToggle = document.createElement('button');
      legendToggle.className = 'toc-legend-toggle';
      legendToggle.title = 'Show/hide legend';
      legendToggle.innerHTML = '<span class="legend-icon">◧</span>';
      legendToggle.addEventListener('click', (e) => {
        e.stopPropagation();
        this._toggleLegend(layerId, layerDef.wms_name, layerDiv, legendToggle);
      });
      layerRow.appendChild(legendToggle);

      // Legend container (hidden by default)
      const legendContainer = document.createElement('div');
      legendContainer.className = 'toc-legend-container';
      legendContainer.id = `legend-${layerId}`;
      legendContainer.style.display = 'none';
      layerDiv.appendChild(legendContainer);
    }

    layerDiv.appendChild(layerRow);

    return layerDiv;
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
        this._loadLegend(wmsName, legendContainer);
      }
    }
  }

  /**
   * Load legend image via WMS GetLegendGraphic.
   * @private
   */
  _loadLegend(wmsName, container) {
    const wmsBaseUrl = this.mapController.wmsBaseUrl;
    const legendUrl = `${wmsBaseUrl}?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetLegendGraphic&LAYER=${encodeURIComponent(wmsName)}&FORMAT=image/png&SLD_VERSION=1.1.0`;
    
    // Show loading state
    container.innerHTML = '<div class="toc-legend-header">Legend</div><span class="toc-legend-loading">Loading...</span>';
    
    const img = document.createElement('img');
    img.className = 'toc-legend-image';
    img.alt = `Legend for ${wmsName}`;
    
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
   * Render Display Settings panel with global boundary opacity slider.
   * @private
   */
  _renderDisplaySettings(container) {
    const panel = document.createElement('div');
    panel.className = 'toc-display-settings';
    panel.id = 'display-settings-panel';

    const header = document.createElement('div');
    header.className = 'toc-display-settings-header';
    header.textContent = 'Display Settings';

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

    panel.appendChild(header);
    panel.appendChild(row);
    container.appendChild(panel);

    // Apply initial boundary opacity
    this._applyBoundaryOpacity(initialValue / 100);
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
    const panel = document.getElementById('display-settings-panel');
    if (!panel) return;

    // Check if any raster or basemap is visible
    const anyRasterOrBasemapVisible = this.olLayers.some(layer => {
      const def = layer.get('layerDef');
      if (!def) return false;
      const isRaster = def.type === 'raster';
      const isBasemap = def.base_layer === true;
      return (isRaster || isBasemap) && layer.getVisible();
    });

    panel.style.display = anyRasterOrBasemapVisible ? 'block' : 'none';
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
            'INFO_FORMAT': 'text/xml',  // Changed from application/json to text/xml
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
    } else {
      this.popup.setPosition(undefined);
    }
  }

  /**
   * Parse WMS GetFeatureInfo XML response.
   * Extracts feature attributes from MapServer XML format.
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

    const features = [];
    
    // MapServer GetFeatureInfo XML format typically uses <FeatureInfoResponse> or similar
    // Extract feature elements (adjust selector based on actual MapServer response)
    const featureElements = xmlDoc.querySelectorAll('FeatureInfoResponse > FIELDS, Layer > Feature, FeatureInfo');
    
    if (featureElements.length === 0) {
      // Try alternative common formats
      const altFeatures = xmlDoc.querySelectorAll('FeatureCollection > featureMember, msGMLOutput > *_layer > *_feature');
      
      if (altFeatures.length > 0) {
        altFeatures.forEach(featureEl => {
          const properties = {};
          
          // Extract all child elements as properties
          Array.from(featureEl.children).forEach(child => {
            const key = child.tagName.replace(/.*:/, ''); // Remove namespace prefix
            const value = child.textContent.trim();
            properties[key] = value;
          });
          
          if (Object.keys(properties).length > 0) {
            features.push({ properties });
          }
        });
      }
    } else {
      // Parse standard FeatureInfoResponse format
      featureElements.forEach(featureEl => {
        const properties = {};
        
        // Extract attributes from XML element
        Array.from(featureEl.attributes).forEach(attr => {
          properties[attr.name] = attr.value;
        });
        
        // Also check child elements
        Array.from(featureEl.children).forEach(child => {
          const key = child.tagName.replace(/.*:/, ''); // Remove namespace prefix
          const value = child.textContent.trim();
          properties[key] = value;
        });
        
        if (Object.keys(properties).length > 0) {
          features.push({ properties });
        }
      });
    }
    
    console.log(`[InteractionController] Parsed ${features.length} features from XML`);
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
          html += `<div class="attribute-row">`;
          html += `<span class="attribute-key">${key}:</span> `;
          html += `<span class="attribute-value">${value !== null ? value : 'N/A'}</span>`;
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
