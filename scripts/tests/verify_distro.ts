
import { calculateDistro } from '../../web/lib/mission-control/calculators/distro'; // Adjust import path as needed
import { getTickerConfig } from '../../web/config/tickers';

async function runVerification() {
    const ticker = 'NQ1'; // Default test ticker
    console.log(`Running Distro Verification for ${ticker}...`);

    try {
        const result = await calculateDistro(ticker);

        console.log('--- Distro Analysis Result ---');
        console.log(`Global Median Range (10-Day): ${result.globalMedianRange.toFixed(2)}`);
        console.log(`Today Daily Range: ${result.todayDailyRange.toFixed(2)} (${result.todayDailyRangePct.toFixed(2)}%)`);
        console.log('\nSession Rows:');

        result.rows.forEach(row => {
            console.log(`\nSession: ${row.label}`);
            if (row.today) {
                console.log(`  Today: ${row.today.range.toFixed(2)} (${row.today.pct.toFixed(2)}%)`);
            } else {
                console.log('  Today: N/A');
            }

            console.log('  History Medians:');
            Object.entries(row.history).forEach(([day, metric]) => {
                console.log(`    ${day}: ${metric.range.toFixed(2)} (${metric.pct.toFixed(2)}%) [n=${metric.count}]`);
            });
        });

    } catch (error) {
        console.error('Verification Failed:', error);
    }
}

runVerification();
