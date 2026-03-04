/**
 * RegistryLoader — Load and normalize YAML/JSON registry
 * 
 * Single responsibility: Parse registry file and emit normalized internal model.
 * 
 * Output structure:
 *   {
 *     atlasConfig: { title, center, zoom, canonical_crs, view_crs, extent },
 *     tocModel: [ { id, label, groups: [ { id, label, layers: [...] } ] } ],
 *     layerDefs: { [layer_id]: { wms_name, label, published, ... } },
 *     scaleMutexPairs: [ [id1, id2], ... ]
 *   }
 */

class RegistryLoader {
  constructor(registryPath) {
    this.registryPath = registryPath;
    this.rawRegistry = null;
    this.lastError = null;
    
    // Event listeners
    this._onLoadListeners = [];
    this._onErrorListeners = [];
  }

  /**
   * Load and parse registry from path.
   * Supports both .yaml (via js-yaml) and .json
   * 
   * @returns {Promise<Object>} Normalized registry model
   */
  async load() {
    try {
      const response = await fetch(this.registryPath);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: Could not fetch registry`);
      }

      const contentType = response.headers.get('content-type');
      let data;

      if (contentType && contentType.includes('json')) {
        data = await response.json();
      } else if (this.registryPath.endsWith('.yaml') || this.registryPath.endsWith('.yml')) {
        // Text response for YAML; parse with js-yaml (must be loaded globally)
        const text = await response.text();
        if (typeof window.jsyaml === 'undefined') {
          throw new Error('js-yaml library not loaded. Include <script src="https://cdn.jsdelivr.net/npm/js-yaml@4.1.0/dist/js-yaml.min.js"></script>');
        }
        data = window.jsyaml.load(text);
      } else {
        throw new Error(`Unsupported registry format: ${this.registryPath}`);
      }

      this.rawRegistry = data;
      const normalized = this._normalize(data);
      
      this._emit('load', normalized);
      return normalized;

    } catch (error) {
      this.lastError = error;
      console.error('[RegistryLoader] Error:', error.message);
      this._emit('error', {
        message: 'Registry unavailable. Please try again later.',
        details: error.message
      });
      throw error;
    }
  }

  /**
   * Validate registry matches frozen CONFIG_MODEL.md schema.
   * 
   * Frozen contract requirements:
   *   - version field must exist
   *   - atlas, services, ui must exist
   *   - categories must be array
   *   - categories[].groups[].layers must be array of STRINGS (layer IDs only)
   *   - layers must be top-level DICT with full metadata
   *   - search must exist (can be empty array)
   *   - rules must exist
   * 
   * @private
   * @throws {Error} If schema is invalid
   */
  _validateSchema(raw) {
    const errors = [];

    // Check required top-level fields
    if (!raw.version) {
      errors.push("Missing 'version' field");
    }
    if (!raw.atlas) {
      errors.push("Missing 'atlas' configuration");
    }
    if (!raw.services || !raw.services.wms) {
      errors.push("Missing 'services.wms' configuration");
    }
    if (!raw.ui) {
      errors.push("Missing 'ui' configuration");
    }

    // Check categories structure
    if (!Array.isArray(raw.categories)) {
      errors.push("'categories' must be an array");
    } else {
      for (let i = 0; i < raw.categories.length; i++) {
        const cat = raw.categories[i];
        if (!Array.isArray(cat.groups)) {
          errors.push(`categories[${i}] missing 'groups' array`);
        } else {
          for (let j = 0; j < cat.groups.length; j++) {
            const grp = cat.groups[j];
            if (!Array.isArray(grp.layers)) {
              errors.push(`categories[${i}].groups[${j}] missing 'layers' array`);
            } else {
              // Validate each layer is a STRING (ID), not an object
              for (let k = 0; k < grp.layers.length; k++) {
                const layer = grp.layers[k];
                if (typeof layer !== 'string') {
                  errors.push(
                    `categories[${i}].groups[${j}].layers[${k}] must be ID string, ` +
                    `got ${typeof layer}. (Frozen schema: use layer IDs only, metadata in top-level 'layers' dict)`
                  );
                }
              }
            }
          }
        }
      }
    }

    // Check layers dict exists
    if (typeof raw.layers !== 'object' || raw.layers === null) {
      errors.push("Missing top-level 'layers' dictionary (must contain full layer metadata)");
    }

    // Check search exists
    if (!Array.isArray(raw.search)) {
      errors.push("Missing 'search' array (can be empty)");
    }

    // Check rules exists
    if (!raw.rules) {
      errors.push("Missing 'rules' object");
    }

    if (errors.length > 0) {
      throw new Error(
        'Registry schema validation failed:\n  - ' + errors.join('\n  - ')
      );
    }
  }

  /**
   * Normalize raw registry into internal model.
   * Handles frozen CONFIG_MODEL.md schema where:
   *   - categories[].groups[].layers[] = array of STRING IDs (not objects)
   *   - full layer metadata in top-level raw.layers[layer_id]
   * 
   * @private
   */
  _normalize(raw) {
    // STEP 1: Validate schema (will throw if invalid)
    this._validateSchema(raw);

    // STEP 2: Extract atlas config
    const atlas = raw.atlas || {};
    const atlasConfig = {
      title: atlas.title || 'TSIRD Atlas',
      center: atlas.center || [38.5, 13.5],
      zoom: atlas.zoom || 7,
      canonical_crs: atlas.canonical_crs || 'EPSG:4326',
      view_crs: atlas.view_crs || 'EPSG:3857',
      extent: atlas.extent || [33.0, 3.0, 48.0, 15.5]
    };

    // STEP 3: Extract WMS base URL with environment override
    let wmsBaseUrl = (raw.services?.wms?.base_url) || '/map/ogc';
    
    // Environment override: check for window.TSIRD_WMS_BASE_URL
    if (window.TSIRD_WMS_BASE_URL) {
      console.warn(
        `[RegistryLoader] WMS base_url overridden by environment: ${window.TSIRD_WMS_BASE_URL}`
      );
      wmsBaseUrl = window.TSIRD_WMS_BASE_URL;
    }
    
    // Safety guard: warn if relative URL in production-like context
    if (wmsBaseUrl.startsWith('/')) {
      console.warn(
        `[RegistryLoader] WMS base_url is relative: '${wmsBaseUrl}'. ` +
        `This will resolve to the frontend origin (${window.location.origin}), not MapServer. ` +
        `For local dev, use: http://localhost:18080/map/ogc. ` +
        `For production, use absolute URL or set window.TSIRD_WMS_BASE_URL override.`
      );
      
      // In dev mode, attempt to resolve to known dev MapServer if on localhost:8001
      if (window.location.hostname === 'localhost' && window.location.port === '8001') {
        const devUrl = 'http://localhost:18080/map/ogc';
        console.warn(
          `[RegistryLoader] Auto-resolving to dev MapServer: ${devUrl}`
        );
        wmsBaseUrl = devUrl;
      }
    }
    
    console.log(`[RegistryLoader] Final WMS base URL: ${wmsBaseUrl}`);

    // STEP 4: Build layer definitions from raw.layers dictionary
    const layerDefs = {};
    const layersDict = raw.layers || {};
    
    for (const [layerId, layerMeta] of Object.entries(layersDict)) {
      // Pass through all raw properties, then override/normalize as needed
      layerDefs[layerId] = {
        ...layerMeta,
        wms_name: layerMeta.wms_name,
        label: layerMeta.label || layerMeta.wms_name || layerId,
        type: layerMeta.type,
        published: layerMeta.published !== false,
        default_visible: layerMeta.default_visible === true,
        queryable: layerMeta.queryable === true,
        min_scale: layerMeta.min_scale,
        max_scale: layerMeta.max_scale,
        identify_fields: layerMeta.identify_fields || [],
        source: layerMeta.source,
        geometry_type: layerMeta.geometry_type,
        attribution: layerMeta.attribution,
        source_type: layerMeta.source_type,
        base_layer: layerMeta.base_layer === true,
        url_template: layerMeta.url_template,
        opacity: layerMeta.opacity,
        legend_mode: layerMeta.legend_mode ?? layerMeta.legendMode ?? null,
        legend: typeof layerMeta.legend !== 'undefined' ? layerMeta.legend : true,
      };
    }

    // STEP 5: Build TOC model from categories[].groups[].layers[] (now strings)
    const tocModel = [];
    const categories = raw.categories || [];
    
    for (const category of categories) {
      const categoryNode = {
        id: category.id || `cat_${categories.indexOf(category)}`,
        label: category.label || 'Category',
        closed: category.closed === true,
        groups: []
      };

      const groups = category.groups || [];
      for (const group of groups) {
        const groupNode = {
          id: group.id || `grp_${groups.indexOf(group)}`,
          label: group.label || 'Group',
          closed: group.closed === true,
          layers: []
        };

        const layerIds = group.layers || [];  // Array of STRINGS now
        for (const layerId of layerIds) {
          // Look up layer metadata from raw.layers[layerId]
          const layerMeta = layersDict[layerId];
          if (!layerMeta) {
            console.warn(`[RegistryLoader] Layer '${layerId}' referenced in TOC but not defined in layers dict`);
            continue;
          }

          // Only add to TOC if published
          if (layerMeta.published !== false) {
            groupNode.layers.push({
              id: layerId,
              label: layerMeta.label || layerId
            });
          }
        }

        // Always include group to preserve folder structure
        categoryNode.groups.push(groupNode);
      }

      // Always include category to preserve folder structure
      tocModel.push(categoryNode);
    }

    // STEP 6: Extract scale mutex pairs
    const scaleMutexPairs = (raw.rules?.scale_mutex_pairs) || [];

    return {
      atlasConfig,
      wmsBaseUrl,
      tocModel,
      layerDefs,
      scaleMutexPairs
    };
  }

  /**
   * Attach event listener for load success.
   */
  onLoad(callback) {
    this._onLoadListeners.push(callback);
  }

  /**
   * Attach event listener for load error.
   */
  onError(callback) {
    this._onErrorListeners.push(callback);
  }

  /**
   * @private Emit event to listeners
   */
  _emit(eventType, data) {
    if (eventType === 'load') {
      this._onLoadListeners.forEach(cb => cb(data));
    } else if (eventType === 'error') {
      this._onErrorListeners.forEach(cb => cb(data));
    }
  }
}

// Export for use in main.js
if (typeof module !== 'undefined' && module.exports) {
  module.exports = RegistryLoader;
}
