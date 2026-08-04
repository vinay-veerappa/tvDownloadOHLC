// ═══════════════════════════════════════════════════════════════════════════
// SessionOpensEngine.cs — Tracks open prices at configurable session times
//
// For CME futures (NQ/MNQ/ES/MES), the trading day starts at 18:00 ET.
// Session opens (Midnight, London, RTH, 4H opens) belong to the GLOBEX day
// that began at 18:00 ET the prior evening — so we reset daily at 18:00 ET.
//
// NinjaTrader bar timestamp convention: Time[0] = bar CLOSE time.
// TradingView bar timestamp convention: timestamp = bar OPEN time.
//
// To capture the price at a target open time T:
//   → Find the first bar whose close time is AFTER T (barMins > targetMins)
//   → Use Open[0] of that bar — it opened AT T (or within the same bar).
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
        private Dictionary<string, int> openBarIndices;
        private Dictionary<string, bool> openSet;

        // Globex date = date the current 18:00 ET session belongs to (next calendar day)
        // e.g. Sunday 18:05 ET → globexDate = Monday
        private DateTime lastGlobexDate = DateTime.MinValue;

        // Previous session's opens (for sweep target persistence)
        private Dictionary<string, double> prevSessionOpens;

        public SessionOpensEngine(bool include4H = true)
        {
            opens = LiquidityLevelsCatalog.GetSessionOpens(include4H);
            currentOpens = new Dictionary<string, double>();
            openTimes = new Dictionary<string, DateTime>();
            openBarIndices = new Dictionary<string, int>();
            openSet = new Dictionary<string, bool>();
            prevSessionOpens = new Dictionary<string, double>();

            foreach (var o in opens)
            {
                currentOpens[o.Name] = 0;
                openTimes[o.Name] = DateTime.MinValue;
                openBarIndices[o.Name] = -1;
                openSet[o.Name] = false;
            }
        }

        // ═══ Returns the "Globex date" for a given ET bar time ═══
        // Futures day starts at 18:00 ET: bars from 18:00-23:59 belong to the NEXT calendar day.
        private static DateTime GetGlobexDate(DateTime barTimeEt)
        {
            return barTimeEt.Hour >= 18 ? barTimeEt.Date.AddDays(1) : barTimeEt.Date;
        }

        // ═══ Called every bar by the host indicator ═══
        // barTimeEt = bar close time in ET (NT convention), openPrice = Open[0]
        public void OnBarUpdate(DateTime barTimeEt, double openPrice, double closePrice, int barIndex)
        {
            // Globex session rollover at 18:00 ET — archive previous session's opens
            DateTime globexDate = GetGlobexDate(barTimeEt);
            if (globexDate != lastGlobexDate)
            {
                if (lastGlobexDate != DateTime.MinValue)
                {
                    foreach (var o in opens)
                    {
                        if (openSet[o.Name] && currentOpens[o.Name] > 0)
                            prevSessionOpens[o.Name] = currentOpens[o.Name];
                    }
                }

                // Reset all opens for the new Globex session
                lastGlobexDate = globexDate;
                foreach (var o in opens)
                {
                    currentOpens[o.Name] = 0;
                    openTimes[o.Name] = DateTime.MinValue;
                    openBarIndices[o.Name] = -1;
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

                // NinjaTrader timestamps bars at their CLOSE time.
                // TradingView timestamps bars at their OPEN time.
                //
                // Example for RTH Open (09:30 ET) on a 5-min chart:
                //   NT bar Time[0]=09:30 → opened 09:25–09:30  → Open[0] = 09:25 price ✗
                //   NT bar Time[0]=09:35 → opened 09:30–09:35  → Open[0] = 09:30 price ✅
                //
                // Rule: capture Open[0] from the FIRST bar whose close time is AFTER the target.
                // Skip session opens that are in the "prior session" range (>= 18:00 ET),
                // since those are set during their own Globex session day.
                if (openMins >= 18 * 60)
                {
                    // Globex open (18:00 ET): capture on the first bar after 18:00 ET
                    if (barMins > openMins)
                    {
                        currentOpens[o.Name] = openPrice;
                        openTimes[o.Name] = barTimeEt;
                        openBarIndices[o.Name] = barIndex;
                        openSet[o.Name] = true;
                    }
                }
                else
                {
                    // Midnight open, London open, RTH open, 4H opens (00:00–17:00 ET range)
                    // CRITICAL: Only fire during the 00:00–17:59 portion of the day.
                    // Without the barMins < 18*60 guard, these would ALL fire at 18:05 ET
                    // (first bar of new Globex session) because 1085 > 0/180/570 is always true.
                    if (barMins < 18 * 60 && barMins > openMins)
                    {
                        currentOpens[o.Name] = openPrice;
                        openTimes[o.Name] = barTimeEt;
                        openBarIndices[o.Name] = barIndex;
                        openSet[o.Name] = true;
                    }
                }
            }
        }

        // ═══ Public accessors ═══
        public double GetOpen(string name)
        {
            return currentOpens.TryGetValue(name, out var p) ? p : 0;
        }

        public int GetOpenBarIndex(string name)
        {
            return openBarIndices.TryGetValue(name, out var idx) ? idx : -1;
        }

        public double MidnightOpen => GetOpen("MNO");
        public double LondonOpen   => GetOpen("LonO");
        public double NyOpen       => GetOpen("NYO");

        public double Get4HOpen(int hour)
        {
            return GetOpen($"{hour:D4}");
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