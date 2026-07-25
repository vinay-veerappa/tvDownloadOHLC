using System;
using System.IO;
using System.Collections.Generic;
using System.Linq;

#if TESTING
using Newtonsoft.Json.Linq;
using Newtonsoft.Json;
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
        public double LatencyMs { get; set; }
        public double AvgSlippageTicks { get; set; }
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
                    DailyLossLimit = this.DailyLossLimit
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

        public List<CopierRelationship> GetActiveRelationshipsForLeader(string leaderAccount)
        {
            var result = new List<CopierRelationship>();
            if (string.IsNullOrWhiteSpace(leaderAccount)) return result;

            lock (_lock)
            {
                var direct = _relationships.Where(r => 
                    r.IsEnabled && 
                    !r.IsQuarantined && 
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
                        
                        if (directRel != null && directRel.IsQuarantined)
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
            string symbol = rawSymbol.Split(' ')[0].ToUpper();

            // 1. Check relationship custom symbol overrides first
            if (rel != null && rel.CustomSymbolMappings != null && rel.CustomSymbolMappings.TryGetValue(symbol, out var customTarget))
            {
                if (!string.IsNullOrEmpty(customTarget))
                {
                    return rawSymbol.Replace(symbol, customTarget.ToUpper());
                }
            }

            // 2. Bidirectional Mini <-> Micro Default Translation Matrix
            if (rel == null || rel.AutoSymbolConversion)
            {
                // Mini -> Micro
                if (symbol == "NQ") return rawSymbol.Replace("NQ", "MNQ");
                if (symbol == "ES") return rawSymbol.Replace("ES", "MES");
                if (symbol == "YM") return rawSymbol.Replace("YM", "MYM");
                if (symbol == "CL") return rawSymbol.Replace("CL", "MCL");
                if (symbol == "GC") return rawSymbol.Replace("GC", "MGC");
                if (symbol == "RTY") return rawSymbol.Replace("RTY", "M2K");

                // Micro -> Mini
                if (symbol == "MNQ") return rawSymbol.Replace("MNQ", "NQ");
                if (symbol == "MES") return rawSymbol.Replace("MES", "ES");
                if (symbol == "MYM") return rawSymbol.Replace("MYM", "YM");
                if (symbol == "MCL") return rawSymbol.Replace("MCL", "CL");
                if (symbol == "MGC") return rawSymbol.Replace("MGC", "GC");
                if (symbol == "M2K") return rawSymbol.Replace("M2K", "RTY");
            }

            return rawSymbol;
        }

        public int CalculateFollowerQuantity(CopierRelationship rel, int leaderQty, string rawSymbol, int currentFollowerPosition, bool isExit, out bool isClamped)
        {
            isClamped = false;
            if (leaderQty <= 0) return 0;
            if (rel.FixedLotMode || rel.SizingMode == CopierSizingMode.FixedLot) return isExit ? leaderQty : rel.FixedLotSize;

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

            int rawCopyQty = (int)Math.Max(1, Math.Round(leaderQty * absRatio * symbolMultiplier));
            if (isExit) return rawCopyQty;

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
                                        IsQuarantined = jObj["IsQuarantined"] != null ? (bool)jObj["IsQuarantined"] : (jObj["isQuarantined"] != null ? (bool)jObj["isQuarantined"] : false)
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

#if !TESTING
        public void OnExecution(Execution exec)
        {
            if (exec == null || exec.Account == null || exec.Quantity <= 0) return;
            
            // Skip copy if order is null (cannot determine order direction safely)
            if (exec.Order == null) return;

            string acctName = exec.Account.Name;

            lock (_lock)
            {
                // Recursion Guard 1: Followers can NEVER act as Leaders (prevents copy feedback loops)
                bool isFollowerInDirect = _relationships.Any(r => r.IsEnabled && r.FollowerAccountName.Equals(acctName, StringComparison.OrdinalIgnoreCase));
                bool isFollowerInGroups = _groups.Any(g => g.IsEnabled && g.FollowerAccounts != null && g.FollowerAccounts.Any(f => f.Equals(acctName, StringComparison.OrdinalIgnoreCase)));
                if (isFollowerInDirect || isFollowerInGroups)
                {
                    return;
                }

                // Recursion Guard 2: Ignore executions originated by copier placement
                if (!string.IsNullOrEmpty(exec.Order.Name) && exec.Order.Name.Contains("COPIER")) return;
                if (exec.Name != null && exec.Name.Contains("COPIER")) return;
            }

            // Redelivery Guard 3: Deduplicate exact duplicate socket redelivery of same execution ID (bounded FIFO queue)
            if (DeduplicateExecutionId(exec.ExecutionId)) return;

            List<CopierRelationship> activeRels = GetActiveRelationshipsForLeader(acctName);

            if (activeRels.Count == 0) return;

            foreach (var rel in activeRels)
            {
                Account followerAcc = Account.All.FirstOrDefault(a => a.Name.Equals(rel.FollowerAccountName, StringComparison.OrdinalIgnoreCase));
                if (followerAcc == null) continue;

                bool isSimFollower = followerAcc.Name.StartsWith("Sim", StringComparison.OrdinalIgnoreCase);

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

                OrderAction leadOrderAction = exec.Order.OrderAction;
                bool isExit = leadOrderAction == OrderAction.Sell || leadOrderAction == OrderAction.BuyToCover;

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
                    if (isClamped)
                    {
                        NinjaTrader.Code.Output.Process($"[CopierEngine] CLAMPED TO ZERO: Follower position on {followerAcc.Name} at MaxPositionSize {rel.MaxPositionSize}. Copy order skipped.", PrintTo.OutputTab1);
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
                    }
                }
                catch (Exception ex)
                {
                    NinjaTrader.Code.Output.Process($"[CopierEngine] Error placing follower order on {followerAcc.Name}: {ex.Message}", PrintTo.OutputTab1);
                }
            }
        }
#endif
    }
}
