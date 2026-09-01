/**
 * Template HUD Module for TradingView Desktop.
 * Copy this file to create new custom HUD overlays.
 */

export const hud = {
  id: 'template_hud',
  domId: 'ws-template-panel',
  styleId: 'ws-template-panel-style',
  name: 'Custom HUD Template',
  description: 'Clean starting template for new TradingView HUD overlays.',
  version: '1.0.0',
  defaultPosition: {
    top: 100,
    right: 80,
    width: 380,
    height: 480,
    minWidth: 280,
    minHeight: 180
  },

  getCss: (options = {}) => {
    const initOpacity = options.opacity ?? 0.96;
    const width = options.width ?? 380;
    const height = options.height ?? 480;

    return `
      #ws-template-panel {
        position: fixed;
        top: ${options.top ?? 100}px;
        right: ${options.right ?? 80}px;
        width: ${width}px;
        height: ${height}px;
        min-width: 280px;
        min-height: 180px;
        background: rgba(19, 23, 34, ${initOpacity});
        border: 1px solid #2a2e39;
        border-radius: 10px;
        box-shadow: 0 16px 40px rgba(0, 0, 0, 0.65);
        z-index: 999999;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        resize: both;
        font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, Ubuntu, sans-serif;
        color: #d1d4dc;
        backdrop-filter: blur(12px);
      }
      #ws-template-panel.minimized {
        height: 38px !important;
        min-height: 38px !important;
        resize: none !important;
      }
      #ws-template-panel.minimized .ws-template-body {
        display: none !important;
      }
      .ws-template-header {
        height: 38px;
        background: #1e222d;
        border-bottom: 1px solid #2a2e39;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 10px;
        cursor: grab;
        user-select: none;
      }
      .ws-template-header:active { cursor: grabbing; }
      .ws-template-title { font-size: 12px; font-weight: 700; color: #f0f3fa; }
      .ws-template-controls { display: flex; align-items: center; gap: 4px; }
      .ws-template-btn {
        background: transparent; border: none; color: #787b86; cursor: pointer;
        padding: 4px 6px; border-radius: 4px; font-size: 12px;
      }
      .ws-template-btn:hover { background: #2a2e39; color: #f0f3fa; }
      .ws-template-btn-close:hover { background: #f7525f; color: #fff; }
      .ws-template-body { flex: 1; padding: 12px; overflow-y: auto; }
    `;
  },

  getHtml: (options = {}) => {
    return `
      <div class="ws-template-header" id="ws-template-drag-handle">
        <span class="ws-template-title">Custom HUD Overlay</span>
        <div class="ws-template-controls">
          <button class="ws-template-btn" id="ws-template-btn-min" title="Minimize / Expand">🗕</button>
          <button class="ws-template-btn ws-template-btn-close" id="ws-template-btn-close" title="Close HUD">✕</button>
        </div>
      </div>
      <div class="ws-template-body">
        <p style="margin: 0 0 8px 0; font-size: 13px;">HUD content goes here...</p>
      </div>
    `;
  },

  initScript: `
    (function(panel) {
      const btnMin = panel.querySelector('#ws-template-btn-min');
      if (btnMin) {
        btnMin.addEventListener('click', (e) => {
          e.stopPropagation();
          panel.classList.toggle('minimized');
          btnMin.textContent = panel.classList.contains('minimized') ? '🗖' : '🗕';
        });
      }

      const btnClose = panel.querySelector('#ws-template-btn-close');
      if (btnClose) {
        btnClose.addEventListener('click', (e) => {
          e.stopPropagation();
          if (window.__TV_HUDS__ && typeof window.__TV_HUDS__.remove === 'function') {
            window.__TV_HUDS__.remove('template_hud');
          } else {
            panel.remove();
          }
        });
      }

      const dragHandle = panel.querySelector('#ws-template-drag-handle');
      if (dragHandle) {
        let isDragging = false, startX = 0, startY = 0, origLeft = 0, origTop = 0;
        dragHandle.addEventListener('mousedown', (e) => {
          if (e.target.closest('button')) return;
          isDragging = true;
          const rect = panel.getBoundingClientRect();
          startX = e.clientX; startY = e.clientY;
          origLeft = rect.left; origTop = rect.top;
          panel.style.left = origLeft + 'px';
          panel.style.top = origTop + 'px';
          panel.style.right = 'auto';
          panel.style.bottom = 'auto';

          const onMouseMove = (ev) => {
            if (!isDragging) return;
            panel.style.left = (origLeft + ev.clientX - startX) + 'px';
            panel.style.top = (origTop + ev.clientY - startY) + 'px';
          };
          const onMouseUp = () => {
            isDragging = false;
            window.removeEventListener('mousemove', onMouseMove);
            window.removeEventListener('mouseup', onMouseUp);
          };
          window.addEventListener('mousemove', onMouseMove);
          window.addEventListener('mouseup', onMouseUp);
        });
      }
    })
  `
};
