# Strategy Engine — Handoff Addendum (v3)

**Date:** 2026-05-19  
**Predecessor:** HANDOFF_v2.md (2026-05-18)  
**Companion:** STRATEGY_ENGINE_SPEC.md  
**Status:** Production incident resolved; options loop running with patched writer

---

## Purpose

This addendum captures the production staleness incident observed on 2026-05-19, the confirmed root causes, code-level fixes, runtime actions taken, and remaining gaps against spec.

---

## 1) Incident summary

### Symptom
- Strategy engine repeatedly logged:
  - `Staleness alert! Latest GEX snapshot ...`
  - `Skipping entry scan for index silo ... GEX data stale`

### Immediate impact
- Tier-1 index variants (SPY/SPX) were blocked from entry scans during RTH.
- Engine was behaving correctly by refusing stale-data entries.

---

## 2) Confirmed root causes

### RC-1: Fallback short-circuit bug in snapshot writer
- File: `scripts/streaming/options/interval_writer.py`
- Behavior before fix:
  - `write_snapshot()` returned the direct DB result immediately.
  - If direct write failed with `False`, API fallback was not attempted.
- Result: snapshot pipeline stopped refreshing rows whenever direct path failed.

### RC-2: Event loop/client lifecycle bug in direct Prisma writes
- File: `scripts/streaming/options/interval_writer.py`
- Behavior before fix:
  - A cached async Prisma client was reused across multiple `asyncio.run()` calls.
  - In long-running loop mode, this caused `RuntimeError('Event loop is closed')` during direct writes.
- Result: intermittent/continuous direct write failures under loop runtime.

### RC-3: stale runtime process still running old code
- An older long-running options loop process continued executing pre-fix code.
- This made stale behavior persist until process restart.

---

## 3) Code changes applied

### `scripts/streaming/options/interval_writer.py`

1. **Fallback flow fixed**
- Direct DB path now returns early only on success.
- On failure/exception, code proceeds to API fallback path.

2. **Prisma client lifecycle fixed**
- Removed cross-call global cached Prisma client usage.
- `_get_prisma()` now creates a connected client for the current event loop.
- `_write_snapshot_direct()` and `_write_macro_snapshot_direct()` now disconnect in `finally`.

3. **Failure observability improved**
- Direct write failure logs now include exception repr and traceback.

---

## 4) Runtime actions taken

1. Stopped stale pre-fix loop process.
2. Restarted options loop with patched code.
3. Forced one-shot SPX/SPY refresh run to clear stale gate immediately.
4. Verified fresh SPY/SPX/QQQ/IWM snapshots in Prisma DB.
5. Verified recent strategy ticks without new staleness warnings.

---

## 5) Verification snapshot (post-fix)

- Latest index snapshots observed as fresh (seconds old) in `web/prisma/dev.db`.
- Strategy log showed continuing `tick_index` cadence and no new `Staleness alert` lines in the monitored window.
- Options loop logs now show successful direct writes for multiple symbols.

---

## 6) Spec gap review (current)

The following differences between implementation and spec are currently known and should be tracked.

1. **GEX stale threshold mismatch (High)**
- Spec text: index staleness warning threshold indicates 5 minutes for index data in parts of the spec.
- Runtime implementation in engine currently uses 900 seconds (15 minutes) in `_check_index_staleness`.
- Recommendation: pick one canonical threshold (5m or 15m), update both code and spec to match.

2. **Daily-strategy routing drift (Medium)**
- Runner currently treats `INCOME_CC` and `LONG_DTE_CREDIT` as daily-only strategy codes in addition to Wheel/Earnings.
- Confirm this is intended policy; if yes, update spec section on Tier-3 daily strategy scope.

3. **Fill metadata wording drift (Low, carried from v2)**
- Implementation applies slippage, but metadata field may still report `fill_assumption="mid"` in some paths.
- Recommendation: standardize metadata to `mid_with_slippage` where slippage is applied.

---

## 7) Handoff notes for next operator

1. Keep options loop and strategy engine as separate processes.
2. If staleness reappears:
   - Check latest `GexSnapshot` timestamps first.
   - Confirm loop process PID/start time is post-fix.
   - Check for `Event loop is closed` in options logs.
3. Prefer operational restart over in-place hot patching for long-running loops.
