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
	public enum ORB_Indicator_EntryMode
	{
		[Display(Name="Breakout (Close)")] BreakoutClose,
		[Display(Name="Retest (0%)")] Retest_0,
		[Display(Name="Shallow (25%)")] Shallow_25,
		[Display(Name="Midpoint (50%)")] Midpoint_50
	}

	public enum ORB_Duration
	{
		[Display(Name="1 Minute")] OneMinute,
		[Display(Name="30 Seconds")] ThirtySeconds
	}

	public class ORB_0930_1min_Indicator : Indicator
	{
		// State Variables for Pullback Logic
		private bool longPending = false;
		private bool shortPending = false;
		private double pbLongPrice = double.NaN;
		private double pbShortPrice = double.NaN;
		private int signalsCount = 0;
		private int maxSignals = 3; 
		private double rHigh = double.MinValue;
		private double rLow = double.MaxValue;

		private bool rDefined = false;
		private int breakoutBarPrimary = -1;
		private int fallbackBarPrimary = -1;
		private TimeZoneInfo estZone;
		private TimeZoneInfo chartZone; // Fix: Class-level variable

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description									= @"9:30 AM ORB V6 Indicator";
				Name										= "ORB_0930_1min_Indicator";
				Calculate									= Calculate.OnBarClose;
				IsOverlay									= true;
				DisplayInDataBox							= true;
				DrawOnPricePanel							= true;
				DrawHorizontalGridLines						= true;
				DrawVerticalGridLines						= true;
				PaintPriceMarkers							= true;
				ScaleJustification							= NinjaTrader.Gui.Chart.ScaleJustification.Right;
				IsSuspendedWhileInactive					= true;
				
				// Initialize Inputs
				ChartTimeZone = "Pacific Standard Time";
				OrbDuration = ORB_Duration.OneMinute;
				EntryModel = ORB_Indicator_EntryMode.Shallow_25;
				SessionStart = "09:30";
				SessionEnd = "10:00";
				UseRegime = true;
				UseVVIX = true;
				UseTuesday = true;
				UseTimeExit = true;
				HardExitTime = DateTime.Parse("10:00", System.Globalization.CultureInfo.InvariantCulture);
				VVIX_Open = 100.0;
				MAE_Threshold = 0.12;
				RiskPercent = 5.0;
				InitialCapital = 3000.0;
				UseSweetSpot = true;
				ShowExits = true;
				TPSetting = 0.35;

				try { estZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time"); } 
				catch { estZone = TimeZoneInfo.Local; }
				
				try { chartZone = TimeZoneInfo.FindSystemTimeZoneById(ChartTimeZone ?? "Pacific Standard Time"); } 
				catch { chartZone = TimeZoneInfo.Local; }
			}
			else if (State == State.Configure)
			{
				AddDataSeries(BarsPeriodType.Second, 1); 
				AddDataSeries(BarsPeriodType.Day, 1);    
				
				AddDataSeries(BarsPeriodType.Day, 1);
			}
		}

		protected override void OnBarUpdate()
		{
			if (CurrentBars[0] < 20) return;

			// Logic Block: Execute ONLY on 1-Second Series (Index 1)
			if (BarsInProgress == 1)
			{
				DateTime estTime;
				if (chartZone != null) estTime = TimeZoneInfo.ConvertTime(Time[0], chartZone, estZone);
				else estTime = Time[0];

				// Reset Logic at Start of Session (9:30 AM EST)
				if (estTime.Hour == 9 && estTime.Minute == 30 && estTime.Second == 0)
				{
					rHigh = double.MinValue;
					rLow = double.MaxValue;
					rDefined = false;
					signalsCount = 0;
					longPending = false;
					shortPending = false;
				}

				// Capture Range Window
				int limitSeconds = (OrbDuration == ORB_Duration.OneMinute) ? 60 : 30;
				TimeSpan timeOfDay = estTime.TimeOfDay;
				TimeSpan startTime = new TimeSpan(9, 30, 0);
				TimeSpan endTime = startTime.Add(TimeSpan.FromSeconds(limitSeconds));

				if (timeOfDay >= startTime && timeOfDay < endTime)
				{
					if (High[0] > rHigh) rHigh = High[0];
					if (Low[0] < rLow) rLow = Low[0];
				}

				// Finalize ORB
				if (!rDefined && timeOfDay >= endTime && timeOfDay < endTime.Add(TimeSpan.FromSeconds(5))) 
				{
					rDefined = rHigh > double.MinValue && rLow < double.MaxValue;
				}
			}

			// Visual Block: Execute ONLY on Primary Chart Series (Index 0)
			if (BarsInProgress == 0)
			{
				// Re-calculate EstTime for display/logic (using Chart Time)
				DateTime estTime;
				if (chartZone != null) estTime = TimeZoneInfo.ConvertTime(Time[0], chartZone, estZone);
				else estTime = Time[0];

				// Reset Variables
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
					// Draw ORB Lines (PAX Style)
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
				// Use BarsArray[2] (Daily) if available, checking count
				if (BarsArray.Length > 2 && BarsArray[2].Count >= 20)
				{
					double sma20_daily = SMA(BarsArray[2], 20)[0];
					double close_daily = BarsArray[2].GetClose(0);
					isBull = close_daily > sma20_daily;
				}



				bool isTuesday = estTime.DayOfWeek == DayOfWeek.Tuesday;
				bool isFiltered = (UseVVIX && VVIX_Open > 115) || (UseRegime && !isBull) || (UseTuesday && isTuesday);
				bool isTradingClosed = UseTimeExit && estTime.TimeOfDay >= HardExitTime.TimeOfDay;
				bool canTrade = rDefined && !isFiltered && !isTradingClosed && signalsCount < maxSignals;
				
				double activeSL = double.NaN;
				double activeTP = double.NaN;

				// Dashboard & Signals Logic
				if (IsFirstTickOfBar && rDefined)
				{
					// Visual Signals (State Machine)
					if (canTrade)
					{
						bool crossUpper = CrossAbove(Close, rHigh, 1);
						bool crossLower = CrossBelow(Close, rLow, 1);
						
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
						else // Pullback Logic
						{

							
							// Arming
							if (!longPending && !shortPending)
							{
								// No Fakeout Logic: Breakout must close validly to arm
								if (crossUpper && Close[0] >= pbLongPrice) { longPending = true; breakoutBarPrimary = CurrentBars[0]; }
								else if (crossLower && Close[0] <= pbShortPrice) { shortPending = true; breakoutBarPrimary = CurrentBars[0]; }
							}
							
							// Guard: Deep Pullback Cancel
							if (longPending && Close[0] < pbLongPrice) longPending = false;
							if (shortPending && Close[0] > pbShortPrice) shortPending = false;
							
							// Legacy Safety Reset
							if (longPending && Low[0] < rLow) longPending = false;
							if (shortPending && High[0] > rHigh) shortPending = false;

							// Confirmation Signal: Touch + Valid Close
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
					if (estTime.Hour == 9 && estTime.Minute == 30) 
					{
						BarBrush = Brushes.Yellow;
					}
					
					if (CurrentBar == breakoutBarPrimary)
					{
						BarBrush = Brushes.Cyan;
					}
					else if (CurrentBar == fallbackBarPrimary)
					{
						// Check direction? Logic passes just index. Assumption: Logic sets direction brush in BiP1? 
						// No, BiP1 can't set Primary Brush easily.
						// We'll simplify: Fallback = Lime (if Bull) / Red (if Bear) - logic needs to store direction
						// For now, simpler: Just Magenta/Lime marker logic or generic color.
						// PineScript said: Lime (Up) / Red (Down).
						// We need fallbackDirection variable.
						// For now, let's use White/Black or just standard Cyan for all breakouts, and specific for Fallback?
						// Let's stick to Cyan for INITIAL breakout.
						// Fallback logic is separate.
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
						string hud = string.Format("REGIME: {0}\nVVIX: {1:F1} ({2})\nRANGE: {3:F2} pts ({4:F3}%)\nMODEL: {5}\nSIZE: {6} Lots\nSTATUS: {7}\nDIAG: {8}", 
							isBull ? "BULL" : "BEAR", VVIX_Open, vvixStatus, rSize, rPct, EntryModel, contracts, status, diagInfo);
						
						Draw.TextFixed(this, "HUD", hud, TextPosition.TopRight, Brushes.White, new Gui.Tools.SimpleFont("Arial", 11), Brushes.Black, Brushes.DimGray, 90);

						// Sweet Spot Highlight
						if (isSweetSpot)
						{
							Draw.Rectangle(this, "SweetSpot", true, 20, rHigh, 0, rLow, Brushes.Transparent, Brushes.Orange, 10);
						}
					}
				}

				// Visual SL/TP Plotting logic
				if (rDefined)
				{
					bool isLongSignal = Close[0] > rHigh;
					bool isShortSignal = Close[0] < rLow;

					if (isLongSignal && (EntryModel == ORB_Indicator_EntryMode.BreakoutClose || (canTrade && Low[0] <= rHigh - (rHigh-rLow) * 0.25))) // Approximation for PB
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
			
			// Define Line Start/End
			// Start: 9:30:XX EST (converted to Chart Time)
			int limitSeconds = (OrbDuration == ORB_Duration.OneMinute) ? 60 : 30;
			DateTime estOpen = rangeDate.Add(new TimeSpan(9, 30, limitSeconds));
			// End: 16:00:00 EST (End of Session)
			DateTime estEnd = rangeDate.Add(new TimeSpan(16, 0, 0));

			DateTime chartStart = TimeZoneInfo.ConvertTime(estOpen, estZone, chartZone);
			DateTime chartEnd = TimeZoneInfo.ConvertTime(estEnd, estZone, chartZone);

			// Extend to current time if before end, but if Historical draw full line
			DateTime displayEnd = (Time[0] < chartEnd && State == State.Realtime) ? Time[0] : chartEnd;
			
			string suffix = rangeDate.ToString("yyyyMMdd");
			
			// Main Lines
			Draw.Line(this, "High"+suffix, false, chartStart, rHigh, displayEnd, rHigh, Brushes.DeepSkyBlue, DashStyleHelper.Solid, 2);
			Draw.Line(this, "Low"+suffix, false, chartStart, rLow, displayEnd, rLow, Brushes.OrangeRed, DashStyleHelper.Solid, 2);
			
			// Labels (At the end of the line)
			SimpleFont font = new SimpleFont("Arial", 11);
			Draw.Text(this, "TxtHigh"+suffix, false, "High: " + rHigh.ToString("F2"), displayEnd, rHigh, 10, Brushes.DeepSkyBlue, font, TextAlignment.Left, Brushes.Transparent, Brushes.Transparent, 0);
			Draw.Text(this, "TxtLow"+suffix, false, "Low: " + rLow.ToString("F2"), displayEnd, rLow, -10, Brushes.OrangeRed, font, TextAlignment.Left, Brushes.Transparent, Brushes.Transparent, 0);

			// Inner Levels
			if (rDefined) {
				double mid = (rHigh+rLow)/2;
				Draw.Line(this, "Mid"+suffix, false, chartStart, mid, displayEnd, mid, Brushes.Gold, DashStyleHelper.Dash, 1);
				Draw.Text(this, "TxtMid"+suffix, false, "Mid: " + mid.ToString("F2"), displayEnd, mid, 0, Brushes.Gold, font, TextAlignment.Left, Brushes.Transparent, Brushes.Transparent, 0);
			}
		}
		
		#region Properties
		// Initialize Inputs
		// Plots Removed - Standard Properties Only
		
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

		[NinjaScriptProperty]
		[Display(Name="Risk Percent (%)", Order=7, GroupName="Risk")]
		public double RiskPercent { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Initial Capital ($)", Order=8, GroupName="Risk")]
		public double InitialCapital { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Use Sweet Spot Highlight", Order=9, GroupName="Addons")]
		public bool UseSweetSpot { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Show Active SL/TP", Order=10, GroupName="Addons")]
		public bool ShowExits { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Projected TP (%)", Order=11, GroupName="Core")]
		public double TPSetting { get; set; }


		#endregion
	}
}




