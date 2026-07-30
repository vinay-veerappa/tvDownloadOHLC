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
	public class BB1 : Strategy
	{
		private Bollinger Bollinger1;
		private Bollinger Bollinger2;
		private int countLong = 0;
		private int countShort = 0;
		
		private AuSuperTrendU11 AuSuperTrendU111;
		
		private int		breakEvenTicks		= 30;		// Default setting for ticks needed to acheive before stop moves to breakeven		
		private int		plusBreakEven		= 10; 		// Default setting for amount of ticks past breakeven to actually breakeven
		private int 	BarTraded 			= 0; 		// Default setting for Bar number that trade occurs	
		private double	initialBreakEven	= 0; 		// Default setting for where you set the breakeven
		private double 	previousPrice		= 0;		// previous price used to calculate trailing stop
		private double 	newPrice			= 0;		// Default setting for new price used to calculate trailing stop
		private 		HMA hmaHigh			;
		private 		HMA hmaSlow			;
		private double	adxValue 			= 0 ;
		private int		hmaLookBackPeriod	= 1 ;
		
		
		
		//private HeikenAshiSmoothed HAshi;
		//private HeikenAshi8Rounded HAshi;
		//private HeikenAshi8 HAshi;
		private vxvHeikenAshi HAshi;		
		private RSI	rsi ;
		StdDev  stddev;
		
		//protected bool myCrossAbove(ISeries <double> series1, ISeries <double> series2,  int lookahead )
		//{
			//if(series1 >= series2) return true;
			//	else return false;
		//}

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description									= @"Enter the description for your new custom Strategy here.";
				Name										= "BB1";
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
				BarsRequiredToTrade							= 100;
				// Disable this property for performance gains in Strategy Analyzer optimizations
				// See the Help Guide for additional information
				IsInstantiatedOnEachOptimizationIteration	= true;
				
				LongTermMAPeriod							= 81;
				ShortTermMAPeriod							= 21;
				Use3Candles									= true;
				
				// Times
				Session1 = true;
				Session1Start = 10000;   
				Session1End = 133059;  

				Session2 = false;
				Session2Start = 90000;
				Session2End = 110000;
				
				Session3 = false;
				Session3Start = 120000;
				Session3End = 125900;

				UseATRforStopLoss							= false;
				adxPeriod									= 14;
				useAdx										= false ;
				adxThreshold								= 25 ;
				
				
				BBPeriod					= 14 ;
				StdDeviations				=2 ;
				
				breakEvenTicks		= 10;		// Default setting for ticks needed to acheive before stop moves to breakeven		
				//plusBreakEven		= 2; 		// Default setting for amount of ticks past breakeven to actually breakeven
				profitTargetTicks	= 30;		// Default setting for how many Ticks away from AvgPrice is profit target
		        stopLossTicks		= 80;		// Default setting for stoploss. Ticks away from AvgPrice		
				trailProfitTrigger	= 5;		// 8 Default Setting for trail trigger ie the number of ticks movede after break even befor activating TrailStep
				trailStepTicks		= 5;		// 2 Default setting for number of ticks advanced in the trails - take into consideration the barsize as is calculated/advanced next bar
			}
			else if (State == State.Configure)
			{
				
				SetStopLoss(CalculationMode.Ticks, stopLossTicks);
				//SetProfitTarget(CalculationMode.Ticks, profitTargetTicks);
			}
			else if (State == State.DataLoaded)
			{				
		//		HAshi 				= HeikenAshiSmoothed(Brushes.Red, Brushes.LightGreen,Brushes.Transparent,2,10,
		//												false,true,34,2, DashStyleHelper.Solid, Brushes.Blue);
				//HAshi 	= HeikenAshi8Rounded();
				//HAshi 	= HeikenAshi8();
				HAshi 	= vxvHeikenAshi();

				AddChartIndicator(HAshi);
				//Bollinger1				= Bollinger(Close, 2, 14);
				Bollinger1				= Bollinger(HAshi.HAClose, StdDeviations, Convert.ToInt32(BBPeriod));
				//SetParabolicStop(CalculationMode.Currency, 20);
				AddChartIndicator(Bollinger1);
				
				hmaHigh = HMA(LongTermMAPeriod);
				//hmaLow = HMA(50);
				//AddChartIndicator(hmaHigh);
				//AddChartIndicator( HMA(ShortTermMAPeriod));
				
				// RSI
				rsi = RSI( Convert.ToInt32(BBPeriod), 3);
				stddev = StdDev(BBPeriod) ;
				
				AuSuperTrendU111 = AuSuperTrendU11(Close, AuSuperTrendU11BaseType.Median, AuSuperTrendU11OffsetType.Median, AuSuperTrendU11VolaType.True_Range, false, 3, 3, 15);
				AuSuperTrendU111.Plots[0].Brush = Brushes.Gray;
				AuSuperTrendU111.Plots[1].Brush = Brushes.Gray;
				AuSuperTrendU111.Plots[2].Brush = Brushes.Transparent;
				AddChartIndicator(AuSuperTrendU111);
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
			bool doTrade = (Session1 || Session2 || Session3)? false: true;
				
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

			if (CurrentBars[0] < 100)
				return;
			
			// Times 
			if( !canTradeTime()) {
				// Halt further processing of our strategy 
				return;
			}
			
			// Need a better way to fix this... with 3 missed out on one large trade.
			//if ( Math.Abs(Bollinger1.Upper[0] -  Bollinger1.Lower[0]) <= 6 )
			//	return;
			
			adxValue = useAdx ? (ADX(adxPeriod)[1]) : 0 ;
			
			stddev = StdDev(7);
			
			
			countLong = incCount(countLong, HAshi.HAClose[0] >= Bollinger1.Upper[0] ,  HAshi.HAClose[1] >= Bollinger1.Upper[1]) ;
			countShort = incCount(countShort, HAshi.HAClose[0]<= Bollinger1.Lower[0] ,  HAshi.HAClose[1] <= Bollinger1.Lower[1]) ;
			
			
			// Resets the stop loss to the original value when all positions are closed
			switch (Position.MarketPosition)
            {
                case MarketPosition.Flat:
                    SetStopLoss(CalculationMode.Ticks, stopLossTicks);
					previousPrice = 0;
                    break;
				 case MarketPosition.Long:
                    // Once the price is greater than entry price+ breakEvenTicks ticks, set stop loss to breakeven
                    if (Close[0] > Position.AveragePrice + breakEvenTicks * TickSize
						&& previousPrice == 0 )
                    {
						initialBreakEven = Position.AveragePrice + plusBreakEven * TickSize;
                        //SetStopLoss(CalculationMode.Price, initialBreakEven);
						previousPrice = Position.AveragePrice;
						Print("previousPrice = "+previousPrice);
                    }
					// Once at breakeven wait till trailProfitTrigger is reached before advancing stoploss by trailStepTicks size step
					else if (previousPrice	!= 0 ////StopLoss is at breakeven
 							&& GetCurrentAsk() > previousPrice + trailProfitTrigger * TickSize
						)
					{
						newPrice = previousPrice + trailStepTicks * TickSize;
						//SetStopLoss(CalculationMode.Price, newPrice);
						previousPrice = newPrice;
						Print("previousPrice = "+previousPrice);
					}
					
					// If the channel is rising then raise the profit target higher
					if(IsRising( HMA(LongTermMAPeriod)))
					{
						//SetProfitTarget(CalculationMode.Price,  trailProfitTrigger * TickSize );
						
					}
					//Long entry will close when price (Close) goes over HF
					if(IsFalling( HMA(LongTermMAPeriod))
						|| CrossBelow( HMA(ShortTermMAPeriod),HMA(LongTermMAPeriod), hmaLookBackPeriod )
						)
					{
						//closeLongCondition = true ;
						//Print("Exiting Longs with MA moving Falling");
						//Draw.Diamond(this,"closeLongCondition"+Low[0].ToString(), true, 0,High[0] + TickSize, Brushes.DeepPink);
						//ExitLong();
					}
					//Stop Loss will happen when price (Close) goes under LL
					
                    break;
                case MarketPosition.Short:
					
					// If the channel is faling then raise the profit target higher
					if( IsFalling( HMA(LongTermMAPeriod))
					  )
					{
						//SetProfitTarget(CalculationMode.Price,  trailProfitTrigger * TickSize );
						
					}
                    // Once the price is Less than entry price - breakEvenTicks ticks, set stop loss to breakeven
                    if (Close[0] < Position.AveragePrice - breakEvenTicks * TickSize
						&& previousPrice == 0)
                    {
						initialBreakEven = Position.AveragePrice - plusBreakEven * TickSize;
                       // SetStopLoss(CalculationMode.Price, initialBreakEven);
						previousPrice = Position.AveragePrice;
						Print("previousPrice = "+previousPrice);
                    }
					// Once at breakeven wait till trailProfitTrigger is reached before advancing stoploss by trailStepTicks size step
					else if (previousPrice	!= 0 ////StopLoss is at breakeven
 							&& GetCurrentAsk() < previousPrice - trailProfitTrigger * TickSize
						)
					{
						newPrice = previousPrice - trailStepTicks * TickSize;
						//SetStopLoss(CalculationMode.Price, newPrice);
						previousPrice = newPrice;
						Print("previousPrice = "+previousPrice);
					}
					
					//Short entry will close when price (Close) goes over LF
					if(IsRising( HMA(LongTermMAPeriod))
						|| CrossAbove( HMA(ShortTermMAPeriod),HMA(LongTermMAPeriod), hmaLookBackPeriod )
					    )
					{
						//Print("Exiting Shorts with MA moving Rising");
						//closeShortCondition = true ;
						//Draw.Diamond(this,"CloseShortEntry"+Low[0].ToString(), true, 0,Low[0] - TickSize, Brushes.Green);
						//ExitShort();
					}
				
				
                    break;
                default:
					//autoStopA900Traded = false;
                    break;
			}
			
			// Interesting Idea.
			// Check for 3 downclose candles and assume heavy selling and hence go with the trend.
			// or Once in a trade, check if the trend/slope is still down, then only exit.
			// or only exit when you hit the middle line? 
			// or we can use the width to figure this out
			// or check MACD/Willams/ RSI for confirmation to exit in case of the a heavy sell.
			

			if (Position.MarketPosition != MarketPosition.Long
				&& (//((HAshi.HALow[1]    <= Bollinger1.Lower[1]) ||  (HAshi.HALow[1]    <=  Bollinger1.Middle[1] ))
				 ((HAshi.HAClose[1]  >  Bollinger1.Lower[1])) // &&  (HAshi.HAClose[1]  <   Bollinger1.Middle[1])
				&& ((HAshi.HAClose[0]  >  Bollinger1.Lower[0]) )) //&&  (HAshi.HAClose[0]  <  Bollinger1.Middle[0] )
				
				//&& (HAshi.HALow[1] <= Bollinger1.Middle[1])
				//&& (HAshi.HAClose[1] > Bollinger1.Middle[1])
				//&& (HAshi.HAClose[0] > Bollinger1.Middle[0])
				
				&& (HAshi.HAOpen [0] < HAshi.HAClose[0]  && HAshi.HALow [0] == HAshi.HAOpen[0]) // Up Close candle
				&& (HAshi.HAOpen [1] < HAshi.HAClose[1] ) // Up Close candle
			
				
				//&& !IsFalling( Bollinger1.Middle)
				//&& IsRising( Bollinger1.Middle)
				//&& countShort >= 1
				//&& High[0] <= MAX(High,50)[1]
				//&& ( rsi.Avg[0] > 30.0)
				//&& (stddev[0] > 6)
				//&& AuSuperTrendU111.StopLine[1]!=AuSuperTrendU111.StopLine[0] 
				//&& AuSuperTrendU111.Trend[0] > 0
				)
			{
				EnterLong(Convert.ToInt32(DefaultQuantity), "");
				
				//SetProfitTarget(CalculationMode.Price,MAX(High,50)[1]);
				//SetStopLoss(CalculationMode.Price,MIN(Low,10)[1]);
				SetStopLoss(CalculationMode.Ticks, stopLossTicks);
				return;
				
			}
			

			if (Position.MarketPosition != MarketPosition.Short
				&& (//((HAshi.HAHigh[1] >= Bollinger1.Upper[1]) || (HAshi.HAHigh[1]  >= Bollinger1.Middle[1] ))
				 ((HAshi.HAClose[1] < Bollinger1.Upper[1])  ) //&& (HAshi.HAClose[1] >=  Bollinger1.Middle[1] )
				&& ((HAshi.HAClose[0] < Bollinger1.Upper[0]) )) //&& (HAshi.HAClose[0] >= Bollinger1.Middle[1] )
				
				//&& (HAshi.HAHigh[1] >= Bollinger1.Middle[1])
				//&& (HAshi.HAClose[1] < Bollinger1.Middle[1])
				//&& (HAshi.HAClose[0] < Bollinger1.Middle[0])
				
				//&& (HAshi.HAOpen [0] > HAshi.HAClose[0] ) // Down Close candle
				//&& (HAshi.HAOpen [1] > HAshi.HAClose[1] ) // Down Close candle
				&& (HAshi.HAOpen [0] > HAshi.HAClose[0]  && HAshi.HAHigh [0] == HAshi.HAOpen[0]) // Down Close candle
				&& (HAshi.HAOpen [1] > HAshi.HAClose[1] ) // Down Close candle
				
				
				//&& !IsRising( Bollinger1.Middle)
				//&& IsFalling( Bollinger1.Middle)
				//&&  countLong >= 1
				//&& HAshi.HALow[0] >= MIN(HAshi.HALow,50)[1]
				
				//&& ( rsi.Avg[0] < 70.0)
				//&& (stddev[0] > 6)
				//&& AuSuperTrendU111.StopLine[1]!=AuSuperTrendU111.StopLine[0] 
				//&& AuSuperTrendU111.Trend[0] < 0
				)
			{
				EnterShort(Convert.ToInt32(DefaultQuantity), "");
				//SetProfitTarget(CalculationMode.Price,MIN(Low,50)[1]);
				
				//SetStopLoss(CalculationMode.Price,MAX(High,10)[1]);
				//SetProfitTarget(CalculationMode.Ticks,profitTargetTicks);
				SetStopLoss(CalculationMode.Ticks, stopLossTicks);
				
				return;
			}
			
			
		}
		private int incCount(int count, bool comparison, bool prevComparison)
		{
			if (comparison)
			{
				if (count == 0 && prevComparison)
				{
					count = 0;
				}
				else
				{
					 count = count + 1;
				}
			}
			else
				count = 0 ;
			return count;
		}

		#region Properties
		[NinjaScriptProperty]
		[Range(3, int.MaxValue)]
		[Display(Name="BBPeriod", Description="Bollinger Bands Period", Order=1, GroupName="Parameters")]
		public int BBPeriod
		{ get; set; }

		[NinjaScriptProperty]
		[Range(0, double.MaxValue)]
		[Display(Name="StdDeviations", Description="NumberOf Standard Deviations", Order=2, GroupName="Parameters")]
		public double StdDeviations
		{ get; set; }
		
		[NinjaScriptProperty]
		[Range(3, int.MaxValue)]
		[Display(Name="LongTermMAPeriod", Description="Long term MA for trend detection", Order=1, GroupName="Parameters")]
		public int LongTermMAPeriod
		{ get; set; }
		
		[NinjaScriptProperty]
		[Range(3, int.MaxValue)]
		[Display(Name="ShortTermMAPeriod", Description="Short term MA for trend detection", Order=2, GroupName="Parameters")]
		public int ShortTermMAPeriod
		{ get; set; }
		
		
		[NinjaScriptProperty]
		[Display(Name="Enable ADX", Description="Use ADX to restrict trades during low volatality", Order=3, GroupName="Parameters")]
		public bool useAdx
		{ get; set; }
		
		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name="ADX Period Length", Description="ADX Period Length", Order=4, GroupName="Parameters")]
		public int adxPeriod
		{ get; set; }
		

		[NinjaScriptProperty]
		[Range(1, 30)]
		[Display(Name="ADX Threshold", Description="ADX Threshold to restrict trades during low volatality", Order=5, GroupName="Parameters")]
		public double adxThreshold
		{ get; set; }

		[NinjaScriptProperty]
		[Display(Name="Use3Candles", Description="Use 2 or 3 candles for confirmation", Order=6, GroupName="Parameters")]
		public bool Use3Candles
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
		[Display(Name="UseATRforStopLoss", Description="Use ATR instead of ticks for stop Loss", Order=12, GroupName="Parameters")]
		public bool UseATRforStopLoss
		{ get; set; }

		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name="TrailProfitTrigger", Description="Profit Trigger for stop loss trailing", Order=13, GroupName="Parameters")]
		public int trailProfitTrigger
		{ get; set; }

		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name="TrailStepTicks", Description="Steps at which we will trail the profit", Order=14, GroupName="Parameters")]
		public int trailStepTicks
		{ get; set; }
		#endregion

	}
}
