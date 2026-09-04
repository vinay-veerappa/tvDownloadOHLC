// =============================================================================
// IfvgCisdConfig.cs — AUTO-GENERATED. DO NOT EDIT BY HAND.
// Source of truth: configs/strategies/ifvg_cisd.yaml
// Regenerate:  python scripts/utils/gen_ifvg_cisd_config.py
// Verify:      python scripts/utils/gen_ifvg_cisd_config.py --verify
// A hand-edited value here that disagrees with the manifest is a defect.
// =============================================================================
namespace NinjaTrader.NinjaScript.Indicators.Vinay
{
    public static class IfvgCisdConfig
    {
        public const int EarliestEntryHHMM = 945;
        public const int LatestEntryHHMM = 1530;
        public const int FlattenByHHMM = 1555;
        public const bool LunchFilterEnabled = true;
        public const int LunchStartHHMM = 1130;
        public const int LunchEndHHMM = 1330;
        public const double MinRiskBps = 2d;
        public const double MaxRiskBps = 15d;
        public const string StopLossTypeName = "BpsStat";  // manifest: bps_stat
        public const double StopLossBps = 5d;
        public const double QueenTargetBps = 10d;
        public const double RunnerTargetBps = 30d;
        public const int HtfResampleMinutes = 5;
        public const int Variant = 2;  // variant2
        public const int EntryMode = 1;  // cisd_limit
        public const bool RequireDirectionalCandle = false;
        public const bool IncludeVi = true;
        public const bool StrictIfvgOnly = true;
        public const double AtrRiskMult = 1.8d;
        public const int CisdScanMaxBars = 500;
        public const int MaxTradesPerDay = 2;
        public const bool UseHtfFilter = false;
        public const int HtfEmaPeriod = 2400;
        public const bool RequireExternalSweep = false;
        public const bool EnableMidlineReclaims = true;
        public const bool EnableConfirmedReentry = true;
        public const int ReentryWindowBars = 20;
        public const int EodFlattenHHMM = 1550;
        public const double CommissionPerContract = 1.05d;
        public const int SlippageTicks = 1;

        // int projection of the stop-loss type for strategy params
        public const int StopLossTypeId = 0;  // 0=BpsStat 1=Structural 2=StructuralCappedBps 3=SkipIfOutOfBand
    }
}
