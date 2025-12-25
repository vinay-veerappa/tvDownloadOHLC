# Performance Optimizations

This document describes the performance optimizations implemented to improve chart responsiveness and reduce UI lag during data loading and navigation.

## VWAP Calculation Optimizations

### Web Worker Off-Thread Calculation
- **Location**: `web/lib/charts/indicators/vwap.worker.ts`, `vwap-worker-manager.ts`
- **Impact**: High
- **Description**: VWAP calculation now runs in a Web Worker, keeping the main thread responsive during scroll updates
- **Fallback**: Automatically falls back to main thread if worker fails

### Cached DateTimeFormat
- **Location**: `web/lib/charts/indicators/vwap.ts`
- **Impact**: High
- **Description**: `Intl.DateTimeFormat` instances are cached in a Map to avoid creating 15k+ objects per calculation

### Binary Search for Visible Index
- **Location**: `web/lib/charts/indicators/vwap.ts`
- **Impact**: Medium
- **Description**: O(log n) binary search replaces O(n) findIndex for locating the visible range start

### Reduced Lookback Limit
- **Location**: `web/lib/charts/indicators/vwap.ts`
- **Impact**: Medium
- **Description**: MAX_LOOKBACK reduced from 15,000 to 2,000 bars for faster anchor detection

### Debounced Scroll Updates
- **Location**: `web/hooks/use-chart.ts`
- **Impact**: Medium
- **Description**: 500ms debounce on scroll listener, with skip logic if visible range unchanged

---

## Data Loading Optimizations

### Chunk Merging with Reverse
- **Location**: `web/actions/data-actions.ts`
- **Impact**: Medium
- **Description**: O(n) array reverse instead of O(n log n) sort when merging chunks

### Removed Sanitization
- **Location**: `web/actions/data-actions.ts`
- **Impact**: Low
- **Description**: Removed sorting and deduplication since parquet data is already clean at source

---

## Chart Rendering Optimizations

### Memoized Heiken Ashi + Whitespace
- **Location**: `web/hooks/use-chart.ts`
- **Impact**: Medium
- **Description**: `useMemo` caches Heiken Ashi calculation and whitespace bar generation

### Reduced Whitespace Bars
- **Location**: `web/hooks/use-chart.ts`
- **Impact**: Low
- **Description**: Reduced from 500 to 100 whitespace bars for faster `setData` calls

### React.memo on ChartContainer
- **Location**: `web/components/chart-container.tsx`
- **Impact**: Low-Medium
- **Description**: Prevents unnecessary re-renders when parent props haven't changed

---

## Network Optimizations

### Gzip Compression
- **Location**: `web/next.config.ts`
- **Impact**: High (88% bandwidth savings)
- **Description**: `compress: true` ensures responses are gzip-compressed
- **Note**: Already enabled by default in Next.js 16 Turbopack dev server

---

## Lazy Loading (Pre-existing)

The data loading hook (`use-data-loading.ts`) already implements:
- Initial load of newest chunk only
- On-demand loading of historical chunks during scroll
- Memory limits with eviction at 500k bars

---

## Experimental Scripts

Located in `scripts/experiments/`:
- `gzip_compression_test.py` - Measures compression potential across all chunks
- `measure_api_response.py` - Measures actual server response sizes

---

## Performance Summary

| Optimization | Complexity | Impact |
|--------------|------------|--------|
| VWAP Web Worker | O(1) spawn | ⭐⭐⭐ High |
| Cached DateTimeFormat | O(1) lookup | ⭐⭐⭐ High |
| Gzip Compression | Automatic | ⭐⭐⭐ High |
| Binary Search | O(log n) | ⭐⭐ Medium |
| Debounced Scroll | 500ms | ⭐⭐ Medium |
| Memoized Heiken Ashi | useMemo | ⭐⭐ Medium |
| Chunk Reverse | O(n) | ⭐⭐ Medium |
| Reduced Lookback | 2k bars | ⭐⭐ Medium |
| React.memo | Shallow compare | ⭐ Low-Medium |
| Reduced Whitespace | 100 bars | ⭐ Low |
