/**
 * InteractionController — Manage user interactions
 * 
 * Milestone 1 scope: TOC rendering + per-layer toggle (no identify, no scale enforcement)
 * 
 * Responsibilities:
 *   - Render TOC from tocModel hierarchy
 *   - Implement layer toggle (checkbox → visibility)
 *   - Apply default visibility from registry (at startup)
 *   - Implement group toggle (optional)
 */

class InteractionController {
  constructor(tocContainerId, layers, tocModel, layerDefs) {
    this.tocContainerId = tocContainerId;
    this.layers = layers;  // Array of ol.layer.Tile objects
    this.tocModel = tocModel;  // Hierarchy: categories → groups → layers
    this.layerDefs = layerDefs;  // Metadata: { [id]: { ... } }
    
    // Map layer ID to ol.Layer for quick lookup
    this.layerMap = {};
    layers.forEach(layer => {
      this.layerMap[layer.layerId] = layer;
    });

    this.tocElement = null;
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

    // Render categories
    for (const category of this.tocModel) {
      const categoryElement = this._renderCategory(category);
      container.appendChild(categoryElement);
    }

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

    const categoryLabel = document.createElement('h3');
    categoryLabel.textContent = category.label;
    headerDiv.appendChild(categoryLabel);

    categoryDiv.appendChild(headerDiv);

    // Groups
    const groupsDiv = document.createElement('div');
    groupsDiv.className = 'toc-groups';

    for (const group of category.groups) {
      const groupElement = this._renderGroup(group);
      groupsDiv.appendChild(groupElement);
    }

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

    // Group header with checkbox (for group toggle)
    const headerDiv = document.createElement('div');
    headerDiv.className = 'toc-group-header';

    const groupCheckbox = document.createElement('input');
    groupCheckbox.type = 'checkbox';
    groupCheckbox.className = 'toc-group-checkbox';
    groupCheckbox.checked = false;  // Default unchecked
    groupCheckbox.addEventListener('change', (e) => {
      this._onGroupToggle(group.id, e.target.checked);
    });

    const groupLabel = document.createElement('label');
    groupLabel.className = 'toc-group-label';
    groupLabel.textContent = group.label;

    headerDiv.appendChild(groupCheckbox);
    headerDiv.appendChild(groupLabel);
    groupDiv.appendChild(headerDiv);

    // Layers
    const layersDiv = document.createElement('div');
    layersDiv.className = 'toc-layers';

    for (const layerRef of group.layers) {
      const layerElement = this._renderLayer(layerRef, group.id);
      layersDiv.appendChild(layerElement);
    }

    groupDiv.appendChild(layersDiv);
    return groupDiv;
  }

  /**
   * Render a single layer with checkbox.
   * @private
   */
  _renderLayer(layerRef, groupId) {
    const layerId = layerRef.id;
    const layerDef = this.layerDefs[layerId];

    const layerDiv = document.createElement('div');
    layerDiv.className = 'toc-layer';
    layerDiv.setAttribute('data-layer-id', layerId);

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

    layerDiv.appendChild(layerCheckbox);
    layerDiv.appendChild(layerLabel);

    return layerDiv;
  }

  /**
   * Initialize layer visibility based on default_visible.
   * Called after layers are added to map.
   */
  initializeLayerVisibility() {
    console.log('[InteractionController] Initializing layer visibility...');

    for (const layer of this.layers) {
      const layerId = layer.layerId;
      const layerDef = layer.layerDef;
      const isVisible = layerDef.default_visible === true;

      layer.setVisible(isVisible);

      console.log(`[InteractionController] ${layerId}: default_visible=${isVisible}`);
    }
  }

  /**
   * Handle layer toggle.
   * @private
   */
  _onLayerToggle(layerId, enabled) {
    const layer = this.layerMap[layerId];
    if (!layer) {
      console.warn(`[InteractionController] Layer not found: ${layerId}`);
      return;
    }

    layer.setVisible(enabled);
    console.log(`[InteractionController] Layer toggled: ${layerId} = ${enabled}`);

    // Update checkbox state
    const checkbox = document.querySelector(`input#layer-${layerId}`);
    if (checkbox) {
      checkbox.checked = enabled;
    }
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
  }

  /**
   * Get checkbox element for a layer.
   */
  getLayerCheckbox(layerId) {
    return document.querySelector(`input#layer-${layerId}`);
  }
}

// Export for use in main.js
if (typeof module !== 'undefined' && module.exports) {
  module.exports = InteractionController;
}
