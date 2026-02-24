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
  }

  /**
   * Handle layer toggle.
   * Milestone 2: Integrates scale constraints and mutex enforcement
   * @private
   */
  _onLayerToggle(layerId, enabled) {
    const layer = this.layerMap[layerId];
    if (!layer) {
      console.warn(`[InteractionController] Layer not found: ${layerId}`);
      return;
    }

    // Update user-requested state
    this.userVisibilityState[layerId] = enabled;

    // Apply visibility with scale and mutex constraints
    this._updateLayerVisibility(layerId);

    console.log(`[InteractionController] Layer toggled: ${layerId} = ${enabled} (user request)`);
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
      return;
    }

    // Step 2: Check scale constraint
    const currentScale = ScaleEngine.getCurrentScale(this.mapController.getView());
    const inScale = ScaleEngine.isLayerInScale(layerDef, currentScale);

    if (!inScale) {
      layer.setVisible(false);
      this._updateLayerCheckboxState(layerId, false, 'out-of-scale');
      console.log(`[InteractionController] ${layerId}: OUT OF SCALE (${ScaleEngine.formatScale(currentScale)})`);
      return;
    }

    // Step 3: Check mutex constraints
    const mutexBlocker = this._getMutexBlocker(layerId);
    if (mutexBlocker) {
      layer.setVisible(false);
      this._updateLayerCheckboxState(layerId, false, 'mutex-suppressed');
      console.log(`[InteractionController] ${layerId}: SUPPRESSED by mutex pair with ${mutexBlocker}`);
      return;
    }

    // All constraints satisfied: show layer
    layer.setVisible(true);
    this._updateLayerCheckboxState(layerId, true, null);
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
