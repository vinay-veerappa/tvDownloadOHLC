/**
 * Frontend Resampling Performance Benchmark
 * 
 * Run with: npx tsx web/lib/resampling.bench.ts
 * Or in browser console after importing
 */

import { resampleOHLC, parseTimeframeToSeconds, canResample } from './resampling';

interface OHLCData {
    time: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

function generateTestData(count: number): OHLCData[] {
    const data: OHLCData[] = [];
    let time = 1700000000; // Fixed start timestamp
    let price = 5000;

    for (let i = 0; i < count; i++) {
        // Random walk for realistic price movement
        price += (Math.random() - 0.5) * 2;
        const high = price + Math.random() * 1;
        const low = price - Math.random() * 1;

        data.push({
            time,
            open: price,
            high,
            low,
            close: price + (Math.random() - 0.5) * 0.5,
            volume: Math.floor(Math.random() * 1000) + 100
        });

        time += 60; // 1-minute bars
    }

    return data;
}

function benchmark(name: string, fn: () => void, iterations: number = 10): void {
    // Warmup
    for (let i = 0; i < 3; i++) {
        fn();
    }

    // Timed runs
    const times: number[] = [];
    for (let i = 0; i < iterations; i++) {
        const start = performance.now();
        fn();
        times.push(performance.now() - start);
    }

    const avg = times.reduce((a, b) => a + b, 0) / times.length;
    const min = Math.min(...times);
    const max = Math.max(...times);

    console.log(`${name}:`);
    console.log(`  Average: ${avg.toFixed(2)}ms`);
    console.log(`  Min: ${min.toFixed(2)}ms, Max: ${max.toFixed(2)}ms`);
}

function runBenchmarks(): void {
    console.log('='.repeat(60));
    console.log('Frontend Resampling Benchmarks');
    console.log('='.repeat(60));
    console.log();

    // Test different data sizes
    const sizes = [10000, 50000, 100000, 500000];

    for (const size of sizes) {
        console.log(`\nGenerating ${size.toLocaleString()} 1m bars...`);
        const data = generateTestData(size);
        console.log(`Generated ${data.length.toLocaleString()} bars`);

        // Resample to various timeframes
        const timeframes = ['5', '15', '60', '240'];

        for (const tf of timeframes) {
            if (canResample('1', tf)) {
                let result: OHLCData[] = [];
                benchmark(`Resample 1m -> ${tf}m (${size.toLocaleString()} bars)`, () => {
                    result = resampleOHLC(data, '1', tf);
                }, 5);
                console.log(`  Output: ${result.length.toLocaleString()} bars`);
            }
        }
    }

    console.log('\n' + '='.repeat(60));
    console.log('Benchmark complete');
}

// Run if executed directly
if (typeof require !== 'undefined' && require.main === module) {
    runBenchmarks();
}

// Export for use in browser console
export { runBenchmarks, generateTestData, benchmark };
