/**
 * SearchIndex.js — In-memory search index for gazetteer
 * 
 * Builds a searchable index from gazetteer records and provides
 * prefix/contains matching with ranking.
 */

const SearchIndex = {
  /**
   * Build a searchable index from gazetteer records.
   * 
   * @param {Array} records - Gazetteer records array
   * @returns {Object} Index object for use with search()
   */
  buildIndex(records) {
    if (!Array.isArray(records)) {
      console.warn('[SearchIndex] buildIndex received non-array, returning empty index');
      return { entries: [], byId: {} };
    }

    const entries = [];
    const byId = {};

    records.forEach(record => {
      // Build searchable entry
      const entry = {
        type: record.type,
        id: record.id,
        name: record.name,
        name_norm: record.name_norm || TextUtils.normalizeText(record.name),
        aliases: record.aliases || [],
        aliases_norm: (record.aliases || []).map(a => TextUtils.normalizeText(a)),
        parent: record.parent || { woreda_id: null },
        center: record.center || null,
        bbox: record.bbox || null,
        admin: record.admin || {}
      };

      // Add tokenized name for partial matching
      entry.tokens = TextUtils.tokenize(entry.name_norm);

      entries.push(entry);
      byId[record.id] = entry;
    });

    console.log(`[SearchIndex] Built index with ${entries.length} entries`);
    return { entries, byId };
  },

  /**
   * Search the index for matching records.
   * 
   * @param {Object} index - Index object from buildIndex()
   * @param {string} query - Search query
   * @param {Object} [options] - Search options
   * @param {number} [options.limit=20] - Maximum results to return
   * @param {string} [options.type] - Filter by type ('woreda' or 'tabia')
   * @returns {Array} Matching records with score, sorted by relevance
   */
  search(index, query, options = {}) {
    const limit = options.limit || 20;
    const typeFilter = options.type || null;

    // Minimum query length
    if (!query || query.length < 2) {
      return [];
    }

    const queryNorm = TextUtils.normalizeText(query);
    if (!queryNorm) {
      return [];
    }

    const queryTokens = TextUtils.tokenize(queryNorm);
    const results = [];

    index.entries.forEach(entry => {
      // Type filter
      if (typeFilter && entry.type !== typeFilter) {
        return;
      }

      let score = 0;
      let matchType = null;

      // Priority 1: name_norm startsWith query (highest score)
      if (entry.name_norm.startsWith(queryNorm)) {
        score = 100;
        matchType = 'name-prefix';
      }
      // Priority 2: any alias startsWith query
      else if (entry.aliases_norm.some(a => a.startsWith(queryNorm))) {
        score = 80;
        matchType = 'alias-prefix';
      }
      // Priority 3: name_norm contains query
      else if (entry.name_norm.includes(queryNorm)) {
        score = 60;
        matchType = 'name-contains';
      }
      // Priority 4: any alias contains query
      else if (entry.aliases_norm.some(a => a.includes(queryNorm))) {
        score = 40;
        matchType = 'alias-contains';
      }
      // Priority 5: token boundary match (any token starts with any query token)
      else if (this._hasTokenMatch(entry.tokens, queryTokens)) {
        score = 30;
        matchType = 'token-match';
      }

      if (score > 0) {
        results.push({
          type: entry.type,
          id: entry.id,
          name: entry.name,
          parent: entry.parent,
          center: entry.center,
          bbox: entry.bbox,
          admin: entry.admin,
          score,
          matchType
        });
      }
    });

    // Sort by score descending, then alphabetically by name
    results.sort((a, b) => {
      if (b.score !== a.score) {
        return b.score - a.score;
      }
      return a.name.localeCompare(b.name);
    });

    return results.slice(0, limit);
  },

  /**
   * Check if any entry token starts with any query token.
   * 
   * @param {string[]} entryTokens - Tokens from entry name
   * @param {string[]} queryTokens - Tokens from query
   * @returns {boolean} True if there's a token match
   */
  _hasTokenMatch(entryTokens, queryTokens) {
    return queryTokens.some(qt => 
      entryTokens.some(et => et.startsWith(qt))
    );
  },

  /**
   * Get a record by ID.
   * 
   * @param {Object} index - Index object
   * @param {string} id - Record ID
   * @returns {Object|null} Record or null if not found
   */
  getById(index, id) {
    return index.byId[id] || null;
  }
};

// Export for browser and Node.js
if (typeof module !== 'undefined' && module.exports) {
  module.exports = SearchIndex;
} else if (typeof window !== 'undefined') {
  window.SearchIndex = SearchIndex;
}
