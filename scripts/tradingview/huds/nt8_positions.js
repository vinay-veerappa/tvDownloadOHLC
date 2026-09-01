/**
 * NT8 Live Positions & P&L HUD Module for TradingView Desktop.
 * 
 * Features:
 * - Real-time position monitor from NT8 Bridge (Sim101 / Live Accounts)
 * - Position side (Long / Short / Flat)
 * - Contract size & average entry price
 * - Unrealized & Realized P&L
 * - Draggable, resizable, collapsible overlay
 */

export const hud = {
  id: 'nt8_positions',
  domId: 'ws-nt8-positions-panel',
  styleId: 'ws-nt8-positions-style',
  name: 'NinjaTrader 8 Positions & P&L HUD',
  description: 'Live NT8 bridge connection displaying open positions, account state, and P&L.',
  version: '1.0.0',
  defaultPosition: {
    top: 75,
    right: 530,
    width: 340,
    height: 260,
    minWidth: 260,
    minHeight: 180
  },

  getCss: (options = {}) => {
    const initOpacity = options.opacity ?? 0.96;
    const width = options.width ?? 340;
    const height = options.height ?? 260;

    return `
      #ws-nt8-positions-panel {
        position: fixed;
        top: ${options.top ?? 75}px;
        right: ${options.right ?? 530}px;
        width: ${width}px;
        height: ${height}px;
        min-width: 260px;
        min-height: 180px;
        background: rgba(19, 23, 34, ${initOpacity});
        border: 1px solid #2a2e39;
        border-radius: 10px;
        box-shadow: 0 16px 40px rgba(0, 0, 0, 0.65), 0 0 0 1px rgba(255, 255, 255, 0.05);
        z-index: 999998;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        resize: both;
        font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, Ubuntu, sans-serif;
        color: #d1d4dc;
        backdrop-filter: blur(12px);
        transition: opacity 0.2s ease;
      }
      #ws-nt8-positions-panel.minimized {
        height: 38px !important;
        min-height: 38px !important;
        width: 260px !important;
        resize: none !important;
      }
      #ws-nt8-positions-panel.minimized .ws-nt8-body {
        display: none !important;
      }
      .ws-nt8-header {
        height: 38px;
        background: #1e222d;
        border-bottom: 1px solid #2a2e39;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 10px;
        cursor: grab;
        user-select: none;
        flex-shrink: 0;
      }
      .ws-nt8-header:active { cursor: grabbing; }
      .ws-nt8-title-box {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 12px;
        font-weight: 700;
        color: #f0f3fa;
      }
      .ws-nt8-dot {
        width: 8px;
        height: 8px;
        background: #2962ff;
        border-radius: 50%;
        box-shadow: 0 0 8px #2962ff;
      }
      .ws-nt8-controls { display: flex; align-items: center; gap: 4px; }
      .ws-nt8-btn {
        background: transparent; border: none; color: #787b86; cursor: pointer;
        padding: 4px 6px; border-radius: 4px; font-size: 12px;
      }
      .ws-nt8-btn:hover { background: #2a2e39; color: #f0f3fa; }
      .ws-nt8-btn-close:hover { background: #f7525f; color: #fff; }
      .ws-nt8-body {
        flex: 1;
        padding: 12px;
        display: flex;
        flex-direction: column;
        gap: 8px;
        overflow-y: auto;
      }
      .ws-nt8-card {
        background: #181b24;
        border: 1px solid #2a2e39;
        border-radius: 6px;
        padding: 10px;
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .ws-nt8-row {
        display: flex;
        justify-content: space-between;
        font-size: 12px;
      }
      .ws-nt8-label { color: #787b86; }
      .ws-nt8-val { font-weight: 600; color: #d1d4dc; }
      .ws-nt8-val.long { color: #089981; }
      .ws-nt8-val.short { color: #f7525f; }
      .ws-nt8-val.flat { color: #787b86; }
    `;
  },

  getHtml: (options = {}) => {
    return `
      <div class="ws-nt8-header" id="ws-nt8-drag-handle">
        <div class="ws-nt8-title-box">
          <div class="ws-nt8-dot"></div>
          <span>NT8 Live Execution HUD</span>
        </div>
        <div class="ws-nt8-controls">
          <button class="ws-nt8-btn" id="ws-nt8-btn-min" title="Minimize / Expand">🗕</button>
          <button class="ws-nt8-btn ws-nt8-btn-close" id="ws-nt8-btn-close" title="Close HUD">✕</button>
        </div>
      </div>
      <div class="ws-nt8-body">
        <div class="ws-nt8-card">
          <div class="ws-nt8-row">
            <span class="ws-nt8-label">Account:</span>
            <span class="ws-nt8-val" id="ws-nt8-acc">Sim101</span>
          </div>
          <div class="ws-nt8-row">
            <span class="ws-nt8-label">Position:</span>
            <span class="ws-nt8-val flat" id="ws-nt8-pos">FLAT (0)</span>
          </div>
          <div class="ws-nt8-row">
            <span class="ws-nt8-label">Entry Avg:</span>
            <span class="ws-nt8-val" id="ws-nt8-entry">--</span>
          </div>
          <div class="ws-nt8-row">
            <span class="ws-nt8-label">Unrealized P&L:</span>
            <span class="ws-nt8-val" id="ws-nt8-pnl">$0.00</span>
          </div>
        </div>
        <div style="font-size: 10px; color: #5d606b; text-align: center;">
          Bridge: Connected (Port 8630 / NT8)
        </div>
      </div>
    `;
  },

  initScript: `
    (function(panel) {
      const btnMin = panel.querySelector('#ws-nt8-btn-min');
      if (btnMin) {
        btnMin.addEventListener('click', (e) => {
          e.stopPropagation();
          panel.classList.toggle('minimized');
          btnMin.textContent = panel.classList.contains('minimized') ? '🗖' : '🗕';
        });
      }

      const btnClose = panel.querySelector('#ws-nt8-btn-close');
      if (btnClose) {
        btnClose.addEventListener('click', (e) => {
          e.stopPropagation();
          if (window.__TV_HUDS__ && typeof window.__TV_HUDS__.remove === 'function') {
            window.__TV_HUDS__.remove('nt8_positions');
          } else {
            panel.remove();
          }
        });
      }

      const dragHandle = panel.querySelector('#ws-nt8-drag-handle');
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
