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
   * Normalize raw registry into internal model.
   * Validates basic structure; full validation done by Stage 4 CLI.
   * 
   * @private
   */
  _normalize(raw) {
    // Extract atlas config
    const atlas = raw.atlas || {};
    const atlasConfig = {
      title: atlas.title || 'TSIRD Atlas',
      center: atlas.center || [38.5, 13.5],
      zoom: atlas.zoom || 7,
      canonical_crs: atlas.canonical_crs || 'EPSG:4326',
      view_crs: atlas.view_crs || 'EPSG:3857',
      extent: atlas.extent || [33.0, 3.0, 48.0, 15.5]
    };

    // Extract WMS base URL
    const wmsBaseUrl = (raw.services?.wms?.base_url) || '/map/ogc';

    // Build layer definitions dictionary
    const layerDefs = {};
    const tocModel = [];

    // Traverse categories → groups → layers, maintaining order
    const categories = raw.categories || [];
    
    for (const category of categories) {
      const categoryNode = {
        id: category.id || `cat_${categories.indexOf(category)}`,
        label: category.label || 'Category',
        groups: []
      };

      const groups = category.groups || [];
      for (const group of groups) {
        const groupNode = {
          id: group.id || `grp_${groups.indexOf(group)}`,
          label: group.label || 'Group',
          layers: []
        };

        const layers = group.layers || [];
        for (const layer of layers) {
          // Store full layer definition
          layerDefs[layer.id] = {
            wms_name: layer.wms_name,
            label: layer.label || layer.wms_name,
            type: layer.type,
            published: layer.published !== false,  // Default true if missing
            default_visible: layer.default_visible === true,
            queryable: layer.queryable === true,
            min_scale: layer.min_scale,
            max_scale: layer.max_scale,
            identify_fields: layer.identify_fields || [],
            source: layer.source,
            geometry_type: layer.geometry_type,
            attribution: layer.attribution
          };

          // Only add to TOC if published
          if (layerDefs[layer.id].published) {
            groupNode.layers.push({
              id: layer.id,
              label: layerDefs[layer.id].label
            });
          }
        }

        // Only add group to TOC if it has layers
        if (groupNode.layers.length > 0) {
          categoryNode.groups.push(groupNode);
        }
      }

      // Only add category to TOC if it has groups
      if (categoryNode.groups.length > 0) {
        tocModel.push(categoryNode);
      }
    }

    // Extract scale mutex pairs
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
