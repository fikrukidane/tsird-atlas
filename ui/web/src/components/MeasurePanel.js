/**
 * MeasurePanel.js — UI panel for measurement tools
 */

const MeasurePanel = {
  _container: null,
  _readout: null,

  /**
   * Create the measure panel UI.
   * 
   * @param {ol.Map} map - OpenLayers map instance  
   * @param {string} [containerId] - Container element ID
   */
  create(map, containerId) {
    if (!map) {
      console.error('[MeasurePanel] Map instance required');
      return;
    }

    // Initialize MeasureTool
    MeasureTool.init(map, (measurement) => {
      this._updateReadout(measurement);
    });

    // Create panel container
    const panel = document.createElement('div');
    panel.className = 'phase3-measure-panel';
    panel.innerHTML = `
      <div class="measure-buttons">
        <button type="button" class="measure-btn" data-mode="distance" title="Measure Distance">📏</button>
        <button type="button" class="measure-btn" data-mode="area" title="Measure Area">⬜</button>
        <button type="button" class="measure-btn measure-clear" data-mode="clear" title="Clear Measurements">🗑️</button>
      </div>
      <div class="measure-readout"></div>
    `;

    // Event handlers
    const buttons = panel.querySelectorAll('.measure-btn');
    buttons.forEach(btn => {
      btn.addEventListener('click', (e) => {
        const mode = e.currentTarget.dataset.mode;
        this._handleButtonClick(mode, buttons);
      });
    });

    this._readout = panel.querySelector('.measure-readout');

    // Find or create container
    let container = containerId ? document.getElementById(containerId) : null;
    if (!container) {
      container = document.querySelector('.phase3-tools-container');
      if (!container) {
        container = document.createElement('div');
        container.className = 'phase3-tools-container';
        const mapEl = document.getElementById('map');
        if (mapEl && mapEl.parentNode) {
          mapEl.parentNode.appendChild(container);
        }
      }
    }

    container.appendChild(panel);
    this._container = panel;

    console.log('[MeasurePanel] Created');
  },

  /**
   * Handle button click.
   */
  _handleButtonClick(mode, buttons) {
    // Clear active state from all buttons
    buttons.forEach(b => b.classList.remove('active'));

    if (mode === 'clear') {
      MeasureTool.clear();
      MeasureTool.setMode('none');
      return;
    }

    // Toggle mode
    const currentMode = MeasureTool.getMode();
    if (currentMode === mode) {
      MeasureTool.setMode('none');
    } else {
      MeasureTool.setMode(mode);
      // Set active state
      const activeBtn = Array.from(buttons).find(b => b.dataset.mode === mode);
      if (activeBtn) activeBtn.classList.add('active');
    }
  },

  /**
   * Update readout display.
   */
  _updateReadout(measurement) {
    if (!this._readout) return;

    if (measurement) {
      this._readout.textContent = measurement.formatted;
      this._readout.classList.add('has-value');
    } else {
      this._readout.textContent = '';
      this._readout.classList.remove('has-value');
    }
  }
};

// Export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = MeasurePanel;
} else if (typeof window !== 'undefined') {
  window.MeasurePanel = MeasurePanel;
}
