/**
 * GazetteerSearchService.js — High-level search service singleton
 */

const GazetteerSearchService = {
  _index: null,
  _initialized: false,
  _gazetteer: null,

  /**
   * Initialize the gazetteer search service.
   * Loads the gazetteer and builds the search index.
   * Fails gracefully - returns empty results on error.
   * 
   * @returns {Promise<GazetteerSearchService>}
   */
  async initGazetteerSearch() {
    if (this._initialized) {
      console.log('[GazetteerSearchService] Already initialized');
      return this;
    }

    console.log('[GazetteerSearchService] Initializing...');

    try {
      this._gazetteer = await GazetteerLoader.loadGazetteer();
      this._index = SearchIndex.buildIndex(this._gazetteer.records);
      this._initialized = true;
      console.log(`[GazetteerSearchService] Ready: ${this._gazetteer.records.length} records`);
      return this;

    } catch (error) {
      console.warn('[GazetteerSearchService] Init failed (search will return empty):', error.message);
      this._initialized = true; // Mark as initialized to prevent retries
      this._index = { entries: [], byId: {} };
      return this;
    }
  },

  /**
   * Search for Woredas and Tabias.
   * 
   * @param {string} query - Search query (min 2 characters)
   * @param {Object} [options] - Search options
   * @returns {Array} Search results
   */
  search(query, options = {}) {
    if (!this._initialized || !this._index) {
      console.warn('[GazetteerSearchService] Not initialized');
      return [];
    }
    return SearchIndex.search(this._index, query, options);
  },

  /**
   * Get a record by ID.
   */
  getById(id) {
    if (!this._initialized || !this._index) return null;
    return SearchIndex.getById(this._index, id);
  },

  /**
   * Get service status.
   */
  getStatus() {
    return {
      initialized: this._initialized,
      recordCount: this._index ? this._index.entries.length : 0,
      version: this._gazetteer ? this._gazetteer.version : null
    };
  }
};

// Export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = GazetteerSearchService;
} else if (typeof window !== 'undefined') {
  window.GazetteerSearchService = GazetteerSearchService;
}
