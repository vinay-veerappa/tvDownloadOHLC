import test from 'node:test';
import assert from 'node:assert/strict';

// Inline implementation of the data merger for pure Node JS test execution
function mergeDatasets(historical, live) {
    if (!historical || historical.length === 0) {
        return (live || []).map(normalizeCandle);
    }
    if (!live || live.length === 0) {
        return historical.map(normalizeCandle);
    }

    const histNormalized = historical.map(normalizeCandle);
    const liveNormalized = live.map(normalizeCandle);

    const map = new Map();
    
    for (const c of histNormalized) {
        map.set(c.time, c);
    }
    
    for (const c of liveNormalized) {
        map.set(c.time, c);
    }

    return Array.from(map.values()).sort((a, b) => a.time - b.time);
}

function normalizeCandle(c) {
    return {
        ...c,
        time: c.time > 10000000000 ? c.time / 1000 : c.time
    };
}

// --- TEST SUITE ---

test('Data Merger - Simple Merge with Gaps', () => {
    const historical = [
        { time: 1000, open: 10, high: 12, low: 9, close: 11 },
        { time: 1060, open: 11, high: 13, low: 10, close: 12 }
    ];
    const live = [
        { time: 1180, open: 12, high: 14, low: 11, close: 13 },
        { time: 1240, open: 13, high: 15, low: 12, close: 14 }
    ];

    const merged = mergeDatasets(historical, live);

    assert.equal(merged.length, 4);
    assert.equal(merged[0].time, 1000);
    assert.equal(merged[1].time, 1060);
    assert.equal(merged[2].time, 1180);
    assert.equal(merged[3].time, 1240);
});

test('Data Merger - Overlap Resolution (Live Overwrites Historical)', () => {
    const historical = [
        { time: 1000, open: 10, high: 12, low: 9, close: 11 },
        { time: 1060, open: 11, high: 13, low: 10, close: 12 } // Duplicate time, historical close is 12
    ];
    const live = [
        { time: 1060, open: 11, high: 13, low: 10, close: 99 }, // Duplicate time, live close is 99 (should win)
        { time: 1120, open: 12, high: 14, low: 11, close: 13 }
    ];

    const merged = mergeDatasets(historical, live);

    assert.equal(merged.length, 3);
    assert.equal(merged[0].time, 1000);
    assert.equal(merged[1].time, 1060);
    assert.equal(merged[1].close, 99); // Verified live override
    assert.equal(merged[2].time, 1120);
});

test('Data Merger - Normalization from Milliseconds', () => {
    const historical = [
        { time: 1700000000000, open: 10, high: 12, low: 9, close: 11 } // in ms
    ];
    const live = [
        { time: 1700000060, open: 11, high: 13, low: 10, close: 12 } // in seconds
    ];

    const merged = mergeDatasets(historical, live);

    assert.equal(merged.length, 2);
    assert.equal(merged[0].time, 1700000000); // 1700000000000 / 1000
    assert.equal(merged[1].time, 1700000060);
});

test('Data Merger - Chronological Sorting', () => {
    const historical = [
        { time: 1200, open: 10, high: 12, low: 9, close: 11 },
        { time: 1000, open: 11, high: 13, low: 10, close: 12 }
    ];
    const live = [
        { time: 1100, open: 12, high: 14, low: 11, close: 13 }
    ];

    const merged = mergeDatasets(historical, live);

    assert.equal(merged.length, 3);
    assert.equal(merged[0].time, 1000);
    assert.equal(merged[1].time, 1100);
    assert.equal(merged[2].time, 1200);
});

test('Data Merger - Empty Inputs', () => {
    const historical = [];
    const live = [
        { time: 1000, open: 10, high: 12, low: 9, close: 11 }
    ];

    const merged1 = mergeDatasets(historical, live);
    assert.equal(merged1.length, 1);
    assert.equal(merged1[0].time, 1000);

    const merged2 = mergeDatasets(live, null);
    assert.equal(merged2.length, 1);
    assert.equal(merged2[0].time, 1000);
});

test('Data Merger - Unsorted/Out of Order Inputs', () => {
    const historical = [
        { time: 1060, open: 11, close: 12 },
        { time: 1000, open: 10, close: 11 }
    ];
    const live = [
        { time: 1120, open: 13, close: 14 },
        { time: 1080, open: 12, close: 13 }
    ];

    const merged = mergeDatasets(historical, live);

    assert.equal(merged.length, 4);
    assert.equal(merged[0].time, 1000);
    assert.equal(merged[1].time, 1060);
    assert.equal(merged[2].time, 1080);
    assert.equal(merged[3].time, 1120);
});

test('Data Merger - Intra-dataset Duplicates', () => {
    const historical = [
        { time: 1000, open: 10, close: 11 },
        { time: 1000, open: 10, close: 99 } // duplicate in historical
    ];
    const live = [
        { time: 1060, open: 12, close: 13 },
        { time: 1060, open: 12, close: 88 } // duplicate in live
    ];

    const merged = mergeDatasets(historical, live);

    assert.equal(merged.length, 2);
    assert.equal(merged[0].time, 1000);
    // In our map insertion, the last one inserted wins.
    assert.equal(merged[0].close, 99);
    assert.equal(merged[1].time, 1060);
    assert.equal(merged[1].close, 88);
});

test('Data Merger - Live Data Starts Before Historical', () => {
    const historical = [
        { time: 2000, open: 10, close: 11 },
        { time: 2060, open: 11, close: 12 }
    ];
    const live = [
        { time: 1940, open: 9, close: 10 }, // starts before
        { time: 2000, open: 10, close: 99 } // overlaps
    ];

    const merged = mergeDatasets(historical, live);

    assert.equal(merged.length, 3);
    assert.equal(merged[0].time, 1940);
    assert.equal(merged[1].time, 2000);
    assert.equal(merged[1].close, 99); // Overwritten by live
    assert.equal(merged[2].time, 2060);
});

test('Data Merger - Null/Undefined/Zero properties in candles', () => {
    const historical = [
        { time: 1000, open: null, high: undefined, low: 0, close: 11 }
    ];
    const live = [
        { time: 1060, open: 12, high: 13, low: 11, close: 12, volume: 0 }
    ];

    const merged = mergeDatasets(historical, live);

    assert.equal(merged.length, 2);
    assert.equal(merged[0].time, 1000);
    assert.equal(merged[0].open, null);
    assert.equal(merged[0].low, 0);
    assert.equal(merged[1].time, 1060);
    assert.equal(merged[1].volume, 0);
});
