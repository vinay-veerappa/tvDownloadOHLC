
import { calculateMissionMatrix } from './web/lib/mission-control/calculators/mission-matrix.ts';

async function test() {
    try {
        const result = await calculateMissionMatrix('NQ1');
        const { context, matrix, total_samples, target_phase_name } = result;

        console.log(`--- ${target_phase_name} (N=${total_samples}) ---`);
        console.log(`- Asia Status: ${context.asia.status} (Streak: ${context.asia.streak}d, Group: ${context.status_streaks?.Asia.group}d)`);
        console.log(`- London Status: ${context.london.status} (Streak: ${context.london.streak}d, Group: ${context.status_streaks?.London.group}d)`);
        console.log(`- NY1 Status: ${context.ny1.status} (Streak: ${context.ny1.streak}d, Group: ${context.status_streaks?.NY1.group}d)`);

        console.log('--- Top Outcomes ---');
        const sorted = [...matrix].sort((a, b) => b.probability - a.probability);
        sorted.forEach((m, idx) => {
            console.log(`- ${m.scenario}: ${m.probability.toFixed(1)}% (LOD: ${m.lod_time_mode}, HOD: ${m.hod_time_mode})`);
            console.log(`  - Hit Rates: P12H=${m.p12h_hit_rate.toFixed(1)}% P12L=${m.p12l_hit_rate.toFixed(1)}% AsiaMid=${m.asia_mid_hit_rate.toFixed(1)}% LonMid=${m.london_mid_hit_rate.toFixed(1)}% MdtOp=${m.midnight_open_hit_rate.toFixed(1)}% 0730Op=${m.open_0730_hit_rate.toFixed(1)}%`);
            console.log(`  - Pcts: LOD=${m.lod_pct_display} HOD=${m.hod_pct_display}`);
        });

    } catch (e) {
        console.error('Test Failed:', e);
    }
}
test();
