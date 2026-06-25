# Proposed Plan for Live Storage Merging and Truncation (Deferred)

This plan is stored for future review and is currently **not approved** for execution.

## Goal
Optimize the Parquet loading and live-storage fusion step in `api/features/shared/data_loader.py` by merging historical data and truncating the live storage files.

## Proposed Changes
1. **Optimize `load_parquet` merge logic** in `api/features/shared/data_loader.py` using `np.searchsorted` to split the historical dataframe and only concat/deduplicate/sort the overlapping suffix.
2. **Merge & Truncate Live Storage**: Run `scripts/maintenance/merge_and_trim_all.py` to merge the 161,000+ live bars into the historical `1m.parquet` files and trim the live storage files to keep only the last 5,000 bars.
3. **Regenerate Derived Data**: Run `scripts/derived/regenerate_derived.py` for ES1 and NQ1 to ensure the 6 months of new historical data is incorporated in the precomputed profiler and level touch caches.

## Status
Deferred by user request on 2026-06-24.
