//Disclosure
//Futures trading and strategy trading involves substantial risk and the potential for loss of capital. 
//The performance results of a trading strategy developed on the NinjaTrader platform may not be indicative of future real-time trading performance. 
//Sample strategies and indicators provided by NinjaTrader, LLC are designed to teach strategy trading and development concepts.
//All NinjaScript code contained herein is provided by NinjaTrader, LLC and is for educational and demonstrational purposes only.
//You alone are responsible for the trading decisions that you make.

//Developed September 2025
//PAX30OpeningRange : Indicator = Version 1.1
//Copyright(c) 2025 

#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Gui.SuperDom;
using NinjaTrader.Gui.Tools;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Indicators.PAX
{
    public class PAX30OpeningRange : Indicator
    {
        // Constants - Protected Values
        private const int DAYS_TO_DISPLAY = 8;  // Fixed number of days to display
		private DateTime cutoffStartDate = DateTime.MinValue;
		private const int EXTRA_DAYS = 2; // your “+2”
        
        // ORB tracking variables
        private double orbHigh;
        private double orbLow;
        private double orbMid;
		private int ORBSeconds;
        private bool inOrbPeriod = false;
        private DateTime currentOrbDate = DateTime.MinValue;
        private DateTime lastProcessTime = DateTime.MinValue; // Track last processed bar time

        // Add these near your other private fields
        private Dictionary<DateTime, Dictionary<int, DateTime>> upperLevelStartTimes = new Dictionary<DateTime, Dictionary<int, DateTime>>();
        private Dictionary<DateTime, Dictionary<int, DateTime>> lowerLevelStartTimes = new Dictionary<DateTime, Dictionary<int, DateTime>>();
        
        // Real-time tracking
        private DateTime realtimeOrbDate = DateTime.MinValue;
        private Dictionary<string, DateTime> activeLabels = new Dictionary<string, DateTime>();
        
        // Storage for completed ORBs - using struct for better memory efficiency
        private struct OrbData
        {
            public double High;
            public double Low;
            public double Mid;
            public bool IsToday;
            
            public OrbData(double high, double low, double mid, bool isToday)
            {
                High = high;
                Low = low;
                Mid = mid;
                IsToday = isToday;
            }
        }
        
        private Dictionary<DateTime, OrbData> orbValues = new Dictionary<DateTime, OrbData>();
        private Dictionary<DateTime, List<double>> upperLevels = new Dictionary<DateTime, List<double>>();
        private Dictionary<DateTime, List<double>> lowerLevels = new Dictionary<DateTime, List<double>>();
        
        // Track which levels have been drawn to avoid duplicates
        private HashSet<string> drawnLevels = new HashSet<string>();
        
        // Timeframe validation
        private bool isValidTimeframe = true;
        
        // Cache for performance - marked as non-serialized
        [XmlIgnore]
        private SimpleFont cachedFont;
        
        // Track last cleanup time to avoid excessive cleanup calls
        private DateTime lastCleanupTime = DateTime.MinValue;
        
        #region Properties
        // TimeSpan properties need string surrogates for serialization
        [XmlIgnore]
        [Browsable(false)]
        public TimeSpan ORBStart { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "ORB LocaL Start Time", Order = 2, GroupName = "ORB Parameters")]
        [PropertyEditor("NinjaTrader.Gui.Tools.TimeEditor")]
        [XmlElement("ORBStart")]
        public string ORBStartSerialize
        {
            get { return ORBStart.ToString(); }
            set { ORBStart = TimeSpan.Parse(value); }
        }

        [XmlIgnore]
        [Browsable(false)]
        public TimeSpan ORBEndPlot { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "ORB LocaL Line End Time", Order = 5, GroupName = "ORB Parameters")]
        [PropertyEditor("NinjaTrader.Gui.Tools.TimeEditor")]
        [XmlElement("ORBEndPlot")]
        public string ORBEndPlotSerialize
        {
            get { return ORBEndPlot.ToString(); }
            set { ORBEndPlot = TimeSpan.Parse(value); }
        }
        
        [NinjaScriptProperty]
        [Display(Name = "Text Vert Offset ", Order = 7, GroupName = "xyDisplay Settings")]
        [Range(-50, 50)]
        public int TextvertPixels  { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Text Horz Offset", Order = 8, GroupName = "xyDisplay Settings")]
        [Range(-100, 100)]
        public int TextHorzOffset { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Font Size", Order = 9, GroupName = "xyDisplay Settings")]
        [Range(6, 36)]
        public int FontSize { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Bold Font", Order = 10, GroupName = "xyDisplay Settings")]
        public bool BoldFont { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Price Label Prefix", Order = 11, GroupName = "xyDisplay Parameters")]
        public string LabelPrefix { get; set; }
        
        [XmlIgnore]
        [NinjaScriptProperty]
        [Display(Name = "High Line Color", Order = 12, GroupName = "xyORB Colors")]
        public Brush HighLineColor { get; set; }
        
        [Browsable(false)]
        [XmlElement("HighLineColorSerializable")]
        public string HighLineColorSerializable
        {
            get { return Serialize.BrushToString(HighLineColor); }
            set { HighLineColor = Serialize.StringToBrush(value); }
        }
        
        [XmlIgnore]
        [NinjaScriptProperty]
        [Display(Name = "Low Line Color", Order = 13, GroupName = "xyORB Colors")]
        public Brush LowLineColor { get; set; }
        
        [Browsable(false)]
        [XmlElement("LowLineColorSerializable")]
        public string LowLineColorSerializable
        {
            get { return Serialize.BrushToString(LowLineColor); }
            set { LowLineColor = Serialize.StringToBrush(value); }
        }
        
        [XmlIgnore]
        [NinjaScriptProperty]
        [Display(Name = "Mid Line Color", Order = 14, GroupName = "xyORB Colors")]
        public Brush MidLineColor { get; set; }
        
        [Browsable(false)]
        [XmlElement("MidLineColorSerializable")]
        public string MidLineColorSerializable
        {
            get { return Serialize.BrushToString(MidLineColor); }
            set { MidLineColor = Serialize.StringToBrush(value); }
        }
        
        [NinjaScriptProperty]
        [Display(Name = "High/Low Line Width", Order = 15, GroupName = "xyDisplay Parameters")]
        [Range(1, 10)]
        public int MainLineWidth { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Mid Line Width", Order = 16, GroupName = "xyDisplay Parameters")]
        [Range(1, 10)]
        public int MidLineWidth { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Levels Line Width", Order = 17, GroupName = "xyDisplay Parameters")]
        [Range(1, 10)]
        public int LevelsLineWidth { get; set; }
        
        [NinjaScriptProperty]
        [Display(Name = "Show Mid Line", Order = 18, GroupName = "xyDisplay Parameters")]
        public bool ShowMid { get; set; }
        #endregion

        /// <summary>
        /// Returns the appropriate level factor based on the instrument symbol
        /// ES/MES = 15 points, NQ/MNQ = 65 points, all others = 0 (no levels)
        /// </summary>
        private double GetMarketLevelFactor()
        {
            if (Instrument == null || Instrument.MasterInstrument == null)
                return 0;
                
            string sym = Instrument.MasterInstrument.Name.ToUpper();
            
            if (sym.Contains("ES") || sym.Contains("MES"))
                return 15;
            else if (sym.Contains("NQ") || sym.Contains("MNQ"))
                return 65;
            else
                return 0;  // No levels for other symbols
        }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "Multi-timeframe 30 second ORB with dynamic levels. Symbol-specific level points. Optimized drawing with real-time label movement.";
                Name = "PAX30OpeningRange";
                IsOverlay = true;
                Calculate = Calculate.OnBarClose;
                
                // Initialize default values
                ORBStart = new TimeSpan(9, 30, 0);  // Central Time
                ORBStartSerialize = ORBStart.ToString();
                ORBSeconds = 30;
                ORBEndPlot = new TimeSpan(17, 0, 0);
                ORBEndPlotSerialize = ORBEndPlot.ToString();
                TextvertPixels = 17;
                TextHorzOffset = 5;
                FontSize = 13;
                BoldFont = false;
				ORBSeconds = 30;
                LabelPrefix = "PAXOR";
                HighLineColor = Brushes.DeepSkyBlue;
                LowLineColor = Brushes.OrangeRed;
                MidLineColor = Brushes.Gold;
                MainLineWidth = 3;
                MidLineWidth = 2;
                LevelsLineWidth = 3;
                ShowMid = false;
            }
            else if (State == State.Configure)
            {
                // Check if we're on a Minute or Second chart ONLY
                if (BarsPeriod.BarsPeriodType != BarsPeriodType.Minute && 
                    BarsPeriod.BarsPeriodType != BarsPeriodType.Second)
                {
                    isValidTimeframe = false;
                    Name = "";
                    Calculate = Calculate.OnBarClose;
                    return;
                }
                else
                {
                    // Only add 1-second data series for valid charts
                    AddDataSeries(BarsPeriodType.Second, 1);
                    Name = "";
                }
            }
            else if (State == State.DataLoaded)
            {
                // Re-initialize collections in case of deserialization
                if (activeLabels == null)
                    activeLabels = new Dictionary<string, DateTime>();
                if (orbValues == null)
                    orbValues = new Dictionary<DateTime, OrbData>();
                if (upperLevels == null)
                    upperLevels = new Dictionary<DateTime, List<double>>();
                if (lowerLevels == null)
                    lowerLevels = new Dictionary<DateTime, List<double>>();
                if (drawnLevels == null)
                    drawnLevels = new HashSet<string>();
                
                // Create/recreate font
                cachedFont = new SimpleFont("Arial", FontSize) { Bold = BoldFont };
                
                // Display warning message if on invalid timeframe
                if (!isValidTimeframe)
                {
                    string timeframeName = GetTimeframeName();
                    
                    Draw.TextFixed(this, "PAXORBWarning", 
                        " PAX30OR only supports Minute and Second charts - Disabled on " + timeframeName + " Charts ", 
                        TextPosition.Center, 
                        Brushes.White, 
                        new SimpleFont("Arial", 16) { Bold = true },
                        Brushes.Transparent, 
                        Brushes.DimGray, 
                        100);
                }
				    // Anchor = last primary-series bar date at load
				    DateTime anchor = BarsArray[0].GetTime(BarsArray[0].Count - 1).Date;
				
				    int keepDays = DAYS_TO_DISPLAY + EXTRA_DAYS; // inclusive window length
				    // Inclusive window: [anchor-(keepDays-1) ... anchor]
				    cutoffStartDate = anchor.AddDays(-(keepDays - 1));
				            }
            else if (State == State.Terminated)
            {
                // Clean up all collections
                if (activeLabels != null)
                    activeLabels.Clear();
                if (orbValues != null)
                    orbValues.Clear();
                if (upperLevels != null)
                {
                    foreach (var list in upperLevels.Values)
                        list.Clear();
                    upperLevels.Clear();
                }
                if (lowerLevels != null)
                {
                    foreach (var list in lowerLevels.Values)
                        list.Clear();
                    lowerLevels.Clear();
                }
                if (drawnLevels != null)
                    drawnLevels.Clear();
            }
        }
        
        /// <summary>
        /// Returns a user-friendly name for the current chart timeframe
        /// </summary>
        private string GetTimeframeName()
        {
            switch (BarsPeriod.BarsPeriodType)
            {
                case BarsPeriodType.Tick: return "Tick";
                case BarsPeriodType.Volume: return "Volume";
                case BarsPeriodType.Range: return "Range";
                case BarsPeriodType.Renko: return "Renko";
                case BarsPeriodType.Day: return "Daily";
                case BarsPeriodType.Week: return "Weekly";
                case BarsPeriodType.Month: return "Monthly";
                case BarsPeriodType.Year: return "Yearly";
                default: return BarsPeriod.BarsPeriodType.ToString();
            }
        }
        
        /// <summary>
        /// Rounds a value to the nearest tick size for the instrument
        /// </summary>
        private double RoundToNearestTick(double value)
        {
            if (double.IsNaN(value) || double.IsInfinity(value))
                return double.NaN;
                
            double tickSize = TickSize;
            return Math.Round(value / tickSize) * tickSize;
        }
        
        /// <summary>
        /// Calculates the label time with horizontal offset based on bar interval
        /// </summary>
		private DateTime GetLabelTimeWithOffset(DateTime baseTime, bool isRealtime)
		{
		    if (TextHorzOffset == 0)
		        return baseTime;
		        
		    try
		    {
		        TimeSpan barInterval = TimeSpan.Zero;
		        
		        // Always use the primary chart's timeframe (BarsArray[0])
		        // When we're on the 1-second series, BarsPeriod would give us 1-second
		        // but we want the primary chart's period for offset calculation
		        var chartPeriod = BarsArray != null && BarsArray.Length > 0 && BarsArray[0] != null 
		            ? BarsArray[0].BarsPeriod 
		            : BarsPeriod;
		        
		        switch (chartPeriod.BarsPeriodType)
		        {
		            case BarsPeriodType.Minute:
		                barInterval = TimeSpan.FromMinutes(chartPeriod.Value * TextHorzOffset);
		                break;
		                
		            case BarsPeriodType.Second:
		                barInterval = TimeSpan.FromSeconds(chartPeriod.Value * TextHorzOffset);
		                break;
		                
		            default:
		                return baseTime;
		        }
		        
		        return baseTime.Add(barInterval);
		    }
		    catch
		    {
		        return baseTime;
		    }
		}
    
        protected override void OnBarUpdate()
        {
            if (!isValidTimeframe || CurrentBar < 1)
                return;
            
            // Handle label movement on primary series ONLY on bar close
            if (BarsInProgress == 0)
            {
                // Only move labels on a new bar, not on every tick
                if (IsFirstTickOfBar && activeLabels.Count > 0)
                {
                    MoveActiveLabels();
                    // Also redraw real-time ORB to extend lines
                    if (orbValues.ContainsKey(realtimeOrbDate))
                    {
                        DrawOrbForDay(realtimeOrbDate, true);
                    }
                }
                return; // Don't process ORB logic on primary series
            }
            
            // Only process ORB logic on the 1-second data series
            if (BarsInProgress != 1)
                return;
			
			DateTime currentDate = Time[0].Date;
			if (currentDate < cutoffStartDate)
			    return; // do nothing before the cutoff window
            
            // Add performance optimization to avoid processing same bar multiple times
            DateTime currentTime = Time[0];
            if (currentTime == lastProcessTime)
                return;
            lastProcessTime = currentTime;
            
            currentDate = currentTime.Date;
            TimeSpan currentTimeOfDay = currentTime.TimeOfDay;
            TimeSpan orbEndTimeOfDay = ORBStart.Add(TimeSpan.FromSeconds(ORBSeconds));
            
            // Improve ORB initialization logic
            if (currentDate != currentOrbDate && !orbValues.ContainsKey(currentDate))
            {
                bool isToday = IsCurrentTradingDay(currentDate);
                
                // Check if we should start new ORB
                if (currentTimeOfDay >= ORBStart && currentTimeOfDay <= orbEndTimeOfDay)
                {
                    // Initialize new ORB
                    currentOrbDate = currentDate;
                    orbHigh = High[0];
                    orbLow = Low[0];
                    inOrbPeriod = true;
                }
                // Only create "catch-up" ORB if we're past the period but still in trading hours
                else if (currentTimeOfDay > orbEndTimeOfDay && currentTimeOfDay <= ORBEndPlot)
                {
                    // This is a fallback for when we start the indicator after ORB period
                    currentOrbDate = currentDate;
                    orbHigh = High[0];
                    orbLow = Low[0];
                    orbMid = RoundToNearestTick(orbLow + ((orbHigh - orbLow) * 0.5));
                    
                    orbValues[currentDate] = new OrbData(orbHigh, orbLow, orbMid, isToday);
                    upperLevels[currentDate] = new List<double>();
                    lowerLevels[currentDate] = new List<double>();
                    
                    double levelFactor = GetMarketLevelFactor();
                    if (levelFactor > 0)
                    {
                        upperLevels[currentDate].Add(RoundToNearestTick(orbHigh + levelFactor));
                        lowerLevels[currentDate].Add(RoundToNearestTick(orbLow - levelFactor));
                    }
                    
                    DrawOrbForDay(currentDate, isToday);
                    
                    if (isToday)
                        realtimeOrbDate = currentDate;
                    
                    inOrbPeriod = false;
                }
            }
            // Update ORB if we're currently tracking one
            else if (inOrbPeriod && currentDate == currentOrbDate)
            {
                // Use > instead of >= for end time check
                if (currentTimeOfDay <= orbEndTimeOfDay)
                {
                    // Update high/low during ORB period
                    if (High[0] > orbHigh) 
                        orbHigh = High[0];
                    if (Low[0] < orbLow) 
                        orbLow = Low[0];
                }
                else // currentTimeOfDay > orbEndTimeOfDay
                {
                    // Finalize the ORB
                    orbMid = RoundToNearestTick(orbLow + ((orbHigh - orbLow) * 0.5));
                    bool isToday = IsCurrentTradingDay(currentDate);
                    orbValues[currentDate] = new OrbData(orbHigh, orbLow, orbMid, isToday);
                    
                    upperLevels[currentDate] = new List<double>();
                    lowerLevels[currentDate] = new List<double>();
                    
                    double levelFactor = GetMarketLevelFactor();
                    if (levelFactor > 0)
                    {
                        upperLevels[currentDate].Add(RoundToNearestTick(orbHigh + levelFactor));
                        lowerLevels[currentDate].Add(RoundToNearestTick(orbLow - levelFactor));
                    }
                    
                    DrawOrbForDay(currentDate, isToday);
                    
                    if (isToday)
                        realtimeOrbDate = currentDate;
                    
                    inOrbPeriod = false;
                }
            }
            
            // Check for level breaks only after ORB completes and during trading hours
            if (!inOrbPeriod && currentTimeOfDay > orbEndTimeOfDay && currentTimeOfDay <= ORBEndPlot)
            {
                CheckAndAddDynamicLevels(currentDate, currentTime);
            }
            
            // Clean up old data periodically (every hour)
            if (currentTime.Subtract(lastCleanupTime).TotalHours >= 1)
            {
                CleanupOldData(currentDate);
                lastCleanupTime = currentTime;
            }
        }
        
        /// <summary>
        /// Determines if a given date is the current trading day
        /// </summary>
        private bool IsCurrentTradingDay(DateTime date)
        {
            // Simple and reliable method to determine if this is today
            // This works well for most use cases and avoids session complexity
            DateTime now = Core.Globals.Now;
            
            // For futures and forex that trade overnight, we need to consider
            // that the trading day might span two calendar days
            // This simple approach works for most instruments
            return date.Date == now.Date;
        }
        
        /// <summary>
        /// Draws all ORB lines and labels for a specific day
        /// </summary>
        private void DrawOrbForDay(DateTime orbDate, bool isRealtime)
        {
            if (!orbValues.ContainsKey(orbDate))
                return;
                
            var orbData = orbValues[orbDate];
            double dayHigh = orbData.High;
            double dayLow = orbData.Low;
            double dayMid = orbData.Mid;
            
            string dateStr = orbDate.ToString("yyyyMMdd");
            
            // Calculate line times
            DateTime lineStart = orbDate.Add(ORBStart.Add(TimeSpan.FromSeconds(ORBSeconds)));
            DateTime maxEndTime = orbDate.Add(ORBEndPlot);
            DateTime lineEnd;
            DateTime labelTime;
            
            if (isRealtime)
            {
                // For real-time: lines extend to current bar, labels just before current bar
                DateTime currentTime = Times[0].Count > 0 ? Times[0][0] : lineStart;
                
                // Line ends at current time or max end time, whichever is earlier
                lineEnd = currentTime < maxEndTime ? currentTime : maxEndTime;
                
                // Labels positioned at current time
                labelTime = currentTime < maxEndTime ? currentTime : maxEndTime;
            }
            else
            {
                // For historical: lines and labels go to ORBEndPlot
                lineEnd = maxEndTime;
                labelTime = maxEndTime;
            }
            
            // Apply horizontal offset to label time
            labelTime = GetLabelTimeWithOffset(labelTime, isRealtime);
            
            try
            {
                // Draw ORB high line and label
                string highLineKey = "PAX_HighLine_" + dateStr;
                Draw.Line(this, highLineKey, true, lineStart, dayHigh, lineEnd, dayHigh, 
                    HighLineColor, DashStyleHelper.Solid, MainLineWidth);
                
                string highLabelKey = "PAX_HighLabel_" + dateStr;
                Draw.Text(this, highLabelKey, true, LabelPrefix + " " + dayHigh.ToString("F2"), 
                    labelTime, dayHigh, TextvertPixels, HighLineColor, cachedFont,
                    TextAlignment.Left, Brushes.Transparent, Brushes.Transparent, 0);
                
                if (isRealtime)
                    activeLabels[highLabelKey] = labelTime;
            }
            catch (Exception ex)
            {
                // Silent error handling - no prints in production
            }
            
            try
            {
                // Draw ORB low line and label
                string lowLineKey = "PAX_LowLine_" + dateStr;
                Draw.Line(this, lowLineKey, true, lineStart, dayLow, lineEnd, dayLow, 
                    LowLineColor, DashStyleHelper.Solid, MainLineWidth);
                
                string lowLabelKey = "PAX_LowLabel_" + dateStr;
                Draw.Text(this, lowLabelKey, true, LabelPrefix + " " + dayLow.ToString("F2"), 
                    labelTime, dayLow, TextvertPixels, LowLineColor, cachedFont,
                    TextAlignment.Left, Brushes.Transparent, Brushes.Transparent, 0);
                
                if (isRealtime)
                    activeLabels[lowLabelKey] = labelTime;
            }
            catch (Exception ex)
            {
                // Silent error handling - no prints in production
            }
            
            // Draw mid line if enabled
            if (ShowMid)
            {
                string midLineKey = "PAX_MidLine_" + dateStr;
                Draw.Line(this, midLineKey, true, lineStart, dayMid, lineEnd, dayMid, 
                    MidLineColor, DashStyleHelper.Solid, MidLineWidth);
                
                string midLabelKey = "PAX_MidLabel_" + dateStr;
                Draw.Text(this, midLabelKey, true, LabelPrefix + " MID " + dayMid.ToString("F2"), 
                    labelTime, dayMid, TextvertPixels, MidLineColor, cachedFont,
                    TextAlignment.Left, Brushes.Transparent, Brushes.Transparent, 0);
                
                if (isRealtime)
                    activeLabels[midLabelKey] = labelTime;
            }
            
            // Draw initial target levels based on symbol
            double levelFactor = GetMarketLevelFactor();
            if (levelFactor > 0 && upperLevels.ContainsKey(orbDate) && lowerLevels.ContainsKey(orbDate))
            {
                // Draw first upper level
                if (upperLevels[orbDate].Count > 0)
                {
                    double upperLevel = upperLevels[orbDate][0];
                    string upperLineKey = "PAX_UpperLevel_" + dateStr + "_0";
                    Draw.Line(this, upperLineKey, true, lineStart, upperLevel, lineEnd, upperLevel, 
                        HighLineColor, DashStyleHelper.Dash, LevelsLineWidth);
                    
                    string upperLabelKey = "PAX_UpperLabel_" + dateStr + "_0";
                    string upperLabelText = LabelPrefix + " " + upperLevel.ToString("F2");
                        
                    Draw.Text(this, upperLabelKey, true, upperLabelText, 
                        labelTime, upperLevel, TextvertPixels, HighLineColor, cachedFont,
                        TextAlignment.Left, Brushes.Transparent, Brushes.Transparent, 0);
                    
                    if (isRealtime)
                        activeLabels[upperLabelKey] = labelTime;
                }
                
                // Draw first lower level
                if (lowerLevels[orbDate].Count > 0)
                {
                    double lowerLevel = lowerLevels[orbDate][0];
                    string lowerLineKey = "PAX_LowerLevel_" + dateStr + "_0";
                    Draw.Line(this, lowerLineKey, true, lineStart, lowerLevel, lineEnd, lowerLevel, 
                        LowLineColor, DashStyleHelper.Dash, LevelsLineWidth);
                    
                    string lowerLabelKey = "PAX_LowerLabel_" + dateStr + "_0";
                    string lowerLabelText = LabelPrefix + " " + lowerLevel.ToString("F2");
                        
                    Draw.Text(this, lowerLabelKey, true, lowerLabelText, 
                        labelTime, lowerLevel, TextvertPixels, LowLineColor, cachedFont,
                        TextAlignment.Left, Brushes.Transparent, Brushes.Transparent, 0);
                    
                    if (isRealtime)
                        activeLabels[lowerLabelKey] = labelTime;
                }
            }
        }
        
        /// <summary>
        /// Checks for price breaks and adds dynamic levels when appropriate
        /// </summary>
        private void CheckAndAddDynamicLevels(DateTime currentDate, DateTime currentTime)
        {
            double levelFactor = GetMarketLevelFactor();
            if (!orbValues.ContainsKey(currentDate) || levelFactor <= 0)
                return;
                
            if (!upperLevels.ContainsKey(currentDate) || !lowerLevels.ContainsKey(currentDate))
                return;
                
            var currentUpperLevels = upperLevels[currentDate];
            var currentLowerLevels = lowerLevels[currentDate];
            
            if (currentUpperLevels.Count > 0 && currentLowerLevels.Count > 0)
            {
                double highestUpperLevel = currentUpperLevels[currentUpperLevels.Count - 1];
                double lowestLowerLevel = currentLowerLevels[currentLowerLevels.Count - 1];
                
                string dateStr = currentDate.ToString("yyyyMMdd");
                DateTime maxEndTime = currentDate.Add(ORBEndPlot);
                bool isRealtime = orbValues[currentDate].IsToday;
                
                // Determine line end based on whether it's real-time
                DateTime lineEnd = isRealtime ? currentTime : maxEndTime;
                
                // Check if High crosses above the highest upper level
                if (High[0] > highestUpperLevel)
                {
                    double newUpperLevel = RoundToNearestTick(highestUpperLevel + levelFactor);
                    int levelIndex = currentUpperLevels.Count;
                    
                    // Check if we haven't drawn this level yet
                    string levelKey = "PAX_UpperLevel_" + dateStr + "_" + levelIndex;
                    if (!drawnLevels.Contains(levelKey))
                    {
                        currentUpperLevels.Add(newUpperLevel);
                        drawnLevels.Add(levelKey);
                        
                        // Track when this level was created
                        if (!upperLevelStartTimes.ContainsKey(currentDate))
                            upperLevelStartTimes[currentDate] = new Dictionary<int, DateTime>();
                        upperLevelStartTimes[currentDate][levelIndex] = currentTime;
                        
                        try
                        {
                            // Draw the new level line from current time (when triggered)
                            Draw.Line(this, levelKey, true, currentTime, newUpperLevel, lineEnd, newUpperLevel, 
                                HighLineColor, DashStyleHelper.Dash, LevelsLineWidth);
                            
                            // For historical days, position label at line end (maxEndTime)
                            // For real-time days, position label at current time
                            DateTime labelTime = isRealtime ? currentTime : maxEndTime;
                            labelTime = GetLabelTimeWithOffset(labelTime, isRealtime);
                            
                            string labelKey = "PAX_UpperLabel_" + dateStr + "_" + levelIndex;
                            Draw.Text(this, labelKey, true, 
                                LabelPrefix + " " + newUpperLevel.ToString("F2"), 
                                labelTime, newUpperLevel, TextvertPixels, HighLineColor, cachedFont,
                                TextAlignment.Left, Brushes.Transparent, Brushes.Transparent, 0);
                            
                            if (isRealtime)
                                activeLabels[labelKey] = labelTime;
                        }
                        catch (Exception ex)
                        {
                            // Silent error handling - no prints in production
                        }
                    }
                }
                
                // Check if Low crosses below the lowest lower level
                if (Low[0] < lowestLowerLevel)
                {
                    double newLowerLevel = RoundToNearestTick(lowestLowerLevel - levelFactor);
                    int levelIndex = currentLowerLevels.Count;
                    
                    // Check if we haven't drawn this level yet
                    string levelKey = "PAX_LowerLevel_" + dateStr + "_" + levelIndex;
                    if (!drawnLevels.Contains(levelKey))
                    {
                        currentLowerLevels.Add(newLowerLevel);
                        drawnLevels.Add(levelKey);
                        
                        // Track when this level was created
                        if (!lowerLevelStartTimes.ContainsKey(currentDate))
                            lowerLevelStartTimes[currentDate] = new Dictionary<int, DateTime>();
                        lowerLevelStartTimes[currentDate][levelIndex] = currentTime;
                        
                        try
                        {
                            // Draw the new level line from current time (when triggered)
                            Draw.Line(this, levelKey, true, currentTime, newLowerLevel, lineEnd, newLowerLevel, 
                                LowLineColor, DashStyleHelper.Dash, LevelsLineWidth);
                            
                            // For historical days, position label at line end (maxEndTime)
                            // For real-time days, position label at current time
                            DateTime labelTime = isRealtime ? currentTime : maxEndTime;
                            labelTime = GetLabelTimeWithOffset(labelTime, isRealtime);
                            
                            string labelKey = "PAX_LowerLabel_" + dateStr + "_" + levelIndex;
                            Draw.Text(this, labelKey, true, 
                                LabelPrefix + " " + newLowerLevel.ToString("F2"), 
                                labelTime, newLowerLevel, TextvertPixels, LowLineColor, cachedFont,
                                TextAlignment.Left, Brushes.Transparent, Brushes.Transparent, 0);
                            
                            if (isRealtime)
                                activeLabels[labelKey] = labelTime;
                        }
                        catch (Exception ex)
                        {
                            // Silent error handling - no prints in production
                        }
                    }
                }
            }
        }
        
        /// <summary>
        /// Moves active labels to follow the current price bar in real-time
        /// </summary>
        private void MoveActiveLabels()
        {
            if (Times[0].Count < 1 || !orbValues.ContainsKey(realtimeOrbDate))
                return;
            
            DateTime currentTime = Times[0][0];
            DateTime orbEndTime = realtimeOrbDate.Add(ORBEndPlot);
            
            // If we're past the end time, don't move labels
            if (currentTime >= orbEndTime)
                return;
            
            // Get the current line end time (for extending lines)
            DateTime lineEnd = currentTime < orbEndTime ? currentTime : orbEndTime;
            
            // Extend all lines to current position
            string dateStr = realtimeOrbDate.ToString("yyyyMMdd");
            var orbData = orbValues[realtimeOrbDate];
            DateTime lineStart = realtimeOrbDate.Add(ORBStart.Add(TimeSpan.FromSeconds(ORBSeconds)));
            
            // Redraw main lines with extended end time
            Draw.Line(this, "PAX_HighLine_" + dateStr, true, lineStart, orbData.High, lineEnd, orbData.High, 
                HighLineColor, DashStyleHelper.Solid, MainLineWidth);
            Draw.Line(this, "PAX_LowLine_" + dateStr, true, lineStart, orbData.Low, lineEnd, orbData.Low, 
                LowLineColor, DashStyleHelper.Solid, MainLineWidth);
            
            if (ShowMid)
            {
                Draw.Line(this, "PAX_MidLine_" + dateStr, true, lineStart, orbData.Mid, lineEnd, orbData.Mid, 
                    MidLineColor, DashStyleHelper.Solid, MidLineWidth);
            }
            
            // Extend level lines using their original start times
            if (upperLevels.ContainsKey(realtimeOrbDate))
            {
                for (int i = 0; i < upperLevels[realtimeOrbDate].Count; i++)
                {
                    DateTime levelStartTime = lineStart; // Default to ORB end for first level
                    if (i > 0 && upperLevelStartTimes.ContainsKey(realtimeOrbDate) && 
                        upperLevelStartTimes[realtimeOrbDate].ContainsKey(i))
                    {
                        levelStartTime = upperLevelStartTimes[realtimeOrbDate][i];
                    }
                    
                    Draw.Line(this, "PAX_UpperLevel_" + dateStr + "_" + i, true, 
                        levelStartTime, upperLevels[realtimeOrbDate][i], lineEnd, upperLevels[realtimeOrbDate][i], 
                        HighLineColor, DashStyleHelper.Dash, LevelsLineWidth);
                }
            }
            
            if (lowerLevels.ContainsKey(realtimeOrbDate))
            {
                for (int i = 0; i < lowerLevels[realtimeOrbDate].Count; i++)
                {
                    DateTime levelStartTime = lineStart; // Default to ORB end for first level
                    if (i > 0 && lowerLevelStartTimes.ContainsKey(realtimeOrbDate) && 
                        lowerLevelStartTimes[realtimeOrbDate].ContainsKey(i))
                    {
                        levelStartTime = lowerLevelStartTimes[realtimeOrbDate][i];
                    }
                    
                    Draw.Line(this, "PAX_LowerLevel_" + dateStr + "_" + i, true, 
                        levelStartTime, lowerLevels[realtimeOrbDate][i], lineEnd, lowerLevels[realtimeOrbDate][i], 
                        LowLineColor, DashStyleHelper.Dash, LevelsLineWidth);
                }
            }
            
            // Now move labels
            DateTime newLabelTime = GetLabelTimeWithOffset(currentTime, true);
            
            // Create a copy of keys to avoid collection modification during iteration
            var labelKeys = activeLabels.Keys.ToList();
            
            foreach (string labelKey in labelKeys)
            {
                // Parse label info from key
                double price = 0;
                string labelText = "";
                Brush color = Brushes.White;
                
                if (labelKey.Contains("HighLabel"))
                {
                    price = orbData.High;
                    labelText = LabelPrefix + " " + price.ToString("F2");
                    color = HighLineColor;
                }
                else if (labelKey.Contains("LowLabel"))
                {
                    price = orbData.Low;
                    labelText = LabelPrefix + " " + price.ToString("F2");
                    color = LowLineColor;
                }
                else if (labelKey.Contains("MidLabel"))
                {
                    price = orbData.Mid;
                    labelText = LabelPrefix + " MID " + price.ToString("F2");
                    color = MidLineColor;
                }
                else if (labelKey.Contains("UpperLabel"))
                {
                    // Extract level index from key
                    string[] parts = labelKey.Split('_');
                    if (parts.Length > 1)
                    {
                        string indexPart = parts[parts.Length - 1];
                        if (int.TryParse(indexPart, out int levelIndex))
                        {
                            if (upperLevels.ContainsKey(realtimeOrbDate) && 
                                levelIndex < upperLevels[realtimeOrbDate].Count)
                            {
                                price = upperLevels[realtimeOrbDate][levelIndex];
                                labelText = LabelPrefix + " " + price.ToString("F2");
                                color = HighLineColor;
                            }
                        }
                    }
                }
                else if (labelKey.Contains("LowerLabel"))
                {
                    // Extract level index from key
                    string[] parts = labelKey.Split('_');
                    if (parts.Length > 1)
                    {
                        string indexPart = parts[parts.Length - 1];
                        if (int.TryParse(indexPart, out int levelIndex))
                        {
                            if (lowerLevels.ContainsKey(realtimeOrbDate) && 
                                levelIndex < lowerLevels[realtimeOrbDate].Count)
                            {
                                price = lowerLevels[realtimeOrbDate][levelIndex];
                                labelText = LabelPrefix + " " + price.ToString("F2");
                                color = LowLineColor;
                            }
                        }
                    }
                }
                
                if (price > 0)
                {
                    Draw.Text(this, labelKey, true, labelText, 
                        newLabelTime, price, TextvertPixels, color, cachedFont,
                        TextAlignment.Left, Brushes.Transparent, Brushes.Transparent, 0);
                    
                    activeLabels[labelKey] = newLabelTime;
                }
            }
        }
        
        /// <summary>
        /// Cleans up old data to prevent memory buildup
        /// </summary>
        private void CleanupOldData(DateTime currentDate)
        {
            var keysToRemove = orbValues.Keys
                .Where(date => (currentDate - date).Days >= DAYS_TO_DISPLAY)
                .ToList();
            
            foreach (var key in keysToRemove)
            {
                string dateStr = key.ToString("yyyyMMdd");
                
                // Remove from tracking
                if (key == realtimeOrbDate)
                {
                    realtimeOrbDate = DateTime.MinValue;
                    activeLabels.Clear();
                }
                
                // Remove from drawn levels
                drawnLevels.RemoveWhere(x => x.Contains(dateStr));
                
                // Remove data
                orbValues.Remove(key);
                
                if (upperLevels.ContainsKey(key))
                {
                    upperLevels[key].Clear();
                    upperLevels.Remove(key);
                }
                
                if (lowerLevels.ContainsKey(key))
                {
                    lowerLevels[key].Clear();
                    lowerLevels.Remove(key);
                }
                
                // Clean up level start times
                if (upperLevelStartTimes.ContainsKey(key))
                {
                    upperLevelStartTimes[key].Clear();
                    upperLevelStartTimes.Remove(key);
                }
                
                if (lowerLevelStartTimes.ContainsKey(key))
                {
                    lowerLevelStartTimes[key].Clear();
                    lowerLevelStartTimes.Remove(key);
                }
            }
        }
    }
}

// Keep the existing #region NinjaScript generated code section unchanged

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
	public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
	{
		private PAX.PAX30OpeningRange[] cachePAX30OpeningRange;
		public PAX.PAX30OpeningRange PAX30OpeningRange(string oRBStartSerialize, string oRBEndPlotSerialize, int textvertPixels, int textHorzOffset, int fontSize, bool boldFont, string labelPrefix, Brush highLineColor, Brush lowLineColor, Brush midLineColor, int mainLineWidth, int midLineWidth, int levelsLineWidth, bool showMid)
		{
			return PAX30OpeningRange(Input, oRBStartSerialize, oRBEndPlotSerialize, textvertPixels, textHorzOffset, fontSize, boldFont, labelPrefix, highLineColor, lowLineColor, midLineColor, mainLineWidth, midLineWidth, levelsLineWidth, showMid);
		}

		public PAX.PAX30OpeningRange PAX30OpeningRange(ISeries<double> input, string oRBStartSerialize, string oRBEndPlotSerialize, int textvertPixels, int textHorzOffset, int fontSize, bool boldFont, string labelPrefix, Brush highLineColor, Brush lowLineColor, Brush midLineColor, int mainLineWidth, int midLineWidth, int levelsLineWidth, bool showMid)
		{
			if (cachePAX30OpeningRange != null)
				for (int idx = 0; idx < cachePAX30OpeningRange.Length; idx++)
					if (cachePAX30OpeningRange[idx] != null && cachePAX30OpeningRange[idx].ORBStartSerialize == oRBStartSerialize && cachePAX30OpeningRange[idx].ORBEndPlotSerialize == oRBEndPlotSerialize && cachePAX30OpeningRange[idx].TextvertPixels == textvertPixels && cachePAX30OpeningRange[idx].TextHorzOffset == textHorzOffset && cachePAX30OpeningRange[idx].FontSize == fontSize && cachePAX30OpeningRange[idx].BoldFont == boldFont && cachePAX30OpeningRange[idx].LabelPrefix == labelPrefix && cachePAX30OpeningRange[idx].HighLineColor == highLineColor && cachePAX30OpeningRange[idx].LowLineColor == lowLineColor && cachePAX30OpeningRange[idx].MidLineColor == midLineColor && cachePAX30OpeningRange[idx].MainLineWidth == mainLineWidth && cachePAX30OpeningRange[idx].MidLineWidth == midLineWidth && cachePAX30OpeningRange[idx].LevelsLineWidth == levelsLineWidth && cachePAX30OpeningRange[idx].ShowMid == showMid && cachePAX30OpeningRange[idx].EqualsInput(input))
						return cachePAX30OpeningRange[idx];
			return CacheIndicator<PAX.PAX30OpeningRange>(new PAX.PAX30OpeningRange(){ ORBStartSerialize = oRBStartSerialize, ORBEndPlotSerialize = oRBEndPlotSerialize, TextvertPixels = textvertPixels, TextHorzOffset = textHorzOffset, FontSize = fontSize, BoldFont = boldFont, LabelPrefix = labelPrefix, HighLineColor = highLineColor, LowLineColor = lowLineColor, MidLineColor = midLineColor, MainLineWidth = mainLineWidth, MidLineWidth = midLineWidth, LevelsLineWidth = levelsLineWidth, ShowMid = showMid }, input, ref cachePAX30OpeningRange);
		}
	}
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
	public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
	{
		public Indicators.PAX.PAX30OpeningRange PAX30OpeningRange(string oRBStartSerialize, string oRBEndPlotSerialize, int textvertPixels, int textHorzOffset, int fontSize, bool boldFont, string labelPrefix, Brush highLineColor, Brush lowLineColor, Brush midLineColor, int mainLineWidth, int midLineWidth, int levelsLineWidth, bool showMid)
		{
			return indicator.PAX30OpeningRange(Input, oRBStartSerialize, oRBEndPlotSerialize, textvertPixels, textHorzOffset, fontSize, boldFont, labelPrefix, highLineColor, lowLineColor, midLineColor, mainLineWidth, midLineWidth, levelsLineWidth, showMid);
		}

		public Indicators.PAX.PAX30OpeningRange PAX30OpeningRange(ISeries<double> input , string oRBStartSerialize, string oRBEndPlotSerialize, int textvertPixels, int textHorzOffset, int fontSize, bool boldFont, string labelPrefix, Brush highLineColor, Brush lowLineColor, Brush midLineColor, int mainLineWidth, int midLineWidth, int levelsLineWidth, bool showMid)
		{
			return indicator.PAX30OpeningRange(input, oRBStartSerialize, oRBEndPlotSerialize, textvertPixels, textHorzOffset, fontSize, boldFont, labelPrefix, highLineColor, lowLineColor, midLineColor, mainLineWidth, midLineWidth, levelsLineWidth, showMid);
		}
	}
}

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		public Indicators.PAX.PAX30OpeningRange PAX30OpeningRange(string oRBStartSerialize, string oRBEndPlotSerialize, int textvertPixels, int textHorzOffset, int fontSize, bool boldFont, string labelPrefix, Brush highLineColor, Brush lowLineColor, Brush midLineColor, int mainLineWidth, int midLineWidth, int levelsLineWidth, bool showMid)
		{
			return indicator.PAX30OpeningRange(Input, oRBStartSerialize, oRBEndPlotSerialize, textvertPixels, textHorzOffset, fontSize, boldFont, labelPrefix, highLineColor, lowLineColor, midLineColor, mainLineWidth, midLineWidth, levelsLineWidth, showMid);
		}

		public Indicators.PAX.PAX30OpeningRange PAX30OpeningRange(ISeries<double> input , string oRBStartSerialize, string oRBEndPlotSerialize, int textvertPixels, int textHorzOffset, int fontSize, bool boldFont, string labelPrefix, Brush highLineColor, Brush lowLineColor, Brush midLineColor, int mainLineWidth, int midLineWidth, int levelsLineWidth, bool showMid)
		{
			return indicator.PAX30OpeningRange(input, oRBStartSerialize, oRBEndPlotSerialize, textvertPixels, textHorzOffset, fontSize, boldFont, labelPrefix, highLineColor, lowLineColor, midLineColor, mainLineWidth, midLineWidth, levelsLineWidth, showMid);
		}
	}
}

#endregion
