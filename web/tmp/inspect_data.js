const http = require('http');

http.get('http://localhost:3000/api/options-live', (res) => {
  let data = '';
  res.on('data', (chunk) => data += chunk);
  res.on('end', () => {
    try {
      const json = JSON.parse(data);
      if (json.success) {
        console.log('Main Keys:', Object.keys(json.data));
        if (json.data.gexHeatmap) {
           console.log('Heatmap Data available');
        }
      }
    } catch (e) {
      console.error('Error parsing JSON:', e.message);
    }
  });
}).on('error', (e) => {
  console.error('Error fetching data:', e.message);
});
