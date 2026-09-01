#!/usr/bin/env node
/**
 * Unified Real-Time P&L & Copier Engine and Standalone Widget Server.
 * 
 * Functions:
 * 1. High-Frequency Poller (200ms) connecting locally to NinjaTrader 8 (port 7890).
 * 2. CDP Real-Time Streamer: Pushes live ticks into TradingView Desktop (CDP port 9222).
 * 3. Local Web Server (port 8635): Serves the standalone floating desktop widget with zero CORS issues.
 */

import http from 'node:http';
import { hud } from './huds/account_pnl.js';

const PORT = Number(process.env.PNL_WIDGET_PORT) || 8635;
const NT8_PORT = Number(process.env.NT8_PORT) || 7890;
const NT8_HOST = process.env.NT8_HOST || 'localhost';
const NT8_TOKEN = process.env.NT8_MCP_TOKEN || 'd0b837223cab4653';
const TV_CDP_PORT = Number(process.env.TV_CDP_PORT) || 9222;
const TV_CDP_HOST = process.env.TV_CDP_HOST || '127.0.0.1';
const POLL_INTERVAL_MS = Number(process.env.POLL_INTERVAL_MS) || 200; // 5x per second

let latestPayload = null;
let lastStateHash = '';
let tvWs = null;
let tvMsgId = 1;
let tvConnecting = false;

// 1. NinjaTrader 8 Bridge Fetcher
async function fetchNt8(path) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: NT8_HOST,
      port: NT8_PORT,
      path: path,
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${NT8_TOKEN}`,
        'Accept': 'application/json'
      },
      timeout: 1200
    };

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => { data += chunk; });
      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try { resolve(JSON.parse(data)); } catch (e) { reject(e); }
        } else {
          reject(new Error(`NT8 HTTP ${res.statusCode}: ${data}`));
        }
      });
    });

    req.on('error', reject);
    req.on('timeout', () => {
      req.destroy();
      reject(new Error(`NT8 request to ${path} timed out`));
    });
    req.end();
  });
}

function computeFleetSummary(accounts, positions, copierSnapshot) {
  let totalLiq = 0;
  let totalRealized = 0;
  let totalUnrealized = 0;
  let activeAccountsCount = 0;

  const posMap = {};
  positions.forEach(p => {
    if (p.account) posMap[p.account] = p;
  });

  accounts.forEach(acc => {
    const pos = posMap[acc.name];
    const liq = Number(acc.netLiquidation || acc.cashValue) || 0;
    const rPnl = Number(acc.realizedPnL) || 0;
    let uPnl = Number(acc.unrealizedPnL) || 0;

    if (pos && pos.unrealizedPnL !== undefined && pos.unrealizedPnL !== null) {
      uPnl = Number(pos.unrealizedPnL) || uPnl;
    }

    totalLiq += liq;
    totalRealized += rPnl;
    totalUnrealized += uPnl;

    if (liq > 0 || rPnl !== 0 || uPnl !== 0 || (pos && pos.marketPosition !== 'Flat')) {
      activeAccountsCount++;
    }
  });

  let totalOpenContracts = 0;
  const posCounts = {};
  positions.forEach(p => {
    if (p.marketPosition && p.marketPosition !== 'Flat') {
      const qty = Math.abs(Number(p.quantity) || 1);
      totalOpenContracts += qty;
      const sym = (p.symbol || p.instrument || '').split(' ')[0];
      const key = `${p.marketPosition === 'Long' ? '+' : '-'}${qty} ${sym}`.trim();
      posCounts[key] = (posCounts[key] || 0) + 1;
    }
  });

  const activePosKeys = Object.keys(posCounts);
  let activeContractsStr = '0 Contracts (Flat)';
  if (totalOpenContracts > 0) {
    const breakdown = activePosKeys.map(k => `${k}${posCounts[k] > 1 ? ` (x${posCounts[k]})` : ''}`).join(', ');
    activeContractsStr = `${totalOpenContracts} Contract${totalOpenContracts > 1 ? 's' : ''} (${breakdown})`;
  }

  return {
    accounts,
    positions,
    copierRows: copierSnapshot?.rows || [],
    copierSystem: copierSnapshot?.system || null,
    totalNetLiquidation: totalLiq,
    totalRealizedPnL: totalRealized,
    totalUnrealizedPnL: totalUnrealized,
    totalOpenContracts,
    activeAccountsCount,
    activeContracts: activeContractsStr,
    timestamp: Date.now()
  };
}

// 2. CDP Connection to TradingView Desktop
async function ensureTvConnection() {
  if (tvWs && tvWs.readyState === WebSocket.OPEN) return tvWs;
  if (tvConnecting) return null;

  tvConnecting = true;
  try {
    const targetRes = await fetch(`http://${TV_CDP_HOST}:${TV_CDP_PORT}/json`);
    const targets = await targetRes.json();
    const chart = targets.find(t => t.type === 'page' && t.url.includes('tradingview.com/chart'))
               || targets.find(t => t.type === 'page');

    if (!chart || !chart.webSocketDebuggerUrl) {
      tvConnecting = false;
      return null;
    }

    const ws = new WebSocket(chart.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('CDP timeout')), 2000);
      ws.onopen = () => { clearTimeout(timer); resolve(); };
      ws.onerror = (e) => { clearTimeout(timer); reject(e); };
    });

    ws.onclose = () => { if (tvWs === ws) tvWs = null; };
    ws.onerror = () => { if (tvWs === ws) tvWs = null; };
    ws.onmessage = (event) => {
      try {
        const res = JSON.parse(event.data);
        if (res.result?.value?.panicRequested) {
          triggerEmergencyFlatten('TradingView In-Chart HUD');
        }
      } catch {}
    };

    tvWs = ws;
    return tvWs;
  } catch (e) {
    tvWs = null;
    return null;
  } finally {
    tvConnecting = false;
  }
}

async function triggerEmergencyFlatten(source = 'HUD') {
  console.log(`[!] EMERGENCY FLATTEN TRIGGERED (Source: ${source})`);
  return new Promise((resolve) => {
    const options = {
      hostname: NT8_HOST,
      port: NT8_PORT,
      path: '/api/emergency-flatten',
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${NT8_TOKEN}`,
        'Content-Type': 'application/json'
      },
      timeout: 3000
    };

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => { data += chunk; });
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          console.log('[OK] Emergency Flatten executed:', json);
          resolve(json);
        } catch {
          resolve({ status: 'sent', raw: data });
        }
      });
    });

    req.on('error', (err) => {
      console.error('[ERR] Emergency Flatten failed:', err.message);
      resolve({ error: err.message });
    });

    req.write(JSON.stringify({ reason: `Operator Panic Flatten (${source})` }));
    req.end();
  });
}

async function pushToTradingView(payload) {
  try {
    const ws = await ensureTvConnection();
    if (ws && ws.readyState === WebSocket.OPEN) {
      const id = tvMsgId++;
      const pushScript = `
        (function() {
          const panel = document.getElementById('ws-pnl-panel');
          const isPanicRequested = panel && panel.getAttribute('data-panic-flatten');
          if (isPanicRequested) {
            panel.removeAttribute('data-panic-flatten');
          }
          if (window.__TV_HUDS__ && typeof window.__TV_HUDS__.update === 'function') {
            window.__TV_HUDS__.update('account_pnl', ${JSON.stringify(payload)});
          }
          return { panicRequested: !!isPanicRequested };
        })()
      `;

      ws.send(JSON.stringify({
        id,
        method: 'Runtime.evaluate',
        params: { expression: pushScript, returnByValue: true }
      }));
    }
  } catch (e) {
    // Quietly ignore TV push errors
  }
}

// Unhandled Exception Protection
process.on('uncaughtException', (err) => {
  console.error('[UNCAUGHT EXCEPTION]', err.message);
});
process.on('unhandledRejection', (reason) => {
  console.error('[UNHANDLED REJECTION]', reason);
});

// Sequential Polling Loop
let isServerPolling = false;
async function pollNt8() {
  if (isServerPolling) return;
  isServerPolling = true;
  try {
    const [accounts, positions, copierSnapshot] = await Promise.all([
      fetchNt8('/api/account').catch(() => null),
      fetchNt8('/api/positions').catch(() => []),
      fetchNt8('/api/copier/snapshot').catch(() => ({ rows: [], system: null }))
    ]);

    if (accounts && Array.isArray(accounts)) {
      latestPayload = computeFleetSummary(accounts, positions, copierSnapshot);
      await pushToTradingView(latestPayload);
    }
  } catch (err) {
    // Keep last known good payload
  } finally {
    isServerPolling = false;
  }
}

async function runPoller() {
  while (true) {
    try {
      await pollNt8();
    } catch (err) {}
    await new Promise(r => setTimeout(r, POLL_INTERVAL_MS));
  }
}

runPoller();

// 4. HTML Generation for Standalone Desktop Window
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
    const panel = document.getElementById('ws-pnl-panel');
    (${initScript})(panel);

    // Local Polling from this Node Server (Port ${PORT})
    let isPolling = false;
    async function updateFromLocalEngine() {
      if (isPolling) return;
      isPolling = true;
      try {
        const res = await fetch('/api/data');
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        
        if (data && data.accounts) {
          if (window.__TV_HUDS__ && typeof window.__TV_HUDS__.update === 'function') {
            window.__TV_HUDS__.update('account_pnl', data);
          }
          const dot = document.getElementById('ws-pnl-status-dot');
          if (dot) dot.classList.remove('offline');
        } else {
          throw new Error('No data');
        }
      } catch (err) {
        const dot = document.getElementById('ws-pnl-status-dot');
        if (dot) dot.classList.add('offline');
        const badge = document.getElementById('ws-pnl-bridge-badge');
        if (badge) {
          badge.textContent = 'OFFLINE';
          badge.className = 'ws-pnl-badge offline';
        }
        const footerTime = document.getElementById('ws-pnl-last-update');
        if (footerTime) footerTime.textContent = 'NT8 Offline';
      } finally {
        isPolling = false;
      }
    }

    // Direct Local 200ms Poll
    updateFromLocalEngine();
    setInterval(updateFromLocalEngine, 200);

    // Hook Panic Flatten to local proxy
    window.__TV_PNL_FLATTEN_HOOK = function() {
      fetch('/api/flatten', { method: 'POST' }).catch(console.error);
    };
  </script>
</body>
</html>`;

// 5. HTTP Server
const server = http.createServer((req, res) => {
  // CORS Headers
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  if (req.url === '/' || req.url.startsWith('/pnl-widget') || req.url.startsWith('/index')) {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(pageHtml);
  } else if (req.url === '/api/data') {
    if (latestPayload) {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(latestPayload));
    } else {
      res.writeHead(503, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: 'NT8 bridge connecting or offline' }));
    }
  } else if (req.url === '/api/flatten' && req.method === 'POST') {
    triggerEmergencyFlatten('Standalone Desktop Widget').then((result) => {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(result));
    }).catch((err) => {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: err.message }));
    });
  } else if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({
      status: 'ok',
      port: PORT,
      nt8Connected: latestPayload !== null,
      accountsCount: latestPayload?.accounts?.length || 0,
      activePositions: latestPayload?.activeContracts || 'Flat'
    }));
  } else {
    res.writeHead(404);
    res.end('Not Found');
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[+] Unified Real-time P&L Engine running at http://127.0.0.1:${PORT}`);
});
