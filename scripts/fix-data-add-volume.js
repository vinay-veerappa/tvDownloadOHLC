const fs = require('fs');
const path = require('path');

const dataDir = path.join(__dirname, '../web/public/data');

function addVolumeToFiles(dir) {
    const files = fs.readdirSync(dir);

    files.forEach(file => {
        const fullPath = path.join(dir, file);
        const stat = fs.statSync(fullPath);

        if (stat.isDirectory()) {
            addVolumeToFiles(fullPath);
        } else if (file.endsWith('.json') && !file.includes('meta.json')) {
            try {
                const content = fs.readFileSync(fullPath, 'utf8');
                let data = JSON.parse(content);

                let modified = false;
                if (Array.isArray(data)) {
                    data = data.map(bar => {
                        if (bar.volume === undefined) {
                            modified = true;
                            // Generate pseudo-random volume based on price movement
                            const range = Math.abs(bar.high - bar.low);
                            const baseVol = 100;
                            const vol = Math.floor(baseVol + (range * 10) + (Math.random() * 50));
                            return { ...bar, volume: vol };
                        }
                        return bar;
                    });
                }

                if (modified) {
                    fs.writeFileSync(fullPath, JSON.stringify(data));
                    console.log(`Updated ${file}`);
                }
            } catch (err) {
                console.error(`Error processing ${file}:`, err);
            }
        }
    });
}

console.log('Starting volume backfill...');
if (fs.existsSync(dataDir)) {
    addVolumeToFiles(dataDir);
    console.log('Done!');
} else {
    console.error('Data directory not found:', dataDir);
}
