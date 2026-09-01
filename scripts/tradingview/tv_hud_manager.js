#!/usr/bin/env node
/**
 * TradingView HUD Manager Engine.
 * 
 * Manages modular Heads-Up Display (HUD) overlays inside TradingView Desktop via Chrome DevTools Protocol.
 * 
 * Usage via CLI:
 *   node tv_hud_manager.js list
 *   node tv_hud_manager.js inject financialjuice
 *   node tv_hud_manager.js remove financialjuice
 *   node tv_hud_manager.js toggle financialjuice
 *   node tv_hud_manager.js clear
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const HUDS_DIR = path.join(__dirname, 'huds');

export class TvHudManager {
  constructor(options = {}) {
    this.host = options.host || process.env.TV_CDP_HOST || '127.0.0.1';
    this.port = Number(options.port || process.env.TV_CDP_PORT) || 9222;
  }

  async getChartTarget() {
    const url = `http://${this.host}:${this.port}/json`;
    let res;
    try {
      res = await fetch(url);
    } catch (err) {
      throw new Error(`Could not connect to TradingView Desktop at ${url}. Ensure TradingView is running with remote debugging (--remote-debugging-port=${this.port}).`);
    }

    const targets = await res.json();
    const chart = targets.find(t => t.type === 'page' && t.url.includes('tradingview.com/chart'))
               || targets.find(t => t.type === 'page');

    if (!chart || !chart.webSocketDebuggerUrl) {
      throw new Error('No active TradingView chart page found in CDP targets.');
    }

    return chart;
  }

  async evaluate(expression, target = null) {
    const chart = target || await this.getChartTarget();
    const ws = new WebSocket(chart.webSocketDebuggerUrl);

    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('WebSocket connection timed out')), 5000);
      ws.onopen = () => { clearTimeout(timeout); resolve(); };
      ws.onerror = (e) => { clearTimeout(timeout); reject(e); };
    });

    let msgId = 1;
    const send = (method, params) => new Promise((resolve, reject) => {
      const id = msgId++;
      const timeout = setTimeout(() => {
        ws.removeEventListener('message', handler);
        reject(new Error(`CDP command ${method} timed out`));
      }, 10000);

      const handler = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.id === id) {
            clearTimeout(timeout);
            ws.removeEventListener('message', handler);
            if (msg.error) {
              reject(new Error(msg.error.message || JSON.stringify(msg.error)));
            } else {
              resolve(msg.result);
            }
          }
        } catch (e) {
          // ignore parse errors for other events
        }
      };

      ws.addEventListener('message', handler);
      ws.send(JSON.stringify({ id, method, params }));
    });

    try {
      const res = await send('Runtime.evaluate', {
        expression,
        returnByValue: true,
        awaitPromise: true
      });
      return res.result?.value;
    } finally {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    }
  }

  getAvailableHuds() {
    if (!fs.existsSync(HUDS_DIR)) return [];
    const files = fs.readdirSync(HUDS_DIR).filter(f => f.endsWith('.js') && f !== 'template_hud.js');
    return files.map(f => path.basename(f, '.js'));
  }

  async loadHudModule(name) {
    const filePath = path.join(HUDS_DIR, `${name}.js`);
    if (!fs.existsSync(filePath)) {
      throw new Error(`HUD module "${name}" not found in ${HUDS_DIR}. Available: ${this.getAvailableHuds().join(', ')}`);
    }
    const moduleUrl = `file://${filePath.replace(/\\/g, '/')}`;
    const mod = await import(moduleUrl);
    if (!mod.hud || !mod.hud.id) {
      throw new Error(`HUD module "${name}" does not export a valid 'hud' object.`);
    }
    return mod.hud;
  }

  async getActiveHuds() {
    const script = `
      (function() {
        if (!window.__TV_HUDS__ || !window.__TV_HUDS__.registry) return [];
        return Object.keys(window.__TV_HUDS__.registry).map(id => {
          const entry = window.__TV_HUDS__.registry[id];
          const el = document.getElementById(entry.domId);
          return {
            id,
            domId: entry.domId,
            name: entry.name,
            version: entry.version,
            visible: !!(el && el.offsetParent !== null),
            minimized: !!(el && el.classList.contains('minimized')),
            opacity: el ? el.style.opacity || 'default' : null
          };
        });
      })()
    `;
    return (await this.evaluate(script)) || [];
  }

  async injectHud(name, options = {}) {
    const hudDef = await this.loadHudModule(name);
    const css = hudDef.getCss(options);
    const html = hudDef.getHtml(options);
    const initScript = hudDef.initScript || '';

    const injectionScript = `
      (function() {
        window.__TV_HUDS__ = window.__TV_HUDS__ || {
          registry: {},
          remove: function(hudId) {
            const item = window.__TV_HUDS__.registry[hudId];
            if (!item) return false;
            const el = document.getElementById(item.domId);
            if (el) el.remove();
            const style = document.getElementById(item.styleId);
            if (style) style.remove();
            delete window.__TV_HUDS__.registry[hudId];
            return true;
          },
          removeAll: function() {
            Object.keys(window.__TV_HUDS__.registry).forEach(id => window.__TV_HUDS__.remove(id));
            return true;
          }
        };

        const HUD_ID = ${JSON.stringify(hudDef.id)};
        const DOM_ID = ${JSON.stringify(hudDef.domId)};
        const STYLE_ID = ${JSON.stringify(hudDef.styleId)};

        // Remove previous instance if existing
        window.__TV_HUDS__.remove(HUD_ID);

        // Inject Stylesheet
        let styleEl = document.getElementById(STYLE_ID);
        if (!styleEl) {
          styleEl = document.createElement('style');
          styleEl.id = STYLE_ID;
          styleEl.textContent = ${JSON.stringify(css)};
          document.head.appendChild(styleEl);
        } else {
          styleEl.textContent = ${JSON.stringify(css)};
        }

        // Inject Panel Container
        const panel = document.createElement('div');
        panel.id = DOM_ID;
        panel.innerHTML = ${JSON.stringify(html)};
        document.body.appendChild(panel);

        // Run Lifecycle Initializer
        try {
          (${initScript})(panel);
        } catch (err) {
          console.error('[TV_HUD_MANAGER] Error initializing HUD ' + HUD_ID + ':', err);
        }

        // Register in window registry
        window.__TV_HUDS__.registry[HUD_ID] = {
          id: HUD_ID,
          domId: DOM_ID,
          styleId: STYLE_ID,
          name: ${JSON.stringify(hudDef.name)},
          version: ${JSON.stringify(hudDef.version)},
          injectedAt: Date.now()
        };

        return {
          success: true,
          action: 'injected',
          hudId: HUD_ID,
          domId: DOM_ID,
          name: ${JSON.stringify(hudDef.name)}
        };
      })()
    `;

    return await this.evaluate(injectionScript);
  }

  async removeHud(name) {
    const script = `
      (function() {
        const id = ${JSON.stringify(name)};
        if (window.__TV_HUDS__ && typeof window.__TV_HUDS__.remove === 'function') {
          const res = window.__TV_HUDS__.remove(id);
          return { success: true, removed: res, hudId: id };
        }
        // Fallback search by ID / common prefixes
        const candidates = [id, 'ws-' + id + '-panel', 'ws-fj-panel'];
        for (const cid of candidates) {
          const el = document.getElementById(cid);
          if (el) { el.remove(); return { success: true, removed: true, hudId: id }; }
        }
        return { success: true, removed: false, hudId: id };
      })()
    `;
    return await this.evaluate(script);
  }

  async removeAllHuds() {
    const script = `
      (function() {
        let count = 0;
        if (window.__TV_HUDS__ && typeof window.__TV_HUDS__.removeAll === 'function') {
          count = Object.keys(window.__TV_HUDS__.registry).length;
          window.__TV_HUDS__.removeAll();
        }
        // Also cleanup any orphaned ws-*-panel elements
        const orphans = document.querySelectorAll('[id^="ws-"][id$="-panel"]');
        orphans.forEach(el => { el.remove(); count++; });
        const styles = document.querySelectorAll('[id^="ws-"][id$="-style"]');
        styles.forEach(s => s.remove());
        return { success: true, removedCount: count };
      })()
    `;
    return await this.evaluate(script);
  }

  async toggleHud(name, options = {}) {
    const active = await this.getActiveHuds();
    const isCurrentlyActive = active.some(h => h.id === name || h.domId === `ws-${name}-panel`);
    if (isCurrentlyActive) {
      const rem = await this.removeHud(name);
      return { success: true, action: 'removed', hudId: name };
    } else {
      return await this.injectHud(name, options);
    }
  }
}

// CLI Execution
if (process.argv[1] && process.argv[1].replace(/\\/g, '/').endsWith('tv_hud_manager.js')) {
  const args = process.argv.slice(2);
  const command = args[0] || 'list';
  const hudName = args[1] || 'financialjuice';

  const manager = new TvHudManager();

  (async () => {
    try {
      switch (command.toLowerCase()) {
        case 'list': {
          const available = manager.getAvailableHuds();
          console.log('\n--- TradingView HUD Catalog ---');
          console.log('Available Modules:');
          for (const h of available) {
            const mod = await manager.loadHudModule(h);
            console.log(`  * ${h.padEnd(16)} - ${mod.name} (v${mod.version})`);
          }
          try {
            const active = await manager.getActiveHuds();
            console.log('\nCurrently Active in TradingView Desktop:');
            if (active.length === 0) {
              console.log('  (No active HUDs)');
            } else {
              active.forEach(a => {
                console.log(`  * [ACTIVE] ${a.id} (${a.name}) - Visible: ${a.visible}, Minimized: ${a.minimized}`);
              });
            }
          } catch (e) {
            console.log(`\nNote: TradingView not connected (${e.message})`);
          }
          console.log('');
          break;
        }

        case 'inject': {
          console.log(`Injecting HUD "${hudName}" into TradingView Desktop...`);
          const res = await manager.injectHud(hudName);
          console.log('Result:', res);
          break;
        }

        case 'remove': {
          console.log(`Removing HUD "${hudName}" from TradingView Desktop...`);
          const res = await manager.removeHud(hudName);
          console.log('Result:', res);
          break;
        }

        case 'toggle': {
          console.log(`Toggling HUD "${hudName}" in TradingView Desktop...`);
          const res = await manager.toggleHud(hudName);
          console.log('Result:', res);
          break;
        }

        case 'clear':
        case 'remove-all': {
          console.log('Clearing all HUD overlays from TradingView Desktop...');
          const res = await manager.removeAllHuds();
          console.log('Result:', res);
          break;
        }

        default: {
          console.log(`Unknown command: "${command}". Available commands: list, inject, remove, toggle, clear.`);
        }
      }
    } catch (err) {
      console.error('[ERR]', err.message);
      process.exit(1);
    }
  })();
}
