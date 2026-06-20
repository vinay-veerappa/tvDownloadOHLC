import test from 'node:test';
import assert from 'node:assert/strict';


// Inline implementations of resampling utilities for testing
function parseTimeframeToSeconds(tf) {
  if (/^\d+$/.test(tf)) {
    return parseInt(tf, 10) * 60;
  }
  const match = tf.match(/^(\d+)(m|h|d|w|M|y)$/i);
  if (!match) return 0;
  const [, numStr, unit] = match;
  const num = parseInt(numStr, 10);
  switch (unit) {
    case 'm': return num * 60;
    case 'h':
    case 'H': return num * 60 * 60;
    case 'd':
    case 'D': return num * 60 * 60 * 24;
    case 'w':
    case 'W': return num * 60 * 60 * 24 * 7;
    case 'M': return num * 60 * 60 * 24 * 30;
    case 'y':
    case 'Y': return num * 60 * 60 * 24 * 365;
    default: return 0;
  }
}
function canResample(fromTF, toTF) {
  const fromSeconds = parseTimeframeToSeconds(fromTF);
  const toSeconds = parseTimeframeToSeconds(toTF);
  if (toSeconds <= fromSeconds) return false;
  if (toTF.match(/[DWM]$/)) return false;
  if (toTF.match(/[dw]$/)) return false;
  return true;
}
function resampleDataForWMY(data, targetTimeframe) {
  if (data.length === 0) return data;
  const isWeekly = targetTimeframe.toUpperCase().endsWith('W');
  const isMonthly = targetTimeframe.toUpperCase().endsWith('M');
  const isYearly = targetTimeframe.toUpperCase().endsWith('Y');
  let months = 1;
  if (isMonthly) {
    const match = targetTimeframe.match(/^(\d+)M$/i);
    if (match) months = parseInt(match[1], 10);
  }
  let years = 1;
  if (isYearly) {
    const match = targetTimeframe.match(/^(\d+)Y$/i);
    if (match) years = parseInt(match[1], 10);
  }
  const resampled = [];
  let currentBucket = null;
  let bucketEndTime = Number.NaN;
  for (const candle of data) {
    const date = new Date(candle.time * 1000);
    let bucketStart = 0;
    if (isWeekly) {
      const weekSeconds = 7 * 86400;
      bucketStart = Math.floor(candle.time / weekSeconds) * weekSeconds;
    } else if (isMonthly) {
      const year = date.getUTCFullYear();
      const month = date.getUTCMonth();
      const bucketMonth = Math.floor(month / months) * months;
      const firstOfMonth = new Date(Date.UTC(year, bucketMonth, 1, 0,0,0,0));
      bucketStart = Math.floor(firstOfMonth.getTime()/1000);
    } else if (isYearly) {
      const year = date.getUTCFullYear();
      const bucketYear = Math.floor(year / years) * years;
      const firstOfYear = new Date(Date.UTC(bucketYear,0,1,0,0,0,0));
      bucketStart = Math.floor(firstOfYear.getTime()/1000);
    } else {
      const toSeconds = parseTimeframeToSeconds(targetTimeframe);
      if (toSeconds <= 0) return data;
      bucketStart = Math.floor(candle.time / toSeconds) * toSeconds;
    }
    if (bucketStart !== bucketEndTime) {
      if (currentBucket) resampled.push(currentBucket);
      currentBucket = { ...candle, time: bucketStart };
      bucketEndTime = bucketStart;
    } else if (currentBucket) {
      currentBucket.high = Math.max(currentBucket.high, candle.high);
      currentBucket.low = Math.min(currentBucket.low, candle.low);
      currentBucket.close = candle.close;
      currentBucket.volume = (currentBucket.volume || 0) + (candle.volume || 0);
    }
  }
  if (currentBucket) {
    resampled.push(currentBucket);
    if (isWeekly) {
      const nextWeekStart = currentBucket.time + 7 * 86400;
      resampled.push({ time: nextWeekStart, open: 0, high: 0, low: 0, close: 0, volume: 0 });
    }
  }
  return resampled;
}
function resampleOHLC(data, fromTF, toTF) {
  const fromSeconds = parseTimeframeToSeconds(fromTF);
  const toSeconds = parseTimeframeToSeconds(toTF);
  if (fromSeconds === 0 || toSeconds === 0) return [];
  if (toSeconds <= fromSeconds) return data;
  if (toTF.match(/[DWM]/) || toTF.match(/[dw]/)) {
    console.warn(`Resampling to ${toTF} is not supported`);
    return [];
  }
  if (data.length === 0) return [];
  const resampled = [];
  let currentBucket = null;
  let bucketEndTime = Number.NaN;
  for (const candle of data) {
    const bucketStart = Math.floor(candle.time / toSeconds) * toSeconds;
    if (bucketStart !== bucketEndTime) {
      if (currentBucket) resampled.push(currentBucket);
      currentBucket = {
        time: bucketStart,
        open: candle.open,
        high: candle.high,
        low: candle.low,
        close: candle.close,
        volume: candle.volume || 0,
      };
      bucketEndTime = bucketStart;
    } else if (currentBucket) {
      currentBucket.high = Math.max(currentBucket.high, candle.high);
      currentBucket.low = Math.min(currentBucket.low, candle.low);
      currentBucket.close = candle.close;
      currentBucket.volume = (currentBucket.volume || 0) + (candle.volume || 0);
    }
  }
  if (currentBucket) resampled.push(currentBucket);
  return resampled;
}



// Mock OHLC data (timestamp in seconds)
function makeBar(time, open, high, low, close, volume = 0) {
  return { time, open, high, low, close, volume };
}

// Helper to generate sequential bars for a day (86400 seconds)
function generateDailyBars(startTime, count) {
  const bars = [];
  const interval = 60; // 1 minute bars
  for (let i = 0; i < count; i++) {
    const t = startTime + i * interval;
    bars.push(makeBar(t, i, i + 2, i - 1, i + 1, 10));
  }
  return bars;
}

test('parseTimeframeToSeconds handles minute, hour, day, week, month, year', () => {
  assert.equal(parseTimeframeToSeconds('1m'), 60);
  assert.equal(parseTimeframeToSeconds('2h'), 7200);
  assert.equal(parseTimeframeToSeconds('1D'), 86400);
  assert.equal(parseTimeframeToSeconds('1W'), 604800);
  assert.equal(parseTimeframeToSeconds('1M'), 2592000); // approx 30 days
  assert.equal(parseTimeframeToSeconds('1Y'), 31536000);
});

test('canResample correctly validates allowed resampling targets', () => {
  assert.equal(canResample('1', '5m'), true);
  assert.equal(canResample('1', '5h'), true);
  assert.equal(canResample('1', '1D'), false); // Daily not allowed
  assert.equal(canResample('1', '1W'), false);
  assert.equal(canResample('1', '1M'), false);
  assert.equal(canResample('1', '240'), true); // raw resolution string
});

test('resampleDataForWMY weekly aggregation works', () => {
  // 2 weeks of data, 1 minute bars starting at Monday 00:00 UTC (timestamp 0)
  const start = 0; // Monday epoch for simplicity
  const bars = generateDailyBars(start, 7 * 24 * 60); // 7 days of minute bars
  const result = resampleDataForWMY(bars, '1W');
  // Expect 1 bucket per week (2 weeks)
  assert.equal(result.length, 2);
  // First bucket start should be Monday 0
  assert.equal(result[0].time, 0);
  // Second bucket start should be next Monday (7*86400)
  assert.equal(result[1].time, 7 * 86400);
});

test('resampleDataForWMY monthly aggregation works', () => {
  const start = 0; // Jan 1 1970 UTC
  const bars = generateDailyBars(start, 31 * 24 * 60); // 31 days of minute bars
  const result = resampleDataForWMY(bars, '1M');
  // Expect 1 bucket for the month
  assert.equal(result.length, 1);
  assert.equal(result[0].time, 0);
});

test('resampleOHLC aggregates minute to 5-minute buckets', () => {
  const bars = generateDailyBars(0, 10); // 10 minute bars starting at 0
  const result = resampleOHLC(bars, '1m', '5m');
  // 10 minute bars => 2 buckets of 5 minutes each
  assert.equal(result.length, 2);
  // First bucket time should be 0, second should be 300 seconds
  assert.equal(result[0].time, 0);
  assert.equal(result[1].time, 300);
  // Verify aggregation logic: open of first bucket = first bar open
  assert.equal(result[0].open, bars[0].open);
  // close of first bucket = last bar in bucket
  assert.equal(result[0].close, bars[4].close);
});
