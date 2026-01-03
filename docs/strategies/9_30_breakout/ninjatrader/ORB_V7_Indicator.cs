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

//This namespace holds Indicators in this folder and is required. Do not change it. 
namespace NinjaTrader.NinjaScript.Indicators
{
	public class ORB_V7_Indicator : Indicator
	{
		// State Variables for Pullback Logic
		private bool longPending = false;
		private bool shortPending = false;
		private double pbLongPrice = double.NaN;
		private double pbShortPrice = double.NaN;
		private int maxSignals = 3; 
		private double rHigh = double.MinValue;
		private double rLow = double.MaxValue;

		private bool rDefined = false;
		private DateTime lastResetDate = DateTime.MinValue;
		private int signalsCount = 0;
		private int breakoutBarPrimary = -1;
		private int fallbackBarPrimary = -1;
		private bool paintedOrbBar = false;
		private TimeZoneInfo estZone;
		private TimeZoneInfo chartZone; 

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description									= @"9:30 AM Breakout Indicator V7.1 [Optimized]";
				Name										= "ORB_V7_Indicator";
				Calculate									= Calculate.OnBarClose;
				IsOverlay									= true;
				DisplayInDataBox							= true;
				DrawOnPricePanel							= true;
				DrawHorizontalGridLines						= true;
				DrawVerticalGridLines						= true;
				PaintPriceMarkers							= true;
				ScaleJustification							= NinjaTrader.Gui.Chart.ScaleJustification.Right;
				IsSuspendedWhileInactive					= true;
				
				// Initialize Inputs (V7 Defaults)
				ChartTimeZone = "Pacific Standard Time";
				OrbDuration = ORB_Duration.OneMinute;
				EntryModel = ORB_Indicator_EntryMode.BreakoutClose; // V7 Default
				SessionStart = "09:30";
				SessionEnd = "10:00";
				UseRegime = true;
				UseVVIX = true;
				UseSweetSpot = true;
				
				UseTuesday = false; // V7 Default (Trade all days)
				UseWednesday = false; // V7 New
				
				UseTimeExit = true;
				HardExitTime = DateTime.Parse("11:00", System.Globalization.CultureInfo.InvariantCulture); // V7 Default
				VVIX_Open = 100.0;
				MAE_Threshold = 0.12;
				RiskPercent = 1.0; // V7 1.0%
				InitialCapital = 100000.0;
				ShowExits = true;
				TPSetting = 0.35;
				
				// V7 New Logic
				UseConfirmedEntry = true;
				ConfirmPct = 0.10;

				try { estZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time"); } 
				catch { estZone = TimeZoneInfo.Local; }
				
				try { chartZone = TimeZoneInfo.FindSystemTimeZoneById(ChartTimeZone ?? "Pacific Standard Time"); } 
				catch { chartZone = TimeZoneInfo.Local; }
			}
			else if (State == State.Configure)
			{
				AddDataSeries(BarsPeriodType.Second, 1); 
				AddDataSeries(BarsPeriodType.Day, 1);    
			}
		}

		protected override void OnBarUpdate()
		{
			// Strict Safety Checks
			if (CurrentBars[0] < 1) return;
			if (BarsInProgress == 1 && CurrentBars[1] < 1) return;

			// Logic Block: Execute ONLY on 1-Second Series (Index 1)
			if (BarsInProgress == 1)
			{
				DateTime estTime;
				if (chartZone != null) estTime = TimeZoneInfo.ConvertTime(Time[0], chartZone, estZone);
				else estTime = Time[0];

				if (estTime.Date != lastResetDate || (estTime.Hour == 9 && estTime.Minute == 30 && estTime.Second == 0))
				{
					rHigh = double.MinValue;
					rLow = double.MaxValue;
					rDefined = false;
					signalsCount = 0;
					longPending = false;
					shortPending = false;
					lastResetDate = estTime.Date;
					paintedOrbBar = false; 
				}

				// Capture Range Window
				int limitSeconds = (OrbDuration == ORB_Duration.OneMinute) ? 60 : 30;
				TimeSpan timeOfDay = estTime.TimeOfDay;
				TimeSpan startTime = new TimeSpan(9, 30, 0); 
				TimeSpan endTime = startTime.Add(TimeSpan.FromSeconds(limitSeconds));

				if (timeOfDay > startTime && timeOfDay <= endTime)
				{
					if (High[0] > rHigh) rHigh = High[0];
					if (Low[0] < rLow) rLow = Low[0];
				}

				if (!rDefined && timeOfDay >= endTime) 
				{
					rDefined = rHigh > double.MinValue && rLow < double.MaxValue;
				}
			}

			// Visual Block: Execute ONLY on Primary Chart Series (Index 0)
			if (BarsInProgress == 0)
			{
				DateTime estTime;
				if (chartZone != null) estTime = TimeZoneInfo.ConvertTime(Time[0], chartZone, estZone);
				else estTime = Time[0];

				if (estTime.Hour == 9 && estTime.Minute == 30 && estTime.Second == 0)
				{
					breakoutBarPrimary = -1;
					fallbackBarPrimary = -1;
				}

				if (Bars.IsFirstBarOfSession) {
					breakoutBarPrimary = -1;
					fallbackBarPrimary = -1;
				}

				if (rDefined)
				{
					DrawOrbLines();

					double rSize = rHigh - rLow;

					// Calculate Pullback Levels Dynamic
					double pbLevel = -1.0;
					if (EntryModel == ORB_Indicator_EntryMode.Retest_0) pbLevel = 0.0;
					else if (EntryModel == ORB_Indicator_EntryMode.Shallow_25) pbLevel = 0.25;
					else if (EntryModel == ORB_Indicator_EntryMode.Midpoint_50) pbLevel = 0.50;
					
					pbLongPrice = pbLevel >= 0 ? rHigh - (rSize * pbLevel) : rHigh;
					pbShortPrice = pbLevel >= 0 ? rLow + (rSize * pbLevel) : rLow;
				}

				// Filter & State Logic
				bool isBull = true;
				if (BarsArray.Length > 2 && BarsArray[2].Count >= 20)
				{
					double sma20_daily = SMA(BarsArray[2], 20)[0];
					double close_daily = BarsArray[2].GetClose(0);
					isBull = close_daily > sma20_daily;
				}

				bool isTuesday = estTime.DayOfWeek == DayOfWeek.Tuesday;
				bool isWednesday = estTime.DayOfWeek == DayOfWeek.Wednesday; // V7
				
				bool isFiltered = (UseVVIX && VVIX_Open > 115) || (UseRegime && !isBull) || (UseTuesday && isTuesday) || (UseWednesday && isWednesday);
				bool isTradingClosed = UseTimeExit && estTime.TimeOfDay >= HardExitTime.TimeOfDay;
				bool canTrade = rDefined && !isFiltered && !isTradingClosed && signalsCount < maxSignals;
				
				double activeSL = double.NaN;
				double activeTP = double.NaN;

				// Dashboard & Signals Logic
				if (IsFirstTickOfBar && rDefined)
				{
					if (canTrade)
					{
						bool crossUpper = false;
						bool crossLower = false;
						
						if (UseConfirmedEntry) {
							double ch = rHigh * (1.0 + ConfirmPct/100.0);
							double cl = rLow * (1.0 - ConfirmPct/100.0);
							crossUpper = CrossAbove(Close, ch, 1);
							crossLower = CrossBelow(Close, cl, 1);
						} else {
							crossUpper = CrossAbove(Close, rHigh, 1);
							crossLower = CrossBelow(Close, rLow, 1);
						}
						
						if (EntryModel == ORB_Indicator_EntryMode.BreakoutClose)
						{
							if (crossUpper) {
								Draw.TriangleUp(this, "Buy" + CurrentBar, true, 0, Low[0] - TickSize, Brushes.SpringGreen);
								signalsCount++;
								breakoutBarPrimary = CurrentBars[0];
							}
							else if (crossLower) {
								Draw.TriangleDown(this, "Sell" + CurrentBar, true, 0, High[0] + TickSize, Brushes.Red);
								signalsCount++;
								breakoutBarPrimary = CurrentBars[0];
							}
						}
						else 
						{
							// Pullback logic (legacy style detection)
							if (!longPending && !shortPending)
							{
								if (crossUpper && Close[0] >= pbLongPrice) { longPending = true; breakoutBarPrimary = CurrentBars[0]; }
								else if (crossLower && Close[0] <= pbShortPrice) { shortPending = true; breakoutBarPrimary = CurrentBars[0]; }
							}
							
							if (longPending && Close[0] < pbLongPrice) longPending = false;
							if (shortPending && Close[0] > pbShortPrice) shortPending = false;
							
							if (longPending && Low[0] < rLow) longPending = false;
							if (shortPending && High[0] > rHigh) shortPending = false;

							if (longPending && Low[0] <= pbLongPrice && Close[0] >= pbLongPrice)
							{
								Draw.Text(this, "PB_Buy" + CurrentBar, "PB BUY", 0, Low[0] - 2 * TickSize, Brushes.SpringGreen);
								Draw.TriangleUp(this, "Buy" + CurrentBar, true, 0, Low[0] - TickSize, Brushes.SpringGreen);
								longPending = false;
								signalsCount++;
							}
							else if (shortPending && High[0] >= pbShortPrice && Close[0] <= pbShortPrice)
							{
								Draw.Text(this, "PB_Sell" + CurrentBar, "PB SELL", 0, High[0] + 2 * TickSize, Brushes.Red);
								Draw.TriangleDown(this, "Sell" + CurrentBar, true, 0, High[0] + TickSize, Brushes.Red);
								shortPending = false;
								signalsCount++;
							}
						}
					}

					// Bar Coloring (Primary)
					if (rDefined && !paintedOrbBar)
					{
						for (int i = 0; i <= 5; i++)
						{
							if (CurrentBar - i < 0) continue;
							
							DateTime barTimeEST = TimeZoneInfo.ConvertTime(Time[i], chartZone, estZone);
							if (barTimeEST.Hour == 9 && (barTimeEST.Minute == 30 || barTimeEST.Minute == 31))
							{
								BarBrushes[i] = Brushes.Yellow;
								if (High[i] > rHigh) rHigh = High[i];
								if (Low[i] < rLow) rLow = Low[i];
								paintedOrbBar = true; 
								break;
							}
						}
					}
					
					if (CurrentBar == breakoutBarPrimary)
					{
						BarBrush = Brushes.Cyan;
					}

					if (CurrentBar == BarsArray[0].Count - 1)
					{
						string status = isTradingClosed ? "TRADING CLOSED" : isFiltered ? "SKIP (Filtered)" : (EntryModel == ORB_Indicator_EntryMode.BreakoutClose ? "READY: Breakout" : "WAIT: Pullback");
						Brush statusColor = isTradingClosed ? Brushes.Gray : isFiltered ? Brushes.Red : Brushes.SpringGreen;

						double rSize = rHigh - rLow;
						double rPct = (rSize / BarsArray[0].GetOpen(0)) * 100;
						int contracts = (int)Math.Max(1, Math.Floor((InitialCapital * (RiskPercent / 100)) / (rSize * Instrument.MasterInstrument.PointValue)));

						bool isSweetSpot = UseSweetSpot && VVIX_Open >= 98 && VVIX_Open <= 115;
						string vvixStatus = isSweetSpot ? "SWEET SPOT" : (VVIX_Open > 115 ? "EXTREME" : "NORMAL");

						string diagInfo = string.Format("{0} / {1}", isFiltered ? "FILT" : "OK", canTrade ? "YES" : "NO");
						bool isRangeTooBig = rPct > MaxRangePct;
						string rangeWarning = isRangeTooBig ? " ⚠️TOO BIG" : "";
						string confirmText = UseConfirmedEntry ? string.Format("CONFIRMED ({0}%)", ConfirmPct) : "STANDARD";
						
						string hud = string.Format("REGIME: {0}\nVVIX: {1:F1} ({2})\nRANGE: {3:F2} pts ({4:F3}%){9}\nENTRY: {10}\nSIZE: {6} Lots\nSTATUS: {7}\nDIAG: {8}", 
							isBull ? "BULL" : "BEAR", VVIX_Open, vvixStatus, rSize, rPct, EntryModel, contracts, status, diagInfo, rangeWarning, confirmText);
						Draw.TextFixed(this, "HUD", hud, TextPosition.TopRight, Brushes.White, new Gui.Tools.SimpleFont("Arial", 11), Brushes.Black, Brushes.DimGray, 90);
					}
				}

				// Visual SL/TP Plotting logic
				if (rDefined)
				{
					bool isLongSignal = Close[0] > rHigh;
					bool isShortSignal = Close[0] < rLow;

					if (isLongSignal && (EntryModel == ORB_Indicator_EntryMode.BreakoutClose || (canTrade && Low[0] <= rHigh - (rHigh-rLow) * 0.25))) 
					{
						activeSL = rLow;
						activeTP = Close[0] * (1 + TPSetting / 100);
					}
					else if (isShortSignal)
					{
						activeSL = rHigh;
						activeTP = Close[0] * (1 - TPSetting / 100);
					}

					if (ShowExits && !double.IsNaN(activeSL))
					{
						Draw.Line(this, "SL_Line", true, 10, activeSL, -5, activeSL, Brushes.Red, DashStyleHelper.Dash, 2);
						Draw.Line(this, "TP_Line", true, 10, activeTP, -5, activeTP, Brushes.SpringGreen, DashStyleHelper.Dash, 2);
					}
				}
			}
		}

		private void DrawOrbLines()
		{
			if (chartZone == null || estZone == null) return;

			DateTime currentEst = TimeZoneInfo.ConvertTime(Time[0], chartZone, estZone);
			DateTime rangeDate = currentEst.Date; 
			
			int limitSeconds = (OrbDuration == ORB_Duration.OneMinute) ? 60 : 30;
			DateTime estOpen = rangeDate.Add(new TimeSpan(9, 30, limitSeconds));
			DateTime estEnd = rangeDate.Add(new TimeSpan(16, 0, 0));

			DateTime chartStart = TimeZoneInfo.ConvertTime(estOpen, estZone, chartZone);
			DateTime chartEnd = TimeZoneInfo.ConvertTime(estEnd, estZone, chartZone);

			DateTime displayEnd = (Time[0] < chartEnd && State == State.Realtime) ? Time[0] : chartEnd;
			
			string suffix = rangeDate.ToString("yyyyMMdd");
			
			// Main Lines
			Draw.Line(this, "High"+suffix, false, chartStart, rHigh, displayEnd, rHigh, Brushes.DeepSkyBlue, DashStyleHelper.Solid, 2);
			Draw.Line(this, "Low"+suffix, false, chartStart, rLow, displayEnd, rLow, Brushes.OrangeRed, DashStyleHelper.Solid, 2);
			
			// V7: Draw Confirmation Lines if enabled
			if (UseConfirmedEntry) {
				double ch = rHigh * (1.0 + ConfirmPct/100.0);
				double cl = rLow * (1.0 - ConfirmPct/100.0);
				Draw.Line(this, "ConfHigh"+suffix, false, chartStart, ch, displayEnd, ch, Brushes.Lime, DashStyleHelper.Dot, 1);
				Draw.Line(this, "ConfLow"+suffix, false, chartStart, cl, displayEnd, cl, Brushes.Red, DashStyleHelper.Dot, 1);
			}
			
			// Labels
			SimpleFont font = new SimpleFont("Arial", 11);
			Draw.Text(this, "TxtHigh"+suffix, false, "High: " + rHigh.ToString("F2"), displayEnd, rHigh, 10, Brushes.DeepSkyBlue, font, TextAlignment.Left, Brushes.Transparent, Brushes.Transparent, 0);
			Draw.Text(this, "TxtLow"+suffix, false, "Low: " + rLow.ToString("F2"), displayEnd, rLow, -10, Brushes.OrangeRed, font, TextAlignment.Left, Brushes.Transparent, Brushes.Transparent, 0);

			if (rDefined) {
				double mid = (rHigh+rLow)/2;
				Draw.Line(this, "Mid"+suffix, false, chartStart, mid, displayEnd, mid, Brushes.Gold, DashStyleHelper.Dash, 1);
				
				double rSize = rHigh - rLow;
				if (rSize > 0)
				{
					bool isSweetSpot = UseSweetSpot && VVIX_Open >= 98 && VVIX_Open <= 115;
					double rPct = (rSize / rLow) * 100;
					bool isRangeTooBig = rPct > MaxRangePct;

					Brush fillBrush = isRangeTooBig ? Brushes.Red : (isSweetSpot ? Brushes.Orange : Brushes.DeepSkyBlue);
					if (!isRangeTooBig && !isSweetSpot) fillBrush = Brushes.DeepSkyBlue; 
					
					Draw.Rectangle(this, "RangeBox"+suffix, false, chartStart, rHigh, displayEnd, rLow, Brushes.Transparent, fillBrush, 20);
					
					double bufferDist = rLow * 0.001; 
					double buffHigh = rHigh + bufferDist;
					double buffLow = rLow - bufferDist;
					Draw.Line(this, "BuffHigh"+suffix, false, chartStart, buffHigh, displayEnd, buffHigh, Brushes.Gray, DashStyleHelper.Dot, 1);
					Draw.Line(this, "BuffLow"+suffix, false, chartStart, buffLow, displayEnd, buffLow, Brushes.Gray, DashStyleHelper.Dot, 1);
				}
			}
		}
		
		#region Properties
		[NinjaScriptProperty]
		[Display(Name="Chart Time Zone", Order=0, GroupName="Time")]
		public string ChartTimeZone { get; set; }

		[NinjaScriptProperty]
		[Display(Name="ORB Duration", Order=1, GroupName="Time")]
		public NinjaTrader.NinjaScript.Indicators.ORB_Duration OrbDuration { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Entry Model", Order=1, GroupName="Core")]
		public NinjaTrader.NinjaScript.Indicators.ORB_Indicator_EntryMode EntryModel { get; set; }
		
		[NinjaScriptProperty]
		[Display(Name="Use Confirmed Entry", Order=2, GroupName="Core")]
		public bool UseConfirmedEntry { get; set; }
		
		[NinjaScriptProperty]
		[Display(Name="Confirm % Loop", Order=3, GroupName="Core")]
		public double ConfirmPct { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Session Start (ET)", Order=1, GroupName="Core")]
		public string SessionStart { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Session End (ET)", Order=2, GroupName="Core")]
		public string SessionEnd { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Use Regime Filter", Order=3, GroupName="Addons")]
		public bool UseRegime { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Use VVIX Filter", Order=4, GroupName="Addons")]
		public bool UseVVIX { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Use Tuesday Skip", Order=5, GroupName="Addons")]
		public bool UseTuesday { get; set; }
		
		[NinjaScriptProperty]
		[Display(Name="Use Wednesday Skip", Order=5, GroupName="Addons")]
		public bool UseWednesday { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Use Time Exit", Order=6, GroupName="Addons")]
		public bool UseTimeExit { get; set; }

		[NinjaScriptProperty]
		[PropertyEditor("NinjaTrader.Gui.Tools.TimeEditorKey")]
		[Display(Name="Hard Exit Time", Order=7, GroupName="Addons")]
		public DateTime HardExitTime { get; set; }

		[NinjaScriptProperty]
		[Display(Name="VVIX Open Value", Order=8, GroupName="Addons")]
		public double VVIX_Open { get; set; }

		[NinjaScriptProperty]
		[Display(Name="MAE % Threshold", Order=9, GroupName="Addons")]
		public double MAE_Threshold { get; set; }

		[Display(Name="Use Sweet Spot Highlight", Order=10, GroupName="Addons")]
		public bool UseSweetSpot { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Max Range %", Order=11, GroupName="Addons")]
		public double MaxRangePct { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Risk Percent (%)", Order=7, GroupName="Risk")]
		public double RiskPercent { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Initial Capital ($)", Order=8, GroupName="Risk")]
		public double InitialCapital { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Show Active SL/TP", Order=10, GroupName="Addons")]
		public bool ShowExits { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Projected TP (%)", Order=11, GroupName="Core")]
		public double TPSetting { get; set; }
		#endregion
	}
}
