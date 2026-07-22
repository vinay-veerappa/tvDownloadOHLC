using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

namespace NinjaTrader.NinjaScript.AddOns
{
    public enum CopierExecutionMode { Executions, Orders }

    public class CopierRelationship
    {
        public string Id { get; set; } = Guid.NewGuid().ToString();
        public string LeaderAccountName { get; set; } = "Sim101";
        public string FollowerAccountName { get; set; } = "SimCopy2";
        public bool IsEnabled { get; set; } = true;
        public CopierExecutionMode Mode { get; set; } = CopierExecutionMode.Executions;
        public double QuantityRatio { get; set; } = 1.0;
        public bool FixedLotMode { get; set; } = false;
        public int FixedLotSize { get; set; } = 1;
        public bool AutoSymbolConversion { get; set; } = true;
        public int MaxPositionSize { get; set; } = 10;
        public double DailyLossLimit { get; set; } = 1000.0;
        public bool IsQuarantined { get; set; } = false;
        public string QuarantineReason { get; set; }
    }

    public class TradeCopierEngine
    {
        private readonly List<CopierRelationship> _relationships = new List<CopierRelationship>();
        private readonly object _lock = new object();

        public void AddRelationship(CopierRelationship rel)
        {
            lock (_lock)
            {
                _relationships.Add(rel);
            }
        }

        public List<CopierRelationship> GetRelationships()
        {
            lock (_lock)
            {
                return new List<CopierRelationship>(_relationships);
            }
        }

        public string TranslateSymbol(string rawSymbol)
        {
            if (string.IsNullOrEmpty(rawSymbol)) return rawSymbol;
            string symbol = rawSymbol.Split(' ')[0].ToUpper();
            if (symbol == "NQ") return rawSymbol.Replace("NQ", "MNQ");
            if (symbol == "ES") return rawSymbol.Replace("ES", "MES");
            if (symbol == "YM") return rawSymbol.Replace("YM", "MYM");
            if (symbol == "CL") return rawSymbol.Replace("CL", "MCL");
            if (symbol == "GC") return rawSymbol.Replace("GC", "MGC");
            return rawSymbol;
        }

        public int CalculateFollowerQuantity(CopierRelationship rel, int leaderQty, string rawSymbol)
        {
            if (rel.FixedLotMode) return rel.FixedLotSize;

            double ratio = rel.QuantityRatio;
            string symbol = rawSymbol.Split(' ')[0].ToUpper();

            // Multiplier for Mini -> Micro conversion
            double symbolMultiplier = 1.0;
            if (rel.AutoSymbolConversion)
            {
                if (symbol == "NQ" || symbol == "ES" || symbol == "YM" || symbol == "CL" || symbol == "GC")
                {
                    symbolMultiplier = 10.0;
                }
            }

            int qty = (int)Math.Round(leaderQty * ratio * symbolMultiplier);
            return Math.Max(1, Math.Min(rel.MaxPositionSize, qty));
        }
    }
}

