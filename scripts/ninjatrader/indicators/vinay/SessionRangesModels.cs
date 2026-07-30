// ═══════════════════════════════════════════════════════════════════════════
// SessionRangesModels.cs — RangeSpec, RangeState, ExcursionHistory
//
// C# port of PineScript RangeSessionLib.pine (RangeSpec + RangeState UDTs).
// Parity contract: docs/indicators/DailyNYLevels/CORE_ENGINE_SPEC.md
//
// These are plain-old-data classes shared by the SessionRanges indicator
// and any consuming strategy/engine. No NT8 dependencies — pure C#.
// ═══════════════════════════════════════════════════════════════════════════

using System;
using System.Collections.Generic;

namespace NinjaTrader.NinjaScript.Indicators.Vinay
{
    // ════════════════════════════════════════════════════════════════════════
    // RangeSpec — static configuration for one session range
    // Mirrors PineScript RangeSessionLib.RangeSpec
    // ════════════════════════════════════════════════════════════════════════
    public class RangeSpec
    {
        public string Name { get; set; }          // "IB", "Asia", "London OR", etc.
        public string PresetGroup { get; set; }   // "ICT Core", "Overnight", "Pre-Market", etc.
        public int OrStartMin { get; set; }       // minutes-of-day (e.g., 570 = 09:30)
        public int OrEndMin { get; set; }         // minutes-of-day (e.g., 600 = 10:00)
        public int CutoffMin { get; set; }        // minutes-of-day (e.g., 960 = 16:00)
        public string Days { get; set; }          // "23456" = Mon-Fri (1=Sun..7=Sat)
        public bool IsTransfer { get; set; }      // 0300 Transfer special logic
        public double EvTargetPct { get; set; }   // 0.30 = 0.30% EV target
        public bool IsEnabled { get; set; }       // user can toggle individual ranges

        // Visual config (defaults set by indicator, overridable per range)
        public int FillOpacity { get; set; }      // 0=solid, 100=transparent
        public bool ShowLabel { get; set; }
        public int LineWidth { get; set; }

        // Computed
        public bool CrossesMidnight => OrEndMin < OrStartMin || CutoffMin < OrEndMin;

        public RangeSpec Clone()
        {
            return new RangeSpec
            {
                Name = Name,
                PresetGroup = PresetGroup,
                OrStartMin = OrStartMin,
                OrEndMin = OrEndMin,
                CutoffMin = CutoffMin,
                Days = Days,
                IsTransfer = IsTransfer,
                EvTargetPct = EvTargetPct,
                IsEnabled = IsEnabled,
                FillOpacity = FillOpacity,
                ShowLabel = ShowLabel,
                LineWidth = LineWidth,
            };
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    // RangeState — mutable per-day state for one range
    // Mirrors PineScript RangeSessionLib.RangeState
    // ════════════════════════════════════════════════════════════════════════
    public class RangeState
    {
        public RangeSpec Spec { get; set; }

        // OR values
        public double SessionOpen;
        public double OrHigh;
        public double OrLow;
        public double OrLastClose;
        public bool OrBuilding;
        public bool OrComplete;
        public int OrStartBarIndex;

        // References
        public double BullRef;     // = OrHigh when complete
        public double BearRef;     // = OrLow when complete
        public double OrMid;       // = (OrHigh + OrLow) / 2
        public bool RefSet;

        // MFE (price % per ADR-002)
        public double DailyBullMfe;
        public double DailyBearMfe;
        public int DailyBullPeakMin;   // minutes since OR start
        public int DailyBearPeakMin;

        // MAE absolute
        public double DailyMaeBullAbs;
        public double DailyMaeBearAbs;

        // MAE pullback
        public double DailyMaeBullPb;
        public double DailyMaeBearPb;

        // Breakout-post MFE/MAE
        public double DailyBoMfeBull;
        public double DailyBoMfeBear;
        public double DailyBoMaeBull;
        public double DailyBoMaeBear;

        // Mid-hit tracking
        public bool MidHitBull;
        public bool MidHitBear;

        // Entry triggers (for fakeout)
        public bool EntryTriggeredBull;
        public bool EntryTriggeredBear;

        // Cutoff
        public double CloseAtCutoff;
        public bool IsCommitted;

        // Signal
        public int SigSide;            // 0=None, 1=Bull, -1=Bear
        public int SigOutcome;         // 0=Pending, 1=Full, -1=Failed
        public bool IsTerminated;
        public int SigBreakoutSide;    // 0=None, 1=Bull, -1=Bear
        public double SigBreakoutPx;
        public int SigBreakoutBarIndex;
        public double SigTargetPx;
        public double SigInvalidPx;

        // Session transition tracking
        public bool PrevInOr;
        public bool PrevInData;

        // Timestamps
        public DateTime BreakoutTime;  // ET timestamp of breakout bar
        public DateTime SessionDate;   // trade date (cutoff date for cross-midnight)

        // ═══ Convenience properties ═══
        public double Range => OrHigh - OrLow;
        public double RangePct => OrLow > 0 ? (Range / OrLow) * 100.0 : 0;
        public bool IsForming => OrBuilding;

        // ═══ Factory ═══
        public static RangeState Create(RangeSpec spec)
        {
            return new RangeState
            {
                Spec = spec,
                OrBuilding = false,
                OrComplete = false,
                RefSet = false,
                SigSide = 0,
                SigOutcome = 0,
                IsTerminated = false,
                SigBreakoutSide = 0,
            };
        }

        // ═══ Reset for new day (parity: CORE_ENGINE_SPEC §5 "Reset") ═══
        public void Reset()
        {
            SessionOpen = 0;
            OrHigh = 0;
            OrLow = 0;
            OrLastClose = 0;
            OrBuilding = false;
            OrComplete = false;
            OrStartBarIndex = 0;
            BullRef = 0;
            BearRef = 0;
            OrMid = 0;
            RefSet = false;

            DailyBullMfe = 0;
            DailyBearMfe = 0;
            DailyBullPeakMin = 0;
            DailyBearPeakMin = 0;
            DailyMaeBullAbs = 0;
            DailyMaeBearAbs = 0;
            DailyMaeBullPb = 0;
            DailyMaeBearPb = 0;
            DailyBoMfeBull = 0;
            DailyBoMfeBear = 0;
            DailyBoMaeBull = 0;
            DailyBoMaeBear = 0;

            MidHitBull = false;
            MidHitBear = false;
            EntryTriggeredBull = false;
            EntryTriggeredBear = false;
            CloseAtCutoff = 0;
            IsCommitted = false;

            SigSide = 0;
            SigOutcome = 0;
            IsTerminated = false;
            SigBreakoutSide = 0;
            SigBreakoutPx = 0;
            SigBreakoutBarIndex = 0;
            SigTargetPx = 0;
            SigInvalidPx = 0;

            PrevInOr = false;
            PrevInData = false;
            BreakoutTime = DateTime.MinValue;
            SessionDate = DateTime.MinValue;
        }

        // ═══ Finalize OR (called when OR window ends) ═══
        public void FinalizeOr()
        {
            if (!OrBuilding) return;
            OrBuilding = false;
            OrComplete = true;
            OrMid = (OrHigh + OrLow) / 2.0;
            BullRef = OrHigh;
            BearRef = OrLow;
            RefSet = true;
        }

        // ═══ Update OR during building phase ═══
        public void UpdateOr(double high, double low, double open, double close, int barIndex)
        {
            if (!OrBuilding)
            {
                OrHigh = high;
                OrLow = low;
                SessionOpen = open;
                OrStartBarIndex = barIndex;
                OrBuilding = true;
            }
            else
            {
                if (high > OrHigh) OrHigh = high;
                if (low < OrLow) OrLow = low;
            }
            OrLastClose = close;
        }

        // ═══ Check breakout (called during data window, after OR complete) ═══
        public void CheckBreakout(double high, double low, int barIndex, DateTime barTime)
        {
            if (!OrComplete || SigBreakoutSide != 0) return;

            if (high > OrHigh)
            {
                SigBreakoutSide = 1;   // Bull breakout
                SigBreakoutPx = OrHigh;
                SigBreakoutBarIndex = barIndex;
                BreakoutTime = barTime;
            }
            else if (low < OrLow)
            {
                SigBreakoutSide = -1;  // Bear breakout
                SigBreakoutPx = OrLow;
                SigBreakoutBarIndex = barIndex;
                BreakoutTime = barTime;
            }
        }

        // ═══ MFE update (price % per ADR-002, CORE_ENGINE_SPEC §6) ═══
        public void UpdateMfe(double barHigh, double barLow)
        {
            if (!OrComplete) return;

            // Bull MFE: how far above OrHigh, as % of OrHigh
            if (OrHigh > 0)
            {
                double bullExc = Math.Max(0, ((barHigh - OrHigh) / OrHigh) * 100.0);
                if (bullExc > DailyBullMfe)
                {
                    DailyBullMfe = bullExc;
                    // Peak minute would be set by caller (needs bar time)
                }
            }

            // Bear MFE: how far below OrLow, as % of OrLow
            if (OrLow > 0)
            {
                double bearExc = Math.Max(0, ((OrLow - barLow) / OrLow) * 100.0);
                if (bearExc > DailyBearMfe)
                {
                    DailyBearMfe = bearExc;
                }
            }
        }

        // ═══ Mid-hit tracking (CORE_ENGINE_SPEC §8) ═══
        public void UpdateMidHit(double barHigh, double barLow)
        {
            if (!OrComplete) return;
            if (!MidHitBull && barHigh >= OrMid) MidHitBull = true;
            if (!MidHitBear && barLow <= OrMid) MidHitBear = true;
        }
    }

    // ════════════════════════════════════════════════════════════════════════
    // ExcursionHistory — accumulated statistics across days
    // Mirrors PineScript StatsLib.ExcursionHistory
    // ════════════════════════════════════════════════════════════════════════
    public class ExcursionHistory
    {
        public List<double> BullMfe { get; set; } = new List<double>();
        public List<double> BearMfe { get; set; } = new List<double>();
        public List<double> BullMaeAbs { get; set; } = new List<double>();
        public List<double> BearMaeAbs { get; set; } = new List<double>();
        public List<double> BullMaePb { get; set; } = new List<double>();
        public List<double> BearMaePb { get; set; } = new List<double>();
        public List<int> BullPeakMins { get; set; } = new List<int>();
        public List<int> BearPeakMins { get; set; } = new List<int>();
        public List<bool> MidHitBullFlags { get; set; } = new List<bool>();
        public List<bool> MidHitBearFlags { get; set; } = new List<bool>();
        public List<bool> EvWinBull { get; set; } = new List<bool>();
        public List<bool> EvWinBear { get; set; } = new List<bool>();
        public List<double> RMultipleBull { get; set; } = new List<double>();
        public List<double> RMultipleBear { get; set; } = new List<double>();
        public List<int> DowValues { get; set; } = new List<int>();
        public List<bool> FakeoutBull { get; set; } = new List<bool>();
        public List<bool> FakeoutBear { get; set; } = new List<bool>();

        // ═══ Percentile (nearest-rank, CORE_ENGINE_SPEC §11) ═══
        public static double Percentile(List<double> values, double pct)
        {
            if (values == null || values.Count == 0) return 0;
            var sorted = new List<double>(values);
            sorted.Sort();
            int n = sorted.Count;
            int rank = (int)Math.Ceiling((pct / 100.0) * n) - 1;
            if (rank < 0) rank = 0;
            if (rank >= n) rank = n - 1;
            return sorted[rank];
        }

        // ═══ Append a day's results ═══
        public void AppendDay(RangeState state, int dow, bool evWinBull, bool evWinBear,
            double rMultBull, double rMultBear, bool fakeoutBull, bool fakeoutBear)
        {
            BullMfe.Add(state.DailyBullMfe);
            BearMfe.Add(state.DailyBearMfe);
            BullMaeAbs.Add(state.DailyMaeBullAbs);
            BearMaeAbs.Add(state.DailyMaeBearAbs);
            BullMaePb.Add(state.DailyMaeBullPb);
            BearMaePb.Add(state.DailyMaeBearPb);
            BullPeakMins.Add(state.DailyBullPeakMin);
            BearPeakMins.Add(state.DailyBearPeakMin);
            MidHitBullFlags.Add(state.MidHitBull);
            MidHitBearFlags.Add(state.MidHitBear);
            EvWinBull.Add(evWinBull);
            EvWinBear.Add(evWinBear);
            RMultipleBull.Add(rMultBull);
            RMultipleBear.Add(rMultBear);
            DowValues.Add(dow);
            FakeoutBull.Add(fakeoutBull);
            FakeoutBear.Add(fakeoutBear);
        }
    }
}