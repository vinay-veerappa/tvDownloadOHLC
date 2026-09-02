/**
 * Trading Account P&L, Position & Copy-Trading Fleet Monitor HUD.
 * 
 * Features:
 * - Instantaneous live P&L, position, and balance updates (< 200ms refresh)
 * - Interactive Multi-Column Sorting (Account, Position/Contracts, Unrealized, Realized, Net Liq, Sync Status)
 * - Explicit Open Contracts Display in summary, header badge, tab, and account rows
 * - Copy-Trading Sync Grid: Leader vs Follower Expected vs Actual position validation
 * - Orphan Position Alert & Desync Warning System
 * - Emergency Fleet Flatten Action Button with 2-click confirm & CDP bridge
 * - Order Ticket: Buy/Sell market entry with a server-side ATM bracket (widget + HUD)
 * - Live Heartbeat & Stream Latency Indicator
 * - Dual Mode Support: TradingView In-Chart HUD & Standalone Floating Desktop Widget
 */

export const hud = {
  id: 'account_pnl',
  domId: 'ws-pnl-panel',
  styleId: 'ws-pnl-panel-style',
  name: 'Fleet P&L & Copy-Trading Sync Monitor',
  description: 'Real-time multi-account P&L, positions, open contracts, and copy-trading follower synchronization validator with interactive sorting.',
  version: '2.4.0',
  defaultPosition: {
    top: 65,
    right: 65,
    width: 570,
    height: 640,
    minWidth: 420,
    minHeight: 280
  },

  getCss: (options = {}) => {
    const initOpacity = options.opacity ?? 0.96;
    const width = options.width ?? 570;
    const height = options.height ?? 640;

    return `
      #ws-pnl-panel {
        position: fixed;
        top: ${options.top ?? 65}px;
        right: ${options.right ?? 65}px;
        width: ${width}px;
        height: ${height}px;
        min-width: 420px;
        min-height: 280px;
        background: rgba(19, 23, 34, ${initOpacity});
        border: 1px solid #2a2e39;
        border-radius: 10px;
        box-shadow: 0 16px 40px rgba(0, 0, 0, 0.75), 0 0 0 1px rgba(255, 255, 255, 0.05);
        z-index: 999999;
        display: flex;
        flex-direction: column;
        overflow: hidden;
        resize: both;
        font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, Ubuntu, sans-serif;
        color: #d1d4dc;
        backdrop-filter: blur(14px);
        transition: opacity 0.2s ease;
      }
      #ws-pnl-panel.minimized {
        height: 38px !important;
        min-height: 38px !important;
        width: 440px !important;
        resize: none !important;
      }
      #ws-pnl-panel.minimized .ws-pnl-body,
      #ws-pnl-panel.minimized .ws-pnl-summary,
      #ws-pnl-panel.minimized .ws-pnl-copier-banner,
      #ws-pnl-panel.minimized .ws-pnl-toolbar,
      #ws-pnl-panel.minimized .ws-pnl-footer {
        display: none !important;
      }
      .ws-pnl-header {
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
      .ws-pnl-header:active { cursor: grabbing; }
      .ws-pnl-title-box {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 12px;
        font-weight: 700;
        color: #f0f3fa;
      }
      .ws-pnl-dot {
        width: 8px;
        height: 8px;
        background: #089981;
        border-radius: 50%;
        box-shadow: 0 0 8px #089981;
        animation: ws-pnl-pulse 1.5s infinite;
      }
      .ws-pnl-dot.offline {
        background: #f7525f;
        box-shadow: 0 0 8px #f7525f;
        animation: none;
      }
      @keyframes ws-pnl-pulse {
        0% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.35; transform: scale(0.85); }
        100% { opacity: 1; transform: scale(1); }
      }
      .ws-pnl-badge {
        font-size: 9px;
        font-weight: 800;
        background: #2962ff;
        color: #fff;
        padding: 2px 6px;
        border-radius: 3px;
        letter-spacing: 0.5px;
      }
      .ws-pnl-badge.offline { background: #f7525f; }
      
      .ws-pnl-contracts-badge {
        font-size: 9px;
        font-weight: 800;
        padding: 2px 6px;
        border-radius: 3px;
        letter-spacing: 0.4px;
        background: #2a2e39;
        color: #787b86;
        transition: all 0.2s ease;
      }
      .ws-pnl-contracts-badge.active-pos {
        background: rgba(8, 153, 129, 0.25);
        color: #089981;
        border: 1px solid rgba(8, 153, 129, 0.5);
      }
      .ws-pnl-contracts-badge.short-pos {
        background: rgba(247, 82, 95, 0.25);
        color: #f7525f;
        border: 1px solid rgba(247, 82, 95, 0.5);
      }

      .ws-pnl-controls { display: flex; align-items: center; gap: 4px; }
      .ws-pnl-btn {
        background: transparent; border: none; color: #787b86; cursor: pointer;
        padding: 4px 6px; border-radius: 4px; font-size: 12px;
        display: flex; align-items: center; justify-content: center;
        transition: all 0.15s ease;
      }
      .ws-pnl-btn:hover { background: #2a2e39; color: #f0f3fa; }
      .ws-pnl-btn-close:hover { background: #f7525f; color: #fff; }

      /* Summary Grid */
      .ws-pnl-summary {
        background: #141822;
        border-bottom: 1px solid #2a2e39;
        padding: 8px 12px;
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 8px;
        flex-shrink: 0;
      }
      .ws-pnl-stat {
        display: flex;
        flex-direction: column;
        gap: 2px;
      }
      .ws-pnl-stat-label {
        font-size: 10px;
        color: #787b86;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.4px;
      }
      .ws-pnl-stat-val {
        font-size: 13px;
        font-weight: 700;
        color: #f0f3fa;
        font-variant-numeric: tabular-nums;
        transition: color 0.2s ease;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .ws-pnl-stat-val.pos { color: #089981; }
      .ws-pnl-stat-val.neg { color: #f7525f; }
      .ws-pnl-stat-val.zero { color: #787b86; }

      /* Copier Status Banner */
      .ws-pnl-copier-banner {
        background: #10141d;
        border-bottom: 1px solid #2a2e39;
        padding: 6px 12px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 11px;
        flex-shrink: 0;
      }
      .ws-pnl-copier-sync-status {
        display: flex;
        align-items: center;
        gap: 6px;
        font-weight: 600;
      }
      .ws-pnl-sync-pill {
        font-size: 10px;
        font-weight: 800;
        padding: 2px 6px;
        border-radius: 4px;
        letter-spacing: 0.3px;
      }
      .ws-pnl-sync-ok { background: rgba(8, 153, 129, 0.2); color: #089981; border: 1px solid #089981; }
      .ws-pnl-sync-warn { background: rgba(247, 166, 0, 0.2); color: #f7a600; border: 1px solid #f7a600; }
      .ws-pnl-sync-alert { background: rgba(247, 82, 95, 0.2); color: #f7525f; border: 1px solid #f7525f; animation: ws-pnl-flash 1s infinite; }
      @keyframes ws-pnl-flash { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

      .ws-pnl-flatten-btn {
        background: rgba(247, 82, 95, 0.15);
        border: 1px solid #f7525f;
        color: #f7525f;
        font-size: 10px;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 4px;
        cursor: pointer;
        transition: all 0.15s ease;
      }
      .ws-pnl-flatten-btn:hover {
        background: #f7525f;
        color: #ffffff;
      }

      /* Navigation Tabs & Filters */
      .ws-pnl-toolbar {
        height: 34px;
        background: #181b24;
        border-bottom: 1px solid #2a2e39;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 8px;
        gap: 6px;
        flex-shrink: 0;
      }
      .ws-pnl-view-tabs {
        display: flex;
        align-items: center;
        gap: 4px;
      }
      .ws-pnl-tab-btn {
        background: transparent;
        border: none;
        color: #787b86;
        font-size: 11px;
        font-weight: 600;
        padding: 4px 8px;
        border-radius: 4px;
        cursor: pointer;
        transition: all 0.15s ease;
      }
      .ws-pnl-tab-btn:hover { background: #2a2e39; color: #d1d4dc; }
      .ws-pnl-tab-btn.active { background: #2962ff; color: #ffffff; }

      .ws-pnl-search {
        background: #131722;
        border: 1px solid #2a2e39;
        border-radius: 4px;
        color: #d1d4dc;
        font-size: 11px;
        padding: 3px 6px;
        width: 120px;
        outline: none;
      }
      .ws-pnl-search:focus { border-color: #2962ff; }

      /* Body & Tables */
      .ws-pnl-body {
        flex: 1;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
      }
      .ws-pnl-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 11px;
      }
      .ws-pnl-table th {
        background: #181b24;
        color: #787b86;
        text-align: left;
        padding: 6px 8px;
        font-size: 10px;
        font-weight: 600;
        border-bottom: 1px solid #2a2e39;
        position: sticky;
        top: 0;
        z-index: 2;
        text-transform: uppercase;
      }
      .ws-pnl-table th.sortable {
        cursor: pointer;
        user-select: none;
        transition: background 0.15s ease, color 0.15s ease;
      }
      .ws-pnl-table th.sortable:hover {
        background: #252a37;
        color: #f0f3fa;
      }
      .ws-pnl-sort-icon {
        margin-left: 4px;
        font-size: 9px;
        color: #5d606b;
        display: inline-block;
      }
      .ws-pnl-sort-icon.active {
        color: #2962ff;
        font-weight: bold;
      }
      .ws-pnl-table td {
        padding: 6px 8px;
        border-bottom: 1px solid #20242f;
        font-variant-numeric: tabular-nums;
      }
      .ws-pnl-table tr:hover td {
        background: rgba(41, 98, 255, 0.08);
      }
      .ws-pnl-acc-name {
        font-weight: 600;
        color: #f0f3fa;
        display: flex;
        align-items: center;
        gap: 5px;
      }
      .ws-pnl-acc-type {
        font-size: 9px;
        padding: 1px 4px;
        border-radius: 2px;
        background: #2a2e39;
        color: #9db2d4;
        font-weight: 700;
      }
      .ws-pnl-rel-badge {
        font-size: 8px;
        font-weight: 800;
        padding: 1px 4px;
        border-radius: 3px;
        letter-spacing: 0.3px;
        white-space: nowrap;
      }
      .ws-pnl-rel-badge.leader {
        background: rgba(41, 98, 255, 0.2);
        color: #5b8def;
        border: 1px solid rgba(41, 98, 255, 0.5);
      }
      .ws-pnl-rel-badge.follower { background: #2a2e39; color: #9db2d4; }
      .ws-pnl-rel-badge.follower.ok { background: rgba(8, 153, 129, 0.15); color: #089981; }
      .ws-pnl-rel-badge.follower.mismatch { background: rgba(247, 82, 95, 0.2); color: #f7525f; font-weight: 800; }
      .ws-pnl-rel-badge.follower.quarantine { background: rgba(171, 71, 188, 0.2); color: #ab47bc; }
      .ws-pnl-rel-badge.follower.disabled { background: #2a2e39; color: #787b86; }
      .ws-pnl-pos-badge {
        font-weight: 700;
        padding: 2px 6px;
        border-radius: 3px;
        font-size: 10px;
        display: inline-block;
      }
      .ws-pnl-pos-long { background: rgba(8, 153, 129, 0.25); color: #089981; border: 1px solid rgba(8, 153, 129, 0.4); }
      .ws-pnl-pos-short { background: rgba(247, 82, 95, 0.25); color: #f7525f; border: 1px solid rgba(247, 82, 95, 0.4); }
      .ws-pnl-pos-flat { color: #5d606b; }

      .ws-pnl-sync-badge {
        font-size: 9px;
        font-weight: 700;
        padding: 1px 5px;
        border-radius: 3px;
        text-transform: uppercase;
      }
      .ws-pnl-sync-badge.ok { background: rgba(8, 153, 129, 0.15); color: #089981; }
      .ws-pnl-sync-badge.mismatch { background: rgba(247, 82, 95, 0.2); color: #f7525f; font-weight: 800; }
      .ws-pnl-sync-badge.quarantine { background: rgba(171, 71, 188, 0.2); color: #ab47bc; }
      .ws-pnl-sync-badge.disabled { background: #2a2e39; color: #787b86; }

      .ws-pnl-money-pos { color: #089981; font-weight: 600; }
      .ws-pnl-money-neg { color: #f7525f; font-weight: 600; }
      .ws-pnl-money-zero { color: #787b86; }

      /* Order Ticket (shared params bar + per-account row buttons) */
      .ws-pnl-order-ticket {
        background: #10141d;
        border-bottom: 1px solid #2a2e39;
        padding: 6px 10px;
        display: flex;
        align-items: center;
        gap: 6px;
        flex-wrap: wrap;
        flex-shrink: 0;
      }
      .ws-pnl-ot-group {
        display: flex;
        align-items: center;
        gap: 4px;
      }
      .ws-pnl-ot-label {
        font-size: 9px;
        color: #787b86;
        text-transform: uppercase;
        font-weight: 700;
        letter-spacing: 0.4px;
      }
      .ws-pnl-ot-symbol {
        background: #131722;
        border: 1px solid #2a2e39;
        border-radius: 4px;
        color: #f0f3fa;
        font-size: 11px;
        font-weight: 700;
        padding: 4px 4px;
        width: 118px;
        outline: none;
        cursor: pointer;
      }
      .ws-pnl-ot-symbol:focus { border-color: #2962ff; }
      .ws-pnl-ot-symbol option { background: #131722; color: #d1d4dc; }
      .ws-pnl-ot-max {
        font-size: 9px;
        font-weight: 700;
        color: #f7a600;
        white-space: nowrap;
      }
      .ws-pnl-guard-chip {
        font-size: 9px;
        font-weight: 800;
        padding: 2px 6px;
        border-radius: 3px;
        letter-spacing: 0.3px;
        white-space: nowrap;
      }
      .ws-pnl-guard-chip.shadow { background: rgba(247, 166, 0, 0.15); color: #f7a600; border: 1px solid rgba(247, 166, 0, 0.5); }
      .ws-pnl-guard-chip.live { background: rgba(8, 153, 129, 0.15); color: #089981; border: 1px solid rgba(8, 153, 129, 0.5); }
      .ws-pnl-guard-chip.off { background: #2a2e39; color: #787b86; }
      .ws-pnl-lock-badge {
        font-size: 9px;
        font-weight: 800;
        padding: 1px 4px;
        border-radius: 3px;
        background: rgba(247, 82, 95, 0.2);
        color: #f7525f;
        white-space: nowrap;
      }
      .ws-pnl-ot-row-btn.locked {
        opacity: 0.25;
        pointer-events: none;
      }
      .ws-pnl-ot-qty {
        background: #131722;
        border: 1px solid #2a2e39;
        border-radius: 4px;
        color: #f0f3fa;
        font-size: 11px;
        font-weight: 700;
        padding: 4px 4px;
        width: 42px;
        text-align: center;
        outline: none;
        font-variant-numeric: tabular-nums;
      }
      .ws-pnl-ot-qty:focus { border-color: #2962ff; }
      .ws-pnl-ot-ticks {
        background: #131722;
        border: 1px solid #2a2e39;
        border-radius: 4px;
        color: #d1d4dc;
        font-size: 11px;
        padding: 4px 4px;
        width: 46px;
        text-align: center;
        outline: none;
        font-variant-numeric: tabular-nums;
      }
      .ws-pnl-ot-ticks:focus { border-color: #2962ff; }
      .ws-pnl-ot-atm {
        background: #131722;
        border: 1px solid #2a2e39;
        border-radius: 4px;
        color: #d1d4dc;
        font-size: 11px;
        padding: 4px 6px;
        width: 108px;
        outline: none;
      }
      .ws-pnl-ot-atm:focus { border-color: #2962ff; }
      .ws-pnl-ot-status {
        font-size: 10px;
        font-weight: 600;
        color: #787b86;
        flex: 1;
        text-align: right;
        min-width: 100px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .ws-pnl-ot-status.ok { color: #089981; }
      .ws-pnl-ot-status.err { color: #f7525f; }

      /* Per-account row trade buttons */
      .ws-pnl-ot-row-btn {
        background: transparent;
        border: 1px solid #2a2e39;
        color: #787b86;
        font-size: 9px;
        font-weight: 800;
        padding: 2px 7px;
        border-radius: 3px;
        cursor: pointer;
        transition: all 0.12s ease;
        letter-spacing: 0.4px;
      }
      .ws-pnl-ot-row-btn.b:hover {
        background: #089981;
        border-color: #089981;
        color: #fff;
      }
      .ws-pnl-ot-row-btn.s:hover {
        background: #f7525f;
        border-color: #f7525f;
        color: #fff;
      }
      .ws-pnl-ot-row-btn.busy {
        opacity: 0.4;
        pointer-events: none;
      }
      .ws-pnl-ot-trade-cell {
        white-space: nowrap;
        text-align: center;
      }

      /* Footer */
      .ws-pnl-footer {
        height: 24px;
        background: #141822;
        border-top: 1px solid #2a2e39;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0 10px;
        font-size: 10px;
        color: #5d606b;
        flex-shrink: 0;
      }
    `;
  },

  getHtml: (options = {}) => {
    return `
      <div class="ws-pnl-header" id="ws-pnl-drag-handle">
        <div class="ws-pnl-title-box">
          <div class="ws-pnl-dot" id="ws-pnl-status-dot"></div>
          <span>Fleet P&L & Copier Monitor</span>
          <span class="ws-pnl-badge" id="ws-pnl-bridge-badge">NT8 LIVE</span>
          <span class="ws-pnl-contracts-badge" id="ws-pnl-contracts-badge">0 CONTRACTS</span>
        </div>
        <div class="ws-pnl-controls">
          <button class="ws-pnl-btn" id="ws-pnl-btn-opacity" title="Toggle Opacity (96% / 85% / 70%)">🌓</button>
          <button class="ws-pnl-btn" id="ws-pnl-btn-min" title="Minimize / Expand">🗕</button>
          <button class="ws-pnl-btn ws-pnl-btn-close" id="ws-pnl-btn-close" title="Close HUD">✕</button>
        </div>
      </div>
      <div class="ws-pnl-summary">
        <div class="ws-pnl-stat">
          <span class="ws-pnl-stat-label">Total Fleet Net Liq</span>
          <span class="ws-pnl-stat-val" id="ws-pnl-total-liq">$0.00</span>
        </div>
        <div class="ws-pnl-stat">
          <span class="ws-pnl-stat-label">Open Unrealized</span>
          <span class="ws-pnl-stat-val zero" id="ws-pnl-total-unrealized">$0.00</span>
        </div>
        <div class="ws-pnl-stat">
          <span class="ws-pnl-stat-label">Realized Today</span>
          <span class="ws-pnl-stat-val zero" id="ws-pnl-total-realized">$0.00</span>
        </div>
        <div class="ws-pnl-stat">
          <span class="ws-pnl-stat-label">Open Contracts</span>
          <span class="ws-pnl-stat-val zero" id="ws-pnl-total-pos" title="Open contracts count and exposure breakdown">0 Contracts (Flat)</span>
        </div>
      </div>
      <div class="ws-pnl-copier-banner" id="ws-pnl-copier-banner">
        <div class="ws-pnl-copier-sync-status">
          <span class="ws-pnl-sync-pill ws-pnl-sync-ok" id="ws-pnl-copier-sync-pill">⚡ COPIER: IDLE</span>
          <span id="ws-pnl-copier-sync-msg" style="color: #9db2d4;">All relationships verified</span>
        </div>
        <button class="ws-pnl-flatten-btn" id="ws-pnl-btn-flatten" title="Emergency Flatten all open accounts">🚨 PANIC FLATTEN</button>
      </div>
      <div class="ws-pnl-order-ticket" id="ws-pnl-order-ticket">
        <div class="ws-pnl-ot-group">
          <span class="ws-pnl-ot-label">Symbol</span>
          <select class="ws-pnl-ot-symbol" id="ws-pnl-ot-symbol">
            <option value="">…</option>
          </select>
          <span class="ws-pnl-ot-max" id="ws-pnl-ot-max" title="Max contracts per RiskGuard config"></span>
        </div>
        <div class="ws-pnl-ot-group">
          <span class="ws-pnl-ot-label">Qty</span>
          <input type="number" class="ws-pnl-ot-qty" id="ws-pnl-ot-qty" value="1" min="1" max="50" />
        </div>
        <div class="ws-pnl-ot-group">
          <span class="ws-pnl-ot-label">ATM</span>
          <select class="ws-pnl-ot-atm" id="ws-pnl-ot-atm" title="ATM bracket strategy — AUTO = per-instrument profile. SL/T ticks apply to tick strategies; ATR strategies compute from ATR.">
            <option value="">AUTO</option>
            <option value="FixedTicks">FixedTicks</option>
            <option value="AtrAdaptive">AtrAdaptive</option>
            <option value="SwingPoint">SwingPoint</option>
            <option value="DrawdownShield">DrawdownShield</option>
            <option value="ScaledRunner">ScaledRunner</option>
            <option value="VolatilityScaled">VolatilityScaled</option>
            <option value="SessionAdaptive">SessionAdaptive</option>
            <option value="KellyOptimal">KellyOptimal</option>
          </select>
        </div>
        <div class="ws-pnl-ot-group">
          <span class="ws-pnl-ot-label">SL/T</span>
          <input type="number" class="ws-pnl-ot-ticks" id="ws-pnl-ot-stop" value="40" min="1" title="Stop distance in ticks" />
          <input type="number" class="ws-pnl-ot-ticks" id="ws-pnl-ot-target" value="80" min="1" title="Target distance in ticks" />
        </div>
        <span class="ws-pnl-guard-chip off" id="ws-pnl-guard-chip" title="RiskGuard mode">GUARD</span>
        <span class="ws-pnl-ot-status" id="ws-pnl-ot-status">B/S on each account row</span>
      </div>
      <div class="ws-pnl-toolbar">
        <div class="ws-pnl-view-tabs" id="ws-pnl-view-tabs">
          <button class="ws-pnl-tab-btn active" data-view="active" id="ws-pnl-tab-active">Active (0)</button>
          <button class="ws-pnl-tab-btn" data-view="copier" id="ws-pnl-tab-copier">⚡ Copier (0)</button>
          <button class="ws-pnl-tab-btn" data-view="all" id="ws-pnl-tab-all">All Accounts (0)</button>
        </div>
        <input type="text" class="ws-pnl-search" id="ws-pnl-search-input" placeholder="Search account..." />
      </div>
      <div class="ws-pnl-body" id="ws-pnl-table-wrap">
        <table class="ws-pnl-table">
          <thead id="ws-pnl-thead">
            <tr>
              <th class="sortable" data-sort="name">Account <span class="ws-pnl-sort-icon">⇅</span></th>
              <th class="sortable" data-sort="pos">Position / Qty <span class="ws-pnl-sort-icon active">▼</span></th>
              <th class="sortable" data-sort="unrealized" style="text-align: right;">Unrealized <span class="ws-pnl-sort-icon">⇅</span></th>
              <th class="sortable" data-sort="realized" style="text-align: right;">Realized <span class="ws-pnl-sort-icon">⇅</span></th>
              <th class="sortable" data-sort="netLiq" style="text-align: right;">Net Liq <span class="ws-pnl-sort-icon">⇅</span></th>
            </tr>
          </thead>
          <tbody id="ws-pnl-tbody">
            <tr>
              <td colspan="5" style="text-align: center; color: #787b86; padding: 20px;">
                Connecting to NinjaTrader 8 Bridge & Copier Engine...
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="ws-pnl-footer">
        <span id="ws-pnl-last-update">Connecting stream...</span>
        <span id="ws-pnl-acc-count">0 accounts</span>
      </div>
    `;
  },

  initScript: `
    (function(panel) {
      window.__TV_PNL_STATE__ = window.__TV_PNL_STATE__ || {
        accounts: [],
        positions: [],
        copierRows: [],
        copierSystem: null,
        currentView: 'active',
        searchQuery: '',
        sortCol: 'pos',
        sortDir: 'desc',
        lastUpdate: Date.now()
      };

      const state = window.__TV_PNL_STATE__;

      // Opacity
      const opacities = [0.96, 0.85, 0.70];
      let opIdx = 0;
      const btnOpacity = panel.querySelector('#ws-pnl-btn-opacity');
      if (btnOpacity) {
        btnOpacity.addEventListener('click', (e) => {
          e.stopPropagation();
          opIdx = (opIdx + 1) % opacities.length;
          panel.style.opacity = opacities[opIdx];
          btnOpacity.title = 'Opacity: ' + Math.round(opacities[opIdx] * 100) + '%';
        });
      }

      // Minimize
      const btnMin = panel.querySelector('#ws-pnl-btn-min');
      if (btnMin) {
        btnMin.addEventListener('click', (e) => {
          e.stopPropagation();
          panel.classList.toggle('minimized');
          btnMin.textContent = panel.classList.contains('minimized') ? '🗖' : '🗕';
        });
      }

      // Close
      const btnClose = panel.querySelector('#ws-pnl-btn-close');
      if (btnClose) {
        btnClose.addEventListener('click', (e) => {
          e.stopPropagation();
          if (window.__TV_HUDS__ && typeof window.__TV_HUDS__.remove === 'function') {
            window.__TV_HUDS__.remove('account_pnl');
          } else {
            panel.remove();
          }
        });
      }

      // Emergency Flatten — single click, no confirmation (it's a PANIC button)
      const btnFlatten = panel.querySelector('#ws-pnl-btn-flatten');
      if (btnFlatten) {
        btnFlatten.addEventListener('click', async (e) => {
          e.stopPropagation();
          btnFlatten.textContent = 'FLATTENING FLEET...';
          panel.setAttribute('data-panic-flatten', Date.now().toString());
          try {
            if (window.__TV_PNL_FLATTEN_HOOK) {
              window.__TV_PNL_FLATTEN_HOOK();
            }
          } catch (err) {
            console.error('Flatten failed:', err);
          }
          setTimeout(() => {
            btnFlatten.textContent = '🚨 PANIC FLATTEN';
          }, 2500);
        });
      }

      // View Tab Switching
      const tabs = panel.querySelectorAll('.ws-pnl-tab-btn');
      tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
          e.stopPropagation();
          tabs.forEach(t => t.classList.remove('active'));
          tab.classList.add('active');
          state.currentView = tab.getAttribute('data-view');
          renderTable();
        });
      });

      // Search Filter
      const searchInput = panel.querySelector('#ws-pnl-search-input');
      if (searchInput) {
        searchInput.addEventListener('input', (e) => {
          state.searchQuery = e.target.value.toLowerCase().trim();
          renderTable();
        });
      }

      // Dragging
      const dragHandle = panel.querySelector('#ws-pnl-drag-handle');
      if (dragHandle) {
        let isDragging = false, startX = 0, startY = 0, origLeft = 0, origTop = 0;
        dragHandle.addEventListener('mousedown', (e) => {
          if (e.target.closest('button') || e.target.closest('input')) return;
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
            panel.style.left = Math.max(10, Math.min(window.innerWidth - panel.offsetWidth - 10, origLeft + ev.clientX - startX)) + 'px';
            panel.style.top = Math.max(10, Math.min(window.innerHeight - panel.offsetHeight - 10, origTop + ev.clientY - startY)) + 'px';
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

      function fmtMoney(val) {
        const num = Number(val) || 0;
        const sign = num > 0 ? '+' : num < 0 ? '-' : '';
        return sign + '$' + Math.abs(num).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      }

      function getAccType(name, provider) {
        const n = (name || '').toUpperCase();
        if (n.startsWith('SIM') || provider === 'Simulator') return 'SIM';
        if (n.startsWith('LFE') || n.startsWith('LDE')) return 'LFE';
        if (n.startsWith('APEX') || n.startsWith('PAAPEX')) return 'APEX';
        if (n.startsWith('TAKEPROFIT')) return 'TPT';
        if (n.startsWith('TDYG') || n.startsWith('TDFYG')) return 'TRADEDAY';
        return 'LIVE';
      }

      function getSortIcon(col) {
        if (state.sortCol !== col) return '<span class="ws-pnl-sort-icon">⇅</span>';
        return '<span class="ws-pnl-sort-icon active">' + (state.sortDir === 'asc' ? '▲' : '▼') + '</span>';
      }

      function attachHeaderSortListeners() {
        const thead = panel.querySelector('#ws-pnl-thead');
        if (!thead) return;
        thead.querySelectorAll('th.sortable').forEach(th => {
          th.onclick = (e) => {
            e.stopPropagation();
            const col = th.getAttribute('data-sort');
            if (state.sortCol === col) {
              state.sortDir = state.sortDir === 'asc' ? 'desc' : 'asc';
            } else {
              state.sortCol = col;
              state.sortDir = (col === 'name' || col === 'rel') ? 'asc' : 'desc';
            }
            renderTable();
          };
        });
      }

      function renderCopierView() {
        const thead = panel.querySelector('#ws-pnl-thead');
        const tbody = panel.querySelector('#ws-pnl-tbody');
        if (!tbody || !thead) return;

        thead.innerHTML = '<tr>' +
          '<th class="sortable" data-sort="rel">Relationship ' + getSortIcon('rel') + '</th>' +
          '<th class="sortable" data-sort="exp">Expected Qty ' + getSortIcon('exp') + '</th>' +
          '<th class="sortable" data-sort="act">Actual Qty ' + getSortIcon('act') + '</th>' +
          '<th class="sortable" data-sort="sync" style="text-align:center;">Sync Status ' + getSortIcon('sync') + '</th>' +
          '<th class="sortable" data-sort="pnl" style="text-align:right;">Follower P&L ' + getSortIcon('pnl') + '</th>' +
        '</tr>';

        attachHeaderSortListeners();

        const copierRows = state.copierRows || [];
        const accounts = state.accounts || [];
        const accMap = {};
        accounts.forEach(a => accMap[a.name] = a);

        let filtered = copierRows.filter(r => {
          if (!state.searchQuery) return true;
          return (r.leaderAccountName && r.leaderAccountName.toLowerCase().includes(state.searchQuery)) ||
                 (r.followerAccountName && r.followerAccountName.toLowerCase().includes(state.searchQuery));
        });

        filtered.sort((a, b) => {
          let diff = 0;
          switch (state.sortCol) {
            case 'rel':
              diff = (a.leaderAccountName + a.followerAccountName).localeCompare(b.leaderAccountName + b.followerAccountName);
              break;
            case 'exp':
              diff = (b.expectedQuantity || 0) - (a.expectedQuantity || 0);
              break;
            case 'act':
              diff = (b.actualQuantity || 0) - (a.actualQuantity || 0);
              break;
            case 'sync': {
              const matchA = (a.expectedSide === a.actualSide && a.expectedQuantity === a.actualQuantity);
              const matchB = (b.expectedSide === b.actualSide && b.expectedQuantity === b.actualQuantity);
              const scoreA = !a.isEnabled ? 1 : a.isQuarantined ? 3 : !matchA ? 4 : 2;
              const scoreB = !b.isEnabled ? 1 : b.isQuarantined ? 3 : !matchB ? 4 : 2;
              diff = scoreB - scoreA;
              break;
            }
            case 'pnl': {
              const pnlA = accMap[a.followerAccountName] ? Number(accMap[a.followerAccountName].unrealizedPnL || 0) : 0;
              const pnlB = accMap[b.followerAccountName] ? Number(accMap[b.followerAccountName].unrealizedPnL || 0) : 0;
              diff = pnlB - pnlA;
              break;
            }
            default:
              diff = 0;
          }
          return state.sortDir === 'asc' ? -diff : diff;
        });

        if (filtered.length === 0) {
          tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:#787b86; padding:20px;">No copy relationships active</td></tr>';
          return;
        }

        let html = '';
        filtered.forEach(r => {
          const leader = r.leaderAccountName || 'Leader';
          const follower = r.followerAccountName || 'Follower';
          const followerAcc = accMap[follower];
          const followerPnl = followerAcc ? Number(followerAcc.unrealizedPnL || 0) : 0;
          const followerPnlCls = followerPnl > 0 ? 'ws-pnl-money-pos' : followerPnl < 0 ? 'ws-pnl-money-neg' : 'ws-pnl-money-zero';

          const expQty = r.expectedQuantity || 0;
          const expSide = r.expectedSide || 'Flat';
          const actQty = r.actualQuantity || 0;
          const actSide = r.actualSide || 'Flat';

          const expStr = expSide === 'Flat' ? '0 (Flat)' : expSide + ' ' + expQty + ' ctr';
          const actStr = actSide === 'Flat' ? '0 (Flat)' : actSide + ' ' + actQty + ' ctr';

          const isMatch = (expSide === actSide && expQty === actQty);
          let syncBadge = '<span class="ws-pnl-sync-badge ok">SYNCED</span>';
          if (!r.isEnabled) {
            syncBadge = '<span class="ws-pnl-sync-badge disabled">DISABLED</span>';
          } else if (r.isQuarantined) {
            syncBadge = '<span class="ws-pnl-sync-badge quarantine">QUARANTINE</span>';
          } else if (!isMatch) {
            syncBadge = '<span class="ws-pnl-sync-badge mismatch">DESYNC</span>';
          }

          html += '<tr>' +
            '<td><div class="ws-pnl-acc-name"><span>' + leader + ' &rarr; ' + follower + '</span></div></td>' +
            '<td><span style="font-weight:600; color:#d1d4dc;">' + expStr + '</span></td>' +
            '<td><span style="font-weight:600; color:' + (isMatch ? '#089981' : '#f7525f') + ';">' + actStr + '</span></td>' +
            '<td style="text-align:center;">' + syncBadge + '</td>' +
            '<td style="text-align:right;" class="' + followerPnlCls + '">' + fmtMoney(followerPnl) + '</td>' +
          '</tr>';
        });

        tbody.innerHTML = html;
      }

      function otBuildRelIndex() {
        const rel = { leaders: {}, followers: {} };
        (state.copierRows || []).forEach(r => {
          const L = r.leaderAccountName, F = r.followerAccountName;
          if (!L || !F) return;
          rel.leaders[L] = (rel.leaders[L] || 0) + 1;
          rel.followers[F] = r;
        });
        return rel;
      }

      // Relationship badges are injected into each account's name cell by
      // otApplyRelBadges() after rows exist; rows are stable, badges are
      // updated in place rather than re-rendered with the table.
      function otApplyRelBadges() {
        const rel = otBuildRelIndex();
        panel.querySelectorAll('tr[data-acc]').forEach(tr => {
          const name = tr.getAttribute('data-acc');
          const nameDiv = tr.querySelector('.ws-pnl-acc-name');
          if (!nameDiv) return;
          let html = '';
          if (rel.leaders[name]) {
            html += '<span class="ws-pnl-rel-badge leader" title="Copy-trader LEADER driving ' + rel.leaders[name] + ' follower account(s)">⚡LEADER·' + rel.leaders[name] + '</span>';
          }
          const fr = rel.followers[name];
          if (fr) {
            const isMatch = (fr.expectedSide === fr.actualSide && fr.expectedQuantity === fr.actualQuantity);
            let cls = 'ok', label = 'SYNCED';
            if (!fr.isEnabled) { cls = 'disabled'; label = 'OFF'; }
            else if (fr.isQuarantined) { cls = 'quarantine'; label = 'QTN'; }
            else if (!isMatch) { cls = 'mismatch'; label = 'DESYNC'; }
            html += '<span class="ws-pnl-rel-badge follower ' + cls + '" title="Copy FOLLOWER of ' + fr.leaderAccountName + ' — ' + label + '">' +
              '↳' + fr.leaderAccountName + '·' + label + '</span>';
          }
          const badgeLayer = tr.querySelector('.ws-pnl-rel-badges');
          if (!badgeLayer) {
            const layer = document.createElement('span');
            layer.className = 'ws-pnl-rel-badges';
            nameDiv.appendChild(layer);
            layer.innerHTML = html;
          } else if (badgeLayer.innerHTML !== html) {
            badgeLayer.innerHTML = html;
          }
        });
      }

      function renderAccountsView() {
        const thead = panel.querySelector('#ws-pnl-thead');
        const tbody = panel.querySelector('#ws-pnl-tbody');
        if (!tbody || !thead) return;

        const desiredHead = '<tr>' +
          '<th class="sortable" data-sort="name">Account ' + getSortIcon('name') + '</th>' +
          '<th class="sortable" data-sort="pos">Position / Contracts ' + getSortIcon('pos') + '</th>' +
          '<th class="sortable" data-sort="unrealized" style="text-align:right;">Unrealized ' + getSortIcon('unrealized') + '</th>' +
          '<th class="sortable" data-sort="realized" style="text-align:right;">Realized ' + getSortIcon('realized') + '</th>' +
          '<th class="sortable" data-sort="netLiq" style="text-align:right;">Net Liq ' + getSortIcon('netLiq') + '</th>' +
          '<th style="text-align:center;" title="Market entry with ATM bracket using the shared ticket params">B / S</th>' +
        '</tr>';
        if (thead.innerHTML !== desiredHead) {
          thead.innerHTML = desiredHead;
          attachHeaderSortListeners();
        }

        const accounts = state.accounts || [];
        const positions = state.positions || [];
        const posMap = {};
        positions.forEach(p => { if (p.account) posMap[p.account] = p; });

        let filtered = accounts.filter(acc => {
          const pos = posMap[acc.name];
          const hasPos = pos && pos.marketPosition && pos.marketPosition !== 'Flat';
          const hasBalance = (acc.cashValue > 0 || acc.netLiquidation > 0);
          const hasPnl = (acc.realizedPnL !== 0 || acc.unrealizedPnL !== 0);

          if (state.searchQuery && !acc.name.toLowerCase().includes(state.searchQuery)) return false;
          if (state.currentView === 'active') return hasPos || hasPnl || hasBalance;
          return true; // 'all'
        });

        filtered.sort((a, b) => {
          const posA = posMap[a.name];
          const posB = posMap[b.name];
          const hasPosA = posA && posA.marketPosition && posA.marketPosition !== 'Flat';
          const hasPosB = posB && posB.marketPosition && posB.marketPosition !== 'Flat';
          const qtyA = hasPosA ? Math.abs(Number(posA.quantity) || 1) : 0;
          const qtyB = hasPosB ? Math.abs(Number(posB.quantity) || 1) : 0;

          const uPnlA = (posA && posA.unrealizedPnL !== undefined) ? Number(posA.unrealizedPnL) : (Number(a.unrealizedPnL) || 0);
          const uPnlB = (posB && posB.unrealizedPnL !== undefined) ? Number(posB.unrealizedPnL) : (Number(b.unrealizedPnL) || 0);
          const rPnlA = Number(a.realizedPnL) || 0;
          const rPnlB = Number(b.realizedPnL) || 0;
          const liqA = Number(a.netLiquidation || a.cashValue) || 0;
          const liqB = Number(b.netLiquidation || b.cashValue) || 0;

          let diff = 0;
          switch (state.sortCol) {
            case 'name':
              diff = a.name.localeCompare(b.name);
              break;
            case 'pos':
              if (qtyA !== qtyB) diff = qtyB - qtyA;
              else diff = liqB - liqA;
              break;
            case 'unrealized':
              diff = uPnlB - uPnlA;
              break;
            case 'realized':
              diff = rPnlB - rPnlA;
              break;
            case 'netLiq':
            default:
              diff = liqB - liqA;
              break;
          }

          return state.sortDir === 'asc' ? -diff : diff;
        });

        // Stable-row rendering: rows are created once per account and reused, so
        // buttons never move or vanish under the cursor. Only the volatile cell
        // values are updated in place on each 200ms tick. A full rebuild happens
        // only when the account SET or its ORDER changes (sort/filter/view).
        const orderKey = filtered.map(a => a.name).join('\u0001');
        if (tbody.getAttribute('data-build-key') !== state.currentView + '|' + orderKey) {
          tbody.setAttribute('data-build-key', state.currentView + '|' + orderKey);
          tbody.innerHTML = '';
          if (filtered.length === 0) {
            const tr = document.createElement('tr');
            const td = document.createElement('td');
            td.colSpan = 6;
            td.style.cssText = 'text-align:center; color:#787b86; padding:20px;';
            td.textContent = 'No accounts found';
            tr.appendChild(td);
            tbody.appendChild(tr);
          }
          filtered.forEach(acc => {
            const tr = document.createElement('tr');
            tr.setAttribute('data-acc', acc.name);
            const nameCell = document.createElement('td');
            const nameDiv = document.createElement('div');
            nameDiv.className = 'ws-pnl-acc-name';
            const nameSpan = document.createElement('span');
            nameSpan.textContent = acc.name;
            const typeSpan = document.createElement('span');
            typeSpan.className = 'ws-pnl-acc-type';
            typeSpan.textContent = getAccType(acc.name, acc.provider);
            nameDiv.appendChild(nameSpan);
            nameDiv.appendChild(typeSpan);
            nameCell.appendChild(nameDiv);
            const posCell = document.createElement('td');
            const uCell = document.createElement('td');
            uCell.style.textAlign = 'right';
            const rCell = document.createElement('td');
            rCell.style.textAlign = 'right';
            const liqCell = document.createElement('td');
            liqCell.style.textAlign = 'right';
            liqCell.style.fontWeight = '600';
            liqCell.style.color = '#f0f3fa';
            const tradeCell = document.createElement('td');
            tradeCell.className = 'ws-pnl-ot-trade-cell';
            const bBtn = document.createElement('button');
            bBtn.className = 'ws-pnl-ot-row-btn b';
            bBtn.setAttribute('data-ot-acc', acc.name);
            bBtn.setAttribute('data-ot-side', 'buy');
            bBtn.textContent = 'B';
            const sBtn = document.createElement('button');
            sBtn.className = 'ws-pnl-ot-row-btn s';
            sBtn.setAttribute('data-ot-acc', acc.name);
            sBtn.setAttribute('data-ot-side', 'sell');
            sBtn.textContent = 'S';
            tradeCell.appendChild(bBtn);
            tradeCell.appendChild(document.createTextNode(' '));
            tradeCell.appendChild(sBtn);
            tr.appendChild(nameCell);
            tr.appendChild(posCell);
            tr.appendChild(uCell);
            tr.appendChild(rCell);
            tr.appendChild(liqCell);
            tr.appendChild(tradeCell);
            tbody.appendChild(tr);
          });
        } else if (filtered.length === 0) {
          return;
        }

        filtered.forEach(acc => {
          const tr = tbody.querySelector('tr[data-acc="' + CSS.escape(acc.name) + '"]');
          if (!tr) return;
          const pos = posMap[acc.name];
          const cells = tr.children;

          let posHtml = '<span class="ws-pnl-pos-badge ws-pnl-pos-flat">0 (FLAT)</span>';
          let uPnl = Number(acc.unrealizedPnL) || 0;

          if (pos && pos.marketPosition && pos.marketPosition !== 'Flat') {
            const isLong = pos.marketPosition.toLowerCase() === 'long';
            const cls = isLong ? 'ws-pnl-pos-long' : 'ws-pnl-pos-short';
            const sign = isLong ? '+' : '-';
            const qty = Math.abs(Number(pos.quantity) || 1);
            const sym = pos.symbol || pos.instrument || '';
            const price = Number(pos.avgPrice || pos.averagePrice || 0);
            const priceStr = price > 0 ? ' @ ' + price.toFixed(2) : '';
            posHtml = '<span class="ws-pnl-pos-badge ' + cls + '">' + (isLong ? 'LONG' : 'SHORT') + ' ' + qty + ' ' + sym + priceStr + '</span>';

            if (pos.unrealizedPnL !== undefined && pos.unrealizedPnL !== null) {
              uPnl = Number(pos.unrealizedPnL) || uPnl;
            }
          }

          const rPnl = Number(acc.realizedPnL) || 0;
          const netLiq = Number(acc.netLiquidation || acc.cashValue) || 0;

          const uCls = uPnl > 0 ? 'ws-pnl-money-pos' : uPnl < 0 ? 'ws-pnl-money-neg' : 'ws-pnl-money-zero';
          const rCls = rPnl > 0 ? 'ws-pnl-money-pos' : rPnl < 0 ? 'ws-pnl-money-neg' : 'ws-pnl-money-zero';

          const posCell = cells[1];
          if (posCell.innerHTML !== posHtml) posCell.innerHTML = posHtml;
          if (cells[2].className !== uCls) cells[2].className = uCls;
          if (cells[2].textContent !== fmtMoney(uPnl)) cells[2].textContent = fmtMoney(uPnl);
          if (cells[3].className !== rCls) cells[3].className = rCls;
          if (cells[3].textContent !== fmtMoney(rPnl)) cells[3].textContent = fmtMoney(rPnl);
          if (cells[4].textContent !== fmtMoney(netLiq)) cells[4].textContent = fmtMoney(netLiq);
        });
      }

      function renderTable() {
        if (state.currentView === 'copier') {
          renderCopierView();
        } else {
          renderAccountsView();
        }
      }

      // Order Ticket — shared params bar + per-account B/S buttons in the P&L table
      const otStatus = panel.querySelector('#ws-pnl-ot-status');
      const otSymbol = panel.querySelector('#ws-pnl-ot-symbol');
      const otQty = panel.querySelector('#ws-pnl-ot-qty');
      const otAtm = panel.querySelector('#ws-pnl-ot-atm');
      const otStop = panel.querySelector('#ws-pnl-ot-stop');
      const otTarget = panel.querySelector('#ws-pnl-ot-target');
      const otMax = panel.querySelector('#ws-pnl-ot-max');
      const guardChip = panel.querySelector('#ws-pnl-guard-chip');
      let tbodyDelegated = false;

      // RiskGuard config — drives the ticker list and qty cap. The guard is the
      // authority; the ticket just renders its rules so a blocked instrument or
      // oversize is unselectable rather than rejected after the fact.
      state.guardCfg = state.guardCfg || null;
      state.lockouts = state.lockouts || {};

      function otQuarterContracts() {
        // Front + next quarterly codes from today (UTC): Mar/Jun/Sep/Dec
        const now = new Date();
        const y0 = now.getUTCFullYear();
        const m0 = now.getUTCMonth(); // 0-11
        const quarters = [[2, '03'], [5, '06'], [8, '09'], [11, '12']];
        const yy = (y) => String(y % 100).padStart(2, '0');
        const q = [];
        for (let y = y0; y <= y0 + 1; y++) {
          quarters.forEach(function (pair) {
            const mm = pair[0], code = pair[1];
            if (y === y0 && mm < m0) return; // past quarters out
            q.push(code + '-' + yy(y));
          });
        }
        return q.slice(0, 2); // front + next
      }

      function otApplyGuardConfig(cfg) {
        state.guardCfg = cfg;
        if (!otSymbol) return;
        if (!cfg || !cfg.loaded) {
          guardChip.textContent = 'GUARD?';
          guardChip.className = 'ws-pnl-guard-chip off';
          guardChip.title = 'RiskGuard config not readable: ' + (cfg && cfg.error ? cfg.error : 'unknown');
          return;
        }
        const modeCls = cfg.mode === 'live' ? 'live' : cfg.mode === 'shadow' ? 'shadow' : 'off';
        guardChip.textContent = 'GUARD: ' + String(cfg.mode).toUpperCase();
        guardChip.className = 'ws-pnl-guard-chip ' + modeCls;
        guardChip.title = 'RiskGuard ' + cfg.mode + ' — allowed: ' + cfg.allowedRoots.join(', ');

        const contracts = otQuarterContracts();
        const prev = otSymbol.value;
        otSymbol.innerHTML = '';
        (cfg.allowedRoots || []).forEach(root => {
          contracts.forEach(c => {
            const opt = document.createElement('option');
            opt.value = root + ' ' + c;
            opt.textContent = root + ' ' + c;
            otSymbol.appendChild(opt);
          });
        });
        if (prev && Array.from(otSymbol.options).some(o => o.value === prev)) otSymbol.value = prev;
        otUpdateQtyCap();
      }

      function otCurrentRoot() {
        return (otSymbol?.value || '').split(' ')[0].toUpperCase();
      }

      function otUpdateQtyCap() {
        if (!otMax) return;
        const cfg = state.guardCfg;
        const root = otCurrentRoot();
        if (!cfg || !cfg.loaded || !root) { otMax.textContent = ''; return; }
        const perInstr = cfg.instrumentLimits && cfg.instrumentLimits[root] && cfg.instrumentLimits[root].MaxContracts;
        const caps = [perInstr, cfg.maxPerAccount, parseInt(otQty?.max, 10) || 50].filter(v => typeof v === 'number' && v > 0);
        const cap = Math.min(...caps);
        otMax.textContent = 'max ' + cap;
        otMax.title = 'RiskGuard cap' + (perInstr ? ' (' + root + ': ' + perInstr + ')' : '') + (cfg.maxPerAccount ? ' / account: ' + cfg.maxPerAccount : '');
        if (otQty) {
          otQty.max = String(cap);
          if ((parseInt(otQty.value, 10) || 1) > cap) otQty.value = String(cap);
        }
      }

      async function otFetchGuardConfig() {
        try {
          const res = await fetch('/api/guard/config');
          otApplyGuardConfig(await res.json());
        } catch { /* keep last */ }
      }
      otFetchGuardConfig();
      setInterval(otFetchGuardConfig, 30000);

      async function otFetchLockouts() {
        try {
          const res = await fetch('/api/lockouts');
          state.lockouts = await res.json();
          otApplyLockouts();
        } catch { /* keep last */ }
      }
      otFetchLockouts();
      setInterval(otFetchLockouts, 3000);

      function otApplyLockouts() {
        panel.querySelectorAll('tr[data-acc]').forEach(tr => {
          const acc = tr.getAttribute('data-acc');
          const locked = state.lockouts[acc] === true;
          tr.querySelectorAll('.ws-pnl-ot-row-btn').forEach(btn => btn.classList.toggle('locked', locked));
          let badge = tr.querySelector('.ws-pnl-lock-badge');
          if (locked && !badge) {
            const nameCell = tr.querySelector('.ws-pnl-acc-name');
            if (nameCell) {
              badge = document.createElement('span');
              badge.className = 'ws-pnl-lock-badge';
              badge.title = 'RiskGuard lockout active — orders refused';
              badge.textContent = '🔒LOCKED';
              nameCell.appendChild(badge);
            }
          } else if (!locked && badge) {
            badge.remove();
          }
        });
      }

      if (otSymbol) otSymbol.addEventListener('change', otUpdateQtyCap);

      function otSetStatus(msg, cls) {
        if (!otStatus) return;
        otStatus.textContent = msg;
        otStatus.className = 'ws-pnl-ot-status' + (cls ? ' ' + cls : '');
      }

      async function otPlaceOrder(side, account) {
        const symbol = (otSymbol?.value || '').trim().toUpperCase();
        const qty = parseInt(otQty?.value, 10) || 0;
        const strategyName = (otAtm?.value || '').trim() || undefined;
        const stopTicks = parseInt(otStop?.value, 10) || 0;
        const targetTicks = parseInt(otTarget?.value, 10) || 0;

        if (!account) return otSetStatus('No account', 'err');
        if (!symbol) return otSetStatus('Pick a symbol in the ticket bar', 'err');
        if (qty < 1) return otSetStatus('Qty must be >= 1', 'err');
        if (!stopTicks || !targetTicks) return otSetStatus('SL/T ticks required', 'err');

        const busyKey = account + '|' + side;
        state.otBusy = state.otBusy || {};
        if (state.otBusy[busyKey]) return;
        state.otBusy[busyKey] = true;
        otApplyBusy();
        otSetStatus('Submitting ' + side.toUpperCase() + ' ' + qty + ' ' + symbol + ' on ' + account + '...');

        try {
          const res = await fetch('/api/order/atm', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              symbol, action: side, quantity: qty, account,
              strategyName, stopTicks, targetTicks,
              idempotencyKey: 'ot-' + Date.now() + '-' + Math.random().toString(36).slice(2, 8)
            })
          });
          const json = await res.json().catch(() => ({}));
          if (res.ok && !json.error) {
            otSetStatus('OK ' + side.toUpperCase() + ' ' + qty + ' ' + symbol + ' ' + account + ' [' + (json.bracketId || 'bracket') + ']', 'ok');
          } else {
            otSetStatus('REJECTED ' + account + ': ' + (json.error || ('HTTP ' + res.status)), 'err');
          }
        } catch (err) {
          otSetStatus('FAILED ' + account + ': ' + err.message, 'err');
        } finally {
          state.otBusy[busyKey] = false;
          otApplyBusy();
        }
      }

      // The table re-renders every 200ms; re-apply busy state to the fresh buttons
      function otApplyBusy() {
        const busy = state.otBusy || {};
        panel.querySelectorAll('.ws-pnl-ot-row-btn').forEach(btn => {
          const key = (btn.getAttribute('data-ot-acc') || '') + '|' + (btn.getAttribute('data-ot-side') || '');
          btn.classList.toggle('busy', !!busy[key]);
        });
      }

      // Merge symbols seen in open positions into the ticker dropdown (keeps the
      // static list but self-corrects for whatever the fleet is actually trading)
      function otSyncSymbolOptions(positions) {
        if (!otSymbol) return;
        const known = new Set(Array.from(otSymbol.options).map(o => o.value.toUpperCase()));
        (positions || []).forEach(p => {
          const sym = (p.symbol || p.instrument || '').toUpperCase();
          if (!sym || !p.marketPosition || p.marketPosition === 'Flat') return;
          if (!known.has(sym)) {
            const opt = document.createElement('option');
            opt.value = sym;
            opt.textContent = sym;
            otSymbol.appendChild(opt);
            known.add(sym);
          }
        });
      }

      // Event delegation: ONE listener on tbody survives every row rebuild/reuse.
      // Per-button listeners were destroyed by the 200ms re-render — a click was
      // eaten whenever innerHTML replaced the node between mousedown and mouseup.
      if (tbodyDelegated !== true) {
        tbodyDelegated = true;
        const tbodyEl = panel.querySelector('#ws-pnl-tbody');
        if (tbodyEl) {
          tbodyEl.addEventListener('click', (e) => {
            const btn = e.target.closest('.ws-pnl-ot-row-btn');
            if (!btn) return;
            e.stopPropagation();
            otPlaceOrder(btn.getAttribute('data-ot-side'), btn.getAttribute('data-ot-acc'));
          });
        }
      }

      // External Update Hook called by background data streamer or local widget poller
      window.__TV_HUDS__ = window.__TV_HUDS__ || {};
      window.__TV_HUDS__.update = function(hudId, data) {
        if (hudId !== 'account_pnl' || !data) return;

        state.accounts = data.accounts || [];
        state.positions = data.positions || [];
        state.copierRows = data.copierRows || [];
        state.copierSystem = data.copierSystem || null;
        state.lastUpdate = Date.now();

        // Update Aggregate Header
        const totalLiq = data.totalNetLiquidation || 0;
        const totalUnrealized = data.totalUnrealizedPnL || 0;
        const totalRealized = data.totalRealizedPnL || 0;
        const totalOpenContracts = data.totalOpenContracts || 0;
        const activeContracts = data.activeContracts || '0 Contracts (Flat)';

        const elLiq = panel.querySelector('#ws-pnl-total-liq');
        const elUnreal = panel.querySelector('#ws-pnl-total-unrealized');
        const elReal = panel.querySelector('#ws-pnl-total-realized');
        const elPos = panel.querySelector('#ws-pnl-total-pos');
        const elContractsBadge = panel.querySelector('#ws-pnl-contracts-badge');

        if (elLiq) elLiq.textContent = fmtMoney(totalLiq);
        if (elUnreal) {
          elUnreal.textContent = fmtMoney(totalUnrealized);
          elUnreal.className = 'ws-pnl-stat-val ' + (totalUnrealized > 0 ? 'pos' : totalUnrealized < 0 ? 'neg' : 'zero');
        }
        if (elReal) {
          elReal.textContent = fmtMoney(totalRealized);
          elReal.className = 'ws-pnl-stat-val ' + (totalRealized > 0 ? 'pos' : totalRealized < 0 ? 'neg' : 'zero');
        }
        if (elPos) {
          elPos.textContent = activeContracts;
          elPos.className = 'ws-pnl-stat-val ' + (totalOpenContracts > 0 ? 'pos' : 'zero');
        }

        // Header Contract Badge
        if (elContractsBadge) {
          if (totalOpenContracts > 0) {
            elContractsBadge.textContent = totalOpenContracts + ' CONTRACT' + (totalOpenContracts > 1 ? 'S' : '') + ' OPEN';
            elContractsBadge.className = 'ws-pnl-contracts-badge active-pos';
          } else {
            elContractsBadge.textContent = '0 CONTRACTS';
            elContractsBadge.className = 'ws-pnl-contracts-badge';
          }
        }

        // Update Copier Banner
        const syncPill = panel.querySelector('#ws-pnl-copier-sync-pill');
        const syncMsg = panel.querySelector('#ws-pnl-copier-sync-msg');
        if (syncPill && syncMsg) {
          const rows = state.copierRows || [];
          const desynced = rows.filter(r => r.isEnabled && (r.expectedSide !== r.actualSide || r.expectedQuantity !== r.actualQuantity));
          const quarantined = rows.filter(r => r.isQuarantined);

          if (desynced.length > 0) {
            syncPill.className = 'ws-pnl-sync-pill ws-pnl-sync-alert';
            syncPill.textContent = '🚨 ' + desynced.length + ' DESYNCED!';
            syncMsg.textContent = 'Follower position mismatch detected!';
          } else if (quarantined.length > 0) {
            syncPill.className = 'ws-pnl-sync-pill ws-pnl-sync-warn';
            syncPill.textContent = '🔒 ' + quarantined.length + ' QUARANTINED';
            syncMsg.textContent = 'RiskGuard protection engaged';
          } else if (rows.length > 0 && rows.some(r => r.isEnabled)) {
            syncPill.className = 'ws-pnl-sync-pill ws-pnl-sync-ok';
            syncPill.textContent = '🟢 SYNC OK (' + rows.filter(r => r.isEnabled).length + ' Active)';
            syncMsg.textContent = 'All follower positions verified';
          } else {
            syncPill.className = 'ws-pnl-sync-pill ws-pnl-sync-ok';
            syncPill.textContent = '⚪ COPIER IDLE';
            syncMsg.textContent = 'Fleet ready';
          }
        }

        // Update Tabs count
        const activeTab = panel.querySelector('#ws-pnl-tab-active');
        const allTab = panel.querySelector('#ws-pnl-tab-all');
        const copierTab = panel.querySelector('#ws-pnl-tab-copier');
        if (activeTab) {
          const ctrStr = totalOpenContracts > 0 ? ' • ' + totalOpenContracts + ' Open' : '';
          activeTab.textContent = 'Active (' + (data.activeAccountsCount || 0) + ctrStr + ')';
        }
        if (allTab) allTab.textContent = 'All Accounts (' + state.accounts.length + ')';
        if (copierTab) copierTab.textContent = '⚡ Copier (' + state.copierRows.length + ')';

        // Update Footer
        const elFooterCount = panel.querySelector('#ws-pnl-acc-count');
        const elFooterTime = panel.querySelector('#ws-pnl-last-update');
        const statusDot = panel.querySelector('#ws-pnl-status-dot');
        const bridgeBadge = panel.querySelector('#ws-pnl-bridge-badge');

        if (statusDot) statusDot.classList.remove('offline');
        if (bridgeBadge) {
          bridgeBadge.textContent = 'NT8 LIVE';
          bridgeBadge.className = 'ws-pnl-badge';
        }
        if (elFooterCount) {
          const ctrFoot = totalOpenContracts > 0 ? ' | ' + totalOpenContracts + ' contract' + (totalOpenContracts > 1 ? 's' : '') + ' open' : ' | Flat';
          elFooterCount.textContent = state.accounts.length + ' accounts | ' + (data.activeAccountsCount || 0) + ' active' + ctrFoot;
        }
        if (elFooterTime) elFooterTime.textContent = 'Live \u2022 ' + new Date().toLocaleTimeString();

        otSyncSymbolOptions(state.positions);
        otApplyBusy();
        otApplyLockouts();
        otApplyRelBadges();
        renderTable();
      };
    })
  `
};
