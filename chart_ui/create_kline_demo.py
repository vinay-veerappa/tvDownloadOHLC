# Create KLineChart Demo
html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Demo: KLineChart (FREE)</title>
    <script src="https://cdn.jsdelivr.net/npm/klinecharts/dist/klinecharts.min.js"></script>
    <style>
        body { margin: 0; background: #1a1a1a; color: #fff; font-family: sans-serif; }
        #toolbar { background: #2a2a2a; padding: 10px; display: flex; gap: 10px; flex-wrap: wrap; }
        button { background: #3a3a3a; color: #fff; border: 1px solid #555; padding: 8px 12px; cursor: pointer; border-radius: 4px; font-size: 13px; }
        button:hover { background: #4a4a4a; }
        .info { padding: 10px; font-size: 12px; color: #888; flex-grow: 1; text-align: right; }
        #chart { width: 100%; height: calc(100vh - 60px); }
    </style>
</head>
<body>
    <div id="toolbar">
        <button onclick="loadData()">📊 Load ES Data</button>
        <button onclick="chart.createShape('segment')">📏 Line</button>
        <button onclick="chart.createShape('ray')">➡️ Ray</button>
        <button onclick="chart.createShape('rect')">▭ Rectangle</button>
        <button onclick="chart.createShape('circle')">○ Circle</button>
        <button onclick="chart.createShape('fibonacciRetracement')">📐 Fibonacci</button>
        <button onclick="addMA()">+ MA</button>
        <button onclick="chart.removeOverlay()">🗑 Clear</button>
        <div class="info">✅ FREE (MIT License) | Drawing Tools Built-in</div>
    </div>
    <div id="chart"></div>
    <script>
        const chart = klinecharts.init('chart');
        
        async function loadData() {
            try {
                const response = await fetch('http://localhost:8000/api/ohlc/1h?limit=5000');
                const result = await response.json();
                
                const data = result.data.map(d => ({
                    timestamp: d.time * 1000,
                    open: d.open,
                    high: d.high,
                    low: d.low,
                    close: d.close,
                    volume: 1000
                }));
                
                chart.applyNewData(data);
                console.log('Loaded', data.length, 'bars');
            } catch (e) {
                alert('Error: ' + e.message);
            }
        }
        
        function addMA() {
            chart.createIndicator('MA', false, { id: 'candle_pane' });
        }
        
        loadData();
    </script>
</body>
</html>"""

with open('demo_klinechart.html', 'w', encoding='utf-8') as f:
    f.write(html_content)
print("Created demo_klinechart.html")
