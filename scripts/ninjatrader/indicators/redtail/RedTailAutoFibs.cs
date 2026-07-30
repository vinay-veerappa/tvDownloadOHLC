#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Core;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
    public class RedTailAutoFibs : Indicator
    {
        #region Private Variables

        private double dailyHigh, dailyLow, dailyOpen, dailyClose;
        private double weeklyHigh, weeklyLow, weeklyOpen, weeklyClose;
        private double monthlyHigh, monthlyLow, monthlyOpen, monthlyClose;

        private double prevDailyHigh, prevDailyLow, prevDailyOpen, prevDailyClose;
        private double prevWeeklyHigh, prevWeeklyLow, prevWeeklyOpen, prevWeeklyClose;
        private double prevMonthlyHigh, prevMonthlyLow, prevMonthlyOpen, prevMonthlyClose;

        private bool dailyHasData, weeklyHasData, monthlyHasData;
        private bool prevDailyValid, prevWeeklyValid, prevMonthlyValid;

        private int lastDailyDay = -1;
        private int lastWeeklyWeek = -1;
        private int lastMonthlyMonth = -1;

        // Cache to avoid redundant redraws
        private double lastDrawnDailyHigh, lastDrawnDailyLow, lastDrawnDailyOpen, lastDrawnDailyClose;
        private double lastDrawnWeeklyHigh, lastDrawnWeeklyLow, lastDrawnWeeklyOpen, lastDrawnWeeklyClose;
        private double lastDrawnMonthlyHigh, lastDrawnMonthlyLow, lastDrawnMonthlyOpen, lastDrawnMonthlyClose;

        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description                 = @"RedTail AutoFibs - Automatically plots Monthly, Weekly and Daily Fibonacci retracement levels with full per-level customization.";
                Name                        = "RedTailAutoFibs";
                Calculate                   = Calculate.OnBarClose;
                IsOverlay                   = true;
                DisplayInDataBox            = false;
                DrawOnPricePanel            = true;
                IsSuspendedWhileInactive    = true;

                // ── Global ──
                LineExtendBars              = 5;
                LabelFontSize               = 10;
                ShowPriceOnLabel            = true;
                LineLookbackDays            = 2;

                // ── Daily ──
                ShowDaily                   = true;
                DailyLineStyle              = DashStyleHelper.Solid;
                DailyLineWidth              = 1;
                DailyOpacity                = 80;

                DailyLevel1Enabled = true;  DailyLevel1Value = 0.0;    DailyLevel1Color = Brushes.DodgerBlue;
                DailyLevel2Enabled = true;  DailyLevel2Value = 0.236;  DailyLevel2Color = Brushes.DodgerBlue;
                DailyLevel3Enabled = true;  DailyLevel3Value = 0.382;  DailyLevel3Color = Brushes.DodgerBlue;
                DailyLevel4Enabled = true;  DailyLevel4Value = 0.5;    DailyLevel4Color = Brushes.DodgerBlue;
                DailyLevel5Enabled = true;  DailyLevel5Value = 0.618;  DailyLevel5Color = Brushes.CornflowerBlue;
                DailyLevel6Enabled = true;  DailyLevel6Value = 0.786;  DailyLevel6Color = Brushes.CornflowerBlue;
                DailyLevel7Enabled = true;  DailyLevel7Value = 1.0;    DailyLevel7Color = Brushes.DodgerBlue;
                DailyLevel8Enabled = false; DailyLevel8Value = -0.272; DailyLevel8Color = Brushes.SteelBlue;
                DailyLevel9Enabled = false; DailyLevel9Value = -0.618; DailyLevel9Color = Brushes.SteelBlue;
                DailyLevel10Enabled = false; DailyLevel10Value = -1.0; DailyLevel10Color = Brushes.SteelBlue;

                // ── Weekly ──
                ShowWeekly                  = true;
                WeeklyLineStyle             = DashStyleHelper.Dash;
                WeeklyLineWidth             = 2;
                WeeklyOpacity               = 80;

                WeeklyLevel1Enabled = true;  WeeklyLevel1Value = 0.0;    WeeklyLevel1Color = Brushes.Orange;
                WeeklyLevel2Enabled = true;  WeeklyLevel2Value = 0.236;  WeeklyLevel2Color = Brushes.Orange;
                WeeklyLevel3Enabled = true;  WeeklyLevel3Value = 0.382;  WeeklyLevel3Color = Brushes.Orange;
                WeeklyLevel4Enabled = true;  WeeklyLevel4Value = 0.5;    WeeklyLevel4Color = Brushes.Orange;
                WeeklyLevel5Enabled = true;  WeeklyLevel5Value = 0.618;  WeeklyLevel5Color = Brushes.DarkOrange;
                WeeklyLevel6Enabled = true;  WeeklyLevel6Value = 0.786;  WeeklyLevel6Color = Brushes.DarkOrange;
                WeeklyLevel7Enabled = true;  WeeklyLevel7Value = 1.0;    WeeklyLevel7Color = Brushes.Orange;
                WeeklyLevel8Enabled = false; WeeklyLevel8Value = -0.272; WeeklyLevel8Color = Brushes.Goldenrod;
                WeeklyLevel9Enabled = false; WeeklyLevel9Value = -0.618; WeeklyLevel9Color = Brushes.Goldenrod;
                WeeklyLevel10Enabled = false; WeeklyLevel10Value = -1.0; WeeklyLevel10Color = Brushes.Goldenrod;

                // ── Monthly ──
                ShowMonthly                 = true;
                MonthlyLineStyle            = DashStyleHelper.DashDot;
                MonthlyLineWidth            = 2;
                MonthlyOpacity              = 80;

                MonthlyLevel1Enabled = true;  MonthlyLevel1Value = 0.0;    MonthlyLevel1Color = Brushes.Magenta;
                MonthlyLevel2Enabled = true;  MonthlyLevel2Value = 0.236;  MonthlyLevel2Color = Brushes.Magenta;
                MonthlyLevel3Enabled = true;  MonthlyLevel3Value = 0.382;  MonthlyLevel3Color = Brushes.Magenta;
                MonthlyLevel4Enabled = true;  MonthlyLevel4Value = 0.5;    MonthlyLevel4Color = Brushes.Magenta;
                MonthlyLevel5Enabled = true;  MonthlyLevel5Value = 0.618;  MonthlyLevel5Color = Brushes.Orchid;
                MonthlyLevel6Enabled = true;  MonthlyLevel6Value = 0.786;  MonthlyLevel6Color = Brushes.Orchid;
                MonthlyLevel7Enabled = true;  MonthlyLevel7Value = 1.0;    MonthlyLevel7Color = Brushes.Magenta;
                MonthlyLevel8Enabled = false; MonthlyLevel8Value = -0.272; MonthlyLevel8Color = Brushes.Plum;
                MonthlyLevel9Enabled = false; MonthlyLevel9Value = -0.618; MonthlyLevel9Color = Brushes.Plum;
                MonthlyLevel10Enabled = false; MonthlyLevel10Value = -1.0; MonthlyLevel10Color = Brushes.Plum;
            }
            else if (State == State.DataLoaded)
            {
                dailyHasData = weeklyHasData = monthlyHasData = false;
                prevDailyValid = prevWeeklyValid = prevMonthlyValid = false;
            }
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBars[0] < 1) return;

            DateTime barTimeET = ConvertToET(Time[0]);
            DateTime sessionDate = GetSessionDate(barTimeET);

            TrackDaily(sessionDate);
            TrackWeekly(sessionDate);
            TrackMonthly(sessionDate);

            bool isLastBar = CurrentBar >= Count - 2 || State == State.Realtime;

            if (ShowDaily && prevDailyValid)
            {
                if (isLastBar || prevDailyHigh != lastDrawnDailyHigh || prevDailyLow != lastDrawnDailyLow
                    || prevDailyOpen != lastDrawnDailyOpen || prevDailyClose != lastDrawnDailyClose)
                {
                    DrawTimeframeFibs("D", "Daily", prevDailyHigh, prevDailyLow, prevDailyOpen, prevDailyClose,
                        DailyLineStyle, DailyLineWidth, DailyOpacity, GetDailyLevels());
                    lastDrawnDailyHigh = prevDailyHigh; lastDrawnDailyLow = prevDailyLow;
                    lastDrawnDailyOpen = prevDailyOpen; lastDrawnDailyClose = prevDailyClose;
                }
            }

            if (ShowWeekly && prevWeeklyValid)
            {
                if (isLastBar || prevWeeklyHigh != lastDrawnWeeklyHigh || prevWeeklyLow != lastDrawnWeeklyLow
                    || prevWeeklyOpen != lastDrawnWeeklyOpen || prevWeeklyClose != lastDrawnWeeklyClose)
                {
                    DrawTimeframeFibs("W", "Weekly", prevWeeklyHigh, prevWeeklyLow, prevWeeklyOpen, prevWeeklyClose,
                        WeeklyLineStyle, WeeklyLineWidth, WeeklyOpacity, GetWeeklyLevels());
                    lastDrawnWeeklyHigh = prevWeeklyHigh; lastDrawnWeeklyLow = prevWeeklyLow;
                    lastDrawnWeeklyOpen = prevWeeklyOpen; lastDrawnWeeklyClose = prevWeeklyClose;
                }
            }

            if (ShowMonthly && prevMonthlyValid)
            {
                if (isLastBar || prevMonthlyHigh != lastDrawnMonthlyHigh || prevMonthlyLow != lastDrawnMonthlyLow
                    || prevMonthlyOpen != lastDrawnMonthlyOpen || prevMonthlyClose != lastDrawnMonthlyClose)
                {
                    DrawTimeframeFibs("M", "Monthly", prevMonthlyHigh, prevMonthlyLow, prevMonthlyOpen, prevMonthlyClose,
                        MonthlyLineStyle, MonthlyLineWidth, MonthlyOpacity, GetMonthlyLevels());
                    lastDrawnMonthlyHigh = prevMonthlyHigh; lastDrawnMonthlyLow = prevMonthlyLow;
                    lastDrawnMonthlyOpen = prevMonthlyOpen; lastDrawnMonthlyClose = prevMonthlyClose;
                }
            }
        }

        #region Level Collection Helpers

        private struct FibLevel
        {
            public bool Enabled;
            public double Value;
            public Brush Color;
        }

        private List<FibLevel> GetDailyLevels()
        {
            return new List<FibLevel>
            {
                new FibLevel { Enabled = DailyLevel1Enabled,  Value = DailyLevel1Value,  Color = DailyLevel1Color },
                new FibLevel { Enabled = DailyLevel2Enabled,  Value = DailyLevel2Value,  Color = DailyLevel2Color },
                new FibLevel { Enabled = DailyLevel3Enabled,  Value = DailyLevel3Value,  Color = DailyLevel3Color },
                new FibLevel { Enabled = DailyLevel4Enabled,  Value = DailyLevel4Value,  Color = DailyLevel4Color },
                new FibLevel { Enabled = DailyLevel5Enabled,  Value = DailyLevel5Value,  Color = DailyLevel5Color },
                new FibLevel { Enabled = DailyLevel6Enabled,  Value = DailyLevel6Value,  Color = DailyLevel6Color },
                new FibLevel { Enabled = DailyLevel7Enabled,  Value = DailyLevel7Value,  Color = DailyLevel7Color },
                new FibLevel { Enabled = DailyLevel8Enabled,  Value = DailyLevel8Value,  Color = DailyLevel8Color },
                new FibLevel { Enabled = DailyLevel9Enabled,  Value = DailyLevel9Value,  Color = DailyLevel9Color },
                new FibLevel { Enabled = DailyLevel10Enabled, Value = DailyLevel10Value, Color = DailyLevel10Color },
            };
        }

        private List<FibLevel> GetWeeklyLevels()
        {
            return new List<FibLevel>
            {
                new FibLevel { Enabled = WeeklyLevel1Enabled,  Value = WeeklyLevel1Value,  Color = WeeklyLevel1Color },
                new FibLevel { Enabled = WeeklyLevel2Enabled,  Value = WeeklyLevel2Value,  Color = WeeklyLevel2Color },
                new FibLevel { Enabled = WeeklyLevel3Enabled,  Value = WeeklyLevel3Value,  Color = WeeklyLevel3Color },
                new FibLevel { Enabled = WeeklyLevel4Enabled,  Value = WeeklyLevel4Value,  Color = WeeklyLevel4Color },
                new FibLevel { Enabled = WeeklyLevel5Enabled,  Value = WeeklyLevel5Value,  Color = WeeklyLevel5Color },
                new FibLevel { Enabled = WeeklyLevel6Enabled,  Value = WeeklyLevel6Value,  Color = WeeklyLevel6Color },
                new FibLevel { Enabled = WeeklyLevel7Enabled,  Value = WeeklyLevel7Value,  Color = WeeklyLevel7Color },
                new FibLevel { Enabled = WeeklyLevel8Enabled,  Value = WeeklyLevel8Value,  Color = WeeklyLevel8Color },
                new FibLevel { Enabled = WeeklyLevel9Enabled,  Value = WeeklyLevel9Value,  Color = WeeklyLevel9Color },
                new FibLevel { Enabled = WeeklyLevel10Enabled, Value = WeeklyLevel10Value, Color = WeeklyLevel10Color },
            };
        }

        private List<FibLevel> GetMonthlyLevels()
        {
            return new List<FibLevel>
            {
                new FibLevel { Enabled = MonthlyLevel1Enabled,  Value = MonthlyLevel1Value,  Color = MonthlyLevel1Color },
                new FibLevel { Enabled = MonthlyLevel2Enabled,  Value = MonthlyLevel2Value,  Color = MonthlyLevel2Color },
                new FibLevel { Enabled = MonthlyLevel3Enabled,  Value = MonthlyLevel3Value,  Color = MonthlyLevel3Color },
                new FibLevel { Enabled = MonthlyLevel4Enabled,  Value = MonthlyLevel4Value,  Color = MonthlyLevel4Color },
                new FibLevel { Enabled = MonthlyLevel5Enabled,  Value = MonthlyLevel5Value,  Color = MonthlyLevel5Color },
                new FibLevel { Enabled = MonthlyLevel6Enabled,  Value = MonthlyLevel6Value,  Color = MonthlyLevel6Color },
                new FibLevel { Enabled = MonthlyLevel7Enabled,  Value = MonthlyLevel7Value,  Color = MonthlyLevel7Color },
                new FibLevel { Enabled = MonthlyLevel8Enabled,  Value = MonthlyLevel8Value,  Color = MonthlyLevel8Color },
                new FibLevel { Enabled = MonthlyLevel9Enabled,  Value = MonthlyLevel9Value,  Color = MonthlyLevel9Color },
                new FibLevel { Enabled = MonthlyLevel10Enabled, Value = MonthlyLevel10Value, Color = MonthlyLevel10Color },
            };
        }

        #endregion

        #region Period Tracking

        private DateTime ConvertToET(DateTime dt)
        {
            try
            {
                TimeZoneInfo etZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
                return TimeZoneInfo.ConvertTime(dt, etZone);
            }
            catch { return dt; }
        }

        private DateTime GetSessionDate(DateTime barTimeET)
        {
            return barTimeET.Hour >= 18 ? barTimeET.Date.AddDays(1) : barTimeET.Date;
        }

        private int GetTradingWeek(DateTime sessionDate)
        {
            System.Globalization.CultureInfo ci = System.Globalization.CultureInfo.InvariantCulture;
            return ci.Calendar.GetWeekOfYear(sessionDate, System.Globalization.CalendarWeekRule.FirstFourDayWeek, DayOfWeek.Monday);
        }

        private void TrackDaily(DateTime sessionDate)
        {
            int dayKey = sessionDate.DayOfYear + sessionDate.Year * 1000;
            if (dayKey != lastDailyDay)
            {
                if (dailyHasData)
                {
                    prevDailyHigh = dailyHigh; prevDailyLow = dailyLow;
                    prevDailyOpen = dailyOpen; prevDailyClose = dailyClose;
                    prevDailyValid = true;
                }
                dailyHigh = High[0]; dailyLow = Low[0];
                dailyOpen = Open[0]; dailyClose = Close[0];
                dailyHasData = true; lastDailyDay = dayKey;
            }
            else
            {
                if (High[0] > dailyHigh) dailyHigh = High[0];
                if (Low[0] < dailyLow) dailyLow = Low[0];
                dailyClose = Close[0];
            }
        }

        private void TrackWeekly(DateTime sessionDate)
        {
            int weekKey = GetTradingWeek(sessionDate) + sessionDate.Year * 100;
            if (weekKey != lastWeeklyWeek)
            {
                if (weeklyHasData)
                {
                    prevWeeklyHigh = weeklyHigh; prevWeeklyLow = weeklyLow;
                    prevWeeklyOpen = weeklyOpen; prevWeeklyClose = weeklyClose;
                    prevWeeklyValid = true;
                }
                weeklyHigh = High[0]; weeklyLow = Low[0];
                weeklyOpen = Open[0]; weeklyClose = Close[0];
                weeklyHasData = true; lastWeeklyWeek = weekKey;
            }
            else
            {
                if (High[0] > weeklyHigh) weeklyHigh = High[0];
                if (Low[0] < weeklyLow) weeklyLow = Low[0];
                weeklyClose = Close[0];
            }
        }

        private void TrackMonthly(DateTime sessionDate)
        {
            int monthKey = sessionDate.Month + sessionDate.Year * 100;
            if (monthKey != lastMonthlyMonth)
            {
                if (monthlyHasData)
                {
                    prevMonthlyHigh = monthlyHigh; prevMonthlyLow = monthlyLow;
                    prevMonthlyOpen = monthlyOpen; prevMonthlyClose = monthlyClose;
                    prevMonthlyValid = true;
                }
                monthlyHigh = High[0]; monthlyLow = Low[0];
                monthlyOpen = Open[0]; monthlyClose = Close[0];
                monthlyHasData = true; lastMonthlyMonth = monthKey;
            }
            else
            {
                if (High[0] > monthlyHigh) monthlyHigh = High[0];
                if (Low[0] < monthlyLow) monthlyLow = Low[0];
                monthlyClose = Close[0];
            }
        }

        #endregion

        #region Fib Drawing

        private void DrawTimeframeFibs(string prefix, string tfName, double high, double low, double open, double close,
            DashStyleHelper lineStyle, int lineWidth, int opacity, List<FibLevel> levels)
        {
            // Bullish: fib drawn from low to high, so 0% = high, retracement goes down toward low
            // Bearish: fib drawn from high to low, so 0% = low, retracement goes up toward high
            bool isBullish = close >= open;
            double basePrice = isBullish ? high : low;
            double topPrice  = isBullish ? low : high;
            double range = topPrice - basePrice;

            // Calculate lookback: estimate bars per day based on BarsPeriod
            int barsPerDay;
            if (BarsPeriod.BarsPeriodType == BarsPeriodType.Minute)
                barsPerDay = (23 * 60) / BarsPeriod.Value;  // ~23 hrs of futures session
            else if (BarsPeriod.BarsPeriodType == BarsPeriodType.Tick)
                barsPerDay = Math.Min(CurrentBar, 5000);    // Reasonable estimate for tick charts
            else if (BarsPeriod.BarsPeriodType == BarsPeriodType.Second)
                barsPerDay = (23 * 3600) / BarsPeriod.Value;
            else
                barsPerDay = 1;  // Daily/Weekly/Monthly bars

            int startBar = Math.Min(CurrentBar, barsPerDay * LineLookbackDays);
            int endBarOffset = -(LineExtendBars);

            for (int i = 0; i < levels.Count; i++)
            {
                string tag    = "RTFib_" + prefix + "_L" + (i + 1);
                string tagLbl = tag + "_lbl";

                if (!levels[i].Enabled)
                {
                    RemoveDrawObject(tag);
                    RemoveDrawObject(tagLbl);
                    continue;
                }

                double fibVal = levels[i].Value;
                double price  = basePrice + (range * fibVal);

                // Format percentage display
                double pct = fibVal * 100.0;
                string pctText = (pct == Math.Floor(pct)) ? pct.ToString("F0") : pct.ToString("F1");
                string labelText = ShowPriceOnLabel
                    ? tfName + " | " + pctText + "% | " + FormatPrice(price)
                    : tfName + " | " + pctText + "%";

                Brush lvlBrush = levels[i].Color.Clone();
                lvlBrush.Opacity = opacity / 100.0;
                lvlBrush.Freeze();

                // Draw the line from far left to LineExtendBars right of current bar
                Draw.Line(this, tag, false, startBar, price, endBarOffset, price, lvlBrush, lineStyle, lineWidth);

                // Label positioned just past end of line
                Draw.Text(this, tagLbl, false, labelText,
                    endBarOffset - 1, price, 0, lvlBrush,
                    new Gui.Tools.SimpleFont("Arial", LabelFontSize),
                    System.Windows.TextAlignment.Left, Brushes.Transparent, Brushes.Transparent, 0);
            }
        }

        private string FormatPrice(double price)
        {
            if (TickSize >= 1)
                return price.ToString("F0");
            else if (TickSize >= 0.25)
                return price.ToString("F2");
            else
                return price.ToString("F2");
        }

        #endregion

        #region Properties - Global

        [NinjaScriptProperty]
        [Range(1, 50)]
        [Display(Name = "Line Extend Bars Right", Description = "How many bars past current bar the lines extend", Order = 1, GroupName = "0. Global")]
        public int LineExtendBars { get; set; }

        [NinjaScriptProperty]
        [Range(1, 30)]
        [Display(Name = "Line Lookback Days", Description = "How many days back the lines extend (lower = faster load)", Order = 2, GroupName = "0. Global")]
        public int LineLookbackDays { get; set; }

        [NinjaScriptProperty]
        [Range(6, 24)]
        [Display(Name = "Label Font Size", Order = 3, GroupName = "0. Global")]
        public int LabelFontSize { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Show Price on Label", Order = 4, GroupName = "0. Global")]
        public bool ShowPriceOnLabel { get; set; }

        #endregion

        // ═══════════════════════════════════════════════════════
        //  DAILY PROPERTIES
        // ═══════════════════════════════════════════════════════
        #region Properties - Daily Main

        [NinjaScriptProperty]
        [Display(Name = "Show Daily Fibs", Order = 1, GroupName = "1. Daily")]
        public bool ShowDaily { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Line Style", Order = 2, GroupName = "1. Daily")]
        public DashStyleHelper DailyLineStyle { get; set; }

        [NinjaScriptProperty]
        [Range(1, 5)]
        [Display(Name = "Line Width", Order = 3, GroupName = "1. Daily")]
        public int DailyLineWidth { get; set; }

        [NinjaScriptProperty]
        [Range(10, 100)]
        [Display(Name = "Opacity", Order = 4, GroupName = "1. Daily")]
        public int DailyOpacity { get; set; }

        #endregion

        #region Properties - Daily Levels

        [NinjaScriptProperty] [Display(Name = "Level 1 Enabled", Order = 1, GroupName = "1a. Daily Levels")] public bool DailyLevel1Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 1 Value",   Order = 2, GroupName = "1a. Daily Levels")] public double DailyLevel1Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 1 Color",   Order = 3, GroupName = "1a. Daily Levels")] public Brush DailyLevel1Color { get; set; }
        [Browsable(false)] public string DailyLevel1ColorSerializable { get { return Serialize.BrushToString(DailyLevel1Color); } set { DailyLevel1Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 2 Enabled", Order = 4, GroupName = "1a. Daily Levels")] public bool DailyLevel2Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 2 Value",   Order = 5, GroupName = "1a. Daily Levels")] public double DailyLevel2Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 2 Color",   Order = 6, GroupName = "1a. Daily Levels")] public Brush DailyLevel2Color { get; set; }
        [Browsable(false)] public string DailyLevel2ColorSerializable { get { return Serialize.BrushToString(DailyLevel2Color); } set { DailyLevel2Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 3 Enabled", Order = 7, GroupName = "1a. Daily Levels")] public bool DailyLevel3Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 3 Value",   Order = 8, GroupName = "1a. Daily Levels")] public double DailyLevel3Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 3 Color",   Order = 9, GroupName = "1a. Daily Levels")] public Brush DailyLevel3Color { get; set; }
        [Browsable(false)] public string DailyLevel3ColorSerializable { get { return Serialize.BrushToString(DailyLevel3Color); } set { DailyLevel3Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 4 Enabled", Order = 10, GroupName = "1a. Daily Levels")] public bool DailyLevel4Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 4 Value",   Order = 11, GroupName = "1a. Daily Levels")] public double DailyLevel4Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 4 Color",   Order = 12, GroupName = "1a. Daily Levels")] public Brush DailyLevel4Color { get; set; }
        [Browsable(false)] public string DailyLevel4ColorSerializable { get { return Serialize.BrushToString(DailyLevel4Color); } set { DailyLevel4Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 5 Enabled", Order = 13, GroupName = "1a. Daily Levels")] public bool DailyLevel5Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 5 Value",   Order = 14, GroupName = "1a. Daily Levels")] public double DailyLevel5Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 5 Color",   Order = 15, GroupName = "1a. Daily Levels")] public Brush DailyLevel5Color { get; set; }
        [Browsable(false)] public string DailyLevel5ColorSerializable { get { return Serialize.BrushToString(DailyLevel5Color); } set { DailyLevel5Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 6 Enabled", Order = 16, GroupName = "1a. Daily Levels")] public bool DailyLevel6Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 6 Value",   Order = 17, GroupName = "1a. Daily Levels")] public double DailyLevel6Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 6 Color",   Order = 18, GroupName = "1a. Daily Levels")] public Brush DailyLevel6Color { get; set; }
        [Browsable(false)] public string DailyLevel6ColorSerializable { get { return Serialize.BrushToString(DailyLevel6Color); } set { DailyLevel6Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 7 Enabled", Order = 19, GroupName = "1a. Daily Levels")] public bool DailyLevel7Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 7 Value",   Order = 20, GroupName = "1a. Daily Levels")] public double DailyLevel7Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 7 Color",   Order = 21, GroupName = "1a. Daily Levels")] public Brush DailyLevel7Color { get; set; }
        [Browsable(false)] public string DailyLevel7ColorSerializable { get { return Serialize.BrushToString(DailyLevel7Color); } set { DailyLevel7Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 8 Enabled", Order = 22, GroupName = "1a. Daily Levels")] public bool DailyLevel8Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 8 Value",   Order = 23, GroupName = "1a. Daily Levels")] public double DailyLevel8Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 8 Color",   Order = 24, GroupName = "1a. Daily Levels")] public Brush DailyLevel8Color { get; set; }
        [Browsable(false)] public string DailyLevel8ColorSerializable { get { return Serialize.BrushToString(DailyLevel8Color); } set { DailyLevel8Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 9 Enabled", Order = 25, GroupName = "1a. Daily Levels")] public bool DailyLevel9Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 9 Value",   Order = 26, GroupName = "1a. Daily Levels")] public double DailyLevel9Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 9 Color",   Order = 27, GroupName = "1a. Daily Levels")] public Brush DailyLevel9Color { get; set; }
        [Browsable(false)] public string DailyLevel9ColorSerializable { get { return Serialize.BrushToString(DailyLevel9Color); } set { DailyLevel9Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 10 Enabled", Order = 28, GroupName = "1a. Daily Levels")] public bool DailyLevel10Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 10 Value",   Order = 29, GroupName = "1a. Daily Levels")] public double DailyLevel10Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 10 Color",   Order = 30, GroupName = "1a. Daily Levels")] public Brush DailyLevel10Color { get; set; }
        [Browsable(false)] public string DailyLevel10ColorSerializable { get { return Serialize.BrushToString(DailyLevel10Color); } set { DailyLevel10Color = Serialize.StringToBrush(value); } }

        #endregion

        // ═══════════════════════════════════════════════════════
        //  WEEKLY PROPERTIES
        // ═══════════════════════════════════════════════════════
        #region Properties - Weekly Main

        [NinjaScriptProperty]
        [Display(Name = "Show Weekly Fibs", Order = 1, GroupName = "2. Weekly")]
        public bool ShowWeekly { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Line Style", Order = 2, GroupName = "2. Weekly")]
        public DashStyleHelper WeeklyLineStyle { get; set; }

        [NinjaScriptProperty]
        [Range(1, 5)]
        [Display(Name = "Line Width", Order = 3, GroupName = "2. Weekly")]
        public int WeeklyLineWidth { get; set; }

        [NinjaScriptProperty]
        [Range(10, 100)]
        [Display(Name = "Opacity", Order = 4, GroupName = "2. Weekly")]
        public int WeeklyOpacity { get; set; }

        #endregion

        #region Properties - Weekly Levels

        [NinjaScriptProperty] [Display(Name = "Level 1 Enabled", Order = 1, GroupName = "2a. Weekly Levels")] public bool WeeklyLevel1Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 1 Value",   Order = 2, GroupName = "2a. Weekly Levels")] public double WeeklyLevel1Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 1 Color",   Order = 3, GroupName = "2a. Weekly Levels")] public Brush WeeklyLevel1Color { get; set; }
        [Browsable(false)] public string WeeklyLevel1ColorSerializable { get { return Serialize.BrushToString(WeeklyLevel1Color); } set { WeeklyLevel1Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 2 Enabled", Order = 4, GroupName = "2a. Weekly Levels")] public bool WeeklyLevel2Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 2 Value",   Order = 5, GroupName = "2a. Weekly Levels")] public double WeeklyLevel2Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 2 Color",   Order = 6, GroupName = "2a. Weekly Levels")] public Brush WeeklyLevel2Color { get; set; }
        [Browsable(false)] public string WeeklyLevel2ColorSerializable { get { return Serialize.BrushToString(WeeklyLevel2Color); } set { WeeklyLevel2Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 3 Enabled", Order = 7, GroupName = "2a. Weekly Levels")] public bool WeeklyLevel3Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 3 Value",   Order = 8, GroupName = "2a. Weekly Levels")] public double WeeklyLevel3Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 3 Color",   Order = 9, GroupName = "2a. Weekly Levels")] public Brush WeeklyLevel3Color { get; set; }
        [Browsable(false)] public string WeeklyLevel3ColorSerializable { get { return Serialize.BrushToString(WeeklyLevel3Color); } set { WeeklyLevel3Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 4 Enabled", Order = 10, GroupName = "2a. Weekly Levels")] public bool WeeklyLevel4Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 4 Value",   Order = 11, GroupName = "2a. Weekly Levels")] public double WeeklyLevel4Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 4 Color",   Order = 12, GroupName = "2a. Weekly Levels")] public Brush WeeklyLevel4Color { get; set; }
        [Browsable(false)] public string WeeklyLevel4ColorSerializable { get { return Serialize.BrushToString(WeeklyLevel4Color); } set { WeeklyLevel4Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 5 Enabled", Order = 13, GroupName = "2a. Weekly Levels")] public bool WeeklyLevel5Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 5 Value",   Order = 14, GroupName = "2a. Weekly Levels")] public double WeeklyLevel5Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 5 Color",   Order = 15, GroupName = "2a. Weekly Levels")] public Brush WeeklyLevel5Color { get; set; }
        [Browsable(false)] public string WeeklyLevel5ColorSerializable { get { return Serialize.BrushToString(WeeklyLevel5Color); } set { WeeklyLevel5Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 6 Enabled", Order = 16, GroupName = "2a. Weekly Levels")] public bool WeeklyLevel6Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 6 Value",   Order = 17, GroupName = "2a. Weekly Levels")] public double WeeklyLevel6Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 6 Color",   Order = 18, GroupName = "2a. Weekly Levels")] public Brush WeeklyLevel6Color { get; set; }
        [Browsable(false)] public string WeeklyLevel6ColorSerializable { get { return Serialize.BrushToString(WeeklyLevel6Color); } set { WeeklyLevel6Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 7 Enabled", Order = 19, GroupName = "2a. Weekly Levels")] public bool WeeklyLevel7Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 7 Value",   Order = 20, GroupName = "2a. Weekly Levels")] public double WeeklyLevel7Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 7 Color",   Order = 21, GroupName = "2a. Weekly Levels")] public Brush WeeklyLevel7Color { get; set; }
        [Browsable(false)] public string WeeklyLevel7ColorSerializable { get { return Serialize.BrushToString(WeeklyLevel7Color); } set { WeeklyLevel7Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 8 Enabled", Order = 22, GroupName = "2a. Weekly Levels")] public bool WeeklyLevel8Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 8 Value",   Order = 23, GroupName = "2a. Weekly Levels")] public double WeeklyLevel8Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 8 Color",   Order = 24, GroupName = "2a. Weekly Levels")] public Brush WeeklyLevel8Color { get; set; }
        [Browsable(false)] public string WeeklyLevel8ColorSerializable { get { return Serialize.BrushToString(WeeklyLevel8Color); } set { WeeklyLevel8Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 9 Enabled", Order = 25, GroupName = "2a. Weekly Levels")] public bool WeeklyLevel9Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 9 Value",   Order = 26, GroupName = "2a. Weekly Levels")] public double WeeklyLevel9Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 9 Color",   Order = 27, GroupName = "2a. Weekly Levels")] public Brush WeeklyLevel9Color { get; set; }
        [Browsable(false)] public string WeeklyLevel9ColorSerializable { get { return Serialize.BrushToString(WeeklyLevel9Color); } set { WeeklyLevel9Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 10 Enabled", Order = 28, GroupName = "2a. Weekly Levels")] public bool WeeklyLevel10Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 10 Value",   Order = 29, GroupName = "2a. Weekly Levels")] public double WeeklyLevel10Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 10 Color",   Order = 30, GroupName = "2a. Weekly Levels")] public Brush WeeklyLevel10Color { get; set; }
        [Browsable(false)] public string WeeklyLevel10ColorSerializable { get { return Serialize.BrushToString(WeeklyLevel10Color); } set { WeeklyLevel10Color = Serialize.StringToBrush(value); } }

        #endregion

        // ═══════════════════════════════════════════════════════
        //  MONTHLY PROPERTIES
        // ═══════════════════════════════════════════════════════
        #region Properties - Monthly Main

        [NinjaScriptProperty]
        [Display(Name = "Show Monthly Fibs", Order = 1, GroupName = "3. Monthly")]
        public bool ShowMonthly { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "Line Style", Order = 2, GroupName = "3. Monthly")]
        public DashStyleHelper MonthlyLineStyle { get; set; }

        [NinjaScriptProperty]
        [Range(1, 5)]
        [Display(Name = "Line Width", Order = 3, GroupName = "3. Monthly")]
        public int MonthlyLineWidth { get; set; }

        [NinjaScriptProperty]
        [Range(10, 100)]
        [Display(Name = "Opacity", Order = 4, GroupName = "3. Monthly")]
        public int MonthlyOpacity { get; set; }

        #endregion

        #region Properties - Monthly Levels

        [NinjaScriptProperty] [Display(Name = "Level 1 Enabled", Order = 1, GroupName = "3a. Monthly Levels")] public bool MonthlyLevel1Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 1 Value",   Order = 2, GroupName = "3a. Monthly Levels")] public double MonthlyLevel1Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 1 Color",   Order = 3, GroupName = "3a. Monthly Levels")] public Brush MonthlyLevel1Color { get; set; }
        [Browsable(false)] public string MonthlyLevel1ColorSerializable { get { return Serialize.BrushToString(MonthlyLevel1Color); } set { MonthlyLevel1Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 2 Enabled", Order = 4, GroupName = "3a. Monthly Levels")] public bool MonthlyLevel2Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 2 Value",   Order = 5, GroupName = "3a. Monthly Levels")] public double MonthlyLevel2Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 2 Color",   Order = 6, GroupName = "3a. Monthly Levels")] public Brush MonthlyLevel2Color { get; set; }
        [Browsable(false)] public string MonthlyLevel2ColorSerializable { get { return Serialize.BrushToString(MonthlyLevel2Color); } set { MonthlyLevel2Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 3 Enabled", Order = 7, GroupName = "3a. Monthly Levels")] public bool MonthlyLevel3Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 3 Value",   Order = 8, GroupName = "3a. Monthly Levels")] public double MonthlyLevel3Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 3 Color",   Order = 9, GroupName = "3a. Monthly Levels")] public Brush MonthlyLevel3Color { get; set; }
        [Browsable(false)] public string MonthlyLevel3ColorSerializable { get { return Serialize.BrushToString(MonthlyLevel3Color); } set { MonthlyLevel3Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 4 Enabled", Order = 10, GroupName = "3a. Monthly Levels")] public bool MonthlyLevel4Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 4 Value",   Order = 11, GroupName = "3a. Monthly Levels")] public double MonthlyLevel4Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 4 Color",   Order = 12, GroupName = "3a. Monthly Levels")] public Brush MonthlyLevel4Color { get; set; }
        [Browsable(false)] public string MonthlyLevel4ColorSerializable { get { return Serialize.BrushToString(MonthlyLevel4Color); } set { MonthlyLevel4Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 5 Enabled", Order = 13, GroupName = "3a. Monthly Levels")] public bool MonthlyLevel5Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 5 Value",   Order = 14, GroupName = "3a. Monthly Levels")] public double MonthlyLevel5Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 5 Color",   Order = 15, GroupName = "3a. Monthly Levels")] public Brush MonthlyLevel5Color { get; set; }
        [Browsable(false)] public string MonthlyLevel5ColorSerializable { get { return Serialize.BrushToString(MonthlyLevel5Color); } set { MonthlyLevel5Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 6 Enabled", Order = 16, GroupName = "3a. Monthly Levels")] public bool MonthlyLevel6Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 6 Value",   Order = 17, GroupName = "3a. Monthly Levels")] public double MonthlyLevel6Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 6 Color",   Order = 18, GroupName = "3a. Monthly Levels")] public Brush MonthlyLevel6Color { get; set; }
        [Browsable(false)] public string MonthlyLevel6ColorSerializable { get { return Serialize.BrushToString(MonthlyLevel6Color); } set { MonthlyLevel6Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 7 Enabled", Order = 19, GroupName = "3a. Monthly Levels")] public bool MonthlyLevel7Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 7 Value",   Order = 20, GroupName = "3a. Monthly Levels")] public double MonthlyLevel7Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 7 Color",   Order = 21, GroupName = "3a. Monthly Levels")] public Brush MonthlyLevel7Color { get; set; }
        [Browsable(false)] public string MonthlyLevel7ColorSerializable { get { return Serialize.BrushToString(MonthlyLevel7Color); } set { MonthlyLevel7Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 8 Enabled", Order = 22, GroupName = "3a. Monthly Levels")] public bool MonthlyLevel8Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 8 Value",   Order = 23, GroupName = "3a. Monthly Levels")] public double MonthlyLevel8Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 8 Color",   Order = 24, GroupName = "3a. Monthly Levels")] public Brush MonthlyLevel8Color { get; set; }
        [Browsable(false)] public string MonthlyLevel8ColorSerializable { get { return Serialize.BrushToString(MonthlyLevel8Color); } set { MonthlyLevel8Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 9 Enabled", Order = 25, GroupName = "3a. Monthly Levels")] public bool MonthlyLevel9Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 9 Value",   Order = 26, GroupName = "3a. Monthly Levels")] public double MonthlyLevel9Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 9 Color",   Order = 27, GroupName = "3a. Monthly Levels")] public Brush MonthlyLevel9Color { get; set; }
        [Browsable(false)] public string MonthlyLevel9ColorSerializable { get { return Serialize.BrushToString(MonthlyLevel9Color); } set { MonthlyLevel9Color = Serialize.StringToBrush(value); } }

        [NinjaScriptProperty] [Display(Name = "Level 10 Enabled", Order = 28, GroupName = "3a. Monthly Levels")] public bool MonthlyLevel10Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "Level 10 Value",   Order = 29, GroupName = "3a. Monthly Levels")] public double MonthlyLevel10Value { get; set; }
        [XmlIgnore]            [Display(Name = "Level 10 Color",   Order = 30, GroupName = "3a. Monthly Levels")] public Brush MonthlyLevel10Color { get; set; }
        [Browsable(false)] public string MonthlyLevel10ColorSerializable { get { return Serialize.BrushToString(MonthlyLevel10Color); } set { MonthlyLevel10Color = Serialize.StringToBrush(value); } }

        #endregion
    }
}
