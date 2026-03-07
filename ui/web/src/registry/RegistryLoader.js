/**
 * RegistryLoader — Load and normalize YAML/JSON registry
 *
 * Plain browser global class (no ES module syntax).
 * Loaded via <script src="src/registry/RegistryLoader.js">.
 *
 * Output structure:
 *   {
 *     atlasConfig: { title, center, zoom, canonical_crs, view_crs, extent },
 *     tocModel: [ { id, label, groups: [ { id, label, layers: [...] } ] } ],
 *     layerDefs: { [layer_id]: { wms_name, label, published, ... } },
 *     scaleMutexPairs: [ [id1, id2], ... ],
 *     wmsBaseUrl: string,
 *     search_config: object
 *   }
 */
class RegistryLoader {
  constructor(registryPath) {
    this.registryPath = registryPath;
    this.rawRegistry = null;
    this.lastError = null;
    this._onLoadListeners = [];
    this._onErrorListeners = [];
  }

  async load() {
    try {
      const resolvedUrl = new URL(this.registryPath, window.location.href);
      const response = await fetch(resolvedUrl);
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: Could not fetch registry`);
      }
      const contentType = response.headers.get('content-type') || '';
      let data;
      if (contentType.includes('json') || this.registryPath.endsWith('.json')) {
        data = await response.json();
      } else if (this.registryPath.endsWith('.yaml') || this.registryPath.endsWith('.yml')) {
        const text = await response.text();
        if (typeof window.jsyaml === 'undefined') {
          throw new Error('js-yaml not loaded');
        }
        data = window.jsyaml.load(text);
      } else {
        // Try JSON fallback
        data = await response.json();
      }
      this.rawRegistry = data;
      const normalized = this._normalize(data);
      this._emit('load', normalized);
      return normalized;
    } catch (error) {
      this.lastError = error;
      console.error('[RegistryLoader] Error:', error.message);
      this._emit('error', { message: 'Registry unavailable.', details: error.message });
      throw error;
    }
  }

  _validateSchema(raw) {
    const errors = [];
    if (!raw.version) errors.push("Missing 'version' field");
    if (!raw.atlas) errors.push("Missing 'atlas' configuration");
    if (!raw.services || !raw.services.wms) errors.push("Missing 'services.wms'");
    if (!raw.ui) errors.push("Missing 'ui' configuration");
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
              for (let k = 0; k < grp.layers.length; k++) {
                if (typeof grp.layers[k] !== 'string') {
                  errors.push(`categories[${i}].groups[${j}].layers[${k}] must be ID string`);
                }
              }
            }
          }
        }
      }
    }
    if (typeof raw.layers !== 'object' || raw.layers === null) {
      errors.push("Missing top-level 'layers' dictionary");
    }
    if (!Array.isArray(raw.search)) {
      errors.push("Missing 'search' array (can be empty)");
    }
    if (!raw.rules) {
      errors.push("Missing 'rules' object");
    }
    if (errors.length > 0) {
      console.error('[RegistryLoader] Schema validation errors:', errors);
      throw new Error('Registry schema validation failed:\n  - ' + errors.join('\n  - '));
    }
  }

  _normalize(raw) {
    this._validateSchema(raw);

    // Atlas config
    const atlas = raw.atlas || {};
    const atlasConfig = {
      title: atlas.title || 'TSIRD Atlas',
      center: atlas.center || [38.5, 13.5],
      zoom: atlas.zoom || 7,
      canonical_crs: atlas.canonical_crs || 'EPSG:4326',
      view_crs: atlas.view_crs || 'EPSG:3857',
      extent: atlas.extent || [33.0, 3.0, 48.0, 15.5],
    };

    // WMS base URL
    let wmsBaseUrl = (raw.services && raw.services.wms && raw.services.wms.base_url) || '/map/ogc';
    if (window.TSIRD_WMS_BASE_URL) {
      wmsBaseUrl = window.TSIRD_WMS_BASE_URL;
    }

    // Layer definitions
    const layerDefs = {};
    const layersDict = raw.layers || {};
    for (const layerId of Object.keys(layersDict)) {
      const m = layersDict[layerId];
      layerDefs[layerId] = {
        ...m,
        wms_name: m.wms_name,
        label: m.label || m.wms_name || layerId,
        type: m.type,
        published: m.published !== false,
        default_visible: m.default_visible === true,
        queryable: m.queryable === true,
        min_scale: m.min_scale,
        max_scale: m.max_scale,
        identify_fields: m.identify_fields || [],
        source: m.source,
        geometry_type: m.geometry_type,
        attribution: m.attribution,
        source_type: m.source_type,
        base_layer: m.base_layer === true,
        url_template: m.url_template,
        opacity: m.opacity,
        legend_mode: m.legend_mode !== undefined ? m.legend_mode : (m.legendMode !== undefined ? m.legendMode : null),
        legend: m.legend !== undefined ? m.legend : true,
        legend_url: m.legend_url || null,
        wms_base_url: m.wms_base_url,
        wms_version: m.wms_version,
        format: m.format,
        transparent: m.transparent,
        tiled: m.tiled,
        z_index: m.z_index,
        temporal: m.temporal || null,
        time_enabled: m.time_enabled === true || !!(m.temporal && m.temporal.mode === 'date'),
        time_mode: m.time_mode || 'global',
        time_default: m.time_default || null,
        time_param_name: m.time_param_name || 'TIME',
      };
    }

    // TOC model
    const tocModel = [];
    const categories = raw.categories || [];
    for (const category of categories) {
      const catNode = {
        id: category.id || ('cat_' + categories.indexOf(category)),
        label: category.label || 'Category',
        closed: category.closed === true,
        groups: []
      };
      for (const group of (category.groups || [])) {
        const grpNode = {
          id: group.id || ('grp_' + (category.groups || []).indexOf(group)),
          label: group.label || 'Group',
          closed: group.closed === true,
          layers: []
        };
        for (const layerId of (group.layers || [])) {
          const layerMeta = layersDict[layerId];
          if (!layerMeta) {
            console.warn('[RegistryLoader] Layer \'' + layerId + '\' in TOC but not in layers dict');
            continue;
          }
          if (layerMeta.published !== false) {
            grpNode.layers.push({ id: layerId, label: layerMeta.label || layerId });
          }
        }
        catNode.groups.push(grpNode);
      }
      tocModel.push(catNode);
    }

    const scaleMutexPairs = (raw.rules && raw.rules.scale_mutex_pairs) || [];

    return {
      ...raw,
      atlasConfig,
      wmsBaseUrl,
      tocModel,
      layerDefs,
      scaleMutexPairs,
    };
  }

  onLoad(callback) { this._onLoadListeners.push(callback); }
  onError(callback) { this._onErrorListeners.push(callback); }

  _emit(eventType, data) {
    const list = eventType === 'load' ? this._onLoadListeners : this._onErrorListeners;
    list.forEach(function(cb) { cb(data); });
  }
}
