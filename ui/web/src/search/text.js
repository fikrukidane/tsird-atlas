/**
 * text.js — Text normalization utilities for search
 */

const TextUtils = {
  /**
   * Normalize text for search matching.
   * - lowercase
   * - trim
   * - collapse whitespace
   * - remove punctuation ['"(),.;:/\-]
   * 
   * @param {string} str - Input string
   * @returns {string} Normalized string
   */
  normalizeText(str) {
    if (!str || typeof str !== 'string') return '';
    
    return str
      .toLowerCase()
      .trim()
      .replace(/['"(),.;:\/\\-]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  },

  /**
   * Tokenize text into searchable tokens.
   * 
   * @param {string} str - Input string (should be normalized first)
   * @returns {string[]} Array of non-empty tokens
   */
  tokenize(str) {
    if (!str || typeof str !== 'string') return [];
    return str.split(/\s+/).filter(token => token.length > 0);
  }
};

// Export for browser and Node.js
if (typeof module !== 'undefined' && module.exports) {
  module.exports = TextUtils;
} else if (typeof window !== 'undefined') {
  window.TextUtils = TextUtils;
}
