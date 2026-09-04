#!/usr/bin/env node
/**
 * Standalone FinancialJuice Squawk & News Widget Server.
 *
 * Serves the shared financialjuice HUD module as an independent floating
 * desktop widget (Edge/Chrome App Mode on port 8636) — same pattern as
 * pnl_widget_server.js, but self-contained: no NT8 bridge, no CDP pump.
 *
 * The Econ Calendar iframe is served through a same-origin reverse proxy
 * (/fjcal/...) so we can inject CSS into it: brighten the text for the dark
 * theme and stretch the embed's hard-coded 340px container to full width.
 * Everything else (headlines, voice, tickstrike) stays a direct iframe.
 */

import http from 'node:http';
import https from 'node:https';
import { hud } from './huds/financialjuice.js';

const PORT = Number(process.env.FJ_WIDGET_PORT) || 8636;
const WIDGET_WIDTH = Number(process.env.FJ_WIDGET_WIDTH) || 520;
const WIDGET_HEIGHT = Number(process.env.FJ_WIDGET_HEIGHT) || 680;
const UPSTREAM = 'feed.financialjuice.com';

const css = hud.getCss({ top: 0, right: 0, width: `${WIDGET_WIDTH}px`, height: `${WIDGET_HEIGHT}px`, opacity: 0.98 });
const html = hud.getHtml({ defaultTab: 'headlines' })
  .replace('ws-fj-iframe ecocal-fit', 'ws-fj-iframe ecocal-full')
  .replace(/https:\/\/feed\.financialjuice\.com\/widgets\/ecocal\.aspx/g, '/fjcal/widgets/ecocal.aspx');
const initScript = hud.initScript;

// CSS injected INTO the proxied calendar page (same-origin via /fjcal proxy):
// brighten text for the dark theme + stretch the embed to the iframe width.
const CAL_OVERRIDE_CSS = `
  <style id="ws-fj-cal-override">
    body { background: #131722 !important; color: #c9cfdb !important; }
    #comingUp, #comingUp-parent, #my-cal-data, .calendar-header,
    #calendar, #calendar-history, #calendar-filters-container {
      width: 100% !important;
      max-width: 100% !important;
      background-color: #131722 !important;
    }
    .div-table-col, .div-table-colspan, .event-title, .event-title a,
    .event-time, .event-actual, .event-forcast, .event-previous,
    .event-strong-data, .event-weak-data, .cal-event-date {
      color: #c9cfdb !important;
    }
    .event-title a:hover { color: #f0f3fa !important; }
    .calendar-header { background-color: #1e222d !important; }
    .calendar-header .div-table-col { color: #f0f3fa !important; font-weight: 700; }
    .event-flag { width: 24px !important; }
    .event-flag img, .event-flag svg { max-width: 100%; }
    .event-history a, .event-history i { color: #5d606b !important; }
  </style>`;

const pageHtml = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>FinancialJuice Squawk</title>
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
    #ws-fj-panel {
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
  <div id="ws-fj-panel">
    ${html}
  </div>
  <script>
    const panel = document.getElementById('ws-fj-panel');
    (${initScript})(panel);
  </script>
</body>
</html>`;

// ---- Same-origin reverse proxy for the Econ Calendar ----
// Everything that is not one of our own routes is forwarded to the upstream
// embed host with the same path, so relative assets/axd/signalr resolve.

function proxyUpstream(req, res) {
  const upstreamPath = req.url.replace(/^\/fjcal/, '') || '/';
  const options = {
    hostname: UPSTREAM,
    port: 443,
    path: upstreamPath,
    method: req.method,
    headers: {
      ...req.headers,
      host: UPSTREAM,
      referer: `https://${UPSTREAM}/`,
      origin: `https://${UPSTREAM}`,
      'accept-encoding': 'identity'
    }
  };

  const up = https.request(options, (upRes) => {
    const contentType = upRes.headers['content-type'] || '';
    const isHtml = contentType.includes('text/html');

    if (!isHtml) {
      res.writeHead(upRes.statusCode, upRes.headers);
      upRes.pipe(res);
      return;
    }

    // HTML: buffer, inject the override stylesheet, fix the postback target
    let body = '';
    upRes.setEncoding('utf8');
    upRes.on('data', (chunk) => { body += chunk; });
    upRes.on('end', () => {
      let injected = body
        .replace(/<head([^>]*)>/i, `<head$1>${CAL_OVERRIDE_CSS}`)
        .replace(/action="\.\/ecocal\.aspx"/gi, 'action="/fjcal/widgets/ecocal.aspx"');
      const headers = { ...upRes.headers };
      delete headers['content-length'];
      delete headers['content-encoding'];
      delete headers['content-security-policy'];
      delete headers['x-frame-options'];
      res.writeHead(upRes.statusCode, headers);
      res.end(injected);
    });
  });

  up.on('error', (err) => {
    res.writeHead(502, { 'Content-Type': 'text/plain' });
    res.end(`Proxy error: ${err.message}`);
  });

  req.pipe(up);
}

const server = http.createServer((req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  if (req.url === '/' || req.url.startsWith('/fj-widget') || req.url.startsWith('/index')) {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    res.end(pageHtml);
  } else if (req.url === '/health') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok', widget: 'financialjuice', port: PORT }));
  } else {
    proxyUpstream(req, res);
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log(`[+] FinancialJuice Widget running at http://127.0.0.1:${PORT}/fj-widget`);
  console.log(`[+] Econ Calendar proxied same-origin at http://127.0.0.1:${PORT}/fjcal/widgets/ecocal.aspx`);
});