// ═══════════════════════════════════════════════════════════════════════════
// SessionOpensEngine.cs — Tracks open prices at configurable session times
//
// Fills the "Session Opens" gap from IB_CONFLUENCE_INDICATOR_DESIGN.md §10a:
//   - Midnight Open (00:00 ET) — ICT Judas Swing axis
//   - 4H opens (00/04/08/12/16/20 ET) — institutional reference points
//   - London Open (02:00 EST / 03:00 EDT — DST-aware)
//   - NY Open (09:30 ET) — IB open (also from @CurrentDayOHL)
//
// This is NOT an NT8 indicator — it's a plain C# class instantiated by
// the LiquidityLevels indicator's OnBarUpdate.
// ═══════════════════════════════════════════════════════════════════════════

using System;
using System.Collections.Generic;

namespace NinjaTrader.NinjaScript.Indicators.Vinay
{
    public class SessionOpensEngine
    {
        private List<SessionOpenDef> opens;
        private Dictionary<string, double> currentOpens;
        private Dictionary<string, DateTime> openTimes;
        private Dictionary<string, bool> openSet;
        private TimeZoneInfo etZone;
        private DateTime lastDate = DateTime.MinValue;

        // Previous day's opens (for sweep target persistence)
        private Dictionary<string, double> prevDayOpens;

        public SessionOpensEngine(bool include4H = true)
        {
            opens = LiquidityLevelsCatalog.GetSessionOpens(include4H);
            currentOpens = new Dictionary<string, double>();
            openTimes = new Dictionary<string, DateTime>();
            openSet = new Dictionary<string, bool>();
            prevDayOpens = new Dictionary<string, double>();

            foreach (var o in opens)
            {
                currentOpens[o.Name] = 0;
                openTimes[o.Name] = DateTime.MinValue;
                openSet[o.Name] = false;
            }

            try
            {
                etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
            }
            catch
            {
                etZone = TimeZoneInfo.FindSystemTimeZoneById("America/New_York");
            }
        }

        // ═══ Called every bar by the host indicator ═══
        // barTimeEt = bar time in ET, openPrice = Open[0]
        public void OnBarUpdate(DateTime barTimeEt, double openPrice, int barIndex)
        {
            // Day rollover — archive previous day's opens
            if (barTimeEt.Date != lastDate)
            {
                if (lastDate != DateTime.MinValue)
                {
                    foreach (var o in opens)
                    {
                        if (openSet[o.Name] && currentOpens[o.Name] > 0)
                            prevDayOpens[o.Name] = currentOpens[o.Name];
                    }
                }

                // Reset for new day
                lastDate = barTimeEt.Date;
                foreach (var o in opens)
                {
                    currentOpens[o.Name] = 0;
                    openTimes[o.Name] = DateTime.MinValue;
                    openSet[o.Name] = false;
                }
            }

            int barMins = barTimeEt.Hour * 60 + barTimeEt.Minute;

            // Check each session open
            foreach (var o in opens)
            {
                if (!o.IsEnabled) continue;
                if (openSet[o.Name]) continue;

                int openMins = o.MinutesOfDay(barTimeEt);
                // Capture the open price on the first bar AT OR AFTER the open time
                // (within 1 minute tolerance for 1-min charts)
                if (barMins >= openMins && barMins <= openMins + 1)
                {
                    currentOpens[o.Name] = openPrice;
                    openTimes[o.Name] = barTimeEt;
                    openSet[o.Name] = true;
                }
            }
        }

        // ═══ Public accessors ═══
        public double GetOpen(string name)
        {
            return currentOpens.TryGetValue(name, out var p) ? p : 0;
        }

        public double MidnightOpen => GetOpen("MidnightOpen");
        public double LondonOpen => GetOpen("LondonOpen");
        public double NyOpen => GetOpen("NYOpen");

        public double Get4HOpen(int hour)
        {
            return GetOpen($"Open_{hour:D2}H");
        }

        public Dictionary<string, double> GetAllOpens()
        {
            var result = new Dictionary<string, double>();
            foreach (var o in opens)
            {
                if (openSet[o.Name] && currentOpens[o.Name] > 0)
                    result[o.Name] = currentOpens[o.Name];
            }
            return result;
        }

        public Dictionary<string, double> GetPrevDayOpens()
        {
            return new Dictionary<string, double>(prevDayOpens);
        }

        public DateTime GetOpenTime(string name)
        {
            return openTimes.TryGetValue(name, out var t) ? t : DateTime.MinValue;
        }

        public bool IsOpenSet(string name)
        {
            return openSet.TryGetValue(name, out var v) && v;
        }

        public List<SessionOpenDef> GetOpenDefs()
        {
            return new List<SessionOpenDef>(opens);
        }
    }
}