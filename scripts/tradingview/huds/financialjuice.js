/**
 * FinancialJuice Live Squawk & News HUD Module for TradingView Desktop.
 * 
 * Features:
 * - Live FinancialJuice News & Squawk Headlines iframe
 * - Economic Calendar (EcoCal)
 * - TickStrike Order Flow / Sentiment
 * - Persistent Real-time Audio Voice Squawk bar
 * - Transparency cycle (96% -> 85% -> 70%)
 * - Minimize to floating pill / Expand
 * - Smooth viewport-constrained dragging & native CSS resizing
 */

export const hud = {
  id: 'financialjuice',
  domId: 'ws-fj-panel',
  styleId: 'ws-fj-panel-style',
  name: 'FinancialJuice Live Squawk & News HUD',
  description: 'Real-time financial news headlines, audio squawk player, economic calendar, and TickStrike flow.',
  version: '1.1.0',
  defaultPosition: {
    top: 75,
    right: 75,
    width: 440,
    height: 620,
    minWidth: 320,
    minHeight: 220
  },

  getCss: (options = {}) => {
    const initOpacity = options.opacity ?? 0.96;
    const width = options.width ?? 440;
    const height = options.height ?? 620;

    return `
      #ws-fj-panel {
        position: fixed;
        top: ${options.top ?? 75}px;
        right: ${options.right ?? 75}px;
        width: ${width}px;
        height: ${height}px;
        min-width: 320px;
        min-height: 220px;
        background: rgba(19, 23, 34, ${initOpacity});
        border: 1px solid #2a2e39;
        border-radius: 10px;
        box-shadow: 0 16px 40px rgba(0, 0, 0, 0.65), 0 0 0 1px rgba(255, 255, 255, 0.05);
        z-index: 999999;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        resize: both;
        font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, Ubuntu, sans-serif;
        color: #d1d4dc;
        backdrop-filter: blur(12px);
        transition: opacity 0.2s ease, width 0.15s ease;
      }
      #ws-fj-panel.minimized {
        height: 38px !important;
        min-height: 38px !important;
        width: 310px !important;
        resize: none !important;
      }
      #ws-fj-panel.minimized .ws-fj-body {
        display: none !important;
      }
      .ws-fj-header {
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
      .ws-fj-header:active {
        cursor: grabbing;
      }
      .ws-fj-title-box {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.3px;
        color: #f0f3fa;
      }
      .ws-fj-live-dot {
        width: 8px;
        height: 8px;
        background: #089981;
        border-radius: 50%;
        box-shadow: 0 0 8px #089981;
        animation: ws-fj-pulse 2s infinite;
      }
      @keyframes ws-fj-pulse {
        0% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.35; transform: scale(0.85); }
        100% { opacity: 1; transform: scale(1); }
      }
      .ws-fj-badge {
        font-size: 9px;
        font-weight: 800;
        background: #f7525f;
        color: #fff;
        padding: 1px 5px;
        border-radius: 3px;
        letter-spacing: 0.5px;
      }
      .ws-fj-controls {
        display: flex;
        align-items: center;
        gap: 4px;
      }
      .ws-fj-btn {
        background: transparent;
        border: none;
        color: #787b86;
        cursor: pointer;
        padding: 4px 6px;
        border-radius: 4px;
        font-size: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        transition: all 0.15s ease;
      }
      .ws-fj-btn:hover {
        background: #2a2e39;
        color: #f0f3fa;
      }
      .ws-fj-btn.active {
        color: #2962ff;
        background: rgba(41, 98, 255, 0.15);
      }
      .ws-fj-btn-close:hover {
        background: #f7525f;
        color: #fff;
      }
      .ws-fj-body {
        display: flex;
        flex-direction: column;
        flex: 1;
        overflow: hidden;
      }
      .ws-fj-tabs {
        height: 34px;
        background: #181b24;
        border-bottom: 1px solid #2a2e39;
        display: flex;
        align-items: center;
        padding: 0 6px;
        gap: 4px;
        flex-shrink: 0;
      }
      .ws-fj-tab {
        background: transparent;
        border: none;
        color: #787b86;
        font-size: 11px;
        font-weight: 600;
        padding: 5px 9px;
        border-radius: 4px;
        cursor: pointer;
        transition: all 0.15s ease;
        display: flex;
        align-items: center;
        gap: 4px;
      }
      .ws-fj-tab:hover {
        background: #2a2e39;
        color: #d1d4dc;
      }
      .ws-fj-tab.active {
        background: #2962ff;
        color: #ffffff;
      }
      .ws-fj-voice-wrap {
        height: 52px;
        background: #131722;
        border-bottom: 1px solid #2a2e39;
        flex-shrink: 0;
        overflow: hidden;
        transition: height 0.2s ease;
      }
      .ws-fj-voice-wrap.hidden {
        height: 0 !important;
        border-bottom: none !important;
      }
      .ws-fj-content {
        flex: 1;
        position: relative;
        background: #131722;
        width: 100%;
        height: 100%;
        overflow: hidden;
      }
      .ws-fj-iframe {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        border: none;
        display: none;
      }
      .ws-fj-iframe.active {
        display: block;
      }
      /* EconCal embed hard-caps its own content at ~350px (#comingUp{width:340px}),
         so rendering it oversized-and-scaled makes it TINIER. Instead: native size,
         centered horizontally, with the panel's spare width as dark background. */
      .ws-fj-iframe.ecocal-fit {
        width: 420px;
        max-width: 100%;
        left: 50%;
        transform: translateX(-50%);
      }
      /* Full-width variant — used by the standalone widget, which serves the
         calendar through its same-origin reverse proxy (/fjcal/) with CSS
         overrides that stretch the embed to the frame */
      .ws-fj-iframe.ecocal-full {
        width: 100%;
        left: 0;
        transform: none;
      }
      /* Voice player embed renders a large logo that overflows its 52px bar — same treatment */
      .ws-fj-voice-wrap iframe {
        width: 200%;
        height: 200%;
        transform: scale(0.5);
        transform-origin: 0 0;
      }
      body.ws-fj-dragging iframe {
        pointer-events: none !important;
      }
    `;
  },

  getHtml: (options = {}) => {
    const defaultTab = options.defaultTab || 'headlines';
    const hideVoice = options.hideVoice === true;
    const voiceBtnClass = hideVoice ? 'ws-fj-btn' : 'ws-fj-btn active';
    const voiceWrapClass = hideVoice ? 'ws-fj-voice-wrap hidden' : 'ws-fj-voice-wrap';

    return `
      <div class="ws-fj-header" id="ws-fj-drag-handle">
        <div class="ws-fj-title-box">
          <div class="ws-fj-live-dot"></div>
          <span>FinancialJuice HUD</span>
          <span class="ws-fj-badge">SQUAWK</span>
        </div>
        <div class="ws-fj-controls">
          <button class="${voiceBtnClass}" id="ws-fj-btn-voice" title="Toggle Live Spoken Voice Squawk">🔊 Squawk</button>
          <button class="ws-fj-btn" id="ws-fj-btn-opacity" title="Toggle Opacity (96% / 85% / 70%)">🌓</button>
          <button class="ws-fj-btn" id="ws-fj-btn-min" title="Minimize / Expand">🗕</button>
          <button class="ws-fj-btn ws-fj-btn-close" id="ws-fj-btn-close" title="Close HUD">✕</button>
        </div>
      </div>
      <div class="ws-fj-body">
        <div class="ws-fj-tabs">
          <button class="ws-fj-tab ${defaultTab === 'headlines' ? 'active' : ''}" data-target="headlines">📰 Headlines</button>
          <button class="ws-fj-tab ${defaultTab === 'ecocal' ? 'active' : ''}" data-target="ecocal">📅 Econ Calendar</button>
          <button class="ws-fj-tab ${defaultTab === 'tickstrike' ? 'active' : ''}" data-target="tickstrike">⚡ TickStrike</button>
        </div>
        <div class="${voiceWrapClass}" id="ws-fj-voice-wrap">
          <iframe src="https://feed.financialjuice.com/voice-player.aspx" style="width:100%; height:52px; border:none;" scrolling="no"></iframe>
        </div>
        <div class="ws-fj-content" id="ws-fj-content">
          <iframe id="ws-fj-frame-headlines" class="ws-fj-iframe ${defaultTab === 'headlines' ? 'active' : ''}" src="https://feed.financialjuice.com/widgets/headlines.aspx"></iframe>
          <iframe id="ws-fj-frame-ecocal" class="ws-fj-iframe ecocal-fit ${defaultTab === 'ecocal' ? 'active' : ''}" ${defaultTab === 'ecocal' ? 'src="https://feed.financialjuice.com/widgets/ecocal.aspx"' : 'data-src="https://feed.financialjuice.com/widgets/ecocal.aspx"'}></iframe>
          <iframe id="ws-fj-frame-tickstrike" class="ws-fj-iframe ${defaultTab === 'tickstrike' ? 'active' : ''}" ${defaultTab === 'tickstrike' ? 'src="https://www.financialjuice.com/widgets/ts.aspx"' : 'data-src="https://www.financialjuice.com/widgets/ts.aspx"'}></iframe>
        </div>
      </div>
    `;
  },

  initScript: `
    (function(panel) {
      // Tab switching
      const tabs = panel.querySelectorAll('.ws-fj-tab');
      tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
          e.stopPropagation();
          tabs.forEach(t => t.classList.remove('active'));
          tab.classList.add('active');
          const target = tab.getAttribute('data-target');
          const frames = panel.querySelectorAll('.ws-fj-iframe');
          frames.forEach(f => f.classList.remove('active'));
          const activeFrame = panel.querySelector('#ws-fj-frame-' + target);
          if (activeFrame) {
            if (!activeFrame.src && activeFrame.getAttribute('data-src')) {
              activeFrame.src = activeFrame.getAttribute('data-src');
            }
            activeFrame.classList.add('active');
          }
        });
      });

      // Voice Toggle
      const btnVoice = panel.querySelector('#ws-fj-btn-voice');
      const voiceWrap = panel.querySelector('#ws-fj-voice-wrap');
      if (btnVoice && voiceWrap) {
        btnVoice.addEventListener('click', (e) => {
          e.stopPropagation();
          voiceWrap.classList.toggle('hidden');
          btnVoice.classList.toggle('active', !voiceWrap.classList.contains('hidden'));
        });
      }

      // Opacity Cycle (0.96 -> 0.85 -> 0.70)
      const opacities = [0.96, 0.85, 0.70];
      let opIdx = 0;
      const btnOpacity = panel.querySelector('#ws-fj-btn-opacity');
      if (btnOpacity) {
        btnOpacity.addEventListener('click', (e) => {
          e.stopPropagation();
          opIdx = (opIdx + 1) % opacities.length;
          panel.style.opacity = opacities[opIdx];
          btnOpacity.title = 'Opacity: ' + Math.round(opacities[opIdx] * 100) + '%';
        });
      }

      // Minimize / Expand
      const btnMin = panel.querySelector('#ws-fj-btn-min');
      if (btnMin) {
        btnMin.addEventListener('click', (e) => {
          e.stopPropagation();
          panel.classList.toggle('minimized');
          btnMin.textContent = panel.classList.contains('minimized') ? '🗖' : '🗕';
        });
      }

      // Close Button
      const btnClose = panel.querySelector('#ws-fj-btn-close');
      if (btnClose) {
        btnClose.addEventListener('click', (e) => {
          e.stopPropagation();
          if (window.__TV_HUDS__ && typeof window.__TV_HUDS__.remove === 'function') {
            window.__TV_HUDS__.remove('financialjuice');
          } else {
            panel.remove();
          }
        });
      }

      // Draggability
      const dragHandle = panel.querySelector('#ws-fj-drag-handle');
      if (dragHandle) {
        let isDragging = false;
        let startX = 0, startY = 0;
        let origLeft = 0, origTop = 0;

        dragHandle.addEventListener('mousedown', (e) => {
          if (e.target.closest('.ws-fj-controls') || e.target.closest('button')) return;
          isDragging = true;
          document.body.classList.add('ws-fj-dragging');
          const rect = panel.getBoundingClientRect();
          startX = e.clientX;
          startY = e.clientY;
          origLeft = rect.left;
          origTop = rect.top;

          panel.style.left = origLeft + 'px';
          panel.style.top = origTop + 'px';
          panel.style.right = 'auto';
          panel.style.bottom = 'auto';

          const onMouseMove = (ev) => {
            if (!isDragging) return;
            const dx = ev.clientX - startX;
            const dy = ev.clientY - startY;
            const newLeft = Math.max(10, Math.min(window.innerWidth - panel.offsetWidth - 10, origLeft + dx));
            const newTop = Math.max(10, Math.min(window.innerHeight - panel.offsetHeight - 10, origTop + dy));
            panel.style.left = newLeft + 'px';
            panel.style.top = newTop + 'px';
          };

          const onMouseUp = () => {
            isDragging = false;
            document.body.classList.remove('ws-fj-dragging');
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
