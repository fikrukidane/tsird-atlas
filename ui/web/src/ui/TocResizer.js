/**
 * TocResizer.js — Handles TOC panel resize functionality
 * 
 * Features:
 * - Drag-to-resize TOC panel width
 * - Auto-fit to longest layer name on init
 * - Remembers user preference in localStorage
 * - Min/max width constraints
 */

class TocResizer {
  constructor() {
    this.resizer = document.getElementById('toc-resizer');
    this.tocContainer = document.getElementById('toc-container');
    this.mapContainer = document.getElementById('map-container');
    
    this.isDragging = false;
    this.startX = 0;
    this.startWidth = 0;
    
    this.minWidth = 180;
    this.maxWidth = window.innerWidth * 0.5;
    
    this.storageKey = 'tsird-toc-width';
    
    if (this.resizer && this.tocContainer) {
      this.init();
    }
  }
  
  init() {
    // Restore saved width or use default
    const savedWidth = localStorage.getItem(this.storageKey);
    if (savedWidth) {
      this.setWidth(parseInt(savedWidth, 10));
    }
    
    // Mouse events
    this.resizer.addEventListener('mousedown', this.onMouseDown.bind(this));
    document.addEventListener('mousemove', this.onMouseMove.bind(this));
    document.addEventListener('mouseup', this.onMouseUp.bind(this));
    
    // Touch events for mobile
    this.resizer.addEventListener('touchstart', this.onTouchStart.bind(this));
    document.addEventListener('touchmove', this.onTouchMove.bind(this));
    document.addEventListener('touchend', this.onTouchEnd.bind(this));
    
    // Update max width on window resize
    window.addEventListener('resize', () => {
      this.maxWidth = window.innerWidth * 0.5;
    });
    
    // Double-click to auto-fit
    this.resizer.addEventListener('dblclick', () => {
      this.autoFitToContent();
    });
    
    console.log('✓ TOC resizer initialized (drag handle or double-click to auto-fit)');
  }
  
  onMouseDown(e) {
    e.preventDefault();
    this.startDrag(e.clientX);
  }
  
  onTouchStart(e) {
    if (e.touches.length === 1) {
      e.preventDefault();
      this.startDrag(e.touches[0].clientX);
    }
  }
  
  startDrag(clientX) {
    this.isDragging = true;
    this.startX = clientX;
    this.startWidth = this.tocContainer.offsetWidth;
    this.resizer.classList.add('is-dragging');
    document.body.style.cursor = 'ew-resize';
    document.body.style.userSelect = 'none';
  }
  
  onMouseMove(e) {
    if (!this.isDragging) return;
    this.doDrag(e.clientX);
  }
  
  onTouchMove(e) {
    if (!this.isDragging || e.touches.length !== 1) return;
    this.doDrag(e.touches[0].clientX);
  }
  
  doDrag(clientX) {
    // Calculate new width (moving left increases TOC width)
    const delta = this.startX - clientX;
    const newWidth = this.startWidth + delta;
    this.setWidth(newWidth);
  }
  
  onMouseUp() {
    this.endDrag();
  }
  
  onTouchEnd() {
    this.endDrag();
  }
  
  endDrag() {
    if (!this.isDragging) return;
    
    this.isDragging = false;
    this.resizer.classList.remove('is-dragging');
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
    
    // Save to localStorage
    const width = this.tocContainer.offsetWidth;
    localStorage.setItem(this.storageKey, width.toString());
    
    // Trigger map resize
    this.triggerMapResize();
  }
  
  setWidth(width) {
    // Clamp to min/max
    const clampedWidth = Math.max(this.minWidth, Math.min(this.maxWidth, width));
    this.tocContainer.style.width = `${clampedWidth}px`;
  }
  
  /**
   * Auto-fit TOC width to longest layer name
   */
  autoFitToContent() {
    // Create a hidden measuring element
    const measurer = document.createElement('div');
    measurer.style.cssText = `
      position: absolute;
      visibility: hidden;
      white-space: nowrap;
      font-size: 13px;
      font-family: inherit;
      padding: 0 40px 0 24px;
    `;
    document.body.appendChild(measurer);
    
    // Find all layer labels and measure them
    const labels = this.tocContainer.querySelectorAll('.toc-layer-label, .toc-group-label, .toc-category-label');
    let maxWidth = this.minWidth;
    
    labels.forEach(label => {
      measurer.textContent = label.textContent;
      const width = measurer.offsetWidth + 60; // Add padding for checkbox, indentation
      if (width > maxWidth) {
        maxWidth = width;
      }
    });
    
    document.body.removeChild(measurer);
    
    // Set width with constraints
    const finalWidth = Math.max(this.minWidth, Math.min(this.maxWidth, maxWidth + 20));
    this.setWidth(finalWidth);
    
    // Save preference
    localStorage.setItem(this.storageKey, finalWidth.toString());
    
    // Trigger map resize
    this.triggerMapResize();
    
    console.log(`✓ TOC auto-fit to ${finalWidth}px`);
  }
  
  /**
   * Trigger OpenLayers map resize after panel width change
   */
  triggerMapResize() {
    // Dispatch resize event for OpenLayers to recalculate
    window.dispatchEvent(new Event('resize'));
  }
}

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  // Delay slightly to ensure TOC is rendered
  setTimeout(() => {
    window.tocResizer = new TocResizer();
    
    // Auto-fit on first load if no saved preference
    if (!localStorage.getItem('tsird-toc-width')) {
      // Wait for TOC to fully render
      setTimeout(() => {
        window.tocResizer.autoFitToContent();
      }, 500);
    }
  }, 100);
});
