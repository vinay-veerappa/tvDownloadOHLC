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
using NinjaTrader.NinjaScript.Indicators.Infinity;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

//This namespace holds Strategies in this folder and is required. Do not change it. 
namespace NinjaTrader.NinjaScript.Strategies
{
	public class WilliamsRStrategy : Strategy
	{
		private WilliamsR WilliamsR1;
		private EMA willy_Signal;
		private EMA willy_EmaOfSignal;
		private HalfTrend halfTrend;
		
		private AuSuperTrendU11 AuSuperTrendU111;
		
		private int		breakEvenTicks		= 30;		// Default setting for ticks needed to acheive before stop moves to breakeven		
		private int		plusBreakEven		= 10; 		// Default setting for amount of ticks past breakeven to actually breakeven
		private int 	BarTraded 			= 0; 		// Default setting for Bar number that trade occurs	
		private double	initialBreakEven	= 0; 		// Default setting for where you set the breakeven
		private double 	previousPrice		= 0;		// previous price used to calculate trailing stop
		private double 	newPrice			= 0;		// Default setting for new price used to calculate trailing stop

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description									= @"Using Williams R ";
				Name										= "WilliamsRStrategy";
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
				IsInstantiatedOnEachOptimizationIteration	= true;
				
				WillyLen						= 21;
				WillySignalEMA					= 13;
				EMAOfWillyEMA					= 26 ;
				
				
				// Times
				Session1 = true;
				Session1Start = 20000;   
				Session1End = 223059;  

				Session2 = false;
				Session2Start = 90000;
				Session2End = 110000;
				
				Session3 = false;
				Session3Start = 120000;
				Session3End = 125900;

				//UseATRforStopLoss							= false;
				//adxPeriod									= 14;
				//useAdx										= false ;
				//adxThreshold								= 25 ;
				

				
				breakEvenTicks		= 10;		// Default setting for ticks needed to acheive before stop moves to breakeven		
				//plusBreakEven		= 2; 		// Default setting for amount of ticks past breakeven to actually breakeven
				profitTargetTicks	= 30;		// Default setting for how many Ticks away from AvgPrice is profit target
		        stopLossTicks		= 60;		// Default setting for stoploss. Ticks away from AvgPrice		
				trailProfitTrigger	= 5;		// 8 Default Setting for trail trigger ie the number of ticks movede after break even befor activating TrailStep
				trailStepTicks		= 5;		// 2 Default setting for number of ticks advanced in the trails 
			}
			else if (State == State.Configure)
			{
				SetStopLoss(CalculationMode.Ticks, stopLossTicks);
				//SetProfitTarget(CalculationMode.Ticks, profitTargetTicks);
			}
			else if (State == State.DataLoaded)
			{				
				WilliamsR1				= WilliamsR(Close, WillyLen);
				willy_Signal		= EMA(WilliamsR1, WillySignalEMA);
				willy_EmaOfSignal	= EMA(willy_Signal, EMAOfWillyEMA);
				
				AuSuperTrendU111				= AuSuperTrendU11(Close, AuSuperTrendU11BaseType.Median, AuSuperTrendU11OffsetType.Median, AuSuperTrendU11VolaType.True_Range, false, 2, 1.5, 15);
				AuSuperTrendU111.Plots[0].Brush = Brushes.Gray;
				AuSuperTrendU111.Plots[1].Brush = Brushes.Gray;
				AuSuperTrendU111.Plots[2].Brush = Brushes.Transparent;
				AddChartIndicator(AuSuperTrendU111);
				
				halfTrend = HalfTrend( 2, 2, 100, false,true, 10);
			}
		}

		private void FillLongEntry1()
		{
			Print("Entering Long");
			EnterLong(1,Convert.ToInt32(DefaultQuantity), "Long");
			BarTraded = CurrentBar;
		}
		
		private void FillShortEntry1()
		{
			Print("Entering Short");	
			EnterShort(1,Convert.ToInt32(DefaultQuantity), "Short");
			BarTraded = CurrentBar;
		}  
		
		private bool canTradeTime()
		{
			int currentTime = ToTime( Time[0] );
			bool doTrade = false;
				
			if( (Session1
				&& (currentTime >= Session1Start && currentTime <= Session1End)) )
			{
				doTrade = true;
			}
			else if( (Session2
				&& (currentTime >= Session2Start && currentTime <= Session2End)) )
			{
				doTrade = true;
			}
			else if( (Session3
					&& (currentTime >= Session3Start && currentTime <= Session3End)) )	
			{
				doTrade = true;
			}

			return doTrade;
		}
		
		protected override void OnBarUpdate()
		{
			if (BarsInProgress != 0) 
				return;

			if (CurrentBars[0] < 1)
				return;

			// Times 
			if( !canTradeTime()) {
				// Halt further processing of our strategy 
				return;
			}
			
			// Resets the stop loss to the original value when all positions are closed
			switch (Position.MarketPosition)
            {
                case MarketPosition.Flat:
                    SetStopLoss(CalculationMode.Ticks, stopLossTicks);
					previousPrice = 0;
                    break;
                default:
					//autoStopA900Traded = false;
                    break;
			}
			
			// Go Long when 
			if (Position.MarketPosition != MarketPosition.Long
				&& (willy_Signal[0] >= willy_EmaOfSignal[0])
				&& AuSuperTrendU111.StopLine[1]!=AuSuperTrendU111.StopLine[0] 
				//&& AuSuperTrendU111.Trend[0] > 0
				//&& halfTrend.Trend[1] != halfTrend.Trend[0] 
				)
			{
				EnterLong(Convert.ToInt32(DefaultQuantity), @"BuyLong");
				SetStopLoss(CalculationMode.Ticks, stopLossTicks);
			}
			
			if (Position.MarketPosition == MarketPosition.Long
				&& (willy_Signal[0] <= willy_EmaOfSignal[0]))
			{
				ExitLong();
			}
			//Go Short when

			if (Position.MarketPosition != MarketPosition.Short
				&& (willy_Signal[0] <= willy_EmaOfSignal[0]) 
				&& AuSuperTrendU111.StopLine[1]!=AuSuperTrendU111.StopLine[0] 
				//&& AuSuperTrendU111.Trend[0] > 0
				//&& halfTrend.Trend[1] != halfTrend.Trend[0] 
				)
			{
				EnterShort(Convert.ToInt32(DefaultQuantity), @"GoShort");
				SetStopLoss(CalculationMode.Ticks, stopLossTicks);
			}
			if (Position.MarketPosition == MarketPosition.Short
				&& (willy_Signal[0] >= willy_EmaOfSignal[0]))
			{
				ExitShort();
			}
		}

		#region Properties
		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name="Willy Length", Description="Lenght of the Williams %R input", Order=1, GroupName="Parameters")]
		public int WillyLen
		{ get; set; }
		
		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name="Willy Signal EMA", Description="EMA of the Williams %R value", Order=2, GroupName="Parameters")]
		public int WillySignalEMA
		{ get; set; }

		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name="EMAOfWillyEMA", Order=3, GroupName="Parameters")]
		public int EMAOfWillyEMA
		{ get; set; }

		[NinjaScriptProperty]
		[Display(ResourceType = typeof(Custom.Resource), Name="Use Session 1 times?", Description="True to use Session 1 start/end times)", Order=1, GroupName="Times")]		
		public bool Session1
		{ get; set; }

		[NinjaScriptProperty]
		[Range(0, 235959)]
		[Display(ResourceType = typeof(Custom.Resource), Name="Session 1 start time", Description="Session 1 start time", Order=2, GroupName="Times")]		
		public int Session1Start
		{ get; set; }        
		
		[NinjaScriptProperty]
		[Range(0, 235959)]
		[Display(ResourceType = typeof(Custom.Resource), Name="Session 1 end time", Description="Session 1 end time", Order=3, GroupName="Times")]		
		public int Session1End
		{ get; set; }        

		[NinjaScriptProperty]
		[Display(ResourceType = typeof(Custom.Resource), Name="Use Session 2 times?", Description="True to use Session 3 start/end times)", Order=4, GroupName="Times")]		
		public bool Session2
		{ get; set; }        

		[NinjaScriptProperty]
		[Range(0, 235959)]
		[Display(ResourceType = typeof(Custom.Resource), Name="Session 2 start time", Description="Session 2 start time", Order=5, GroupName="Times")]		
		public int Session2Start
		{ get; set; }        

		[NinjaScriptProperty]
		[Range(0, 235959)]
		[Display(ResourceType = typeof(Custom.Resource), Name="Session 2 end time", Description="Session 1 end time", Order=6, GroupName="Times")]		
		public int Session2End
		{ get; set; }        

		[NinjaScriptProperty]
		[Display(ResourceType = typeof(Custom.Resource), Name="Use Session 3 times?", Description="True to use Session 3 start/end times)", Order=7, GroupName="Times")]		
		public bool Session3
		{ get; set; }        

		[NinjaScriptProperty]
		[Range(0, 235959)]
		[Display(ResourceType = typeof(Custom.Resource), Name="Session 3 start time", Description="Session 3 end time", Order=8, GroupName="Times")]		
		public int Session3Start
		{ get; set; }        

		[NinjaScriptProperty]
		[Range(0, 235959)]
		[Display(ResourceType = typeof(Custom.Resource), Name="Session 3 end time", Description="Session 3 end time", Order=9, GroupName="Times")]		
		public int Session3End
		{ get; set; }   

		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name="TakeProfitTicks", Description="What is the min Profit target", Order=10, GroupName="Parameters")]
		public int profitTargetTicks
		{ get; set; }

		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name="StopLossTicks", Description="What is the StopLoss", Order=11, GroupName="Parameters")]
		public int stopLossTicks
		{ get; set; }


		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name="TrailProfitTrigger", Description="Profit Trigger for stop loss trailing", Order=12, GroupName="Parameters")]
		public int trailProfitTrigger
		{ get; set; }

		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name="TrailStepTicks", Description="Steps at which we will trail the profit", Order=13, GroupName="Parameters")]
		public int trailStepTicks
		{ get; set; }
		#endregion


	}
}
