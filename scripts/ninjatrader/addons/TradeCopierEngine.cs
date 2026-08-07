using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;

#if TESTING
using Newtonsoft.Json.Linq;
using Newtonsoft.Json;
// OnExecution now compiles in the test build, so it needs the Cbi types (Account, Order,
// Execution, Instrument, OrderAction, ...) which are provided by the stubs in
// RiskGuardAddOnTests.cs under the same namespace.
using NinjaTrader.Cbi;
using NinjaTrader.Code;
#else
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using NinjaTrader.Cbi;
using NinjaTrader.Core;
#endif

namespace NinjaTrader.NinjaScript.AddOns
{
    public enum CopierExecutionMode { Executions, Orders }
    public enum CopierSizingMode { QuantityRatio, FixedLot, NetLiquidationRatio, AvailableCashPercent, PerTickerMatrix }

    public class CopierRelationship
    {
        public string Id { get; set; } = Guid.NewGuid().ToString();
        public string LeaderAccountName { get; set; } = "Sim101";
        public string FollowerAccountName { get; set; } = "SimCopy2";
        public bool IsEnabled { get; set; } = true;
        public bool ArmedForLive { get; set; } = false; // MUST default to false for safety
        public CopierExecutionMode Mode { get; set; } = CopierExecutionMode.Executions;
        public CopierSizingMode SizingMode { get; set; } = CopierSizingMode.QuantityRatio;
        public double QuantityRatio { get; set; } = 1.0;
        public bool FixedLotMode { get; set; } = false;
        public int FixedLotSize { get; set; } = 1;
        public bool AutoSymbolConversion { get; set; } = true;
        public Dictionary<string, double> PerTickerRatios { get; set; } = new Dictionary<string, double>(StringComparer.OrdinalIgnoreCase);
        public Dictionary<string, string> CustomSymbolMappings { get; set; } = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        public bool EnableFollowerAtm { get; set; } = false;
        public string FollowerAtmStrategyName { get; set; } = "Standard_ATM";
        public bool StealthMode { get; set; } = true;
        public int MaxPositionSize { get; set; } = 100;
        public double DailyLossLimit { get; set; } = 1000.0;
        public bool IsQuarantined { get; set; } = false;
        public string QuarantineReason { get; set; }

        // P1-22: these two were displayed in TradeCopierWindow (:799) but written by nothing --
        // the UI reported 0ms and 0.0t however badly a copy actually filled. Both are now
        // populated from the follower's own fill. LatencyMs is the LAST observed leader-fill ->
        // follower-fill gap; AvgSlippageTicks is a running mean, matching what the names claim.
        public double LatencyMs { get; set; }
        public double AvgSlippageTicks { get; set; }

        // P1-22: ticks of adverse slippage on an ENTRY copy that quarantine this relationship.
        // 0 disables the check. Signed so only slippage *against* the follower counts.
        public double MaxSlippageTicks { get; set; } = 0.0;
    }

    public class CopierGroup
    {
        public string Id { get; set; } = Guid.NewGuid().ToString();
        public string GroupName { get; set; } = "DefaultGroup";
        public string LeaderAccountName { get; set; } = "Sim101";
        public bool IsEnabled { get; set; } = true;
        public bool ArmedForLive { get; set; } = false; // MUST default to false for safety
        public CopierExecutionMode Mode { get; set; } = CopierExecutionMode.Executions;
        public CopierSizingMode SizingMode { get; set; } = CopierSizingMode.QuantityRatio;
        public double QuantityRatio { get; set; } = 1.0;
        public bool FixedLotMode { get; set; } = false;
        public int FixedLotSize { get; set; } = 1;
        public bool AutoSymbolConversion { get; set; } = true;
        public Dictionary<string, double> PerTickerRatios { get; set; } = new Dictionary<string, double>(StringComparer.OrdinalIgnoreCase);
        public Dictionary<string, string> CustomSymbolMappings { get; set; } = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        public bool EnableFollowerAtm { get; set; } = false;
        public string FollowerAtmStrategyName { get; set; } = "Standard_ATM";
        public bool StealthMode { get; set; } = true;
        public int MaxPositionSize { get; set; } = 100;
        public double DailyLossLimit { get; set; } = 1000.0;
        public double MaxSlippageTicks { get; set; } = 0.0;   // P1-22
        public List<string> FollowerAccounts { get; set; } = new List<string>();

        public List<CopierRelationship> ToRelationships()
        {
            var list = new List<CopierRelationship>();
            if (FollowerAccounts == null) return list;
            foreach (var follower in FollowerAccounts)
            {
                if (string.IsNullOrWhiteSpace(follower)) continue;
                list.Add(new CopierRelationship
                {
                    Id = $"{Id}_{follower}",
                    LeaderAccountName = this.LeaderAccountName,
                    FollowerAccountName = follower.Trim(),
                    IsEnabled = this.IsEnabled,
                    ArmedForLive = this.ArmedForLive,
                    Mode = this.Mode,
                    SizingMode = this.SizingMode,
                    QuantityRatio = this.QuantityRatio,
                    FixedLotMode = this.FixedLotMode,
                    FixedLotSize = this.FixedLotSize,
                    AutoSymbolConversion = this.AutoSymbolConversion,
                    PerTickerRatios = this.PerTickerRatios != null ? new Dictionary<string, double>(this.PerTickerRatios, StringComparer.OrdinalIgnoreCase) : new Dictionary<string, double>(),
                    CustomSymbolMappings = this.CustomSymbolMappings != null ? new Dictionary<string, string>(this.CustomSymbolMappings, StringComparer.OrdinalIgnoreCase) : new Dictionary<string, string>(),
                    EnableFollowerAtm = this.EnableFollowerAtm,
                    FollowerAtmStrategyName = this.FollowerAtmStrategyName,
                    StealthMode = this.StealthMode,
                    MaxPositionSize = this.MaxPositionSize,
                    DailyLossLimit = this.DailyLossLimit,
                    MaxSlippageTicks = this.MaxSlippageTicks
                });
            }
            return list;
        }
    }

    public class CopierConfigPayload
    {
        public Dictionary<string, CopierRelationship> Relationships { get; set; } = new Dictionary<string, CopierRelationship>();
        public Dictionary<string, CopierGroup> Groups { get; set; } = new Dictionary<string, CopierGroup>();
    }

    public class TradeCopierEngine
    {
        private static readonly Lazy<TradeCopierEngine> _instance = new Lazy<TradeCopierEngine>(() => new TradeCopierEngine());
        public static TradeCopierEngine Instance => _instance.Value;

        private readonly List<CopierRelationship> _relationships = new List<CopierRelationship>();
        private readonly List<CopierGroup> _groups = new List<CopierGroup>();
        private readonly HashSet<string> _copiedExecutionIds = new HashSet<string>();
        private readonly Queue<string> _executionIdQueue = new Queue<string>();
        private const int MaxExecutionCacheSize = 5000;
        private readonly object _lock = new object();

        public void AddRelationship(CopierRelationship rel) => UpsertRelationship(rel);

        public void UpsertRelationship(CopierRelationship rel, bool confirmLive = false)
        {
            if (rel == null || string.IsNullOrEmpty(rel.LeaderAccountName)) return;

            // Safety Gate: Disarm ArmedForLive unless confirmLive == true is explicitly passed
            if (rel.ArmedForLive && !confirmLive)
            {
                rel.ArmedForLive = false;
            }

            lock (_lock)
            {
                var existing = _relationships.FirstOrDefault(r => 
                    r.LeaderAccountName.Equals(rel.LeaderAccountName, StringComparison.OrdinalIgnoreCase) && 
                    r.FollowerAccountName.Equals(rel.FollowerAccountName, StringComparison.OrdinalIgnoreCase));
                
                if (existing != null)
                {
                    _relationships.Remove(existing);
                }
                _relationships.Add(rel);
            }
        }

        public void RemoveRelationship(string leaderAccount, string followerAccount = null)
        {
            lock (_lock)
            {
                _relationships.RemoveAll(r => 
                    r.LeaderAccountName.Equals(leaderAccount, StringComparison.OrdinalIgnoreCase) &&
                    (string.IsNullOrEmpty(followerAccount) || r.FollowerAccountName.Equals(followerAccount, StringComparison.OrdinalIgnoreCase)));
            }
        }

        public int CalculateScaledQuantity(int sourceQuantity, decimal scaleFactor)
        {
            if (sourceQuantity <= 0 || scaleFactor <= 0) return 0;
            decimal rawQuantity = (decimal)sourceQuantity * scaleFactor;
            decimal rounded = Math.Round(rawQuantity, 0, MidpointRounding.AwayFromZero);
            if (rounded > int.MaxValue) return int.MaxValue;
            return (int)rounded;
        }

        public int CalculateSafeFollowerDelta(int leaderTargetQty, int currentFollowerQty, bool isMarketOrder, out bool isBlocked)
        {
            isBlocked = false;
            int delta = leaderTargetQty - currentFollowerQty;
            if (delta == 0) return 0;

            if (isMarketOrder && currentFollowerQty == 0)
            {
                bool isLeaderShort = leaderTargetQty < 0;
                bool isLeaderLong = leaderTargetQty > 0;
                bool isOppositeMarketOrder = (isLeaderShort && delta > 0) || (isLeaderLong && delta < 0);

                if (isOppositeMarketOrder)
                {
                    isBlocked = true;
                    return 0;
                }
            }

            if (currentFollowerQty != 0 && ((currentFollowerQty > 0 && delta < 0) || (currentFollowerQty < 0 && delta > 0)))
            {
                int maxReduce = Math.Abs(currentFollowerQty);
                delta = Math.Sign(delta) * Math.Min(Math.Abs(delta), maxReduce);
            }

            return delta;
        }

#if !TESTING
        public void ReconcileFollowerPosition(Account leaderAccount, Account followerAccount, Instrument instrument)
        {
            if (leaderAccount == null || followerAccount == null || instrument == null) return;

            var leaderPosObj = leaderAccount.Positions.FirstOrDefault(p => p.Instrument == instrument);
            var followerPosObj = followerAccount.Positions.FirstOrDefault(p => p.Instrument == instrument);
            double leaderQty = leaderPosObj != null ? leaderPosObj.Quantity : 0;
            double followerQty = followerPosObj != null ? followerPosObj.Quantity : 0;

            if (Math.Abs(leaderQty) < double.Epsilon)
            {
                if (Math.Abs(followerQty) > double.Epsilon)
                {
                    System.Windows.Application.Current?.Dispatcher.InvokeAsync(() =>
                    {
                        var workingOrders = followerAccount.Orders
                            .Where(o => o.Instrument == instrument && (o.OrderState == OrderState.Working || o.OrderState == OrderState.Submitted))
                            .ToList();
                        foreach (var ord in workingOrders) { try { followerAccount.Cancel(new[] { ord }); } catch {} }
                        try { followerAccount.Flatten(new[] { instrument }); } catch {}
                    });
                }
                return;
            }

            bool directionMismatch = (leaderQty > 0 && followerQty < 0) || (leaderQty < 0 && followerQty > 0);
            if (directionMismatch)
            {
                System.Windows.Application.Current?.Dispatcher.InvokeAsync(() =>
                {
                    NinjaTrader.Code.Output.Process($"[RECONCILER MISMATCH] Leader: {leaderQty}, Follower: {followerQty}. Exiting follower position.", PrintTo.OutputTab1);
                    try { followerAccount.Flatten(new[] { instrument }); } catch {}
                });
            }
        }
#endif

        public List<CopierRelationship> GetRelationships()
        {
            lock (_lock)
            {
                return new List<CopierRelationship>(_relationships);
            }
        }

        public void UpsertGroup(CopierGroup group, bool confirmLive = false)
        {
            if (group == null || string.IsNullOrWhiteSpace(group.GroupName)) return;

            if (group.ArmedForLive && !confirmLive)
            {
                group.ArmedForLive = false;
            }

            lock (_lock)
            {
                var existing = _groups.FirstOrDefault(g => 
                    g.GroupName.Equals(group.GroupName, StringComparison.OrdinalIgnoreCase));
                
                if (existing != null)
                {
                    _groups.Remove(existing);
                }
                _groups.Add(group);
            }
        }

        public void RemoveGroup(string groupName)
        {
            if (string.IsNullOrWhiteSpace(groupName)) return;
            lock (_lock)
            {
                _groups.RemoveAll(g => g.GroupName.Equals(groupName, StringComparison.OrdinalIgnoreCase));
            }
        }

        public List<CopierGroup> GetGroups()
        {
            lock (_lock)
            {
                return new List<CopierGroup>(_groups);
            }
        }

        public CopierGroup GetGroup(string groupName)
        {
            if (string.IsNullOrWhiteSpace(groupName)) return null;
            lock (_lock)
            {
                return _groups.FirstOrDefault(g => g.GroupName.Equals(groupName, StringComparison.OrdinalIgnoreCase));
            }
        }

        public bool AddFollowerToGroup(string groupName, string followerAccount)
        {
            if (string.IsNullOrWhiteSpace(groupName) || string.IsNullOrWhiteSpace(followerAccount)) return false;
            lock (_lock)
            {
                var grp = _groups.FirstOrDefault(g => g.GroupName.Equals(groupName, StringComparison.OrdinalIgnoreCase));
                if (grp == null) return false;

                if (grp.FollowerAccounts == null) grp.FollowerAccounts = new List<string>();
                if (!grp.FollowerAccounts.Any(f => f.Equals(followerAccount, StringComparison.OrdinalIgnoreCase)))
                {
                    grp.FollowerAccounts.Add(followerAccount.Trim());
                }
                return true;
            }
        }

        public bool RemoveFollowerFromGroup(string groupName, string followerAccount)
        {
            if (string.IsNullOrWhiteSpace(groupName) || string.IsNullOrWhiteSpace(followerAccount)) return false;
            lock (_lock)
            {
                var grp = _groups.FirstOrDefault(g => g.GroupName.Equals(groupName, StringComparison.OrdinalIgnoreCase));
                if (grp == null || grp.FollowerAccounts == null) return false;

                grp.FollowerAccounts.RemoveAll(f => f.Equals(followerAccount, StringComparison.OrdinalIgnoreCase));
                return true;
            }
        }

        /// <param name="includeQuarantined">
        /// P1-22: pass true for an EXIT copy. A quarantined relationship must still be able to
        /// close the follower out; blocking its exits strands it in a position the leader has
        /// already left. Defaults to false so every existing caller keeps the old behaviour.
        /// </param>
        public List<CopierRelationship> GetActiveRelationshipsForLeader(string leaderAccount, bool includeQuarantined = false)
        {
            var result = new List<CopierRelationship>();
            if (string.IsNullOrWhiteSpace(leaderAccount)) return result;

            lock (_lock)
            {
                var direct = _relationships.Where(r =>
                    r.IsEnabled &&
                    (includeQuarantined || !r.IsQuarantined) &&
                    r.LeaderAccountName.Equals(leaderAccount, StringComparison.OrdinalIgnoreCase));
                result.AddRange(direct);

                var matchingGroups = _groups.Where(g => 
                    g.IsEnabled && 
                    g.LeaderAccountName.Equals(leaderAccount, StringComparison.OrdinalIgnoreCase));

                foreach (var group in matchingGroups)
                {
                    foreach (var rel in group.ToRelationships())
                    {
                        var directRel = _relationships.FirstOrDefault(r => 
                            r.LeaderAccountName.Equals(leaderAccount, StringComparison.OrdinalIgnoreCase) &&
                            r.FollowerAccountName.Equals(rel.FollowerAccountName, StringComparison.OrdinalIgnoreCase));
                        
                        if (!includeQuarantined && directRel != null && directRel.IsQuarantined)
                        {
                            continue; // Skip if direct relationship for this follower is quarantined
                        }

                        result.Add(rel);
                    }
                }

                // Deduplicate by FollowerAccountName so an account doesn't receive duplicate orders
                result = result
                    .GroupBy(r => r.FollowerAccountName, StringComparer.OrdinalIgnoreCase)
                    .Select(g => g.First())
                    .ToList();
            }
            return result;
        }

        public string TranslateSymbol(string rawSymbol, CopierRelationship rel = null)
        {
            if (string.IsNullOrEmpty(rawSymbol)) return rawSymbol;

            // P1-23: substitute the parsed ROOT only, and match case-insensitively.
            // The previous implementation ran rawSymbol.Replace(root, target) across the whole
            // string, which is fragile against any later occurrence of the root, and compared an
            // upper-cased root against the raw string -- so a lower-case instrument name matched
            // nothing, returned untranslated, and the copy silently went to the LEADER's contract
            // on a follower configured for the converted one.
            int split = rawSymbol.IndexOf(' ');
            string root = (split >= 0 ? rawSymbol.Substring(0, split) : rawSymbol).ToUpper();
            string remainder = split >= 0 ? rawSymbol.Substring(split) : string.Empty;

            // 1. Relationship custom overrides win.
            if (rel != null && rel.CustomSymbolMappings != null
                && rel.CustomSymbolMappings.TryGetValue(root, out var customTarget)
                && !string.IsNullOrEmpty(customTarget))
            {
                return customTarget.ToUpper() + remainder;
            }

            // 2. Bidirectional Mini <-> Micro default matrix.
            if (rel == null || rel.AutoSymbolConversion)
            {
                string mapped = null;
                switch (root)
                {
                    case "NQ":  mapped = "MNQ"; break;
                    case "ES":  mapped = "MES"; break;
                    case "YM":  mapped = "MYM"; break;
                    case "CL":  mapped = "MCL"; break;
                    case "GC":  mapped = "MGC"; break;
                    case "RTY": mapped = "M2K"; break;
                    case "MNQ": mapped = "NQ";  break;
                    case "MES": mapped = "ES";  break;
                    case "MYM": mapped = "YM";  break;
                    case "MCL": mapped = "CL";  break;
                    case "MGC": mapped = "GC";  break;
                    case "M2K": mapped = "RTY"; break;
                }
                if (mapped != null) return mapped + remainder;
            }

            return rawSymbol;
        }

        public int CalculateFollowerQuantity(CopierRelationship rel, int leaderQty, string rawSymbol, int currentFollowerPosition, bool isExit, out bool isClamped)
        {
            isClamped = false;
            if (leaderQty <= 0) return 0;

            int rawCopyQty;

            if (rel.FixedLotMode || rel.SizingMode == CopierSizingMode.FixedLot)
            {
                // Fixed-lot: entries use the configured lot size; exits mirror the leader's exit quantity.
                rawCopyQty = isExit ? leaderQty : rel.FixedLotSize;
            }
            else if (rel.SizingMode == CopierSizingMode.NetLiquidationRatio
                  || rel.SizingMode == CopierSizingMode.AvailableCashPercent)
            {
                // P1-23: these are declared in CopierSizingMode but never implemented. They used
                // to fall through to the QuantityRatio branch, so a small follower configured for
                // equity-scaling silently received the FULL leader size -- the P0-6 over-size
                // failure arriving through the config instead of the conversion matrix.
                //
                // Fail closed on ENTRIES rather than guess at a size. Never on exits: blocking an
                // exit strands the follower in a position the leader has already left, which is
                // the P0-5 failure and is worse than an unscaled one.
                if (!isExit)
                {
                    NinjaTrader.Code.Output.Process(
                        $"[CopierEngine] BLOCKED entry copy: sizing mode {rel.SizingMode} is declared but not implemented. "
                        + $"Refusing to size {rel.LeaderAccountName} -> {rel.FollowerAccountName} rather than silently copying 1:1. "
                        + "Use QuantityRatio or FixedLot.", PrintTo.OutputTab1);
                    isClamped = true;
                    return 0;
                }
                rawCopyQty = leaderQty;
            }
            else
            {
                double absRatio = Math.Abs(rel.QuantityRatio);
                string symbol = rawSymbol.Split(' ')[0].ToUpper();

                // 1. Check Per-Ticker Ratio Overrides
                if (rel.PerTickerRatios != null && rel.PerTickerRatios.TryGetValue(symbol, out double tickerRatio))
                {
                    absRatio = Math.Abs(tickerRatio);
                }

                // 2. Bidirectional Symbol Multiplier (Mini -> Micro 10x, Micro -> Mini 0.1x)
                double symbolMultiplier = 1.0;
                if (rel.AutoSymbolConversion)
                {
                    if (symbol == "NQ" || symbol == "ES" || symbol == "YM" || symbol == "CL" || symbol == "GC" || symbol == "RTY")
                    {
                        symbolMultiplier = 10.0; // Mini -> Micro
                    }
                    else if (symbol == "MNQ" || symbol == "MES" || symbol == "MYM" || symbol == "MCL" || symbol == "MGC" || symbol == "M2K")
                    {
                        symbolMultiplier = 0.1; // Micro -> Mini
                    }
                }

                rawCopyQty = (int)Math.Round(leaderQty * absRatio * symbolMultiplier);
            }

            if (rawCopyQty < 1)
            {
                // Entries: skip. Flooring a sub-one-contract conversion up to 1 is
                // exactly the P0-6 notional blowout (1 MNQ -> 1 NQ is 10x).
                //
                // Exits are the opposite case and must NOT be skipped. Rounding an
                // exit down to 0 strands the follower in a position the leader has
                // already left, and because every partial exit rounds down
                // independently the position may never close at all: a leader who
                // entered 10 MNQ (follower: 1 NQ) and exits in any increment below
                // 10 produces 0 each time -- note Math.Round(0.5) is 0 under
                // banker's rounding, so even a 5+5 exit strands it. Exit at least
                // one contract whenever the follower actually holds one; the clamp
                // below caps it at the real position size, so this can only reduce.
                if (!isExit || currentFollowerPosition == 0)
                {
                    isClamped = false;
                    return 0;
                }
                rawCopyQty = 1;
            }

            if (isExit)
            {
                int positionSize = Math.Abs(currentFollowerPosition);
                if (rawCopyQty > positionSize)
                {
                    isClamped = positionSize > 0;
                    rawCopyQty = positionSize;
                }
                return Math.Max(0, rawCopyQty);
            }

            // Position-level Clamping: Cap against follower's resulting total position size
            int availableCapacity = Math.Max(0, rel.MaxPositionSize - Math.Abs(currentFollowerPosition));
            int finalQty = Math.Min(rawCopyQty, availableCapacity);

            if (rawCopyQty > availableCapacity)
            {
                isClamped = true;
            }

            return Math.Max(0, finalQty);
        }

        public int CalculateFollowerQuantity(CopierRelationship rel, int leaderQty, string rawSymbol, bool isExit = false)
        {
            return CalculateFollowerQuantity(rel, leaderQty, rawSymbol, 0, isExit, out _);
        }

        private bool DeduplicateExecutionId(string execId)
        {
            if (string.IsNullOrEmpty(execId)) return false;
            lock (_lock)
            {
                if (_copiedExecutionIds.Contains(execId)) return true;

                _copiedExecutionIds.Add(execId);
                _executionIdQueue.Enqueue(execId);
                while (_executionIdQueue.Count > MaxExecutionCacheSize)
                {
                    string oldest = _executionIdQueue.Dequeue();
                    _copiedExecutionIds.Remove(oldest);
                }
                return false;
            }
        }

        public void LoadFromDisk(string filePath)
        {
            if (string.IsNullOrEmpty(filePath) || !File.Exists(filePath)) return;
            try
            {
                string json = File.ReadAllText(filePath);
                var jRoot = JObject.Parse(json);

                lock (_lock)
                {
                    _relationships.Clear();
                    _groups.Clear();

                    var relsObj = jRoot["Relationships"] as JObject ?? jRoot["relationships"] as JObject;
                    var grpsObj = jRoot["Groups"] as JObject ?? jRoot["groups"] as JObject;
                    bool hasStructuredSections = relsObj != null || grpsObj != null;

                    if (hasStructuredSections)
                    {
                        if (relsObj != null)
                        {
                            foreach (var kv in relsObj)
                            {
                                if (kv.Value is JObject jObj)
                                {
                                    var rel = new CopierRelationship
                                    {
                                        Id = jObj["Id"]?.ToString() ?? Guid.NewGuid().ToString(),
                                        LeaderAccountName = jObj["LeaderAccountName"]?.ToString() ?? jObj["leaderAccount"]?.ToString() ?? (kv.Key.Contains("_") ? kv.Key.Split('_')[0] : kv.Key),
                                        FollowerAccountName = jObj["FollowerAccountName"]?.ToString() ?? jObj["followerAccount"]?.ToString() ?? (kv.Key.Contains("_") ? kv.Key.Split('_')[1] : "SimCopy2"),
                                        IsEnabled = jObj["IsEnabled"] != null ? (bool)jObj["IsEnabled"] : (jObj["isEnabled"] != null ? (bool)jObj["isEnabled"] : true),
                                        ArmedForLive = jObj["ArmedForLive"] != null ? (bool)jObj["ArmedForLive"] : (jObj["armedForLive"] != null ? (bool)jObj["armedForLive"] : false),
                                        QuantityRatio = jObj["QuantityRatio"] != null ? (double)jObj["QuantityRatio"] : (jObj["quantityRatio"] != null ? (double)jObj["quantityRatio"] : 1.0),
                                        FixedLotMode = jObj["FixedLotMode"] != null ? (bool)jObj["FixedLotMode"] : (jObj["fixedLotMode"] != null ? (bool)jObj["fixedLotMode"] : false),
                                        FixedLotSize = jObj["FixedLotSize"] != null ? (int)jObj["FixedLotSize"] : (jObj["fixedLotSize"] != null ? (int)jObj["fixedLotSize"] : 1),
                                        AutoSymbolConversion = jObj["AutoSymbolConversion"] != null ? (bool)jObj["AutoSymbolConversion"] : (jObj["autoSymbolConversion"] != null ? (bool)jObj["autoSymbolConversion"] : true),
                                        MaxPositionSize = jObj["MaxPositionSize"] != null ? (int)jObj["MaxPositionSize"] : (jObj["maxPositionSize"] != null ? (int)jObj["maxPositionSize"] : 100),
                                        DailyLossLimit = jObj["DailyLossLimit"] != null ? (double)jObj["DailyLossLimit"] : (jObj["dailyLossLimit"] != null ? (double)jObj["dailyLossLimit"] : 1000.0),
                                        IsQuarantined = jObj["IsQuarantined"] != null ? (bool)jObj["IsQuarantined"] : (jObj["isQuarantined"] != null ? (bool)jObj["isQuarantined"] : false),
                                        MaxSlippageTicks = jObj["MaxSlippageTicks"] != null ? (double)jObj["MaxSlippageTicks"] : (jObj["maxSlippageTicks"] != null ? (double)jObj["maxSlippageTicks"] : 0.0)
                                    };
                                    _relationships.Add(rel);
                                }
                            }
                        }

                        if (grpsObj != null)
                        {
                            foreach (var kv in grpsObj)
                            {
                                if (kv.Value is JObject jObj)
                                {
                                    var followers = new List<string>();
                                    var followersToken = jObj["FollowerAccounts"] ?? jObj["followerAccounts"];
                                    if (followersToken != null)
                                    {
                                        var parsed = JsonConvert.DeserializeObject<List<string>>(followersToken.ToString());
                                        if (parsed != null) followers = parsed;
                                    }

                                    var grp = new CopierGroup
                                    {
                                        Id = jObj["Id"]?.ToString() ?? Guid.NewGuid().ToString(),
                                        GroupName = jObj["GroupName"]?.ToString() ?? kv.Key,
                                        LeaderAccountName = jObj["LeaderAccountName"]?.ToString() ?? jObj["leaderAccount"]?.ToString() ?? "Sim101",
                                        IsEnabled = jObj["IsEnabled"] != null ? (bool)jObj["IsEnabled"] : (jObj["isEnabled"] != null ? (bool)jObj["isEnabled"] : true),
                                        ArmedForLive = jObj["ArmedForLive"] != null ? (bool)jObj["ArmedForLive"] : (jObj["armedForLive"] != null ? (bool)jObj["armedForLive"] : false),
                                        QuantityRatio = jObj["QuantityRatio"] != null ? (double)jObj["QuantityRatio"] : (jObj["quantityRatio"] != null ? (double)jObj["quantityRatio"] : 1.0),
                                        FixedLotMode = jObj["FixedLotMode"] != null ? (bool)jObj["FixedLotMode"] : (jObj["fixedLotMode"] != null ? (bool)jObj["fixedLotMode"] : false),
                                        FixedLotSize = jObj["FixedLotSize"] != null ? (int)jObj["FixedLotSize"] : (jObj["fixedLotSize"] != null ? (int)jObj["fixedLotSize"] : 1),
                                        AutoSymbolConversion = jObj["AutoSymbolConversion"] != null ? (bool)jObj["AutoSymbolConversion"] : (jObj["autoSymbolConversion"] != null ? (bool)jObj["autoSymbolConversion"] : true),
                                        MaxPositionSize = jObj["MaxPositionSize"] != null ? (int)jObj["MaxPositionSize"] : (jObj["maxPositionSize"] != null ? (int)jObj["maxPositionSize"] : 100),
                                        DailyLossLimit = jObj["DailyLossLimit"] != null ? (double)jObj["DailyLossLimit"] : (jObj["dailyLossLimit"] != null ? (double)jObj["dailyLossLimit"] : 1000.0),
                                        FollowerAccounts = followers
                                    };
                                    _groups.Add(grp);
                                }
                            }
                        }
                    }
                    else
                    {
                        var dict = JsonConvert.DeserializeObject<Dictionary<string, JObject>>(json);
                        if (dict != null)
                        {
                            foreach (var kv in dict)
                            {
                                var jObj = kv.Value;
                                var rel = new CopierRelationship
                                {
                                    LeaderAccountName = jObj["LeaderAccountName"]?.ToString() ?? jObj["leaderAccount"]?.ToString() ?? kv.Key,
                                    FollowerAccountName = jObj["FollowerAccountName"]?.ToString() ?? jObj["followerAccount"]?.ToString() ?? "SimCopy2",
                                    IsEnabled = jObj["IsEnabled"] != null ? (bool)jObj["IsEnabled"] : (jObj["isEnabled"] != null ? (bool)jObj["isEnabled"] : true),
                                    ArmedForLive = jObj["ArmedForLive"] != null ? (bool)jObj["ArmedForLive"] : (jObj["armedForLive"] != null ? (bool)jObj["armedForLive"] : false),
                                    QuantityRatio = jObj["QuantityRatio"] != null ? (double)jObj["QuantityRatio"] : (jObj["quantityRatio"] != null ? (double)jObj["quantityRatio"] : 1.0),
                                    FixedLotMode = jObj["FixedLotMode"] != null ? (bool)jObj["FixedLotMode"] : (jObj["fixedLotMode"] != null ? (bool)jObj["fixedLotMode"] : false),
                                    FixedLotSize = jObj["FixedLotSize"] != null ? (int)jObj["FixedLotSize"] : (jObj["fixedLotSize"] != null ? (int)jObj["fixedLotSize"] : 1),
                                    AutoSymbolConversion = jObj["AutoSymbolConversion"] != null ? (bool)jObj["AutoSymbolConversion"] : (jObj["autoSymbolConversion"] != null ? (bool)jObj["autoSymbolConversion"] : true),
                                    MaxPositionSize = jObj["MaxPositionSize"] != null ? (int)jObj["MaxPositionSize"] : (jObj["maxPositionSize"] != null ? (int)jObj["maxPositionSize"] : 100),
                                    DailyLossLimit = jObj["DailyLossLimit"] != null ? (double)jObj["DailyLossLimit"] : (jObj["dailyLossLimit"] != null ? (double)jObj["dailyLossLimit"] : 1000.0),
                                    IsQuarantined = jObj["IsQuarantined"] != null ? (bool)jObj["IsQuarantined"] : (jObj["isQuarantined"] != null ? (bool)jObj["isQuarantined"] : false)
                                };
                                _relationships.Add(rel);
                            }
                        }
                    }
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[LoadFromDisk EXCEPTION] {ex}");
            }
        }

        public void SaveToDisk(string filePath)
        {
            if (string.IsNullOrEmpty(filePath)) return;
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(filePath));
                lock (_lock)
                {
                    var jRels = new JObject();
                    foreach (var rel in _relationships)
                    {
                        jRels[rel.LeaderAccountName + "_" + rel.FollowerAccountName] = JObject.Parse(JsonConvert.SerializeObject(rel));
                    }

                    var jGrps = new JObject();
                    foreach (var grp in _groups)
                    {
                        jGrps[grp.GroupName] = JObject.Parse(JsonConvert.SerializeObject(grp));
                    }

                    var jRoot = new JObject
                    {
                        ["Relationships"] = jRels,
                        ["Groups"] = jGrps
                    };

                    string jsonToSave = jRoot.ToString(Formatting.Indented);
                    File.WriteAllText(filePath, jsonToSave);
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"[SaveToDisk EXCEPTION] {ex}");
            }
        }

        /// <summary>
        /// True only when the account is demonstrably a NinjaTrader simulation account.
        ///
        /// This is the switch that decides whether an account can lose real money, so it
        /// must not be inferred from the account NAME. Names are chosen by the user, and
        /// the previous `Name.StartsWith("Sim")` test exempted a funded account called
        /// "SimpsonFund" -- or "Simplex Capital", or any prop firm starting with those
        /// three letters -- from BOTH live gates at once: the `ArmedForLive` check and
        /// T5's requirement that a live follower be protected by RiskGuard (P1-20).
        ///
        /// Fails closed by construction: a null account, an unset provider, or anything
        /// this cannot positively identify as the simulator is treated as live. Playback
        /// is deliberately NOT exempt -- it costs nothing to arm a relationship for a
        /// playback run, and guessing wrong in the other direction costs money.
        /// </summary>
        internal static bool IsSimulationAccount(Account account)
        {
            if (account == null) return false;
            return account.Provider == Provider.Simulator;
        }

        // ------------------------------------------------------------------
        // ACCOUNT EVENT SUBSCRIPTIONS (P1-21)
        //
        // The copier's ExecutionUpdate handlers used to be attached by McpBridgeAddOn in a
        // single pass over Account.All at State.Configure. Any account that came online after
        // that pass -- a broker connecting late, a reconnect, an account added from the
        // Control Center -- never raised OnExecution. A relationship whose leader arrived late
        // was therefore silently dead: enabled in the config, listed in the UI, copying
        // nothing. RiskGuard already solves this by re-running its subscribe pass on every
        // Connection.ConnectionStatusUpdate (RiskGuardAddOn.OnConnectionStatusUpdate); this
        // mirrors that.
        //
        // The bookkeeping lives here, not in McpBridgeAddOn, because that file is excluded
        // from the test build by RiskGuardTests.csproj -- an untestable subscription is how
        // this defect survived in the first place.
        // ------------------------------------------------------------------

        // Held only across event add/remove, which touch no broker call and cannot re-enter.
        // Deliberately NOT _lock: OnExecution takes that one, and a subscribe pass must never
        // be able to serialise behind an in-flight copy.
        private readonly object _subscriptionLock = new object();

        // The Account objects this engine instance has attached to, so teardown can detach
        // from exactly those. Reference identity, not name: a reconnect that hands back a new
        // Account object for the same name must be treated as a new subscription target.
        private readonly HashSet<Account> _subscribedAccounts = new HashSet<Account>();

        /// <summary>
        /// Attaches the copier's execution handler to every account NT8 currently knows about.
        /// Safe to call repeatedly, and meant to be: once at startup and again on every
        /// connection-status change. Returns the number of accounts newly subscribed.
        /// </summary>
        public int RefreshAccountSubscriptions()
        {
            int added = 0;
            lock (_subscriptionLock)
            {
                foreach (Account acc in Account.All.ToList())
                {
                    if (acc == null) continue;

                    // `-=` is a no-op when the handler is not attached, so re-running the pass
                    // cannot double-deliver an execution. Note this only dedupes handlers owned
                    // by *this* engine instance -- it cannot detach one left behind by a
                    // previous instance, which is why Terminated must call
                    // UnsubscribeAllAccounts.
                    acc.ExecutionUpdate -= OnAccountExecutionUpdate;
                    acc.ExecutionUpdate += OnAccountExecutionUpdate;

                    if (_subscribedAccounts.Add(acc)) added++;
                }
            }
            return added;
        }

        /// <summary>
        /// Detaches from every account subscribed by this engine instance. Must run at
        /// State.Terminated: NT8 reloads every AddOn on each recompile, and a handler left
        /// attached to a surviving Account object would keep delivering executions to the dead
        /// engine alongside the new one -- every fill copied twice.
        /// </summary>
        public int UnsubscribeAllAccounts()
        {
            lock (_subscriptionLock)
            {
                int count = _subscribedAccounts.Count;
                foreach (Account acc in _subscribedAccounts)
                {
                    if (acc != null) acc.ExecutionUpdate -= OnAccountExecutionUpdate;
                }
                _subscribedAccounts.Clear();
                return count;
            }
        }

        /// <summary>Number of accounts currently subscribed by this engine instance.</summary>
        public int SubscribedAccountCount
        {
            get { lock (_subscriptionLock) { return _subscribedAccounts.Count; } }
        }

        private void OnAccountExecutionUpdate(object sender, ExecutionEventArgs e)
        {
            if (e != null && e.Execution != null)
            {
                OnExecution(e.Execution);
            }
        }

        // ------------------------------------------------------------------
        // COPY LATENCY AND SLIPPAGE (P1-22)
        //
        // Every copy went out as a bare OrderType.Market with no reference to what the leader
        // actually paid, no measurement of the gap, and no ceiling on it -- while
        // TradeCopierWindow.cs:799 rendered `LatencyMs` and `AvgSlippageTicks` as though they
        // were real. Nothing anywhere wrote either field, so the UI reported 0ms / 0.0t however
        // badly a copy filled. A displayed number that is never computed is worse than no
        // number: it reads as evidence that the copy was clean.
        //
        // The follower's own fill is the only place this can be observed, and it arrives as an
        // ExecutionUpdate on the follower account -- which OnExecution drops at recursion guard
        // 1. So the measurement hooks in immediately before that drop.
        // ------------------------------------------------------------------

        private class PendingCopy
        {
            public string RelationshipId;
            public string LeaderAccountName;
            public string FollowerAccountName;
            public DateTime LeaderExecTime;    // raw exec.Time; never converted (see ObserveFollowerFill)
            public DateTime SubmittedUtc;
            public double LeaderFillPrice;
            public double FollowerTickSize;
            public bool PriceComparable;
            public bool FollowerIsBuy;
            public bool IsEntry;
        }

        /// <summary>
        /// Reference identity for Order keys. **`Order.OrderId` must not be used as a key**: NT8
        /// does not guarantee it is unique, and it can change over an order's lifetime across the
        /// historical->live transition. `RiskGuardAddOn.cs:4481` already carries that warning and
        /// tracks recognised stops by object reference for the same reason (RiskGuardAddOn.md
        /// §6.6). Keying on the id here would mis-attribute a fill to the wrong copy and could
        /// quarantine the wrong relationship -- and no test would catch it, because the test stub
        /// hands out a stable GUID per order.
        ///
        /// `RuntimeHelpers.GetHashCode` is used rather than `order.GetHashCode()` so the map is
        /// unaffected if Order ever overrides equality.
        /// </summary>
        private sealed class OrderReferenceComparer : IEqualityComparer<Order>
        {
            public static readonly OrderReferenceComparer Instance = new OrderReferenceComparer();
            public bool Equals(Order x, Order y) { return ReferenceEquals(x, y); }
            public int GetHashCode(Order obj) { return System.Runtime.CompilerServices.RuntimeHelpers.GetHashCode(obj); }
        }

        // Keyed by the follower Order object. Bounded FIFO for the same reason
        // `_copiedExecutionIds` is: a copy whose fill never arrives (rejected, cancelled,
        // expired) would otherwise leak an entry per order forever, and hold the Order alive with
        // it. P1-14 is this exact defect elsewhere in the addon.
        private readonly Dictionary<Order, PendingCopy> _pendingCopies =
            new Dictionary<Order, PendingCopy>(OrderReferenceComparer.Instance);
        private readonly Queue<Order> _pendingCopyQueue = new Queue<Order>();
        private const int MaxPendingCopies = 2000;

        // Sample counts for the running slippage mean, keyed by relationship id. Held here rather
        // than on CopierRelationship so the persisted config does not accumulate telemetry.
        private readonly Dictionary<string, int> _slippageSampleCounts =
            new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);

        /// <summary>
        /// True when two instrument roots track the same underlying at the same price, so a fill
        /// price on one can be compared to a fill price on the other. Equal roots qualify, as does
        /// either direction of the built-in mini/micro matrix (NQ/MNQ fill at the same index
        /// level). A root pairing that only exists because of `CustomSymbolMappings` does not:
        /// mapping ES to NQ is legitimate, but their prices are unrelated and a "slippage" figure
        /// derived from them would be pure noise -- and could quarantine a healthy relationship.
        /// </summary>
        internal static bool ArePricesComparable(string leaderRoot, string followerRoot)
        {
            if (string.IsNullOrEmpty(leaderRoot) || string.IsNullOrEmpty(followerRoot)) return false;
            if (leaderRoot.Equals(followerRoot, StringComparison.OrdinalIgnoreCase)) return true;

            string a = leaderRoot.ToUpper();
            string b = followerRoot.ToUpper();
            switch (a)
            {
                case "NQ":  return b == "MNQ";
                case "ES":  return b == "MES";
                case "YM":  return b == "MYM";
                case "CL":  return b == "MCL";
                case "GC":  return b == "MGC";
                case "RTY": return b == "M2K";
                case "MNQ": return b == "NQ";
                case "MES": return b == "ES";
                case "MYM": return b == "YM";
                case "MCL": return b == "CL";
                case "MGC": return b == "GC";
                case "M2K": return b == "RTY";
            }
            return false;
        }

        private static string RootOf(string fullName)
        {
            if (string.IsNullOrEmpty(fullName)) return null;
            int split = fullName.IndexOf(' ');
            return (split >= 0 ? fullName.Substring(0, split) : fullName).ToUpper();
        }

        private void RecordPendingCopy(
            Order followerOrder, CopierRelationship rel, Execution leaderExec,
            Instrument targetInstrument, OrderAction followerAction, bool isExit)
        {
            if (followerOrder == null || rel == null || leaderExec == null) return;

            double tickSize = 0.0;
            if (targetInstrument != null && targetInstrument.MasterInstrument != null)
                tickSize = targetInstrument.MasterInstrument.TickSize;

            var pending = new PendingCopy
            {
                RelationshipId = rel.Id,
                LeaderAccountName = rel.LeaderAccountName,
                FollowerAccountName = rel.FollowerAccountName,
                LeaderExecTime = leaderExec.Time,
                SubmittedUtc = DateTime.UtcNow,
                LeaderFillPrice = leaderExec.Price,
                FollowerTickSize = tickSize,
                PriceComparable = ArePricesComparable(
                    RootOf(leaderExec.Instrument != null ? leaderExec.Instrument.FullName : null),
                    RootOf(targetInstrument != null ? targetInstrument.FullName : null)),
                FollowerIsBuy = followerAction == OrderAction.Buy || followerAction == OrderAction.BuyToCover,
                IsEntry = !isExit
            };

            lock (_lock)
            {
                if (!_pendingCopies.ContainsKey(followerOrder)) _pendingCopyQueue.Enqueue(followerOrder);
                _pendingCopies[followerOrder] = pending;
                while (_pendingCopyQueue.Count > MaxPendingCopies)
                {
                    Order oldest = _pendingCopyQueue.Dequeue();
                    _pendingCopies.Remove(oldest);
                }
            }
        }

        /// <summary>
        /// Called when an execution lands on an account that is a follower somewhere. If it
        /// matches a copy this engine submitted, records how long it took and how far it filled
        /// from the leader, and quarantines the relationship if an ENTRY slipped past
        /// `MaxSlippageTicks`.
        /// </summary>
        private void ObserveFollowerFill(Execution exec)
        {
            if (exec == null || exec.Order == null) return;

            PendingCopy pending;
            CopierRelationship rel;
            lock (_lock)
            {
                // Matched on the Order object, never on OrderId -- see OrderReferenceComparer.
                if (!_pendingCopies.TryGetValue(exec.Order, out pending)) return;
                _pendingCopies.Remove(exec.Order);

                // Resolve the canonical stored relationship. A group-derived relationship is a
                // fresh object from ToRelationships(), so writing the metric onto the instance
                // OnExecution was handed would update a copy that is discarded.
                rel = _relationships.FirstOrDefault(r => r.Id == pending.RelationshipId)
                      ?? _relationships.FirstOrDefault(r =>
                            r.LeaderAccountName.Equals(pending.LeaderAccountName, StringComparison.OrdinalIgnoreCase) &&
                            r.FollowerAccountName.Equals(pending.FollowerAccountName, StringComparison.OrdinalIgnoreCase));
            }
            if (rel == null) return;

            // Latency. Both timestamps come from NT8 executions, so they are subtracted raw --
            // exec.Time's DateTimeKind is not dependable and converting one side only would
            // inject the UTC offset as latency. When the leader timestamp is absent (the field
            // is optional and some feeds leave it default) fall back to wall-clock since submit.
            double latencyMs;
            if (pending.LeaderExecTime != default(DateTime) && exec.Time != default(DateTime))
                latencyMs = (exec.Time - pending.LeaderExecTime).TotalMilliseconds;
            else
                latencyMs = (DateTime.UtcNow - pending.SubmittedUtc).TotalMilliseconds;

            // A negative or absurd figure means the clocks disagree, not that the copy was fast.
            // Recording it would make the UI lie in a new direction.
            if (latencyMs >= 0 && latencyMs < 600000)
                rel.LatencyMs = latencyMs;

            if (!pending.PriceComparable || pending.FollowerTickSize <= 0
                || pending.LeaderFillPrice <= 0 || exec.Price <= 0)
                return;

            double rawTicks = (exec.Price - pending.LeaderFillPrice) / pending.FollowerTickSize;
            // Positive always means WORSE for the follower: a buy filled above the leader, or a
            // sell filled below it. Without this the sign is meaningless and a threshold on it
            // would fire on favourable fills.
            double ticks = pending.FollowerIsBuy ? rawTicks : -rawTicks;

            lock (_lock)
            {
                int n;
                _slippageSampleCounts.TryGetValue(rel.Id, out n);
                n++;
                _slippageSampleCounts[rel.Id] = n;
                rel.AvgSlippageTicks = rel.AvgSlippageTicks + (ticks - rel.AvgSlippageTicks) / n;
            }

            if (rel.MaxSlippageTicks <= 0 || ticks <= rel.MaxSlippageTicks) return;

            // Quarantine is ENTRY-ONLY, and quarantined relationships still copy exits
            // (see OnExecution). IsQuarantined otherwise blocks every copy including the one
            // that closes the follower out, which would strand it in a position the leader has
            // already left -- the P0-5 failure, reached by a different route. Same asymmetry as
            // P0-6's exit clamp and P1-23's fail-closed sizing modes.
            if (pending.IsEntry)
            {
                rel.IsQuarantined = true;
                rel.QuarantineReason = string.Format(
                    "Entry slipped {0:F1} ticks against the follower vs the leader fill (limit {1:F1}). Exits are still copied.",
                    ticks, rel.MaxSlippageTicks);
                NinjaTrader.Code.Output.Process(
                    $"[CopierEngine] SLIPPAGE_QUARANTINE: {rel.LeaderAccountName} -> {rel.FollowerAccountName} entry slipped {ticks:F1} ticks (limit {rel.MaxSlippageTicks:F1}). New entries blocked; exits still copied.",
                    PrintTo.OutputTab1);
            }
            else
            {
                NinjaTrader.Code.Output.Process(
                    $"[CopierEngine] SLIPPAGE_ON_EXIT: {rel.LeaderAccountName} -> {rel.FollowerAccountName} exit slipped {ticks:F1} ticks (limit {rel.MaxSlippageTicks:F1}). Not quarantining -- that would strand the follower.",
                    PrintTo.OutputTab1);
            }
        }

        // OnExecution is deliberately NOT behind `#if !TESTING`. It is the trade-copy
        // path - the riskiest code in this file - and excluding it left it with zero
        // test coverage. It compiles against the NinjaTrader stubs in
        // RiskGuardAddOnTests.cs (Account.All/CreateOrder/Submit, Instrument.GetInstrument,
        // NinjaTrader.Code.Output).
        public void OnExecution(Execution exec)
        {
            if (exec == null || exec.Account == null || exec.Quantity <= 0) return;
            
            // Skip copy if order is null (cannot determine order direction safely)
            if (exec.Order == null) return;

            string acctName = exec.Account.Name;

            // Recursion Guard 1: Followers can NEVER act as Leaders (prevents copy feedback loops)
            bool isFollowerAccount;
            lock (_lock)
            {
                bool isFollowerInDirect = _relationships.Any(r => r.IsEnabled && r.FollowerAccountName.Equals(acctName, StringComparison.OrdinalIgnoreCase));
                bool isFollowerInGroups = _groups.Any(g => g.IsEnabled && g.FollowerAccounts != null && g.FollowerAccounts.Any(f => f.Equals(acctName, StringComparison.OrdinalIgnoreCase)));
                isFollowerAccount = isFollowerInDirect || isFollowerInGroups;
            }

            if (isFollowerAccount)
            {
                // P1-22: a copy coming back as a follower fill is the ONLY observation the copier
                // ever gets of what its own order actually cost. Measure it before the recursion
                // guard drops the execution.
                ObserveFollowerFill(exec);
                return;
            }

            lock (_lock)
            {
                // Recursion Guard 2: Ignore executions originated by copier placement
                if (!string.IsNullOrEmpty(exec.Order.Name) && exec.Order.Name.Contains("COPIER")) return;
                if (exec.Name != null && exec.Name.Contains("COPIER")) return;
            }

            // Redelivery Guard 3: Deduplicate exact duplicate socket redelivery of same execution ID (bounded FIFO queue)
            if (DeduplicateExecutionId(exec.ExecutionId)) return;

            // P1-22: a quarantined relationship must still be able to CLOSE the follower. Blocking
            // its exits strands it in a position the leader has already left -- the P0-5 failure
            // reached by another route. Entries stay blocked.
            OrderAction leadAction = exec.Order.OrderAction;
            bool leaderIsExiting = leadAction == OrderAction.Sell || leadAction == OrderAction.BuyToCover;

            List<CopierRelationship> activeRels =
                GetActiveRelationshipsForLeader(acctName, includeQuarantined: leaderIsExiting);

            if (activeRels.Count == 0) return;

            foreach (var rel in activeRels)
            {
                if (rel.IsQuarantined)
                {
                    NinjaTrader.Code.Output.Process(
                        $"[CopierEngine] QUARANTINE_EXIT_ALLOWED: {rel.LeaderAccountName} -> {rel.FollowerAccountName} is quarantined ({rel.QuarantineReason}), but this is an exit, so it is copied anyway.",
                        PrintTo.OutputTab1);
                }

                Account followerAcc = Account.All.FirstOrDefault(a => a.Name.Equals(rel.FollowerAccountName, StringComparison.OrdinalIgnoreCase));
                if (followerAcc == null) continue;

                bool isSimFollower = IsSimulationAccount(followerAcc);

                // SAFETY GATE: Disarmed copier MUST NOT place orders on non-Sim (live) accounts
                if (!rel.ArmedForLive && !isSimFollower)
                {
                    NinjaTrader.Code.Output.Process($"[CopierEngine] BLOCKED execution copy to live account {followerAcc.Name} (ArmedForLive=false)", PrintTo.OutputTab1);
                    continue;
                }

                // Determine target Instrument (AutoSymbolConversion e.g. NQ -> MNQ)
                Instrument targetInstrument = exec.Instrument;
                if (rel.AutoSymbolConversion && exec.Instrument != null)
                {
                    string translatedSymbolName = TranslateSymbol(exec.Instrument.FullName, rel);
                    if (!string.Equals(translatedSymbolName, exec.Instrument.FullName, StringComparison.OrdinalIgnoreCase))
                    {
                        var resolvedInst = Instrument.GetInstrument(translatedSymbolName);
                        if (resolvedInst != null)
                        {
                            targetInstrument = resolvedInst;
                        }
                    }
                }

                // RiskGuard tradeability and protection checks (outside _lock to avoid lock-ordering with RiskGuard)
                var riskGuard = RiskGuardAddOn.Instance;
                if (riskGuard != null)
                {
                    if (!riskGuard.CanTrade(acctName, exec.Instrument.FullName, "TradeCopier"))
                    {
                        NinjaTrader.Code.Output.Process($"[CopierEngine] BLOCKED execution copy: leader account {acctName} is locked for {exec.Instrument.FullName}", PrintTo.OutputTab1);
                        continue;
                    }

                    if (!riskGuard.CanTrade(followerAcc.Name, targetInstrument.FullName, "TradeCopier"))
                    {
                        NinjaTrader.Code.Output.Process($"[CopierEngine] BLOCKED execution copy: follower account {followerAcc.Name} is locked for {targetInstrument.FullName}", PrintTo.OutputTab1);
                        continue;
                    }

                    if (!isSimFollower && !riskGuard.IsGuardProtecting(followerAcc.Name))
                    {
                        NinjaTrader.Code.Output.Process($"[CopierEngine] COPY_BLOCKED_NO_GUARD: follower account {followerAcc.Name} is live but not protected by RiskGuard; skipping copy for {targetInstrument.FullName}", PrintTo.OutputTab1);
                        continue;
                    }
                }
                else
                {
                    if (!isSimFollower)
                    {
                        NinjaTrader.Code.Output.Process($"[CopierEngine] COPY_BLOCKED_NO_GUARD: RiskGuard is unavailable and follower account {followerAcc.Name} is live; skipping copy for {targetInstrument.FullName}", PrintTo.OutputTab1);
                        continue;
                    }
                }

                OrderAction leadOrderAction = leadAction;
                bool isExit = leaderIsExiting;   // computed once above; the quarantine gate uses it too

                int currentFollowerPos = 0;
                var followerPositionObj = followerAcc.Positions.FirstOrDefault(p => p.Instrument.FullName.Equals(targetInstrument.FullName, StringComparison.OrdinalIgnoreCase));
                if (followerPositionObj != null)
                {
                    currentFollowerPos = followerPositionObj.Quantity;
                }

                bool isClamped;
                int targetQty = CalculateFollowerQuantity(rel, exec.Quantity, exec.Instrument.FullName, currentFollowerPos, isExit, out isClamped);
                if (targetQty <= 0)
                {
                    if (isExit && currentFollowerPos == 0)
                    {
                        NinjaTrader.Code.Output.Process($"[CopierEngine] NO POSITION TO EXIT: Follower has no position in {targetInstrument.FullName} on account {followerAcc.Name}. Copy order skipped.", PrintTo.OutputTab1);
                    }
                    else if (isClamped)
                    {
                        NinjaTrader.Code.Output.Process($"[CopierEngine] CLAMPED TO ZERO: Follower position on {followerAcc.Name} at MaxPositionSize {rel.MaxPositionSize}. Copy order skipped.", PrintTo.OutputTab1);
                    }
                    else
                    {
                        NinjaTrader.Code.Output.Process($"[CopierEngine] SUB_MINIMUM_SKIPPED: Scaled copy quantity for {targetInstrument.FullName} is below 1 contract on account {followerAcc.Name}. Copy order skipped.", PrintTo.OutputTab1);
                    }
                    continue;
                }

                if (isClamped)
                {
                    NinjaTrader.Code.Output.Process($"[CopierEngine] POSITION CLAMP WARNING: Follower copy qty for {targetInstrument.FullName} clamped to {targetQty} (MaxPositionSize: {rel.MaxPositionSize}, CurrentPos: {currentFollowerPos}) on account {followerAcc.Name}", PrintTo.OutputTab1);
                }

                OrderAction followerAction = leadOrderAction;

                // Handle Inverse / Fade Trading (QuantityRatio < 0)
                if (rel.QuantityRatio < 0)
                {
                    if (leadOrderAction == OrderAction.Buy) followerAction = OrderAction.Sell;
                    else if (leadOrderAction == OrderAction.Sell) followerAction = OrderAction.BuyToCover;
                    else if (leadOrderAction == OrderAction.SellShort) followerAction = OrderAction.Buy;
                    else if (leadOrderAction == OrderAction.BuyToCover) followerAction = OrderAction.SellShort;
                }
                else if (isExit)
                {
                    // Align exit order action with follower's current position direction if non-zero
                    if (currentFollowerPos < 0) followerAction = OrderAction.BuyToCover;
                    else if (currentFollowerPos > 0) followerAction = OrderAction.Sell;
                }

                TimeInForce tif = (exec.Order.TimeInForce != TimeInForce.Gtc) ? exec.Order.TimeInForce : TimeInForce.Day;

                try
                {
                    Order followerOrder = followerAcc.CreateOrder(
                        targetInstrument,
                        followerAction,
                        OrderType.Market,
                        tif,
                        targetQty,
                        0,
                        0,
                        "",
                        "COPIER_FOLLOW",
                        null
                    );

                    // Submit follower order
                    if (followerOrder != null)
                    {
                        followerAcc.Submit(new[] { followerOrder });

                        // P1-22: remember what the leader paid so the follower's fill can be
                        // measured against it. Recorded only after a successful Submit -- an
                        // order that never reached the broker has no fill coming, and its entry
                        // would sit in the pending map until evicted.
                        RecordPendingCopy(followerOrder, rel, exec, targetInstrument, followerAction, isExit);
                    }
                }
                catch (Exception ex)
                {
                    NinjaTrader.Code.Output.Process($"[CopierEngine] Error placing follower order on {followerAcc.Name}: {ex.Message}", PrintTo.OutputTab1);
                }
            }
        }

    }
}
