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
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

//This namespace holds Strategies in this folder and is required. Do not change it. 
namespace NinjaTrader.NinjaScript.Strategies
{
	public class ORB_V6_Strategy : Strategy
	{
		private double rHigh = double.MinValue;
		private double rLow = double.MaxValue;
		private bool rDefined = false;
		private int attemptsToday = 0;
		private bool longPending = false;
		private bool shortPending = false;
		private double sigCandleExtreme = double.NaN;
		private int breakoutBar = -1;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description									= @"9:30 AM ORB Strategy V6 [Unified Specification]";
				Name										= "ORB_V6_Strategy";
				Calculate									= Calculate.OnBarClose;
				EntriesPerDirection							= 1;
				EntryHandling								= EntryHandling.AllEntries;
				IsExitOnSessionCloseStrategy				= true;
				ExitOnSessionCloseSeconds					= 30;
				IsFillLimitOnTouch							= true;
				MaximumBarsLookBack							= MaximumBarsLookBack.TwoHundredFiftySix;
				OrderFillResolution							= OrderFillResolution.Standard;
				Slippage									= 0;
				StartBehavior								= StartBehavior.WaitUntilFlat;
				TimeInForce									= TimeInForce.Gtc;
				TraceOrders									= false;
				RealtimeErrorHandling						= RealtimeErrorHandling.StopCancelClose;
				StopTargetHandling							= StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade							= 20;
				
				// Inputs
				EntryModel = "Shallow (25%)";
				MaxAttempts = 3;
				PBConfirm = true;
				BufferBreakout = true;
				PBTimeoutBars = 5;
				TP_Pct = 0.35;
				MAE_Threshold = 0.12;
				UseRegime = true;
				UseVVIX = true;
				UseSweetSpot = true;
				ShowExits = true;
				VVIX_Open = 100.0;
				UseEarlyExit = true;
				UseMAEFilter = true;
				SigCandleExit = "None"; // Options: None, Candle Close, Wick
				MaxRangePct = 0.25;
				EnableMultiTP = true;
				TP1Level = 0.10;
				TP1QtyPct = 50;
				TP2Level = 0.25;
				TP2QtyPct = 25;
				RunnerMode = "Trailing";
				TrailPct = 0.08;
				HardExitTime = DateTime.Parse("10:00", System.Globalization.CultureInfo.InvariantCulture);
			}
			else if (State == State.Configure)
			{
				AddDataSeries(BarsPeriodType.Day, 1); // For Regime (Daily SMA20)
			}
		}

		protected override void OnBarUpdate()
		{
			if (CurrentBar < 20 || BarsInProgress != 0) return;

			// Reset on new session
			if (Bars.IsFirstBarOfSession)
			{
				rHigh = double.MinValue;
				rLow = double.MaxValue;
				rDefined = false;
				attemptsToday = 0;
				longPending = false;
				shortPending = false;
			}

			// Capture Range
			if (Time[0].Hour == 9 && Time[0].Minute == 30)
			{
				rHigh = High[0];
				rLow = Low[0];
				rDefined = true;
				
				double rSize = rHigh - rLow;
				Draw.Line(this, "RHigh", true, 0, rHigh, -50, rHigh, Brushes.Gray, DashStyleHelper.Dash, 2);
				Draw.Line(this, "Level25", true, 0, rHigh - (rSize * 0.25), -50, rHigh - (rSize * 0.25), Brushes.Gray, DashStyleHelper.Dash, 1);
				Draw.Line(this, "Level50", true, 0, rHigh - (rSize * 0.50), -50, rHigh - (rSize * 0.50), Brushes.Gray, DashStyleHelper.Dash, 1);
				Draw.Line(this, "Level75", true, 0, rHigh - (rSize * 0.75), -50, rHigh - (rSize * 0.75), Brushes.Gray, DashStyleHelper.Dash, 1);
				Draw.Line(this, "RLow", true, 0, rLow, -50, rLow, Brushes.Gray, DashStyleHelper.Dash, 2);
				
				// 0.10% Buffer Lines (of Price, offset from boundaries)
				Draw.Line(this, "BufUpper", true, 0, rHigh + (Close[0] * 0.001), -50, rHigh + (Close[0] * 0.001), Brushes.Gray, DashStyleHelper.Dash, 1);
				Draw.Line(this, "BufLower", true, 0, rLow - (Close[0] * 0.001), -50, rLow - (Close[0] * 0.001), Brushes.Gray, DashStyleHelper.Dash, 1);
			}

			if (!rDefined) return;

			// Sizing logic uses Instrument.MasterInstrument.PointValue

			// Filters logic (Default to Bull if data missing)
			bool isBull = true; 
			if (BarsArray[1].Count >= 20)
			{
				double sma20_daily = SMA(BarsArray[1], 20)[0];
				double close_daily = BarsArray[1].GetClose(0);
				isBull = close_daily > sma20_daily;
			}
			bool isTuesday = Time[0].DayOfWeek == DayOfWeek.Tuesday;
			double rPctCheck = rDefined ? ((rHigh - rLow) / Close[0]) * 100 : 0;
			bool isFiltered = (UseRegime && !isBull) || (UseVVIX && VVIX_Open > 115) || isTuesday || (rPctCheck > MaxRangePct);

			// Trade Window (9:31 - 10:00)
			bool isWindow = Time[0].Hour == 9 && Time[0].Minute >= 31 && Time[0].Minute < 60;
			
			// Hard Exit
			if (ToTime(Time[0]) >= ToTime(HardExitTime) && Position.MarketPosition != MarketPosition.Flat)
			{
				ExitLong("Time Exit");
				ExitShort("Time Exit");
			}

			if (isWindow && Position.MarketPosition == MarketPosition.Flat && attemptsToday < MaxAttempts && !isFiltered)
			{
				double rSize = rHigh - rLow;
				double pbLongPrice = rHigh;
				double pbShortPrice = rLow;
				
				double riskAmt = InitialCapital * (RiskPercent / 100);
				int qty = (int)Math.Max(1, Math.Floor(riskAmt / (rSize * Instrument.MasterInstrument.PointValue)));

				if (EntryModel == "Shallow (25%)") { pbLongPrice = rHigh - (rSize * 0.25); pbShortPrice = rLow + (rSize * 0.25); }
				else if (EntryModel == "Midpoint (50%)") { pbLongPrice = rHigh - (rSize * 0.5); pbShortPrice = rLow + (rSize * 0.5); }

				if (EntryModel == "Breakout (Close)")
				{
					if (Close[0] > rHigh) { EnterLong(qty, "BO Long"); attemptsToday++; }
					else if (Close[0] < rLow) { EnterShort(qty, "BO Short"); attemptsToday++; }
				}
				else
				{
					// Pullback Logic with Buffer Confirmation + Timeout Fallback
					double bufferHigh = rHigh + (Close[0] * 0.001);
					double bufferLow = rLow - (Close[0] * 0.001);
					
					bool breakoutLong = BufferBreakout ? Close[0] > bufferHigh : (PBConfirm ? Close[0] > rHigh : High[0] > rHigh);
					bool breakoutShort = BufferBreakout ? Close[0] < bufferLow : (PBConfirm ? Close[0] < rLow : Low[0] < rLow);

					if (!longPending && !shortPending)
					{
						if (breakoutLong) { longPending = true; breakoutBar = CurrentBar; }
						else if (breakoutShort) { shortPending = true; breakoutBar = CurrentBar; }
					}

					int barsSinceBreakout = breakoutBar >= 0 ? CurrentBar - breakoutBar : 0;
					bool timeoutReached = barsSinceBreakout >= PBTimeoutBars;

					if (longPending)
					{
						// Always place the pullback limit order
						EnterLongLimit(0, true, qty, pbLongPrice, "PB Long");
						
						// Check if filled
						if (Position.MarketPosition == MarketPosition.Long)
						{
							longPending = false;
							breakoutBar = -1;
							attemptsToday++;
						}
						// Extra Entry: Timeout reached, not filled, AND price still above range
						else if (timeoutReached && Close[0] > rHigh)
						{
							CancelOrder(null);
							EnterLong(qty, "Timeout Long");
							longPending = false;
							breakoutBar = -1;
							attemptsToday++;
						}
						// Cancel if breakout failed (price went to opposite side)
						else if (Close[0] < rLow)
						{
							CancelOrder(null);
							longPending = false;
							breakoutBar = -1;
						}
					}
					
					if (shortPending)
					{
						// Always place the pullback limit order
						EnterShortLimit(0, true, qty, pbShortPrice, "PB Short");
						
						// Check if filled
						if (Position.MarketPosition == MarketPosition.Short)
						{
							shortPending = false;
							breakoutBar = -1;
							attemptsToday++;
						}
						// Extra Entry: Timeout reached, not filled, AND price still below range
						else if (timeoutReached && Close[0] < rLow)
						{
							CancelOrder(null);
							EnterShort(qty, "Timeout Short");
							shortPending = false;
							breakoutBar = -1;
							attemptsToday++;
						}
						// Cancel if breakout failed (price went to opposite side)
						else if (Close[0] > rHigh)
						{
							CancelOrder(null);
							shortPending = false;
							breakoutBar = -1;
						}
					}
						}
					}
				}
				}
			}

			// Management
			if (Position.MarketPosition != MarketPosition.Flat)
			{
				longPending = false;
				shortPending = false;
				
				// Target & Stop (Using percentage-based logic for parity)
				double entry = Position.AveragePrice;
				double tp = Position.MarketPosition == MarketPosition.Long ? entry * (1 + TP_Pct/100) : entry * (1 - TP_Pct/100);
				double sl = Position.MarketPosition == MarketPosition.Long ? rLow : rHigh;
				
				double tp1 = Position.MarketPosition == MarketPosition.Long ? entry * (1 + TP1Level/100) : entry * (1 - TP1Level/100);

				if (CoverQueen)
				{
					// TP1: Partial Exit
					int tp1Qty = (int)(Position.Quantity * TP1QtyPct / 100.0);
					if (Position.MarketPosition == MarketPosition.Long)
					{
						ExitLongLimit(0, true, tp1Qty, tp1, "TP1", "");
						ExitLongLimit(0, true, Position.Quantity - tp1Qty, tp, "TP2", "");
						ExitLongStopMarket(0, true, Position.Quantity, sl, "SL", "");
					}
					else
					{
						ExitShortLimit(0, true, tp1Qty, tp1, "TP1", "");
						ExitShortLimit(0, true, Position.Quantity - tp1Qty, tp, "TP2", "");
						ExitShortStopMarket(0, true, Position.Quantity, sl, "SL", "");
					}
				}
				else
				{
					// Single Full Exit
					ExitLongLimit(0, true, Position.Quantity, tp, "Target", "PB Long");
					ExitLongLimit(0, true, Position.Quantity, tp, "Target", "BO Long");
					ExitLongStopMarket(0, true, Position.Quantity, sl, "Stop", "PB Long");
					ExitLongStopMarket(0, true, Position.Quantity, sl, "Stop", "BO Long");
					
					ExitShortLimit(0, true, Position.Quantity, tp, "Target", "PB Short");
					ExitShortLimit(0, true, Position.Quantity, tp, "Target", "BO Short");
					ExitShortStopMarket(0, true, Position.Quantity, sl, "Stop", "PB Short");
					ExitShortStopMarket(0, true, Position.Quantity, sl, "Stop", "BO Short");
				}

				if (ShowExits)
				{
					Draw.Line(this, "SL_Line", true, 10, sl, -5, sl, Brushes.Red, DashStyleHelper.Dash, 2);
					Draw.Line(this, "TP_Line", true, 10, tp, -5, tp, Brushes.SpringGreen, DashStyleHelper.Dash, 2);
				}

				// MAE Heat Filter
				if (UseMAEFilter)
				{
					double heatDist = entry * (MAE_Threshold / 100);
					if (Position.MarketPosition == MarketPosition.Long && Low[0] < entry - heatDist) ExitLong("MAE Cut");
					else if (Position.MarketPosition == MarketPosition.Short && High[0] > entry + heatDist) ExitShort("MAE Cut");
				}
				
				// Signal Candle Reversal Exit
				if (SigCandleExit != "None" && !double.IsNaN(sigCandleExtreme))
				{
					bool isLong = Position.MarketPosition == MarketPosition.Long;
					bool sigTrigger = false;
					if (SigCandleExit == "Wick")
						sigTrigger = isLong ? Low[0] < sigCandleExtreme : High[0] > sigCandleExtreme;
					else // "Candle Close"
						sigTrigger = isLong ? Close[0] < sigCandleExtreme : Close[0] > sigCandleExtreme;

					if (sigTrigger)
					{
						ExitLong("Sig Candle");
						ExitShort("Sig Candle");
						sigCandleExtreme = double.NaN;
					}
				}
				if (UseEarlyExit)
				{
					if (Position.MarketPosition == MarketPosition.Long && Close[0] < rHigh) ExitLong("Early Exit");
					else if (Position.MarketPosition == MarketPosition.Short && Close[0] > rLow) ExitShort("Early Exit");
				}
			}

			// Dashboard Logic
			if (IsFirstTickOfBar && rDefined && CurrentBar == BarsArray[0].Count - 1)
			{
				bool isTradingClosed = ToTime(Time[0]) >= ToTime(HardExitTime);
				bool isWindow = Time[0].Hour == 9 && Time[0].Minute >= 31 && Time[0].Minute < 60;
				bool canTrade = rDefined && isWindow && !isFiltered && attemptsToday < MaxAttempts && Position.MarketPosition == MarketPosition.Flat;

				string status = Position. MarketPosition != MarketPosition.Flat ? "IN TRADE" : isTradingClosed ? "TRADING CLOSED" : isFiltered ? "SKIP (Filtered)" : (EntryModel == "Breakout (Close)" ? "READY: Breakout" : "WAIT: Pullback");
				
				double rSize = rHigh - rLow;
				double rPct = (rSize / BarsArray[0].GetOpen(0)) * 100;
				double riskAmt = InitialCapital * (RiskPercent / 100);
				int qty = (int)Math.Max(1, Math.Floor(riskAmt / (rSize * Instrument.MasterInstrument.PointValue)));

				string diagInfo = string.Format("{0} / {1}", isFiltered ? "FILT" : "OK", canTrade ? "YES" : "NO");
				
				bool isSweetSpot = UseSweetSpot && VVIX_Open >= 98 && VVIX_Open <= 115;
				bool isRangeTooBig = rPct > MaxRangePct;
				string vvixStatus = isSweetSpot ? "SWEET SPOT" : (VVIX_Open > 115 ? "EXTREME" : "NORMAL");
				string rangeWarning = isRangeTooBig ? " ⚠️TOO BIG" : "";

				string hud = string.Format("REGIME: {0}\nVVIX: {1:F1} ({2})\nRANGE: {3:F2} pts ({4:F3}%){9}\nMODEL: {5}\nSIZE: {6} Lots\nSTATUS: {7}\nDIAG: {8}", 
					isBull ? "BULL" : "BEAR", VVIX_Open, vvixStatus, rSize, rPct, EntryModel, qty, status, diagInfo, rangeWarning);
				
				Draw.TextFixed(this, "HUD", hud, TextPosition.TopRight, Brushes.White, new Gui.Tools.SimpleFont("Arial", 11), Brushes.Black, Brushes.DimGray, 90);

				// Color priority: Red (too big) > Orange (sweet spot) > Transparent (normal)
				if (isRangeTooBig)
				{
					Draw.Rectangle(this, "RangeBox", true, 20, rHigh, 0, rLow, Brushes.Transparent, Brushes.Red, 10);
				}
				else if (isSweetSpot)
				{
					Draw.Rectangle(this, "SweetSpot", true, 20, rHigh, 0, rLow, Brushes.Transparent, Brushes.Orange, 10);
				}
			}
		}

		#region Properties
		[NinjaScriptProperty]
		[Display(Name="Entry Model", Order=1, GroupName="Entry")]
		public string EntryModel { get; set; }

		[NinjaScriptProperty]
		[Display(Name="PB Confirmation (Close)", Order=2, GroupName="Entry")]
		public bool PBConfirm { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Buffer Breakout (0.10%)", Order=2, GroupName="Entry")]
		public bool BufferBreakout { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Pullback Timeout (Bars)", Order=2, GroupName="Entry")]
		public int PBTimeoutBars { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Max Attempts", Order=3, GroupName="Entry")]
		public int MaxAttempts { get; set; }

		[NinjaScriptProperty]
		[Display(Name="TP %", Order=4, GroupName="Risk")]
		public double TP_Pct { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Use MAE Filter", Order=5, GroupName="Risk")]
		public bool UseMAEFilter { get; set; }

		[NinjaScriptProperty]
		[Display(Name="MAE % Threshold", Order=6, GroupName="Risk")]
		public double MAE_Threshold { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Use Regime Filter", Order=7, GroupName="Addons")]
		public bool UseRegime { get; set; }

		[Display(Name="Use Sweet Spot Highlight", Order=9, GroupName="Addons")]
		public bool UseSweetSpot { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Show Active SL/TP", Order=10, GroupName="Addons")]
		public bool ShowExits { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Signal Candle Exit", Order=12, GroupName="Addons")]
		public string SigCandleExit { get; set; }

		[NinjaScriptProperty]
		[Display(Name="VVIX Open Value", Order=11, GroupName="Addons")]
		public double VVIX_Open { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Use Early Exit (Inside)", Order=10, GroupName="Addons")]
		public bool UseEarlyExit { get; set; }

		[NinjaScriptProperty]
		[PropertyEditor("NinjaTrader.Gui.Tools.TimeEditorKey")]
		[Display(Name="Hard Exit Time", Order=11, GroupName="Core")]
		public DateTime HardExitTime { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Max Range % (Skip if larger)", Order=13, GroupName="Addons")]
		public double MaxRangePct { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Enable Multi-TP", Order=14, GroupName="Multi-TP")]
		public bool EnableMultiTP { get; set; }

		[NinjaScriptProperty]
		[Display(Name="TP1 Level (%)", Order=15, GroupName="Multi-TP")]
		public double TP1Level { get; set; }

		[NinjaScriptProperty]
		[Display(Name="TP1 Qty (%)", Order=16, GroupName="Multi-TP")]
		public int TP1QtyPct { get; set; }

		[NinjaScriptProperty]
		[Display(Name="TP2 Level (%)", Order=17, GroupName="Multi-TP")]
		public double TP2Level { get; set; }

		[NinjaScriptProperty]
		[Display(Name="TP2 Qty (%)", Order=18, GroupName="Multi-TP")]
		public int TP2QtyPct { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Runner Mode", Order=19, GroupName="Multi-TP")]
		public string RunnerMode { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Trail %", Order=20, GroupName="Multi-TP")]
		public double TrailPct { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Account Equity ($)", Order=12, GroupName="Risk")]
		public double InitialCapital { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Risk per Trade (%)", Order=13, GroupName="Risk")]
		public double RiskPercent { get; set; }
		#endregion
	}
}
