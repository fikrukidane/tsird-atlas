/**
 * GazetteerLoader.js — Fetch and validate gazetteer JSON
 * 
 * Loads the Woreda/Tabia gazetteer from /map/data/gazetteer-woreda-tabia.v1.json
 * Uses explicit /map/ prefix for compatibility with nginx routing.
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
   * @throws {Error} On fetch failure or validation error
   */
  async load(path) {
    const gazetteerPath = path || this.DEFAULT_PATH;
    
    console.log(`[GazetteerLoader] Fetching: ${gazetteerPath}`);

    try {
      const response = await fetch(gazetteerPath);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: Could not fetch gazetteer from ${gazetteerPath}`);
      }

      const data = await response.json();
      
      // Validate required fields
      this._validate(data);
      
      console.log(`[GazetteerLoader] Loaded successfully: ${data.records.length} records`);
      return data;

    } catch (error) {
      console.error('[GazetteerLoader] Error:', error.message);
      throw error;
    }
  },

  /**
   * Validate gazetteer structure.
   * 
   * @param {Object} data - Parsed JSON
   * @throws {Error} If validation fails
   */
  _validate(data) {
    if (!data || typeof data !== 'object') {
      throw new Error('Gazetteer must be a JSON object');
    }
    
    if (!data.version) {
      throw new Error('Gazetteer missing required field: version');
    }
    
    if (!data.crs) {
      throw new Error('Gazetteer missing required field: crs');
    }
    
    if (!Array.isArray(data.records)) {
      throw new Error('Gazetteer missing required field: records (must be array)');
    }
    
    // Validate each record has minimum required fields
    data.records.forEach((record, idx) => {
      if (!record.type || !record.id || !record.name) {
        throw new Error(`Gazetteer record[${idx}] missing required fields (type, id, name)`);
      }
      if (!['woreda', 'tabia'].includes(record.type)) {
        throw new Error(`Gazetteer record[${idx}] has invalid type: ${record.type}`);
      }
    });
  }
};

// Export for browser and Node.js
if (typeof module !== 'undefined' && module.exports) {
  module.exports = GazetteerLoader;
} else if (typeof window !== 'undefined') {
  window.GazetteerLoader = GazetteerLoader;
}
