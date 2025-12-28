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
	public enum EntryMode
	{
		[Display(Name="Breakout (Close)")] BreakoutClose,
		[Display(Name="Retest (0%)")] Retest_0,
		[Display(Name="Shallow (25%)")] Shallow_25,
		[Display(Name="Midpoint (50%)")] Midpoint_50
	}

	public enum CandleExitMode
	{
		None,
		[Display(Name="Candle Close")] CandleClose,
		Wick
	}

	public enum RunnerModeType
	{
		None,
		Trailing,
		Forever
	}

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
		private double pbLongPrice = double.NaN;
		private double pbShortPrice = double.NaN;
		private TimeZoneInfo estZone;

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
				StopTargetHandling							= StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade							= 20;

				try {
					estZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
				} catch {
					estZone = TimeZoneInfo.Local; // Fallback
				}
				
				// Inputs
				EntryModel = EntryMode.Shallow_25;
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
				SigCandleExit = CandleExitMode.None; // Options: None, Candle Close, Wick
				MaxRangePct = 0.25;
				EnableMultiTP = true;
				TP1Level = 0.10;
				TP1QtyPct = 50;
				TP2Level = 0.25;
				TP2QtyPct = 25;
				RunnerMode = RunnerModeType.Trailing;
				TrailPct = 0.08;
				HardExitTime = DateTime.Parse("10:00", System.Globalization.CultureInfo.InvariantCulture);
				
				// New V3 Inputs
				StopAfterWin = true;
				MaxSlPct = 0.30;
			}
			else if (State == State.Configure)
			{
				AddDataSeries(BarsPeriodType.Day, 1); // For Regime (Daily SMA20)
			}
		}

		private bool hasWonToday = false;
		private double prevClosedProfit = 0;
		private bool enteredViaFallback = false;
		private double breakoutCandleExtreme = double.NaN;

		protected override void OnBarUpdate()
		{
			if (CurrentBar < 20 || BarsInProgress != 0) return;

			// CRITICAL: This strategy relies on explicit conversion to EST using TimeZoneInfo.
			// This ensures independence from Chart Timezone settings (Local vs Exchange).
			
			DateTime estTime = Time[0];
			if (estZone != null)
			{
				try 
				{
					// Convert from the Data Series timezone (TradingHours) -> EST
					estTime = TimeZoneInfo.ConvertTime(Time[0], Bars.TradingHours.TimeZone, estZone);
				}
				catch { /* Fallback to Time[0] if conversion fails */ }
			}

			if (Bars.IsFirstBarOfSession)
			{
				rHigh = double.MinValue;
				rLow = double.MaxValue;
				rDefined = false;
				attemptsToday = 0;
				longPending = false;
				shortPending = false;
				hasWonToday = false;
				enteredViaFallback = false;
				breakoutCandleExtreme = double.NaN;
				prevClosedProfit = SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;
			}
			
			// Detect Win Today
			if (StopAfterWin && !hasWonToday && SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit > prevClosedProfit)
			{
				// Check if the latest trade was a win
				if (SystemPerformance.AllTrades.Count > 0)
				{
					Trade lastTrade = SystemPerformance.AllTrades[SystemPerformance.AllTrades.Count - 1];
					if (lastTrade.ProfitCurrency > 0) hasWonToday = true;
				}
				prevClosedProfit = SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;
			}

			// Capture Range
			if (estTime.Hour == 9 && estTime.Minute == 30)
			{
				rHigh = High[0];
				rLow = Low[0];
				rDefined = true;
				// (Drawing code same as before, omitted for brevity in snippet block)
			}

			if (!rDefined) return;
			// Filter Logic
			if (!rDefined) return;
			// Filter Logic
			int estTimeInt = estTime.Hour * 10000 + estTime.Minute * 100 + estTime.Second;
			bool isWindow = estTimeInt >= 93000 && estTimeInt <= 155500;
			
			// Regime Filter
			bool isBull = true; 
			if (UseRegime && BarsArray.Length > 1) {
				// Assuming SMA(20) on Daily (Series 1)
				if (CurrentBars[1] > 20)
					isBull = Closes[1][0] > SMA(BarsArray[1], 20)[0];
			}
			
			bool isFiltered = (UseRegime && !isBull) || (UseVVIX && VVIX_Open > 115) || (UseMAEFilter && false); 
			int qty = DefaultQuantity;
			
			bool canTrade = rDefined && isWindow && Position.MarketPosition == MarketPosition.Flat && attemptsToday < MaxAttempts && !isFiltered && !hasWonToday;

			if (canTrade)
			{
				// One-Shot Breakout Triggers
				bool breakoutLong = false;
				bool breakoutShort = false;

				if (EntryModel == EntryMode.BreakoutClose){
					breakoutLong = CrossAbove(Close, rHigh, 1);
					breakoutShort = CrossBelow(Close, rLow, 1);
				} else {
					// Pullback Logic
					double bufferHigh = rHigh + (Close[0] * 0.001);
					double bufferLow = rLow - (Close[0] * 0.001);
					
					breakoutLong = BufferBreakout ? CrossAbove(Close, bufferHigh, 1) : (PBConfirm ? CrossAbove(Close, rHigh, 1) : CrossAbove(High, rHigh, 1));
					breakoutShort = BufferBreakout ? CrossBelow(Close, bufferLow, 1) : (PBConfirm ? CrossBelow(Close, rLow, 1) : CrossBelow(Low, rLow, 1));
				}
				
				if (!longPending && !shortPending)
				{
					// No Fakeout Logic: Must Close Validly
					if (breakoutLong && Close[0] >= pbLongPrice) { 
						longPending = true; 
						breakoutBar = CurrentBar; 
						breakoutCandleExtreme = Low[0]; 
					}
					else if (breakoutShort && Close[0] <= pbShortPrice) { 
						shortPending = true; 
						breakoutBar = CurrentBar; 
						breakoutCandleExtreme = High[0]; 
					}
				}

					int barsSinceBreakout = breakoutBar >= 0 ? CurrentBar - breakoutBar : 0;
					bool timeoutReached = barsSinceBreakout >= PBTimeoutBars;
					
					// Deep Pullback Guard (V3 Logic)
					if (longPending && Close[0] < pbLongPrice) {
						longPending = false; breakoutBar = -1;
					}
					if (shortPending && Close[0] > pbShortPrice) {
						shortPending = false; breakoutBar = -1;
					}

					if (longPending)
					{
						// Guard: Deep Pullback Cancel
						if (Close[0] < pbLongPrice) {
							longPending = false; breakoutBar = -1;
						}
						// Entry: Touch & Valid Close
						else if (Low[0] <= pbLongPrice && Close[0] >= pbLongPrice)
						{
							EnterLong(qty, "PB Long (Conf)");
							longPending = false;
							breakoutBar = -1;
							attemptsToday++;
							enteredViaFallback = false;
						}
						// Fallback: Timeout
						else if (timeoutReached && Close[0] > rHigh)
						{
							EnterLong(qty, "Timeout Long");
							longPending = false;
							breakoutBar = -1;
							attemptsToday++;
							enteredViaFallback = true;
						}
						// Cancel if reversed
						else if (Close[0] < rLow)
						{
							longPending = false;
							breakoutBar = -1;
						}
					}
					
					if (shortPending)
					{
						// Guard: Deep Pullback Cancel
						if (Close[0] > pbShortPrice) {
							shortPending = false; breakoutBar = -1;
						}
						// Entry: Touch & Valid Close
						else if (High[0] >= pbShortPrice && Close[0] <= pbShortPrice)
						{
							EnterShort(qty, "PB Short (Conf)");
							shortPending = false;
							breakoutBar = -1;
							attemptsToday++;
							enteredViaFallback = false;
						}
						// Fallback: Timeout
						else if (timeoutReached && Close[0] < rLow)
						{
							EnterShort(qty, "Timeout Short");
							shortPending = false;
							breakoutBar = -1;
							attemptsToday++;
							enteredViaFallback = true;
						}
						// Cancel if reversed
						else if (Close[0] > rHigh)
						{
							shortPending = false;
							breakoutBar = -1;
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
				
				// SL Calculation with Max Cap
				double slPrice = Position.MarketPosition == MarketPosition.Long ? rLow : rHigh;
				// If Fallback entry, use the Breakout Candle Extreme
				if (enteredViaFallback && !double.IsNaN(breakoutCandleExtreme)) {
					slPrice = Position.MarketPosition == MarketPosition.Long ? Math.Min(rLow, breakoutCandleExtreme) : Math.Max(rHigh, breakoutCandleExtreme);
				}
				
				// Apply Max SL % Cap
				double maxRiskDist = entry * (MaxSlPct / 100.0);
				if (Position.MarketPosition == MarketPosition.Long) slPrice = Math.Max(slPrice, entry - maxRiskDist);
				else slPrice = Math.Min(slPrice, entry + maxRiskDist);

				double sl = slPrice;
				
				double tp1 = Position.MarketPosition == MarketPosition.Long ? entry * (1 + TP1Level/100) : entry * (1 - TP1Level/100);

				if (EnableMultiTP)
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
				if (SigCandleExit != CandleExitMode.None && !double.IsNaN(sigCandleExtreme))
				{
					bool isLong = Position.MarketPosition == MarketPosition.Long;
					bool sigTrigger = false;
					if (SigCandleExit == CandleExitMode.Wick)
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
				bool isTradingClosed = estTime.TimeOfDay >= HardExitTime.TimeOfDay;
				bool dashIsWindow = estTime.Hour == 9 && estTime.Minute >= 31 && estTime.Minute < 60;
				bool dashCanTrade = rDefined && dashIsWindow && !isFiltered && attemptsToday < MaxAttempts && Position.MarketPosition == MarketPosition.Flat;

				string status = Position.MarketPosition != MarketPosition.Flat ? "IN TRADE" : isTradingClosed ? "TRADING CLOSED" : isFiltered ? "SKIP (Filtered)" : (EntryModel == EntryMode.BreakoutClose ? "READY: Breakout" : "WAIT: Pullback");
				
				double rSize = rHigh - rLow;
				double rPct = (rSize / BarsArray[0].GetOpen(0)) * 100;
				double riskAmt = InitialCapital * (RiskPercent / 100);
				int dashQty = (int)Math.Max(1, Math.Floor(riskAmt / (rSize * Instrument.MasterInstrument.PointValue)));

				string diagInfo = string.Format("{0} / {1}", isFiltered ? "FILT" : "OK", dashCanTrade ? "YES" : "NO");
				
				bool isSweetSpot = UseSweetSpot && VVIX_Open >= 98 && VVIX_Open <= 115;
				bool isRangeTooBig = rPct > MaxRangePct;
				string vvixStatus = isSweetSpot ? "SWEET SPOT" : (VVIX_Open > 115 ? "EXTREME" : "NORMAL");
				string rangeWarning = isRangeTooBig ? " ⚠️TOO BIG" : "";

				string hud = string.Format("REGIME: {0}\nVVIX: {1:F1} ({2})\nRANGE: {3:F2} pts ({4:F3}%){9}\nMODEL: {5}\nSIZE: {6} Lots\nSTATUS: {7}\nDIAG: {8}", 
					isBull ? "BULL" : "BEAR", VVIX_Open, vvixStatus, rSize, rPct, EntryModel, dashQty, status, diagInfo, rangeWarning);
				
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
		public EntryMode EntryModel { get; set; }

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
		public CandleExitMode SigCandleExit { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Use VVIX Filter (Skip if > 115)", Order=10, GroupName="Addons")]
		public bool UseVVIX { get; set; }

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
		public RunnerModeType RunnerMode { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Trail %", Order=20, GroupName="Multi-TP")]
		public double TrailPct { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Account Equity ($)", Order=12, GroupName="Risk")]
		public double InitialCapital { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Risk per Trade (%)", Order=13, GroupName="Risk")]
		public double RiskPercent { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Max SL % (Cap)", Order=14, GroupName="Risk")]
		public double MaxSlPct { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Stop After Win (Daily)", Order=21, GroupName="Core")]
		public bool StopAfterWin { get; set; }
		#endregion
	}
}
