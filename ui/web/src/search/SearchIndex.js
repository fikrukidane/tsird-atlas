/**
 * SearchIndex.js — In-memory search index for gazetteer
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
      console.warn('[SearchIndex] buildIndex received non-array');
      return { entries: [], byId: {} };
    }

    const entries = [];
    const byId = {};

    records.forEach(record => {
      const entry = {
        type: record.type,
        id: record.id,
        name: record.name,
        name_norm: record.name_norm || TextUtils.normalizeText(record.name),
        aliases: record.aliases || [],
        aliases_norm: (record.aliases || []).map(a => TextUtils.normalizeText(a)),
        parent: record.parent || { woreda_id: null },
        center: record.center || null,
        bbox: record.bbox || null
      };

      entry.tokens = TextUtils.tokenize(entry.name_norm);
      entries.push(entry);
      byId[record.id] = entry;
    });

    console.log(`[SearchIndex] Built index: ${entries.length} entries`);
    return { entries, byId };
  },

  /**
   * Search the index for matching records.
   * 
   * @param {Object} index - Index object from buildIndex()
   * @param {string} query - Search query
   * @param {Object} [options] - Search options
   * @param {number} [options.limit=20] - Maximum results
   * @returns {Array} Matching records sorted by relevance
   */
  search(index, query, options = {}) {
    const limit = options.limit || 20;

    // Minimum query length
    if (!query || query.length < 2) {
      return [];
    }

    const queryNorm = TextUtils.normalizeText(query);
    if (!queryNorm) return [];

    const queryTokens = TextUtils.tokenize(queryNorm);
    const results = [];

    index.entries.forEach(entry => {
      let score = 0;
      let matchType = null;

      // Priority 1: name startsWith
      if (entry.name_norm.startsWith(queryNorm)) {
        score = 100;
        matchType = 'name-prefix';
      }
      // Priority 2: alias startsWith
      else if (entry.aliases_norm.some(a => a.startsWith(queryNorm))) {
        score = 80;
        matchType = 'alias-prefix';
      }
      // Priority 3: name contains
      else if (entry.name_norm.includes(queryNorm)) {
        score = 60;
        matchType = 'name-contains';
      }
      // Priority 4: alias contains
      else if (entry.aliases_norm.some(a => a.includes(queryNorm))) {
        score = 40;
        matchType = 'alias-contains';
      }
      // Priority 5: token match
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
          score,
          matchType
        });
      }
    });

    // Sort by score desc, then name asc
    results.sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      return a.name.localeCompare(b.name);
    });

    return results.slice(0, limit);
  },

  _hasTokenMatch(entryTokens, queryTokens) {
    return queryTokens.some(qt => 
      entryTokens.some(et => et.startsWith(qt))
    );
  },

  getById(index, id) {
    return index.byId[id] || null;
  }
};

// Export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = SearchIndex;
} else if (typeof window !== 'undefined') {
  window.SearchIndex = SearchIndex;
}
