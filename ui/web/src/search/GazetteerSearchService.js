/**
 * GazetteerSearchService.js — High-level search service
 * 
 * Single entry point for gazetteer search functionality.
 * Combines GazetteerLoader, TextUtils, and SearchIndex into a simple API.
 */

const GazetteerSearchService = {
  _index: null,
  _initialized: false,
  _gazetteer: null,

  /**
   * Initialize the gazetteer search service.
   * Loads the gazetteer and builds the search index.
   * 
   * @param {Object} [options] - Options
   * @param {string} [options.path] - Custom gazetteer path
   * @returns {Promise<Object>} Service object with search() method
   */
  async init(options = {}) {
    if (this._initialized) {
      console.log('[GazetteerSearchService] Already initialized');
      return this;
    }

    console.log('[GazetteerSearchService] Initializing...');

    try {
      // Load gazetteer
      this._gazetteer = await GazetteerLoader.load(options.path);
      
      // Build search index
      this._index = SearchIndex.buildIndex(this._gazetteer.records);
      
      this._initialized = true;
      console.log(`[GazetteerSearchService] Ready. ${this._gazetteer.records.length} records indexed.`);
      
      return this;

    } catch (error) {
      console.error('[GazetteerSearchService] Initialization failed:', error.message);
      throw error;
    }
  },

  /**
   * Search for Woredas and Tabias.
   * 
   * @param {string} query - Search query (min 2 characters)
   * @param {Object} [options] - Search options
   * @param {number} [options.limit=20] - Maximum results
   * @param {string} [options.type] - Filter by 'woreda' or 'tabia'
   * @returns {Array} Search results
   */
  search(query, options = {}) {
    if (!this._initialized) {
      console.warn('[GazetteerSearchService] Not initialized. Call init() first.');
      return [];
    }

    return SearchIndex.search(this._index, query, options);
  },

  /**
   * Get a record by ID.
   * 
   * @param {string} id - Record ID
   * @returns {Object|null} Record or null
   */
  getById(id) {
    if (!this._initialized) {
      console.warn('[GazetteerSearchService] Not initialized. Call init() first.');
      return null;
    }

    return SearchIndex.getById(this._index, id);
  },

  /**
   * Get service status.
   * 
   * @returns {Object} Status object
   */
  getStatus() {
    return {
      initialized: this._initialized,
      recordCount: this._index ? this._index.entries.length : 0,
      version: this._gazetteer ? this._gazetteer.version : null
    };
  },

  /**
   * Run a diagnostic test (for console verification).
   * 
   * @param {string} [testQuery='adw'] - Test query
   */
  runDiagnostic(testQuery = 'adw') {
    console.log('═══════════════════════════════════════════════════');
    console.log('[GazetteerSearchService] Diagnostic');
    console.log('═══════════════════════════════════════════════════');
    
    const status = this.getStatus();
    console.log('Status:', status);
    
    if (status.initialized) {
      console.log(`Test query: "${testQuery}"`);
      const results = this.search(testQuery);
      console.log(`Results (${results.length}):`, results);
    } else {
      console.log('Service not initialized. Run: window.tsirdSearch.init()');
    }
    
    console.log('═══════════════════════════════════════════════════');
  }
};

// Export for browser and Node.js
if (typeof module !== 'undefined' && module.exports) {
  module.exports = GazetteerSearchService;
} else if (typeof window !== 'undefined') {
  window.GazetteerSearchService = GazetteerSearchService;
  
  // Also expose as window.tsirdSearch for easy console access
  window.tsirdSearch = {
    init: () => GazetteerSearchService.init(),
    search: (q, opts) => GazetteerSearchService.search(q, opts),
    getById: (id) => GazetteerSearchService.getById(id),
    status: () => GazetteerSearchService.getStatus(),
    diagnostic: (q) => GazetteerSearchService.runDiagnostic(q)
  };
}
