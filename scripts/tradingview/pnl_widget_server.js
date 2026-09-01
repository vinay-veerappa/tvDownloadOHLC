#!/usr/bin/env node
/**
 * Standalone Desktop P&L & Copier Widget Server.
 * 
 * Serves the responsive Fleet P&L & Copy-Trading Monitor on port 7892.
 * Can be opened in any browser or launched as a frameless floating desktop window via Edge/Chrome App Mode.
 */

import http from 'node:http';
import { hud } from './huds/account_pnl.js';

const PORT = Number(process.env.PNL_WIDGET_PORT) || 8635;
const NT8_PORT = Number(process.env.NT8_PORT) || 7890;
const NT8_HOST = process.env.NT8_HOST || 'localhost';
const NT8_TOKEN = process.env.NT8_MCP_TOKEN || 'd0b837223cab4653';

const css = hud.getCss({ top: 0, right: 0, width: '100%', height: '100%', opacity: 0.98 });
const html = hud.getHtml();
const initScript = hud.initScript;

const pageHtml = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Fleet P&L & Copier Monitor</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #131722;
      color: #d1d4dc;
      font-family: -apple-system, BlinkMacSystemFont, "Trebuchet MS", Roboto, Ubuntu, sans-serif;
      height: 100vh;
      overflow: hidden;
      display: flex;
    }
    #ws-pnl-panel {
      position: relative !important;
      top: 0 !important;
      right: 0 !important;
      left: 0 !important;
      bottom: 0 !important;
      width: 100vw !important;
      height: 100vh !important;
      max-width: 100vw !important;
      max-height: 100vh !important;
      border-radius: 0 !important;
      border: none !important;
      box-shadow: none !important;
      resize: none !important;
    }
    ${css}
  </style>
</head>
<body>
  <div id="ws-pnl-panel">
    ${html}
  </div>

  <script>
    // Initialize component logic
    const panel = document.getElementById('ws-pnl-panel');
    (${initScript})(panel);

    // Direct Live Polling Loop from NinjaTrader 8
    const NT8_TOKEN = ${JSON.stringify(NT8_TOKEN)};
    const NT8_URL = 'http://${NT8_HOST}:${NT8_PORT}';

    async function fetchNt8(path) {
      const res = await fetch(NT8_URL + path, {
        headers: { 'Authorization': 'Bearer ' + NT8_TOKEN }
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      return await res.json();
    }

    function computeFleetSummary(accounts, positions, copierSnapshot) {
      let totalLiq = 0, totalRealized = 0, totalUnrealized = 0, activeAccountsCount = 0;
      accounts.forEach(acc => {
        const liq = Number(acc.netLiquidation || acc.cashValue) || 0;
        const rPnl = Number(acc.realizedPnL) || 0;
        const uPnl = Number(acc.unrealizedPnL) || 0;
        totalLiq += liq;
        totalRealized += rPnl;
        totalUnrealized += uPnl;
        if (liq > 0 || rPnl !== 0 || uPnl !== 0) activeAccountsCount++;
      });

      const posCounts = {};
      positions.forEach(p => {
        if (p.marketPosition && p.marketPosition !== 'Flat') {
          const key = (p.marketPosition === 'Long' ? '+' : '-') + p.quantity + ' ' + (p.instrument || '');
          posCounts[key] = (posCounts[key] || 0) + 1;
        }
      });

      const activePosKeys = Object.keys(posCounts);
      let activeContractsStr = 'Flat';
      if (activePosKeys.length > 0) {
        activeContractsStr = activePosKeys.map(k => k + (posCounts[k] > 1 ? ' (x' + posCounts[k] + ')' : '')).join(', ');
      }

      return {
        accounts,
        positions,
        copierRows: copierSnapshot ? copierSnapshot.rows || [] : [],
        copierSystem: copierSnapshot ? copierSnapshot.system || null : null,
        totalNetLiquidation: totalLiq,
        totalRealizedPnL: totalRealized,
        totalUnrealizedPnL: totalUnrealized,
        activeAccountsCount,
        activeContracts: activeContractsStr
      };
    }

    let isPolling = false;
    async function poll() {
      if (isPolling) return;
      isPolling = true;
      try {
        const [accounts, positions, copierSnapshot] = await Promise.all([
          fetchNt8('/api/account'),
          fetchNt8('/api/positions').catch(() => []),
          fetchNt8('/api/copier/snapshot').catch(() => ({ rows: [], system: null }))
        ]);

        const data = computeFleetSummary(accounts, positions, copierSnapshot);
        if (window.__TV_HUDS__ && typeof window.__TV_HUDS__.update === 'function') {
          window.__TV_HUDS__.update('account_pnl', data);
        }

        const dot = document.getElementById('ws-pnl-status-dot');
        if (dot) dot.classList.remove('offline');
      } catch (err) {
        const dot = document.getElementById('ws-pnl-status-dot');
        if (dot) dot.classList.add('offline');
        const footerTime = document.getElementById('ws-pnl-last-update');
        if (footerTime) footerTime.textContent = 'Disconnected (NT8 offline)';
      } finally {
        isPolling = false;
      }
    }

    // Direct Instant Polling (250ms interval)
    poll();
    setInterval(poll, 250);
  </script>
</body>
</html>`;

const server = http.createServer((req, res) => {
  if (req.url === '/' || req.url.startsWith('/index') || req.url.startsWith('/pnl-widget')) {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(pageHtml);
  } else if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', port: PORT }));
  } else {
    res.writeHead(404);
    res.end('Not Found');
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[+] Standalone P&L & Copier Monitor Server running at http://127.0.0.1:${PORT}`);
});
