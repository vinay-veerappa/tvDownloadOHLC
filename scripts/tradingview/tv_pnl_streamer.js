#!/usr/bin/env node
/**
 * High-Frequency Real-Time Account P&L & Copier Sync Data Streamer.
 * 
 * Pumps live account balances, floating unrealized P&L, realized P&L, open positions,
 * and TradeCopierEngine sync states from NinjaTrader 8 REST bridge (port 7890) directly
 * into TradingView Desktop (CDP port 9222).
 */

import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const LOG_FILE = path.join(__dirname, 'streamer.log');

const NT8_PORT = Number(process.env.NT8_PORT) || 7890;
const NT8_HOST = process.env.NT8_HOST || 'localhost';
const NT8_TOKEN = process.env.NT8_MCP_TOKEN || 'd0b837223cab4653';
const TV_CDP_PORT = Number(process.env.TV_CDP_PORT) || 9222;
const TV_CDP_HOST = process.env.TV_CDP_HOST || '127.0.0.1';
const POLL_INTERVAL_MS = Number(process.env.POLL_INTERVAL_MS) || 250; // 4x per second

function log(msg) {
  const line = `[${new Date().toISOString()}] ${msg}\n`;
  try { fs.appendFileSync(LOG_FILE, line); } catch {}
}

export class PnlStreamer {
  constructor() {
    this.ws = null;
    this.msgId = 1;
    this.lastStateHash = '';
    this.isRunning = false;
    this.lastSuccessfulTick = 0;
    this.isConnecting = false;
  }

  async fetchNt8(path) {
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
            try {
              resolve(JSON.parse(data));
            } catch (e) {
              reject(e);
            }
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

  async ensureCdpConnection() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      return this.ws;
    }
    if (this.isConnecting) {
      throw new Error('Connection in progress');
    }

    this.isConnecting = true;
    try {
      const targetRes = await fetch(`http://${TV_CDP_HOST}:${TV_CDP_PORT}/json`);
      const targets = await targetRes.json();
      const chart = targets.find(t => t.type === 'page' && t.url.includes('tradingview.com/chart'))
                 || targets.find(t => t.type === 'page');

      if (!chart || !chart.webSocketDebuggerUrl) {
        throw new Error('No TradingView chart target found');
      }

      if (this.ws) {
        try { this.ws.close(); } catch {}
        this.ws = null;
      }

      const ws = new WebSocket(chart.webSocketDebuggerUrl);
      await new Promise((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error('CDP WS connection timeout')), 2500);
        ws.onopen = () => { clearTimeout(timer); resolve(); };
        ws.onerror = (e) => { clearTimeout(timer); reject(e); };
      });

      ws.onclose = () => {
        if (this.ws === ws) this.ws = null;
      };
      ws.onerror = () => {
        if (this.ws === ws) this.ws = null;
      };

      this.ws = ws;
      return this.ws;
    } finally {
      this.isConnecting = false;
    }
  }

  async evaluateInTv(expression) {
    try {
      const ws = await this.ensureCdpConnection();
      if (ws && ws.readyState === WebSocket.OPEN) {
        const id = this.msgId++;
        const payload = JSON.stringify({
          id,
          method: 'Runtime.evaluate',
          params: {
            expression,
            returnByValue: true
          }
        });
        ws.send(payload);
      }
    } catch (e) {
      // Quietly ignore connection errors to TV
    }
  }

  computeFleetSummary(accounts, positions, copierSnapshot) {
    let totalLiq = 0;
    let totalRealized = 0;
    let totalUnrealized = 0;
    let activeAccountsCount = 0;

    accounts.forEach(acc => {
      const liq = Number(acc.netLiquidation || acc.cashValue) || 0;
      const rPnl = Number(acc.realizedPnL) || 0;
      const uPnl = Number(acc.unrealizedPnL) || 0;

      totalLiq += liq;
      totalRealized += rPnl;
      totalUnrealized += uPnl;

      if (liq > 0 || rPnl !== 0 || uPnl !== 0) {
        activeAccountsCount++;
      }
    });

    const posCounts = {};
    positions.forEach(p => {
      if (p.marketPosition && p.marketPosition !== 'Flat') {
        const key = `${p.marketPosition === 'Long' ? '+' : '-'}${p.quantity} ${p.instrument || ''}`.trim();
        posCounts[key] = (posCounts[key] || 0) + 1;
      }
    });

    const activePosKeys = Object.keys(posCounts);
    let activeContractsStr = 'Flat';
    if (activePosKeys.length > 0) {
      activeContractsStr = activePosKeys.map(k => `${k}${posCounts[k] > 1 ? ` (x${posCounts[k]})` : ''}`).join(', ');
    }

    return {
      accounts,
      positions,
      copierRows: copierSnapshot?.rows || [],
      copierSystem: copierSnapshot?.system || null,
      totalNetLiquidation: totalLiq,
      totalRealizedPnL: totalRealized,
      totalUnrealizedPnL: totalUnrealized,
      activeAccountsCount,
      activeContracts: activeContractsStr,
      timestamp: Date.now()
    };
  }

  async tick() {
    try {
      const [accounts, positions, copierSnapshot] = await Promise.all([
        this.fetchNt8('/api/account'),
        this.fetchNt8('/api/positions').catch(() => []),
        this.fetchNt8('/api/copier/snapshot').catch(() => ({ rows: [], system: null }))
      ]);

      this.lastSuccessfulTick = Date.now();
      const payload = this.computeFleetSummary(accounts, positions, copierSnapshot);

      const pushScript = `
        if (window.__TV_HUDS__ && typeof window.__TV_HUDS__.update === 'function') {
          window.__TV_HUDS__.update('account_pnl', ${JSON.stringify(payload)});
        }
        window.__TV_PNL_FLATTEN_HOOK = function() {
          fetch('http://${NT8_HOST}:${NT8_PORT}/api/emergency-flatten', {
            method: 'POST',
            headers: { 'Authorization': 'Bearer ${NT8_TOKEN}', 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason: 'Operator HUD Panic Flatten' })
          }).catch(console.error);
        };
      `;
      await this.evaluateInTv(pushScript);
      return payload;
    } catch (err) {
      log(`Tick error: ${err.message}`);
      return null;
    }
  }

  async start() {
    this.isRunning = true;
    log(`Streamer started (Poll: ${POLL_INTERVAL_MS}ms, NT8: ${NT8_PORT}, TV CDP: ${TV_CDP_PORT})`);
    
    while (this.isRunning) {
      try {
        await this.tick();
      } catch (err) {
        log(`Unhandled loop error: ${err.message}`);
      }
      await new Promise(r => setTimeout(r, POLL_INTERVAL_MS));
    }
  }

  stop() {
    this.isRunning = false;
    if (this.ws) {
      try { this.ws.close(); } catch {}
      this.ws = null;
    }
  }
}

// CLI Execution
if (process.argv[1] && process.argv[1].replace(/\\/g, '/').endsWith('tv_pnl_streamer.js')) {
  const args = process.argv.slice(2);
  const once = args.includes('--once') || args.includes('-1');

  const streamer = new PnlStreamer();
  if (once) {
    (async () => {
      const res = await streamer.tick();
      if (res) {
        console.log(`[OK] Pushed P&L Snapshot: Fleet NetLiq $${res.totalNetLiquidation.toLocaleString()}, Active Accounts: ${res.activeAccountsCount}, Copier Relationships: ${res.copierRows.length}`);
      } else {
        console.log('[WARN] Tick returned null (check NT8 connection)');
      }
      process.exit(0);
    })();
  } else {
    streamer.start().catch(err => {
      log(`Fatal streamer error: ${err.message}`);
      process.exit(1);
    });
  }
}
