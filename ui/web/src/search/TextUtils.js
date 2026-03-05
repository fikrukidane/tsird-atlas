/**
 * TextUtils.js — Text normalization utilities for search
 * 
 * Provides consistent text normalization for gazetteer search.
 */

const TextUtils = {
  /**
   * Normalize text for search matching.
   * - lowercase
   * - trim
   * - collapse whitespace
   * - remove punctuation ['"(),.;:/\-]
   * 
   * @param {string} s - Input string
   * @returns {string} Normalized string
   */
  normalizeText(s) {
    if (!s || typeof s !== 'string') return '';
    
    return s
      .toLowerCase()
      .trim()
      // Remove punctuation
      .replace(/['"(),.;:\/\\-]/g, ' ')
      // Collapse whitespace
      .replace(/\s+/g, ' ')
      .trim();
  },

  /**
   * Tokenize text into searchable tokens.
   * 
   * @param {string} s - Input string (should be normalized first)
   * @returns {string[]} Array of non-empty tokens
   */
  tokenize(s) {
    if (!s || typeof s !== 'string') return [];
    
    return s.split(/\s+/).filter(token => token.length > 0);
  }
};

// Export for browser and Node.js
if (typeof module !== 'undefined' && module.exports) {
  module.exports = TextUtils;
} else if (typeof window !== 'undefined') {
  window.TextUtils = TextUtils;
}
