async function check() {
  const targetRes = await fetch('http://127.0.0.1:9222/json');
  const targets = await targetRes.json();
  const chart = targets.find(t => t.type === 'page' && t.url.includes('tradingview.com/chart'));
  
  if (!chart) {
    console.log('No chart found');
    return;
  }

  const ws = new WebSocket(chart.webSocketDebuggerUrl);
  await new Promise(r => ws.onopen = r);
  
  let id = 1;
  const send = (method, params) => new Promise(resolve => {
    const curId = id++;
    const handler = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.id === curId) {
        ws.removeEventListener('message', handler);
        resolve(msg.result);
      }
    };
    ws.addEventListener('message', handler);
    ws.send(JSON.stringify({ id: curId, method, params }));
  });

  const res = await send('Runtime.evaluate', {
    expression: `({
      totalUnrealized: document.getElementById('ws-pnl-total-unrealized')?.textContent,
      totalRealized: document.getElementById('ws-pnl-total-realized')?.textContent,
      totalLiq: document.getElementById('ws-pnl-total-liq')?.textContent,
      openContracts: document.getElementById('ws-pnl-total-pos')?.textContent,
      contractsBadge: document.getElementById('ws-pnl-contracts-badge')?.textContent,
      activeTab: document.getElementById('ws-pnl-tab-active')?.textContent,
      footerTime: document.getElementById('ws-pnl-last-update')?.textContent,
      footerCount: document.getElementById('ws-pnl-acc-count')?.textContent,
      accountsCount: window.__TV_PNL_STATE__?.accounts?.length,
      firstRowText: document.querySelector('#ws-pnl-tbody tr')?.innerText?.replace(/\\t/g, ' | ')
    })`,
    returnByValue: true
  });

  console.log('TradingView Live DOM Status:');
  console.log(res.result.value);
  ws.close();
}

check().catch(console.error);
