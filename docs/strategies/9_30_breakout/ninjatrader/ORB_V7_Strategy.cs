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
	public class ORB_V7_Strategy : Strategy
	{
		// Enums defined locally or reused from namespace if possible
		// Since V6 defined them in the namespace, we can reuse if namespace matches.
		// However, to be safe and self-contained, if they are legally in the namespace, we can use them.
		
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
		private bool hasWonToday = false;
		private double prevClosedProfit = 0;
		private bool enteredViaFallback = false;
		private double breakoutCandleExtreme = double.NaN;
		private DateTime lastResetDate = DateTime.MinValue;
		private bool paintedOrbBar = false;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description									= @"9:30 AM Breakout Strategy V7.1 [Optimized]";
				Name										= "ORB_V7_Strategy";
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
				
				// Initialize Inputs (V7 Defaults)
				ChartTimeZone = "Pacific Standard Time";
				OrbDuration = ORB_Duration.OneMinute;
				EntryModel = EntryMode.BreakoutClose; // Default is IMMEDIATE in V7 plan implies BreakoutClose
				
				// V7 New Defaults
				UseConfirmedEntry = true;
				ConfirmPct = 0.10;
				
				MaxAttempts = 3;
				PBConfirm = true;
				BufferBreakout = true;
				PBTimeoutBars = 5;
				TP_Pct = 0.35;
				MAE_Threshold = 0.12;
				UseRegime = true;
				UseVVIX = true;
				UseSweetSpot = true;
				
				InitialCapital              = 100000;
				RiskPercent                 = 1.0; // V7 Plan: 1.0%
				MaxSlPct                    = 0.30; 
				StopAfterWin                = true;
				ShowExits                   = true;
				VVIX_Open = 100.0;
				UseEarlyExit = true;
				UseMAEFilter = true;
				SigCandleExit = CandleExitMode.None; // Legacy
				UseEngulfingExit = true; // V7 New
				
				MaxRangePct = 0.25;
				EnableMultiTP = true;
				TP1Level = 0.05; // V7 Default
				TP1QtyPct = 50;
				TP2Level = 0.25;
				TP2QtyPct = 25;
				RunnerMode = RunnerModeType.Trailing;
				TrailPct = 0.08;
				
				UseTuesday = false; // V7 Default OFF
				UseWednesday = false; // V7 New OFF
				
				HardExitTime = DateTime.Parse("11:00", System.Globalization.CultureInfo.InvariantCulture); // V7 Default
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

		protected override void OnBarUpdate()
		{
			// Strict Safety Checks
			if (CurrentBars[0] < 1) return;
			if (BarsArray.Length > 1 && CurrentBars[1] < 1) return;
			if (BarsArray.Length > 2 && CurrentBars[2] < 1) return;
			if (BarsArray.Length < 2) return;

			// Logic Block: Execute ONLY on 1-Second Series (Index 1)
			if (BarsInProgress == 1)
			{
				DateTime estTime;
				if (chartZone != null) estTime = TimeZoneInfo.ConvertTime(Time[0], chartZone, estZone);
				else estTime = Time[0];

				// Robust Reset Logic
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
					paintedOrbBar = false; 
					lastResetDate = estTime.Date;
					
					if (SystemPerformance.AllTrades.Count > 0)
						prevClosedProfit = SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;
					else 
						prevClosedProfit = 0;
						
					breakoutBarPrimary = -1;
					fallbackBarPrimary = -1;
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

				if (!rDefined && timeOfDay > endTime)
				{
					rDefined = rHigh > double.MinValue && rLow < double.MaxValue;
				}
			}

			// Primary Logic Loop (BiP 0)
			if (BarsInProgress == 0 && rDefined)
			{
				DateTime estTime;
				if (chartZone != null) estTime = TimeZoneInfo.ConvertTime(Time[0], chartZone, estZone);
				else estTime = Time[0];

				bool isTradingClosed = estTime.TimeOfDay >= HardExitTime.TimeOfDay;
				
				// Re-calc Filter Logic
				bool isBull = true; 
				if (UseRegime && BarsArray.Length > 2 && BarsArray[2].Count >= 20) {
					isBull = BarsArray[2].GetClose(0) > regimeSMA[0];
				}
				bool isTuesday = estTime.DayOfWeek == DayOfWeek.Tuesday;
				bool isWednesday = estTime.DayOfWeek == DayOfWeek.Wednesday; // V7 Logic
				
				bool isFiltered = (UseVVIX && VVIX_Open > 115) || (UseRegime && !isBull) || (UseTuesday && isTuesday) || (UseWednesday && isWednesday);

				double rSize = rHigh - rLow;

				// --- EXECUTION LOGIC START ---
				if (StopAfterWin && !hasWonToday && SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit > prevClosedProfit + 10) 
					hasWonToday = true;

				bool canTrade = !isFiltered && !isTradingClosed && attemptsToday < MaxAttempts && !hasWonToday && Position.MarketPosition == MarketPosition.Flat;

				if (canTrade)
				{
					int qty = DefaultQuantity;
					if (RiskPercent > 0 && rSize > 0)
					{
						double riskAmt = InitialCapital * (RiskPercent / 100.0);
						qty = (int)Math.Max(1, Math.Floor(riskAmt / (rSize * Instrument.MasterInstrument.PointValue)));
					}

					bool breakoutLong = false;
					bool breakoutShort = false;

					// Breakout Detection
					// V7: Confirmed Entry Logic
					if (UseConfirmedEntry) {
						double confirmLong = rHigh * (1.0 + ConfirmPct/100.0);
						double confirmShort = rLow * (1.0 - ConfirmPct/100.0);
						
						breakoutLong = CrossAbove(Close, confirmLong, 1);
						breakoutShort = CrossBelow(Close, confirmShort, 1);
					}
					else if (EntryModel == EntryMode.BreakoutClose)
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
								}
								else if (breakoutShort) { 
									EnterShort(0, qty, "BreakoutSell"); 
									attemptsToday++; 
									breakoutBarPrimary = CurrentBar; 
									Draw.TriangleDown(this, "SignalDown"+CurrentBar, true, 0, High[0] + TickSize, Brushes.Red);
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
					
					// Pullback State Logic (Same as V6)
					int barsSinceBreakout = breakoutBar >= 0 ? CurrentBar - breakoutBar : 0;
					bool timeoutReached = barsSinceBreakout >= PBTimeoutBars;

					if (longPending)
					{
						if (Close[0] < pbLongPrice) { longPending = false; breakoutBar = -1;  }
						else if (Low[0] <= pbLongPrice && Close[0] >= pbLongPrice) {
							EnterLong(0, qty, "PB Long (Conf)");
							longPending = false; breakoutBar = -1; attemptsToday++; enteredViaFallback = false;
							Draw.Text(this, "PBText"+CurrentBar, "PB BUY", 0, Low[0] - 2*TickSize, Brushes.SpringGreen);
							Draw.TriangleUp(this, "PBUp"+CurrentBar, true, 0, Low[0] - TickSize, Brushes.SpringGreen);
						}
						else if (timeoutReached && Close[0] > rHigh) {
							EnterLong(0, qty, "Timeout Long");
							longPending = false; breakoutBar = -1; attemptsToday++; enteredViaFallback = true;
							fallbackBarPrimary = CurrentBar; fallbackIsLong = true;
						}
						else if (Close[0] < rLow) { longPending = false; breakoutBar = -1;  }
					}
					
					if (shortPending)
					{
						if (Close[0] > pbShortPrice) { shortPending = false; breakoutBar = -1;  }
						else if (High[0] >= pbShortPrice && Close[0] <= pbShortPrice) {
							EnterShort(0, qty, "PB Short (Conf)");
							shortPending = false; breakoutBar = -1; attemptsToday++; enteredViaFallback = false;
							Draw.Text(this, "PBText"+CurrentBar, "PB SELL", 0, High[0] + 2*TickSize, Brushes.Red);
							Draw.TriangleDown(this, "PBDown"+CurrentBar, true, 0, High[0] + TickSize, Brushes.Red);
						}
						else if (timeoutReached && Close[0] < rLow) {
							EnterShort(0, qty, "Timeout Short");
							shortPending = false; breakoutBar = -1; attemptsToday++; enteredViaFallback = true;
							fallbackBarPrimary = CurrentBar; fallbackIsLong = false;
						}
						else if (Close[0] > rHigh) { shortPending = false; breakoutBar = -1;  }
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

					// Exits
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
						// Single Exit
						if (Position.MarketPosition == MarketPosition.Long) {
							ExitLongLimit(0, true, Position.Quantity, tp, "Target", "");
							ExitLongStopMarket(0, true, Position.Quantity, sl, "Stop", "");
						} else {
							ExitShortLimit(0, true, Position.Quantity, tp, "Target", "");
							ExitShortStopMarket(0, true, Position.Quantity, sl, "Stop", "");
						}
					}
					
					// MAE Cut
					if (UseMAEFilter) {
						double heatDist = entry * (MAE_Threshold / 100);
						if (Position.MarketPosition == MarketPosition.Long && Low[0] < entry - heatDist) ExitLong("MAE Cut");
						else if (Position.MarketPosition == MarketPosition.Short && High[0] > entry + heatDist) ExitShort("MAE Cut");
					}
					
					// V7: Engulfing Exit
					if (UseEngulfingExit && breakoutBarPrimary != -1 && CurrentBar == breakoutBarPrimary + 1)
					{
						// Check engulfing pattern on the bar AFTER breakout
						bool isLong = Position.MarketPosition == MarketPosition.Long;
						bool isEngulfing = false;
						
						double boOpen = Open[1];
						double boClose = Close[1];
						
						if (isLong)
						{
							// Bearish Engulfing: Current red, engulfs previous green body
							// Pine: close < open and close < breakoutOpen and open > breakoutClose
							isEngulfing = Close[0] < Open[0] && Close[0] < boOpen && Open[0] > boClose;
						}
						else
						{
							// Bullish Engulfing: Current green, engulfs previous red body
							// Pine: close > open and close > breakoutOpen and Open < breakoutClose
							isEngulfing = Close[0] > Open[0] && Close[0] > boOpen && Open[0] < boClose;
						}
						
						if (isEngulfing)
						{
							if (isLong) ExitLong("Engulfing Exit");
							else ExitShort("Engulfing Exit");
							Draw.Text(this, "Engulf"+CurrentBar, "Engulfing", 0, isLong?High[0]:Low[0], Brushes.Magenta);
						}
					}
					
					// Legacy Sig Candle
					if (SigCandleExit != CandleExitMode.None && !double.IsNaN(sigCandleExtreme)) {
						bool isLong = Position.MarketPosition == MarketPosition.Long;
						bool sigTrigger = (SigCandleExit == CandleExitMode.Wick) ? (isLong ? Low[0] < sigCandleExtreme : High[0] > sigCandleExtreme)
																				 : (isLong ? Close[0] < sigCandleExtreme : Close[0] > sigCandleExtreme);
						if (sigTrigger) { if(isLong) ExitLong("Sig Candle"); else ExitShort("Sig Candle"); sigCandleExtreme = double.NaN; }
					}
					
					// Early Exit
					if (UseEarlyExit) {
						if (Position.MarketPosition == MarketPosition.Long && Close[0] < rHigh) ExitLong("Early Exit");
						else if (Position.MarketPosition == MarketPosition.Short && Close[0] > rLow) ExitShort("Early Exit");
					}

					// Visuals: Active SL/TP Lines
					if (ShowExits)
					{
						Draw.Line(this, "SL_Line", true, 1, sl, -5, sl, Brushes.Red, DashStyleHelper.Dash, 2);
						Draw.Line(this, "TP_Line", true, 1, tp, -5, tp, Brushes.SpringGreen, DashStyleHelper.Dash, 2);
					}
				}
				else
				{
					RemoveDrawObject("SL_Line");
					RemoveDrawObject("TP_Line");
				}
				// --- EXECUTION LOGIC END ---

				string status = Position.MarketPosition != MarketPosition.Flat ? "IN TRADE" : isTradingClosed ? "TRADING CLOSED" : isFiltered ? "SKIP (Filtered)" : (EntryModel == EntryMode.BreakoutClose ? "READY: Breakout" : "WAIT: Pullback");
				
				double rPct = (rSize / BarsArray[0].GetOpen(0)) * 100;
				int dashQty = DefaultQuantity; 
				if (RiskPercent > 0 && rSize > 0) 
					dashQty = (int)Math.Max(1, Math.Floor((InitialCapital * (RiskPercent / 100.0)) / (rSize * Instrument.MasterInstrument.PointValue)));

				string diagInfo = string.Format("{0} / {1}", isFiltered ? "FILT" : "OK", Position.MarketPosition == MarketPosition.Flat ? "YES" : "NO");
				string confirmText = UseConfirmedEntry ? string.Format("CONFIRMED ({0}%)", ConfirmPct) : "STANDARD";
				
				bool isSweetSpot = UseSweetSpot && VVIX_Open >= 98 && VVIX_Open <= 115;
				bool isRangeTooBig = rPct > MaxRangePct;
				string vvixStatus = isSweetSpot ? "SWEET SPOT" : (VVIX_Open > 115 ? "EXTREME" : "NORMAL");
				string rangeWarning = isRangeTooBig ? " ⚠️TOO BIG" : "";
				
				if (rDefined)
				{
					Brush fillBrush = isRangeTooBig ? Brushes.Red : (isSweetSpot ? Brushes.Orange : Brushes.DeepSkyBlue);
					if (!isRangeTooBig && !isSweetSpot) fillBrush = Brushes.DeepSkyBlue; 
					Draw.Rectangle(this, "RangeBox", true, 20, rHigh, 0, rLow, Brushes.Transparent, fillBrush, 20);
				}

				string hud = string.Format("REGIME: {0}\nVVIX: {1:F1} ({2})\nRANGE: {3:F2} pts ({4:F3}%){9}\nENTRY: {10}\nSIZE: {6} Lots\nSTATUS: {7}\nDIAG: {8}", 
					isBull ? "BULL" : "BEAR", VVIX_Open, vvixStatus, rSize, rPct, EntryModel, dashQty, status, diagInfo, rangeWarning, confirmText);
				
				Draw.TextFixed(this, "HUD", hud, TextPosition.TopRight, Brushes.White, new Gui.Tools.SimpleFont("Arial", 11), Brushes.Black, Brushes.DimGray, 90);

				if (isRangeTooBig) Draw.Rectangle(this, "RangeBox", true, 20, rHigh, 0, rLow, Brushes.Transparent, Brushes.Yellow	, 10);
				
				// Draw Range Lines
				int limitSeconds = (OrbDuration == ORB_Duration.OneMinute) ? 60 : 30;
				DateTime rangeDate = estTime.Date;
				DateTime estOpen = rangeDate.Add(new TimeSpan(9, 30, limitSeconds));
				DateTime estEnd = rangeDate.Add(new TimeSpan(16, 0, 0));

				DateTime chartStart = TimeZoneInfo.ConvertTime(estOpen, estZone, chartZone);
				DateTime chartEnd = TimeZoneInfo.ConvertTime(estEnd, estZone, chartZone);

				DateTime displayEnd = (Time[0] < chartEnd && State == State.Realtime) ? Time[0] : chartEnd;
				
				string suffix = rangeDate.ToString("yyyyMMdd");
				
				Draw.Line(this, "High"+suffix, false, chartStart, rHigh, displayEnd, rHigh, Brushes.DeepSkyBlue, DashStyleHelper.Solid, 2);
				Draw.Line(this, "Low"+suffix, false, chartStart, rLow, displayEnd, rLow, Brushes.OrangeRed, DashStyleHelper.Solid, 2);
				
				// V7: Draw Confirmation Lines if enabled
				if (UseConfirmedEntry) {
					double ch = rHigh * (1.0 + ConfirmPct/100.0);
					double cl = rLow * (1.0 - ConfirmPct/100.0);
					Draw.Line(this, "ConfHigh"+suffix, false, chartStart, ch, displayEnd, ch, Brushes.Lime, DashStyleHelper.Dot, 1);
					Draw.Line(this, "ConfLow"+suffix, false, chartStart, cl, displayEnd, cl, Brushes.Red, DashStyleHelper.Dot, 1);
				}
				
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
				if (CurrentBar == breakoutBarPrimary) BarBrush = Brushes.Cyan;
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
		[Display(Name="Use Confirmed Entry", Order=2, GroupName="Entry")]
		public bool UseConfirmedEntry { get; set; }
		
		[NinjaScriptProperty]
		[Display(Name="Confirm % Loop", Order=3, GroupName="Entry")]
		public double ConfirmPct { get; set; }

		[NinjaScriptProperty]
		[Display(Name="PB Confirmation (Close)", Order=4, GroupName="Entry")]
		public bool PBConfirm { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Buffer Breakout (0.10%)", Order=5, GroupName="Entry")]
		public bool BufferBreakout { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Pullback Timeout (Bars)", Order=6, GroupName="Entry")]
		public int PBTimeoutBars { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Max Attempts", Order=7, GroupName="Entry")]
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
		[Display(Name="Use Engulfing Exit", Order=11, GroupName="Addons")]
		public bool UseEngulfingExit { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Signal Candle Exit", Order=12, GroupName="Addons")]
		public NinjaTrader.NinjaScript.Strategies.CandleExitMode SigCandleExit { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Use VVIX Filter (Skip if > 115)", Order=13, GroupName="Addons")]
		public bool UseVVIX { get; set; }

		[NinjaScriptProperty]
		[Display(Name="VVIX Open Value", Order=14, GroupName="Addons")]
		public double VVIX_Open { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Use Early Exit (Inside)", Order=15, GroupName="Addons")]
		public bool UseEarlyExit { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Use Time Exit", Order=11, GroupName="Time")]
		public bool UseTimeExit { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Use Tuesday Filter", Order=16, GroupName="Addons")]
		public bool UseTuesday { get; set; }
		
		[NinjaScriptProperty]
		[Display(Name="Use Wednesday Filter", Order=17, GroupName="Addons")]
		public bool UseWednesday { get; set; }

		[NinjaScriptProperty]
		[PropertyEditor("NinjaTrader.Gui.Tools.TimeEditorKey")]
		[Display(Name="Hard Exit Time", Order=11, GroupName="Core")]
		public DateTime HardExitTime { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Max Range % (Skip if larger)", Order=18, GroupName="Addons")]
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
