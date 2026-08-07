using System;
using System.IO;
using System.Collections.Generic;

#if TESTING
using Newtonsoft.Json.Linq;
using Newtonsoft.Json;
#else
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
#endif

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
        public bool ArmedForLive { get; set; } = false; // MUST default to false for safety
        public bool EnableNewsShield { get; set; } = true;
        public int NewsBufferMinutesBefore { get; set; } = 2;
        public int NewsBufferMinutesAfter { get; set; } = 2;
        public string LocalNewsEventsFilePath { get; set; } = "";
        public bool EnableProfitTargetLock { get; set; } = true;
        public double EvaluationTargetProfit { get; set; } = 3000.0;
        public bool EnablePeakEquityProtection { get; set; } = true;
        public double MaxPeakGivebackPct { get; set; } = 0.30;
        // P1-40: absolute floor, in dollars, below which an open gain is not treated as an
        // established peak. The giveback rule is proportional, so without this a one-tick peak
        // ($0.50 on MNQ) makes any retrace a >=100% giveback and flattens the position seconds
        // after entry. Set to 0 for the old, purely proportional behaviour.
        public double MinPeakGainDollars { get; set; } = 50.0;
        public bool EnableConsistencyCap { get; set; } = true;
        public double MaxDailyProfitPctOfTarget { get; set; } = 0.35;
        public bool EnableAutoDayFiller { get; set; } = false;
    }

    public class PropFirmProtectionSuite
    {
        private static readonly Lazy<PropFirmProtectionSuite> _instance = new Lazy<PropFirmProtectionSuite>(() => new PropFirmProtectionSuite());
        public static PropFirmProtectionSuite Instance => _instance.Value;

        private readonly List<EconomicNewsEvent> _newsEvents = new List<EconomicNewsEvent>();
        private readonly object _lock = new object();
        public PropFirmProtectionConfig Config { get; private set; } = new PropFirmProtectionConfig();

        public void AddTestNewsEvent(EconomicNewsEvent ev)
        {
            lock (_lock)
            {
                _newsEvents.Add(ev);
            }
        }

        public void UpdateConfig(PropFirmProtectionConfig config, bool confirmLive = false)
        {
            if (config == null) return;

            // Safety Gate: Disarm ArmedForLive unless confirmLive == true is explicitly passed
            if (config.ArmedForLive && !confirmLive)
            {
                config.ArmedForLive = false;
            }

            lock (_lock)
            {
                Config = config;
            }
        }

        public bool IsInNewsWindow(DateTime nowUtc, int bufferMinutesBefore, int bufferMinutesAfter)
        {
            lock (_lock)
            {
                foreach (var ev in _newsEvents)
                {
                    if (!string.Equals(ev.Impact, "High", StringComparison.OrdinalIgnoreCase)) continue;
                    var startWindow = ev.EventTimeUtc.AddMinutes(-bufferMinutesBefore);
                    var endWindow = ev.EventTimeUtc.AddMinutes(bufferMinutesAfter);
                    if (nowUtc >= startWindow && nowUtc <= endWindow)
                    {
                        return true;
                    }
                }
            }
            return false;
        }

        public bool EvaluateProfitTargetLock(double currentRealizedPnL, PropFirmProtectionConfig config = null)
        {
            var cfg = config ?? Config;
            if (cfg == null || !cfg.EnableProfitTargetLock) return false;
            return currentRealizedPnL >= cfg.EvaluationTargetProfit;
        }

        public bool EvaluatePeakEquityGiveback(double peakOpenGain, double currentUnrealized, PropFirmProtectionConfig config = null)
        {
            // Both arguments must be unrealized-only PnL in dollars. Passing a
            // total-equity peak combined with unrealized PnL causes spurious
            // giveback breaches when the account is flat after a profitable session.
            var cfg = config ?? Config;
            if (cfg == null || !cfg.EnablePeakEquityProtection || peakOpenGain <= 0 || currentUnrealized >= peakOpenGain) return false;
            // P1-40: the test below is proportional, so without an absolute floor a peak of one
            // tick ($0.50 on MNQ) turns any retrace into a >=100% giveback. Live on 2026-08-07
            // that fired six times in 36 seconds, first 2.4s after entry with the position down
            // $1.00; in an acting mode it would flatten nearly every trade on entry. Below the
            // floor there is no meaningful profit to protect, and the daily-loss and stop-guard
            // rules already cover the downside.
            if (peakOpenGain < cfg.MinPeakGainDollars) return false;
            double giveback = peakOpenGain - currentUnrealized;
            double givebackPct = giveback / peakOpenGain;
            return givebackPct >= cfg.MaxPeakGivebackPct;
        }

        public void LoadFromDisk(string filePath)
        {
            if (string.IsNullOrEmpty(filePath) || !File.Exists(filePath)) return;
            try
            {
                string json = File.ReadAllText(filePath);
                var dict = JsonConvert.DeserializeObject<Dictionary<string, JObject>>(json);
                JObject jObj = null;
                if (dict != null && dict.ContainsKey("global")) jObj = dict["global"];
                else if (!string.IsNullOrWhiteSpace(json)) jObj = JObject.Parse(json);

                if (jObj != null)
                {
                    var cfg = ParseConfig(jObj);
                    UpdateConfig(cfg);
                }
            }
            catch {}
        }

        public void SaveToDisk(string filePath)
        {
            if (string.IsNullOrEmpty(filePath)) return;
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(filePath));
                lock (_lock)
                {
                    var dict = new Dictionary<string, PropFirmProtectionConfig> { ["global"] = Config };
                    File.WriteAllText(filePath, JsonConvert.SerializeObject(dict, Formatting.Indented));
                }
            }
            catch {}
        }

        public PropFirmProtectionConfig ParseConfig(JObject jObj)
        {
            if (jObj == null) return new PropFirmProtectionConfig();
            return new PropFirmProtectionConfig
            {
                ArmedForLive = jObj["ArmedForLive"] != null ? (bool)jObj["ArmedForLive"] : (jObj["armedForLive"] != null ? (bool)jObj["armedForLive"] : false), // Default false
                EnableNewsShield = jObj["EnableNewsShield"] != null ? (bool)jObj["EnableNewsShield"] : (jObj["enableNewsShield"] != null ? (bool)jObj["enableNewsShield"] : (jObj["newsShield"] != null ? (bool)jObj["newsShield"] : true)),
                NewsBufferMinutesBefore = jObj["NewsBufferMinutesBefore"] != null ? (int)jObj["NewsBufferMinutesBefore"] : (jObj["newsBufferMinutesBefore"] != null ? (int)jObj["newsBufferMinutesBefore"] : 2),
                NewsBufferMinutesAfter = jObj["NewsBufferMinutesAfter"] != null ? (int)jObj["NewsBufferMinutesAfter"] : (jObj["newsBufferMinutesAfter"] != null ? (int)jObj["newsBufferMinutesAfter"] : 2),
                LocalNewsEventsFilePath = jObj["LocalNewsEventsFilePath"]?.ToString() ?? jObj["localNewsEventsFilePath"]?.ToString() ?? "",
                EnableProfitTargetLock = jObj["EnableProfitTargetLock"] != null ? (bool)jObj["EnableProfitTargetLock"] : (jObj["enableProfitTargetLock"] != null ? (bool)jObj["enableProfitTargetLock"] : (jObj["profitTargetLock"] != null ? (bool)jObj["profitTargetLock"] : true)),
                EvaluationTargetProfit = jObj["EvaluationTargetProfit"] != null ? (double)jObj["EvaluationTargetProfit"] : (jObj["evaluationTargetProfit"] != null ? (double)jObj["evaluationTargetProfit"] : (jObj["profitTarget"] != null ? (double)jObj["profitTarget"] : 3000.0)),
                EnablePeakEquityProtection = jObj["EnablePeakEquityProtection"] != null ? (bool)jObj["EnablePeakEquityProtection"] : (jObj["enablePeakEquityProtection"] != null ? (bool)jObj["enablePeakEquityProtection"] : (jObj["peakEquityProtection"] != null ? (bool)jObj["peakEquityProtection"] : true)),
                MaxPeakGivebackPct = jObj["MaxPeakGivebackPct"] != null ? (double)jObj["MaxPeakGivebackPct"] : (jObj["maxPeakGivebackPct"] != null ? (double)jObj["maxPeakGivebackPct"] : (jObj["givebackPct"] != null ? (double)jObj["givebackPct"] : 0.30)),
                MinPeakGainDollars = jObj["MinPeakGainDollars"] != null ? (double)jObj["MinPeakGainDollars"] : (jObj["minPeakGainDollars"] != null ? (double)jObj["minPeakGainDollars"] : 50.0),
                EnableConsistencyCap = jObj["EnableConsistencyCap"] != null ? (bool)jObj["EnableConsistencyCap"] : (jObj["enableConsistencyCap"] != null ? (bool)jObj["enableConsistencyCap"] : true),
                MaxDailyProfitPctOfTarget = jObj["MaxDailyProfitPctOfTarget"] != null ? (double)jObj["MaxDailyProfitPctOfTarget"] : (jObj["maxDailyProfitPctOfTarget"] != null ? (double)jObj["maxDailyProfitPctOfTarget"] : 0.35),
                EnableAutoDayFiller = jObj["EnableAutoDayFiller"] != null ? (bool)jObj["EnableAutoDayFiller"] : (jObj["enableAutoDayFiller"] != null ? (bool)jObj["enableAutoDayFiller"] : false)
            };
        }
    }
}
