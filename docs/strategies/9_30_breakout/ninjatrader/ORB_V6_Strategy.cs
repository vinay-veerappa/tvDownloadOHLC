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
		[Display(Name="Deep (50%)")] Deep_50,
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
		private TimeZoneInfo estZone;
		private TimeZoneInfo chartZone;
		
		// Internal Variables
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
		private SMA regimeSMA;
		private int breakoutBarPrimary = -1;
		private int fallbackBarPrimary = -1;
		private bool fallbackIsLong = false;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description									= @"9:30 AM Breakout Strategy V6";
				Name										= "ORB_V6_Strategy";
				Calculate									= Calculate.OnBarClose;
				EntriesPerDirection							= 1;
				EntryHandling								= EntryHandling.AllEntries;
				IsExitOnSessionCloseStrategy				= true;
				ExitOnSessionCloseSeconds					= 30;
				IsFillLimitOnTouch							= false;
				MaximumBarsLookBack							= MaximumBarsLookBack.TwoHundredFiftySix;
				OrderFillResolution							= OrderFillResolution.Standard;
				Slippage									= 0;
				StartBehavior								= StartBehavior.WaitUntilFlat;
				TimeInForce									= TimeInForce.Gtc;
				TraceOrders									= false;
				RealtimeErrorHandling						= RealtimeErrorHandling.StopCancelClose;
				StopTargetHandling							= StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade							= 20;

				try {
					estZone = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time");
				} catch {
					estZone = TimeZoneInfo.Local; // Fallback
				}
				
				try {
					chartZone = TimeZoneInfo.FindSystemTimeZoneById(ChartTimeZone);
				} catch {
					chartZone = TimeZoneInfo.Local; // Fallback
				}
				
				// Initialize Inputs
				// Initialize Inputs
				ChartTimeZone = "Pacific Standard Time";
				OrbDuration = ORB_Duration.OneMinute;
				EntryModel = EntryMode.BreakoutClose;
				MaxAttempts = 3;
				PBConfirm = true;
				BufferBreakout = true;
				PBTimeoutBars = 5;
				TP_Pct = 0.35;
				MAE_Threshold = 0.12;
				UseRegime = true;
				UseVVIX = true;
				UseSweetSpot = true;
				RunnerMode                  = RunnerModeType.Trailing;
				InitialCapital              = 3000;
				RiskPercent                 = 10.0;
				MaxSlPct                    = 0.30; // Cap SL at 0.30% of range
				StopAfterWin                = true;
				ShowExits                   = true;
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
				AddDataSeries(BarsPeriodType.Second, 1); // Index 1: 1-Second Logic
				AddDataSeries(BarsPeriodType.Day, 1);    // Index 2: Regime Filter
			}
			else if (State == State.DataLoaded)
			{
				regimeSMA = SMA(BarsArray[2], 20);
			}
		}

		private bool hasWonToday = false;
		private double prevClosedProfit = 0;
		private bool enteredViaFallback = false;
		private double breakoutCandleExtreme = double.NaN;
		private DateTime lastResetDate = DateTime.MinValue;
		private bool paintedOrbBar = false;

		protected override void OnBarUpdate()
		{
			// Strict Safety Checks
			if (CurrentBars[0] < 1) return;
			if (BarsArray.Length > 1 && CurrentBars[1] < 1) return;
			if (BarsArray.Length > 2 && CurrentBars[2] < 1) return;

			// Ensure we have secondary series
			if (BarsArray.Length < 2) return;

			// Logic Block: Execute ONLY on 1-Second Series (Index 1)
			if (BarsInProgress == 1)
			{
				DateTime estTime;
				if (chartZone != null) estTime = TimeZoneInfo.ConvertTime(Time[0], chartZone, estZone);
				else estTime = Time[0];

				// Robust Reset Logic: Reset state if this is a new day
				if (estTime.Date != lastResetDate || (estTime.Hour == 9 && estTime.Minute == 30 && estTime.Second == 0))
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
					paintedOrbBar = false; // Reset Paint State
					lastResetDate = estTime.Date;
					
					// Re-calculate prevClosedProfit at session start
					if (SystemPerformance.AllTrades.Count > 0)
						prevClosedProfit = SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;
					else 
						prevClosedProfit = 0;
						
					// Reset visual markers
					breakoutBarPrimary = -1;
					fallbackBarPrimary = -1;
				}

				// Capture Range Window
				// Capture Range Window (Adjusted for End-of-Period Timestamps)
				// If 1s bars are stamped at Close:
				// 9:30:00 bar covers 9:29:59-9:30:00. This is PRE-MARKET. We skip.
				// 9:30:01 bar covers 9:30:00-9:30:01. This is FIRST bar.
				// 9:31:00 bar covers 9:30:59-9:31:00. This is LAST bar.
				
				int limitSeconds = (OrbDuration == ORB_Duration.OneMinute) ? 60 : 30;
				TimeSpan timeOfDay = estTime.TimeOfDay;
				TimeSpan startTime = new TimeSpan(9, 30, 0); // Exclude exact 9:30:00 (it's end of pre-market)
				TimeSpan endTime = startTime.Add(TimeSpan.FromSeconds(limitSeconds));

				// Logic: Time > 9:30:00 AND Time <= 9:31:00
				if (timeOfDay > startTime && timeOfDay <= endTime)
				{
					if (High[0] > rHigh) rHigh = High[0];
					if (Low[0] < rLow) rLow = Low[0];
				}

				// Finalize ORB
				// Finalize ORB after the last second bar (9:31:00) is processed
				if (!rDefined && timeOfDay > endTime)
				{
					rDefined = rHigh > double.MinValue && rLow < double.MaxValue;
				}

				// Execution/Management moved to Primary Logic Loop (BiP 0)
			}

			// Primary Logic Loop (BiP 0)
			// Runs on Bar Close effectively if Calculate=OnBarClose
			if (BarsInProgress == 0 && rDefined)
			{
				DateTime estTime;
				if (chartZone != null) estTime = TimeZoneInfo.ConvertTime(Time[0], chartZone, estZone);
				else estTime = Time[0];

				bool isTradingClosed = estTime.TimeOfDay >= HardExitTime.TimeOfDay;
				
				// Re-calc Filter Logic for Execution
				bool isBull = true; 
				if (UseRegime && BarsArray.Length > 2 && BarsArray[2].Count >= 20) {
					isBull = BarsArray[2].GetClose(0) > regimeSMA[0];
				}
				bool isTuesday = estTime.DayOfWeek == DayOfWeek.Tuesday;
				bool isFiltered = (UseVVIX && VVIX_Open > 115) || (UseRegime && !isBull) || (UseTuesday && isTuesday);

				// Common rSize calc for both Logic and HUD
				double rSize = rHigh - rLow;

				// --- EXECUTION LOGIC START ---
				// Detect Win Today
				if (StopAfterWin && !hasWonToday && SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit > prevClosedProfit + 10) 
					hasWonToday = true;

				bool canTrade = !isFiltered && !isTradingClosed && attemptsToday < MaxAttempts && !hasWonToday && Position.MarketPosition == MarketPosition.Flat;

				// DEBUG SUITE: State Analysis
				if (!canTrade)
				{
					// Only print if we are in the session key hours (9:30 - 16:00) to avoid spam
					if (estTime.Hour >= 9 && estTime.Hour < 16)
						Print(string.Format("BLOCKED [{0}]: Filtered={1} Closed={2} Att={3}/{4} Won={5} Pos={6}", 
							estTime, isFiltered, isTradingClosed, attemptsToday, MaxAttempts, hasWonToday, Position.MarketPosition));
				}
				else
				{
					Print(string.Format("ACTIVE [{0}]: Close={1} rHigh={2} rLow={3} Model={4}", estTime, Close[0], rHigh, rLow, EntryModel));
				}

				if (canTrade)
				{
					// Dynamic Sizing Logic
					// If RiskPercent > 0, calculate based on risk. Otherwise fallback to DefaultQuantity.
					int qty = DefaultQuantity;
					if (RiskPercent > 0 && rSize > 0)
					{
						double riskAmt = InitialCapital * (RiskPercent / 100.0);
						// Qty = Risk / (StopDistance * PointValue)
						// Stop Distance = rSize (approx, since SL is typically at other side of range)
						qty = (int)Math.Max(1, Math.Floor(riskAmt / (rSize * Instrument.MasterInstrument.PointValue)));
						Print(string.Format("SIZE CALC [{0}]: Risk=${1:F2} Range={2} Val={3} -> Qty={4}", estTime, riskAmt, rSize, Instrument.MasterInstrument.PointValue, qty));
					}
					bool breakoutLong = false;
					bool breakoutShort = false;

					// Breakout Detection (Primary Close)
					if (EntryModel == EntryMode.BreakoutClose)
					{
						breakoutLong = CrossAbove(Close, rHigh, 1);
						breakoutShort = CrossBelow(Close, rLow, 1);
					} 
					else 
					{
						// Pullback Mode
						double bufferHigh = rHigh + (Close[0] * 0.001);
						double bufferLow = rLow - (Close[0] * 0.001);
						
						breakoutLong = BufferBreakout ? CrossAbove(Close, bufferHigh, 1) : (PBConfirm ? CrossAbove(Close, rHigh, 1) : CrossAbove(High, rHigh, 1));
						breakoutShort = BufferBreakout ? CrossBelow(Close, bufferLow, 1) : (PBConfirm ? CrossBelow(Close, rLow, 1) : CrossBelow(Low, rLow, 1));
					}
					
					if (breakoutLong || breakoutShort)
						Print(string.Format("BREAKOUT SIGNAL [{0}]: Long={1} Short={2} Close={3} rHigh={4} rLow={5}", estTime, breakoutLong, breakoutShort, Close[0], rHigh, rLow));
					
					// rSize already calculated above
					double pbLevel = (EntryModel == EntryMode.Retest_0) ? 0.0 : (EntryModel == EntryMode.Shallow_25) ? 0.25 : 0.50;
					pbLongPrice = rHigh - (rSize * pbLevel);
					pbShortPrice = rLow + (rSize * pbLevel);

						if (!longPending && !shortPending)
						{
							// 1. Immediate Entry (BreakoutClose) - PRIORITIZED
							if (EntryModel == EntryMode.BreakoutClose)
							{
								if (breakoutLong) { 
									EnterLong(0, qty, "BreakoutBuy"); 
									attemptsToday++; 
									breakoutBarPrimary = CurrentBar; 
									Draw.TriangleUp(this, "SignalUp"+CurrentBar, true, 0, Low[0] - TickSize, Brushes.SpringGreen);
									Print(string.Format("ENTRY: Breakout Buy @ {0}", Close[0])); 
								}
								else if (breakoutShort) { 
									EnterShort(0, qty, "BreakoutSell"); 
									attemptsToday++; 
									breakoutBarPrimary = CurrentBar; 
									Draw.TriangleDown(this, "SignalDown"+CurrentBar, true, 0, High[0] + TickSize, Brushes.Red);
									Print(string.Format("ENTRY: Breakout Sell @ {0}", Close[0])); 
								}
							}
							// 2. Arming for Pullback Modes
							else 
							{
								if (breakoutLong && Close[0] >= pbLongPrice) { 
									longPending = true; breakoutBar = CurrentBar; breakoutCandleExtreme = Low[0]; 
									Draw.TriangleUp(this, "ArmUp"+CurrentBar, true, 0, Low[0] - TickSize, Brushes.DimGray); // Armed
								}
								else if (breakoutShort && Close[0] <= pbShortPrice) { 
									shortPending = true; breakoutBar = CurrentBar; breakoutCandleExtreme = High[0]; 
									Draw.TriangleDown(this, "ArmDown"+CurrentBar, true, 0, High[0] + TickSize, Brushes.DimGray); // Armed
								}
							}
						}
					
					// Pending Logic Debug
					if (longPending || shortPending)
						Print(string.Format("PENDING [{0}]: Long={1} Short={2} Close={3} PB_L={4} PB_S={5}", estTime, longPending, shortPending, Close[0], pbLongPrice, pbShortPrice));

					// Pullback State
					int barsSinceBreakout = breakoutBar >= 0 ? CurrentBar - breakoutBar : 0;
					bool timeoutReached = barsSinceBreakout >= PBTimeoutBars;

					if (longPending)
					{
						if (Close[0] < pbLongPrice) { longPending = false; breakoutBar = -1; Print(string.Format("PB CANCEL [{0}]: Long Deep PB. Close={1} < Level={2}", estTime, Close[0], pbLongPrice)); }
						else if (Low[0] <= pbLongPrice && Close[0] >= pbLongPrice) {
							EnterLong(0, qty, "PB Long (Conf)");
							longPending = false; breakoutBar = -1; attemptsToday++; enteredViaFallback = false;
							Draw.Text(this, "PBText"+CurrentBar, "PB BUY", 0, Low[0] - 2*TickSize, Brushes.SpringGreen);
							Draw.TriangleUp(this, "PBUp"+CurrentBar, true, 0, Low[0] - TickSize, Brushes.SpringGreen);
							Print(string.Format("PB ENTRY [{0}]: Long Confirmed. Low={1} <= Level={2}", estTime, Low[0], pbLongPrice));
						}
						else if (timeoutReached && Close[0] > rHigh) {
							EnterLong(0, qty, "Timeout Long");
							longPending = false; breakoutBar = -1; attemptsToday++; enteredViaFallback = true;
							fallbackBarPrimary = CurrentBar; fallbackIsLong = true;
							Print(string.Format("PB ENTRY [{0}]: Long Timeout. Bars={1}", estTime, barsSinceBreakout));
						}
						else if (Close[0] < rLow) { longPending = false; breakoutBar = -1; Print(string.Format("PB CANCEL [{0}]: Long Reverse. Close={1} < rLow={2}", estTime, Close[0], rLow)); }
					}
					
					if (shortPending)
					{
						if (Close[0] > pbShortPrice) { shortPending = false; breakoutBar = -1; Print(string.Format("PB CANCEL [{0}]: Short Deep PB. Close={1} > Level={2}", estTime, Close[0], pbShortPrice)); }
						else if (High[0] >= pbShortPrice && Close[0] <= pbShortPrice) {
							EnterShort(0, qty, "PB Short (Conf)");
							shortPending = false; breakoutBar = -1; attemptsToday++; enteredViaFallback = false;
							Draw.Text(this, "PBText"+CurrentBar, "PB SELL", 0, High[0] + 2*TickSize, Brushes.Red);
							Draw.TriangleDown(this, "PBDown"+CurrentBar, true, 0, High[0] + TickSize, Brushes.Red);
							Print(string.Format("PB ENTRY [{0}]: Short Confirmed. High={1} >= Level={2}", estTime, High[0], pbShortPrice));
						}
						else if (timeoutReached && Close[0] < rLow) {
							EnterShort(0, qty, "Timeout Short");
							shortPending = false; breakoutBar = -1; attemptsToday++; enteredViaFallback = true;
							fallbackBarPrimary = CurrentBar; fallbackIsLong = false;
							Print(string.Format("PB ENTRY [{0}]: Short Timeout. Bars={1}", estTime, barsSinceBreakout));
						}
						else if (Close[0] > rHigh) { shortPending = false; breakoutBar = -1; Print(string.Format("PB CANCEL [{0}]: Short Reverse. Close={1} > rHigh={2}", estTime, Close[0], rHigh)); }
					}
				}

				// Management (Runs on Primary Bar Close)
				if (Position.MarketPosition != MarketPosition.Flat)
				{
					longPending = false; shortPending = false;
					double entry = Position.AveragePrice;
					double tp = Position.MarketPosition == MarketPosition.Long ? entry * (1 + TP_Pct/100) : entry * (1 - TP_Pct/100);
					
					double slPrice = Position.MarketPosition == MarketPosition.Long ? rLow : rHigh;
					if (enteredViaFallback && !double.IsNaN(breakoutCandleExtreme)) {
						slPrice = Position.MarketPosition == MarketPosition.Long ? Math.Min(rLow, breakoutCandleExtreme) : Math.Max(rHigh, breakoutCandleExtreme);
					}
					double maxRiskDist = entry * (MaxSlPct / 100.0);
					if (Position.MarketPosition == MarketPosition.Long) slPrice = Math.Max(slPrice, entry - maxRiskDist);
					else slPrice = Math.Min(slPrice, entry + maxRiskDist);
					double sl = slPrice;
					double tp1 = Position.MarketPosition == MarketPosition.Long ? entry * (1 + TP1Level/100) : entry * (1 - TP1Level/100);

					if (EnableMultiTP) {
						int tp1Qty = (int)(Position.Quantity * TP1QtyPct / 100.0);
						if (Position.MarketPosition == MarketPosition.Long) {
							ExitLongLimit(0, true, tp1Qty, tp1, "TP1", "");
							ExitLongLimit(0, true, Position.Quantity - tp1Qty, tp, "TP2", "");
							ExitLongStopMarket(0, true, Position.Quantity, sl, "SL", "");
						} else {
							ExitShortLimit(0, true, tp1Qty, tp1, "TP1", "");
							ExitShortLimit(0, true, Position.Quantity - tp1Qty, tp, "TP2", "");
							ExitShortStopMarket(0, true, Position.Quantity, sl, "SL", "");
						}
					} else {
						if (Position.MarketPosition == MarketPosition.Long) {
							ExitLongLimit(0, true, Position.Quantity, tp, "Target", "");
							ExitLongStopMarket(0, true, Position.Quantity, sl, "Stop", "");
						} else {
							ExitShortLimit(0, true, Position.Quantity, tp, "Target", "");
							ExitShortStopMarket(0, true, Position.Quantity, sl, "Stop", "");
						}
					}
					
					if (UseMAEFilter) {
						double heatDist = entry * (MAE_Threshold / 100);
						if (Position.MarketPosition == MarketPosition.Long && Low[0] < entry - heatDist) ExitLong("MAE Cut");
						else if (Position.MarketPosition == MarketPosition.Short && High[0] > entry + heatDist) ExitShort("MAE Cut");
					}
					
					if (SigCandleExit != CandleExitMode.None && !double.IsNaN(sigCandleExtreme)) {
						bool isLong = Position.MarketPosition == MarketPosition.Long;
						bool sigTrigger = (SigCandleExit == CandleExitMode.Wick) ? (isLong ? Low[0] < sigCandleExtreme : High[0] > sigCandleExtreme)
																				 : (isLong ? Close[0] < sigCandleExtreme : Close[0] > sigCandleExtreme);
						if (sigTrigger) { ExitLong("Sig Candle"); ExitShort("Sig Candle"); sigCandleExtreme = double.NaN; }
					}
					
					if (UseEarlyExit) {
						if (Position.MarketPosition == MarketPosition.Long && Close[0] < rHigh) ExitLong("Early Exit");
						else if (Position.MarketPosition == MarketPosition.Short && Close[0] > rLow) ExitShort("Early Exit");
					}

					// Visuals: Active SL/TP Lines
					if (ShowExits)
					{
						// Re-calc active SL/TP for display (since we did it above for logic, but local scope)
						// We can use the 'sl' and 'tp' vars from logic block if we move this block inside, OR recalc.
						// Simpler to just recalc active SL/TP for visuals here if holding position.
						// actually 'sl' and 'tp' are local to the if block above.
						// We should ideally plot lines where we think they are.
						// Using the logic variables 'sl' and 'tp' isn't possible as they are out of scope here.
						// Valid approximation:
						Draw.Line(this, "SL_Line", true, 1, sl, -5, sl, Brushes.Red, DashStyleHelper.Dash, 2);
						Draw.Line(this, "TP_Line", true, 1, tp, -5, tp, Brushes.SpringGreen, DashStyleHelper.Dash, 2);
					}
				}
				else
				{
					// If Flat, remove old lines
					RemoveDrawObject("SL_Line");
					RemoveDrawObject("TP_Line");
				}
				// --- EXECUTION LOGIC END ---

				string status = Position.MarketPosition != MarketPosition.Flat ? "IN TRADE" : isTradingClosed ? "TRADING CLOSED" : isFiltered ? "SKIP (Filtered)" : (EntryModel == EntryMode.BreakoutClose ? "READY: Breakout" : "WAIT: Pullback");
				
				// rSize calculated at top of block
				double rPct = (rSize / BarsArray[0].GetOpen(0)) * 100;
				// Used calculated qty if available, or recalc for display if outside trading block
				int dashQty = DefaultQuantity; 
				if (RiskPercent > 0 && rSize > 0) 
					dashQty = (int)Math.Max(1, Math.Floor((InitialCapital * (RiskPercent / 100.0)) / (rSize * Instrument.MasterInstrument.PointValue)));

				string diagInfo = string.Format("{0} / {1}", isFiltered ? "FILT" : "OK", Position.MarketPosition == MarketPosition.Flat ? "YES" : "NO");
				
				bool isSweetSpot = UseSweetSpot && VVIX_Open >= 98 && VVIX_Open <= 115;
				bool isRangeTooBig = rPct > MaxRangePct;
				string vvixStatus = isSweetSpot ? "SWEET SPOT" : (VVIX_Open > 115 ? "EXTREME" : "NORMAL");
				string rangeWarning = isRangeTooBig ? " ⚠️TOO BIG" : "";
				
				// Transparent Shading for Range
				// Use Draw.Rectangle with Opacity (requires Brushes cleanup)
				if (rDefined)
				{
					Brush fillBrush = isRangeTooBig ? Brushes.Red : (isSweetSpot ? Brushes.Orange : Brushes.DeepSkyBlue);
					// Opacity handled by Draw.Rectangle opacity parameter (0-100)
					if (!isRangeTooBig && !isSweetSpot) fillBrush = Brushes.DeepSkyBlue; 
					
					// Draw Box (Transparent Fill)
					Draw.Rectangle(this, "RangeBox", true, 20, rHigh, 0, rLow, Brushes.Transparent, fillBrush, 20);
				}

				string hud = string.Format("REGIME: {0}\nVVIX: {1:F1} ({2})\nRANGE: {3:F2} pts ({4:F3}%){9}\nMODEL: {5}\nSIZE: {6} Lots\nSTATUS: {7}\nDIAG: {8}", 
					isBull ? "BULL" : "BEAR", VVIX_Open, vvixStatus, rSize, rPct, EntryModel, dashQty, status, diagInfo, rangeWarning);
				
				Draw.TextFixed(this, "HUD", hud, TextPosition.TopRight, Brushes.White, new Gui.Tools.SimpleFont("Arial", 11), Brushes.Black, Brushes.DimGray, 90);

				if (isRangeTooBig) Draw.Rectangle(this, "RangeBox", true, 20, rHigh, 0, rLow, Brushes.Transparent, Brushes.Yellow	, 10);
				// else if (isSweetSpot) Draw.Rectangle(this, "SweetSpot", true, 20, rHigh, 0, rLow, Brushes.Transparent, Brushes.Orange, 10);
				// Moved to Time-Based Drawing below

				// Visuals Sync: Draw Lines (DeepSkyBlue/OrangeRed) matching Indicator
				// Start: 9:30:XX EST (converted to Chart Time)
				int limitSeconds = (OrbDuration == ORB_Duration.OneMinute) ? 60 : 30;
				// Need date component, strictly today
				DateTime rangeDate = estTime.Date;
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
					
					// Draw Transparent Shaded Box (Time-Based)
					Brush fillBrush = isRangeTooBig ? Brushes.Red : (isSweetSpot ? Brushes.Orange : Brushes.DeepSkyBlue);
					if (!isRangeTooBig && !isSweetSpot) fillBrush = Brushes.DeepSkyBlue; 
					
					Draw.Rectangle(this, "RangeBox"+suffix, false, chartStart, rHigh, displayEnd, rLow, Brushes.Transparent, fillBrush, 20);
					
					// 0.10% Buffer Lines (Visual Aid)
					double bufferDist = rLow * 0.001;
					double buffHigh = rHigh + bufferDist;
					double buffLow = rLow - bufferDist;
					Draw.Line(this, "BuffHigh"+suffix, false, chartStart, buffHigh, displayEnd, buffHigh, Brushes.Gray, DashStyleHelper.Dot, 1);
					Draw.Line(this, "BuffLow"+suffix, false, chartStart, buffLow, displayEnd, buffLow, Brushes.Gray, DashStyleHelper.Dot, 1);
				}
				
				// Bar Coloring (Primary) - LOOK BACK METHOD (Synced with Indicator)
				if (rDefined && !paintedOrbBar)
				{
					// Look back up to 5 bars to find the 9:30/9:31 candle
					for (int i = 0; i <= 5; i++)
					{
						if (CurrentBar - i < 0) continue;
						
						DateTime barTimeEST = TimeZoneInfo.ConvertTime(Time[i], chartZone, estZone);
						// Match 9:30 (Start) or 9:31 (End)
						if (barTimeEST.Hour == 9 && (barTimeEST.Minute == 30 || barTimeEST.Minute == 31))
						{
							BarBrushes[i] = Brushes.Yellow;
							
							// Force Sync Gap Fix (Universal)
							if (High[i] > rHigh) rHigh = High[i];
							if (Low[i] < rLow) rLow = Low[i];
							
							paintedOrbBar = true; // Done for this session
							break;
						}
					}
				}
				if (CurrentBar == breakoutBarPrimary) BarBrush = Brushes.Cyan;
				
				// Fallback Marker (Lightning)
				if (CurrentBar == fallbackBarPrimary)
				{
					if (fallbackIsLong) Draw.Text(this, "Bolt"+CurrentBar, "⚡", 0, Low[0] - TickSize, Brushes.Lime);
					else Draw.Text(this, "Bolt"+CurrentBar, "⚡", 0, High[0] + TickSize, Brushes.Red);
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
		[Display(Name="Entry Model", Order=1, GroupName="Entry")]
		public NinjaTrader.NinjaScript.Strategies.EntryMode EntryModel { get; set; }

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
		public NinjaTrader.NinjaScript.Strategies.CandleExitMode SigCandleExit { get; set; }

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
		[Display(Name="Use Time Exit", Order=11, GroupName="Time")]
		public bool UseTimeExit { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Use Tuesday Filter", Order=12, GroupName="Addons")]
		public bool UseTuesday { get; set; }

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
		public NinjaTrader.NinjaScript.Strategies.RunnerModeType RunnerMode { get; set; }

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
