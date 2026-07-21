#if TESTING
using System;
using System.Collections.Generic;

namespace NinjaTrader.NinjaScript.AddOns
{
    public class EconomicNewsEvent
    {
        public DateTime EventTimeUtc { get; set; }
        public string Title { get; set; } = "CPI Release";
        public string Currency { get; set; } = "USD";
        public string Impact { get; set; } = "High";
    }

    public class PropFirmProfile
    {
        public string Name { get; set; } = "Apex Trader Funding";
        public List<string> AllowedInstruments { get; set; } = new List<string> { "NQ", "MNQ", "ES", "MES", "YM", "MYM", "CL", "MCL", "GC", "MGC", "RTY", "M2K" };
        public List<string> BlockedInstruments { get; set; } = new List<string> { "ZB", "ZN", "6E", "6B" };
    }

    public class PropFirmProtectionConfig
    {
        public bool EnableNewsShield { get; set; } = true;
        public int NewsBufferMinutesBefore { get; set; } = 2;
        public int NewsBufferMinutesAfter { get; set; } = 2;
        public string NewsCalendarApiUrl { get; set; } = "https://napi.forexfactory.com/calendar.json";
        public bool EnableProfitTargetLock { get; set; } = true;
        public double EvaluationTargetProfit { get; set; } = 3000.0;
        public bool EnablePeakEquityProtection { get; set; } = true;
        public double MaxPeakGivebackPct { get; set; } = 0.30;
        public bool EnableConsistencyCap { get; set; } = true;
        public double MaxDailyProfitPctOfTarget { get; set; } = 0.35;
        public bool EnableAutoDayFiller { get; set; } = false;
    }

    public class PropFirmProtectionSuite
    {
        private readonly List<EconomicNewsEvent> _newsEvents = new List<EconomicNewsEvent>();

        public void AddTestNewsEvent(EconomicNewsEvent ev)
        {
            _newsEvents.Add(ev);
        }

        public bool IsInNewsWindow(DateTime nowUtc, int bufferMinutesBefore, int bufferMinutesAfter)
        {
            foreach (var ev in _newsEvents)
            {
                if (ev.Impact != "High") continue;
                var startWindow = ev.EventTimeUtc.AddMinutes(-bufferMinutesBefore);
                var endWindow = ev.EventTimeUtc.AddMinutes(bufferMinutesAfter);
                if (nowUtc >= startWindow && nowUtc <= endWindow)
                {
                    return true;
                }
            }
            return false;
        }

        public bool EvaluateProfitTargetLock(double currentRealizedPnL, PropFirmProtectionConfig config)
        {
            if (!config.EnableProfitTargetLock) return false;
            return currentRealizedPnL >= config.EvaluationTargetProfit;
        }

        public bool EvaluatePeakEquityGiveback(double peakOpenGain, double currentUnrealized, PropFirmProtectionConfig config)
        {
            if (!config.EnablePeakEquityProtection || peakOpenGain <= 0) return false;
            double giveback = peakOpenGain - currentUnrealized;
            double givebackPct = giveback / peakOpenGain;
            return givebackPct >= config.MaxPeakGivebackPct;
        }
    }
}
#endif
