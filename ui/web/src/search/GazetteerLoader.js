/**
 * GazetteerLoader.js — Fetch and validate gazetteer JSON
 * 
 * Uses explicit /map/data/ prefix for nginx routing compatibility.
 */

const GazetteerLoader = {
  /**
   * Default gazetteer path (absolute under /map/)
   * CRITICAL: Must use /map/data/ prefix for nginx routing
   */
  DEFAULT_PATH: '/map/data/gazetteer-woreda-tabia.v1.json',

  /**
   * Load and validate the gazetteer JSON.
   * 
   * @param {string} [path] - Optional custom path (defaults to DEFAULT_PATH)
   * @returns {Promise<Object>} Parsed gazetteer with version, crs, records
   */
  async loadGazetteer(path) {
    const gazetteerPath = path || this.DEFAULT_PATH;
    
    console.log(`[GazetteerLoader] Fetching: ${gazetteerPath}`);

    try {
      const response = await fetch(gazetteerPath);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: Could not fetch gazetteer`);
      }

      const data = await response.json();
      this._validate(data);
      
      console.log(`[GazetteerLoader] Loaded: ${data.records.length} records`);
      return data;

    } catch (error) {
      console.error('[GazetteerLoader] Error:', error.message);
      throw error;
    }
  },

  /**
   * Validate gazetteer structure.
   */
  _validate(data) {
    if (!data || typeof data !== 'object') {
      throw new Error('Gazetteer must be a JSON object');
    }
    if (!data.version) {
      throw new Error('Gazetteer missing: version');
    }
    if (!data.crs) {
      throw new Error('Gazetteer missing: crs');
    }
    if (!Array.isArray(data.records)) {
      throw new Error('Gazetteer missing: records array');
    }
  }
};

// Export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = GazetteerLoader;
} else if (typeof window !== 'undefined') {
  window.GazetteerLoader = GazetteerLoader;
}
