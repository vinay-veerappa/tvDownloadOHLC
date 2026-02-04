
import { calculateDistro } from '../../web/lib/mission-control/calculators/distro';

async function runVerification() {
    console.log('--- Verifying Derived Distro Loading ---');
    try {
        const result = await calculateDistro('NQ1');

        console.log(`Global Median: ${result.globalMedianRange.toFixed(2)}`);
        console.log(`Today Daily: ${result.todayDailyRange.toFixed(2)}`);

        if (result.rows.length === 0) {
            console.error('ERROR: No rows returned. Derived data load might have failed.');
        } else {
            console.log(`Loaded ${result.rows.length} session rows.`);
            result.rows.forEach(r => {
                console.log(`- ${r.label}: Hist keys: ${Object.keys(r.history).join(', ')}`);
                // Check a sample median
                const mon = r.history['MON'];
                if (mon) {
                    console.log(`  MON Median Range: ${mon.range.toFixed(2)}`);
                }
            });
            console.log('SUCCESS: Derived data loaded correctly.');
        }

    } catch (e) {
        console.error('Verification Failed:', e);
    }
}

runVerification();
