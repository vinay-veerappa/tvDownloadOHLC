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

	public class ORB_0930_1min_Indicator : Indicator
	{
		// State Variables for Pullback Logic
		private bool longPending = false;
		private bool shortPending = false;
		private double pbLongPrice = double.NaN;
		private double pbShortPrice = double.NaN;
		private int signalsCount = 0;
		private int maxSignals = 3; // Hardcoded for now to match Pine default
		private double rHigh = double.MinValue;
		private double rLow = double.MaxValue;
		private bool rDefined = false;
		private TimeZoneInfo estZone;

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
				//Disable this property if your indicator requires custom values that cumulate with each new market data event. 
				//See Help Guide for additional information.
				IsSuspendedWhileInactive					= true;
				
				// Initialize Inputs
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

				try {
					estZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
				} catch {
					estZone = TimeZoneInfo.Local; // Fallback
				}
			}
			else if (State == State.Configure)
			{
				AddDataSeries(BarsPeriodType.Day, 1);
			}
		}

		protected override void OnBarUpdate()
		{
			if (CurrentBar < 20) return;
			
			// Explicit EST Conversion
			DateTime estTime = Time[0];
			if (estZone != null) 
			{
				try 
				{
					// CS1503 Fix: Treat TradingHours.TimeZone as string ID based on error report
					estTime = TimeZoneInfo.ConvertTime(Time[0], TimeZoneInfo.FindSystemTimeZoneById(Bars.TradingHours.TimeZone.ToString()), estZone);
				}
				catch { /* Fallback */ }
			}

			// Logic to capture 9:30 OR
			if (Bars.IsFirstBarOfSession)
			{
				rHigh = double.MinValue;
				rLow = double.MaxValue;
				rDefined = false;
				longPending = false;
				shortPending = false;
				signalsCount = 0;
			}

			// Capture Range
			if (estTime.Hour == 9 && estTime.Minute == 30)
			{
				rHigh = High[0];
				rLow = Low[0];
				rDefined = true;
			}

			if (rDefined)
			{
				double rSize = rHigh - rLow;
				Values[0][0] = rHigh;
				Values[1][0] = rHigh - (rSize * 0.25);
				Values[2][0] = rHigh - (rSize * 0.50);
				Values[3][0] = rHigh - (rSize * 0.75);
				Values[4][0] = rLow;

				// 0.10% Buffer Lines (of Price, offset from boundaries)
				Values[5][0] = rHigh + (Close[0] * 0.001);
				Values[6][0] = rLow - (Close[0] * 0.001);
				
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
			if (BarsArray.Length > 1 && BarsArray[1].Count >= 20)
			{
				double sma20_daily = SMA(BarsArray[1], 20)[0];
				double close_daily = BarsArray[1].GetClose(0);
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
						}
						else if (crossLower) {
							Draw.TriangleDown(this, "Sell" + CurrentBar, true, 0, High[0] + TickSize, Brushes.Red);
							signalsCount++;
						}
					}
					else // Pullback Logic
					{
						// Arming
						if (!longPending && !shortPending)
						{
							// No Fakeout Logic: Breakout must close validly to arm
							if (crossUpper && Close[0] >= pbLongPrice) longPending = true;
							else if (crossLower && Close[0] <= pbShortPrice) shortPending = true;
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

		#region Properties
		[NinjaScriptProperty]
		[Display(Name="Entry Model", Order=0, GroupName="Core")]
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

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> RangeHigh { get { return Values[0]; } }

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> Level25 { get { return Values[1]; } }

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> Level50 { get { return Values[2]; } }

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> Level75 { get { return Values[3]; } }

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> RangeLow { get { return Values[4]; } }

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> BufferUpper { get { return Values[5]; } }

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> BufferLower { get { return Values[6]; } }
		#endregion
	}
}




