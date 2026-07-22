using System;
using System.Collections.Generic;

namespace NinjaTrader.NinjaScript.AddOns
{
    public enum AtmStrategyType { FixedTicks, SwingPoint, AtrAdaptive, DrawdownShield, ScaledRunner }

    public class AtmStrategyConfig
    {
        public string Name { get; set; } = "PropFirm_Standard";
        public AtmStrategyType Type { get; set; } = AtmStrategyType.DrawdownShield;
        public double AtrMultiplierSL { get; set; } = 1.5;
        public double AtrMultiplierTP { get; set; } = 2.5;
        public int SwingLookbackBars { get; set; } = 5;
        public int SwingBufferTicks { get; set; } = 4;
        public int BreakevenTriggerTicks { get; set; } = 12;
        public int BreakevenOffsetTicks { get; set; } = 2;
        public double PartialProfitPct { get; set; } = 0.50;
    }

    public class DynamicAtmManager
    {
        public bool ShouldTriggerBreakeven(AtmStrategyConfig config, double entryPrice, double currentPrice, bool isLong, double tickSize)
        {
            if (config.Type != AtmStrategyType.DrawdownShield && config.Type != AtmStrategyType.ScaledRunner)
                return false;

            double diff = isLong ? (currentPrice - entryPrice) : (entryPrice - currentPrice);
            double ticksGain = diff / tickSize;

            return ticksGain >= config.BreakevenTriggerTicks;
        }

        public double CalculateBreakevenStopPrice(double entryPrice, bool isLong, double tickSize, int offsetTicks)
        {
            double offset = offsetTicks * tickSize;
            return isLong ? (entryPrice + offset) : (entryPrice - offset);
        }

        public double CalculateAtrStopPrice(double entryPrice, double atrValue, double atrMultiplier, bool isLong)
        {
            double dist = atrValue * atrMultiplier;
            return isLong ? (entryPrice - dist) : (entryPrice + dist);
        }
    }
}

