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
	public class HmaCrossOver : Strategy
	{
		private HMA HMA1;
		private HMA HMA2;
		private EMA SMA1;
		private ADX ADX1;
		private bool CrossDown = false;
		private bool CrossUp = false;
		private bool smaCrossUp = false;
		private bool smaCrossDown = false ;
		private bool adxUp = false;
		private HeikenAshi8 HAshi;
		// Daily Target 
		private int priorTradesCount        = 0;
		private double priorTradesCumProfit = 0;
		

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description									= @"This strategy takes a long position when the fast period hull moving average crosses avove the slow period hull moving average and short positions when crossing below. You can add a filter to only take long positions when price is above a simple moving average and short positions below the moving average. There is also a time filter to only enter trades during a set time period and an ADX minimum to filter out trades when the market is not trending";
				Name										= "HmaCrossOver";
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
				// Disable this property for performance gains in Strategy Analyzer optimizations
				// See the Help Guide for additional information
				IsInstantiatedOnEachOptimizationIteration	= false;
				StartTime						= DateTime.Parse("17:00", System.Globalization.CultureInfo.InvariantCulture);
				EndTime							= DateTime.Parse("13:00", System.Globalization.CultureInfo.InvariantCulture);
				FastPeriodHMA					= 23;
				SlowPeriodHMA					= 60;
				EnableSmaFilter					= true;
				SmaPeriod						= 100;
				EnableAdxFilter					= true;
				AdxMin							= 15;
				AdxPeriod						= 14;
				ProfitTarget					= 0.0015;
				StopLoss						= 0.001;
				
				Contracts                                   =   1;
				DailyLossLimit                              = -1000;
				DailyProfitLimit                            =  1000;
				DailyTradesCount                            =  10;
			}
			else if (State == State.Configure)
			{
			}
			else if (State == State.DataLoaded)
			{				
				HAshi 				= HeikenAshi8();
				AddChartIndicator(HAshi);
				HMA1				= HMA(HAshi.HAClose, Convert.ToInt32(FastPeriodHMA));
				HMA2				= HMA(HAshi.HAClose, Convert.ToInt32(SlowPeriodHMA));
				SMA1				= EMA(HAshi.HAClose, Convert.ToInt32(SmaPeriod));
				ADX1				= ADX(HAshi.HAClose, Convert.ToInt32(AdxPeriod));
				HMA1.Plots[0].Brush = Brushes.Lime;
				HMA2.Plots[0].Brush = Brushes.Red;
				SMA1.Plots[0].Brush = Brushes.Goldenrod;
				ADX1.Plots[0].Brush = Brushes.DarkCyan;
				AddChartIndicator(HMA1);
				AddChartIndicator(HMA2);
				AddChartIndicator(SMA1);
				AddChartIndicator(ADX1);
				//SetProfitTarget(@"Entry", CalculationMode.Percent, ProfitTarget);
				SetStopLoss(@"Entry", CalculationMode.Percent, StopLoss, false);
			}
		}

		protected override void OnBarUpdate()
		{
			if (BarsInProgress != 0) 
				return;

			if (CurrentBars[0] < 30)
				return;
			
			// Daily Target
			if (Bars.IsFirstBarOfSession)
				
			{
				// Store the strategy's prior cumulated realized profit and number of trades
				priorTradesCount = SystemPerformance.RealTimeTrades.Count;
				priorTradesCumProfit = SystemPerformance.RealTimeTrades.TradesPerformance.Currency.CumProfit;
				/* NOTE: Using . " AllTrades " will include both historical virtual trades as well as real-time trades.
				For only count profits from real-time trades use . " RealTimeTrades "  */
			}
			if (SystemPerformance.RealTimeTrades.TradesPerformance.Currency.CumProfit - priorTradesCumProfit >= DailyProfitLimit
				|| SystemPerformance.RealTimeTrades.TradesPerformance.Currency.CumProfit - priorTradesCumProfit <= DailyLossLimit 
				|| SystemPerformance.RealTimeTrades.Count - priorTradesCount > DailyTradesCount)
			{
				Draw.TextFixed(this, "limitText", "Daily loss / profit reached"
				, TextPosition.BottomRight);
				
				// Halt further processing of our strategy 
				return;
			}	
			else
			{
				RemoveDrawObject("limitText");
		    }
			

			HAshi 				= HeikenAshi8();
			
			HMA1				= HMA(HAshi.HAClose, Convert.ToInt32(FastPeriodHMA));
			HMA2				= HMA(HAshi.HAClose, Convert.ToInt32(SlowPeriodHMA));
			SMA1				= EMA(HAshi.HAClose, Convert.ToInt32(SmaPeriod));
			ADX1				= ADX(HAshi.HAClose, Convert.ToInt32(AdxPeriod));
			
			if (( HMA1[0] < HMA2[0])) //
			{
				CrossDown = true;
				CrossUp = false;
			}
			if (  HMA1[0] > HMA2[0])// CrossAbove(HMA1, HMA2, 1) || HMA1[0] > HMA2[0])
			{
				CrossDown = false;
				CrossUp = true;
			}
			
			adxUp = (EnableAdxFilter == true)?  ADX1[0] > AdxMin : true ;
			smaCrossUp = (EnableSmaFilter == true)? GetCurrentAsk(0) > SMA1[0] : true ;
			smaCrossDown = (EnableSmaFilter == true)? GetCurrentAsk(0) < SMA1[0] : true ;
			
			
			// Store the value of the crossover to re use for re entry into the trade in the right direction.
			// Some times the trade gets missed because of time restrictions or because of hitting the SL but the trade is still valid.
			// Another option is to consider the BarUp/Down strategy and combine it with this.
			// For Profit target, consider using a fixed or Swing/Pivot based approach to capture partial profits.
			// Also explore how to close the trade when a fixed percentage of profit is achieved.
			
			// Has a lot of losses in choppy conditions... but loses trades when ADX is turned on. :-(
			// May be ok to lose a little?
			// Meed to see how it performs when it is ranging with a wider range.
			// Need to think of using 3 HMA's like a envelope to navigate conditions or to stay/get out of a trade. (higher Higher time frame trend???)
			// Use of Heiken Ashi for calculations is also a idea to try out.
			// smaller HMA values gets stopped out faster leading to losing what ever profit is gained.
			
			
			if ((Position.MarketPosition == MarketPosition.Long )
				&& HMA1[1] < HMA1[0]  // Fast EMA hooking Down
				)
			{
				//ExitLong(@"Entry");
				//return;
			}
			
			if ((Position.MarketPosition == MarketPosition.Short )
				&& HMA1[1] > HMA1[0]  // Fast EMA hooking Up
				)
			{
				//ExitShort(@"Entry Short");
				//return;
			}
			
			if(Times[0][0].TimeOfDay < StartTime.TimeOfDay
				 && (Times[0][0].TimeOfDay > EndTime.TimeOfDay))
			{
				return;	
			}
			 // Set 1
			if ( (CrossUp)
				 && (smaCrossUp)
				 && (adxUp)
				 && (Position.MarketPosition != MarketPosition.Long )
				)
			{
				EnterLong(Convert.ToInt32(DefaultQuantity), @"Entry");
			}
			
			 // Set 2
			if ( (CrossDown)
				 && (smaCrossDown)
				 && (adxUp)
				 && (Position.MarketPosition != MarketPosition.Short ))
			{
				EnterShort(Convert.ToInt32(DefaultQuantity), @"Entry Short");
			}
			
			
//			 // Set 3
//			if ((Times[0][0].TimeOfDay > StartTime.TimeOfDay)
//				 && (Times[0][0].TimeOfDay < EndTime.TimeOfDay)
//				 && (CrossUp)
//				 && (EnableSmaFilter == true)
//				 && (EnableAdxFilter == false)
//				 && (GetCurrentAsk(0) > SMA1[0])
//				 && (Position.MarketPosition != MarketPosition.Long )
//				)
//			{
//				EnterLong(Convert.ToInt32(DefaultQuantity), @"Entry");
//			}
			
//			 // Set 4
//			if ((Times[0][0].TimeOfDay > StartTime.TimeOfDay)
//				 && (Times[0][0].TimeOfDay < EndTime.TimeOfDay)
//				 && (CrossDown)
//				 && (EnableSmaFilter == true)
//				 && (EnableAdxFilter == false)
//				 && (GetCurrentAsk(0) < SMA1[0])
//				 && (Position.MarketPosition != MarketPosition.Short )
//				)
//			{
//				EnterShort(Convert.ToInt32(DefaultQuantity), @"Entry");
//			}
			
//			 // Set 5
//			if ((Times[0][0].TimeOfDay > StartTime.TimeOfDay)
//				 && (Times[0][0].TimeOfDay < EndTime.TimeOfDay)
//				 && (CrossUp)
//				 && (EnableSmaFilter == false)
//				 && (EnableAdxFilter == true)
//				 && (ADX1[0] > AdxMin)
//				 && (Position.MarketPosition != MarketPosition.Long )
//				)
//			{
//				EnterLong(Convert.ToInt32(DefaultQuantity), @"Entry");
//			}
			
//			 // Set 6
//			if ((Times[0][0].TimeOfDay > StartTime.TimeOfDay)
//				 && (Times[0][0].TimeOfDay < EndTime.TimeOfDay)
//				 && (CrossDown)
//				 && (EnableSmaFilter == false)
//				 && (EnableAdxFilter == true)
//				 && (ADX1[0] > AdxMin)
//				 && (Position.MarketPosition != MarketPosition.Short )
//				)
//			{
//				EnterShort(Convert.ToInt32(DefaultQuantity), @"Entry");
//			}
			
//			 // Set 7
//			if ((Times[0][0].TimeOfDay > StartTime.TimeOfDay)
//				 && (Times[0][0].TimeOfDay < EndTime.TimeOfDay)
//				 && (CrossUp)
//				 && (EnableSmaFilter == true)
//				 && (EnableAdxFilter == true)
//				 && (GetCurrentAsk(0) > SMA1[0])
//				 && (ADX1[0] > AdxMin)
//				 && (Position.MarketPosition != MarketPosition.Long )
//				)
//			{
//				EnterLong(Convert.ToInt32(DefaultQuantity), @"Entry");
//			}
			
//			 // Set 8
//			if ((Times[0][0].TimeOfDay > StartTime.TimeOfDay)
//				 && (Times[0][0].TimeOfDay < EndTime.TimeOfDay)
//				 && (CrossDown) 
//				 && (EnableSmaFilter == true)
//				 && (EnableAdxFilter == true)
//				 && (GetCurrentAsk(0) < SMA1[0])
//				 && (ADX1[0] > AdxMin)
//				 && (Position.MarketPosition != MarketPosition.Short )
//				)
//			{
//				EnterShort(Convert.ToInt32(DefaultQuantity), @"Entry");
//			}
			
		}

		#region Properties
		[NinjaScriptProperty]
		[PropertyEditor("NinjaTrader.Gui.Tools.TimeEditorKey")]
		[Display(Name="StartTime", Order=1, GroupName="Parameters")]
		public DateTime StartTime
		{ get; set; }

		[NinjaScriptProperty]
		[PropertyEditor("NinjaTrader.Gui.Tools.TimeEditorKey")]
		[Display(Name="EndTime", Order=2, GroupName="Parameters")]
		public DateTime EndTime
		{ get; set; }

		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name="FastPeriodHMA", Order=3, GroupName="Parameters")]
		public int FastPeriodHMA
		{ get; set; }

		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name="SlowPeriodHMA", Order=4, GroupName="Parameters")]
		public int SlowPeriodHMA
		{ get; set; }

		[NinjaScriptProperty]
		[Display(Name="EnableSmaFilter", Order=5, GroupName="Parameters")]
		public bool EnableSmaFilter
		{ get; set; }

		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name="SmaPeriod", Order=6, GroupName="Parameters")]
		public int SmaPeriod
		{ get; set; }

		[NinjaScriptProperty]
		[Display(Name="EnableAdxFilter", Order=7, GroupName="Parameters")]
		public bool EnableAdxFilter
		{ get; set; }

		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name="AdxMin", Order=8, GroupName="Parameters")]
		public int AdxMin
		{ get; set; }

		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name="AdxPeriod", Order=9, GroupName="Parameters")]
		public int AdxPeriod
		{ get; set; }

		[NinjaScriptProperty]
		[Range(0, double.MaxValue)]
		[Display(Name="ProfitTarget", Description="Profit Target (percent based)", Order=10, GroupName="Parameters")]
		public double ProfitTarget
		{ get; set; }

		[NinjaScriptProperty]
		[Range(0, double.MaxValue)]
		[Display(Name="StopLoss", Description="Stop Loss (percent based)", Order=11, GroupName="Parameters")]
		public double StopLoss
		{ get; set; }
		
		
		[Range(1, int.MaxValue)]
		[NinjaScriptProperty]
		[Display(Name="Contracts", Description="The number of contracts to trade", Order=1, GroupName="Daily Target")]
		public int Contracts
		{ get; set; }
		
		[NinjaScriptProperty]
		[Display(Name = "DailyLossLimit", Description = "Daily Loss Limit", Order = 2, GroupName = "Daily Target")]
		public double DailyLossLimit
		{ get; set; }

		[NinjaScriptProperty]
		[Display(Name = "DailyProfitLimit", Description = "Daily Profit Limit", Order = 3, GroupName = "Daily Target")]
		public double DailyProfitLimit
		{ get; set; }
		
		[Range(1, int.MaxValue)]
		[NinjaScriptProperty]
		[Display(Name="DailyTradesCount", Description="The number of daily TradesCount", Order=4, GroupName="Daily Target")]
		public int DailyTradesCount
		{ get; set; }
		#endregion

	}
}

