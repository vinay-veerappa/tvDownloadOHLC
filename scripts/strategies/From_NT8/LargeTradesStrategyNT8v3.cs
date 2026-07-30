
    /// <summary>
	/// Coded by bcomas July 2020. Email: bernardocomas@hotmail.com for improvements
    /// Trading the major transactions that have taken place during
    /// short period of time and at the same price (Limit buyer / seller)
    /// ***Updated September 2020
    /// </summary>

// Using declarations
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

//This namespace holds Strategies in this folder and is required. Do not change it. 
namespace NinjaTrader.NinjaScript.Strategies
{
	public class LargeTradesStrategyNT8v3 : Strategy
	{
		private bcomasLargeTradesV3 LargeTradesSignal1;
		private int vol                      = 50; 
		private int fix                      = 1; 
        private bcomasVolumeUpDown VolumeUpDown1;

		// Daily Target 
		private int priorTradesCount        = 0;
		private double priorTradesCumProfit = 0;
		
		private SMA smaFast;
		private SMA smaSlow;
		
		// Email
		private string toEmailAddress       = @""; 
		
		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description									= @"NT8 Strategy based on LargeTrades , 1 min timeframe";
				Name										= "LargeTradesStrategyNT8v3";
				Calculate									= Calculate.OnBarClose;
				EntriesPerDirection							= 1;
				EntryHandling								= EntryHandling.AllEntries;
				IsExitOnSessionCloseStrategy				= true;
				ExitOnSessionCloseSeconds					= 3000;
				IsFillLimitOnTouch							= false;
				MaximumBarsLookBack							= MaximumBarsLookBack.TwoHundredFiftySix;
				OrderFillResolution							= OrderFillResolution.Standard;
				Slippage									= 0;
				StartBehavior								= StartBehavior.ImmediatelySubmit;
				TimeInForce									= TimeInForce.Day;
				TraceOrders									= false;
				StopTargetHandling							= StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade							= 100;
				// Disable this property for performance gains in Strategy Analyzer optimizations
				// See the Help Guide for additional information
				IsInstantiatedOnEachOptimizationIteration	= true;
				
			    // Keeps the strategy running as if no disconnect occurred	
                ConnectionLossHandling                      = ConnectionLossHandling.KeepRunning;
				
			    // Trend
				UseTrend		                            = false;
				Fast		                                = 7;
				Slow		                                = 14;
				
				// StopLoss & ProfitTarget
				UseProtectiveStops		                    = true;
				StopLoss				                    = 50;
				ProfitTarget			                    = 100;
				
				// Daily Target
				Contracts                                   =    2;
				DailyLossLimit                              = -100;
				DailyProfitLimit                            =  100;
				DailyTradesCount                            =  100;

				// Email alerts
				UseEmail	                                = false;
				EnableEntryAlert			                = false;
				EnableExitAlert				                = false;
				toEmailAddress                              = @"";
				
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
				
			}
			else if (State == State.Configure)
			{
				{ 
				if( UseProtectiveStops )
				SetProfitTarget(@"LongA", CalculationMode.Ticks, ProfitTarget);
				if( UseProtectiveStops )
				SetTrailStop(@"LongA", CalculationMode.Ticks, StopLoss, false);
                }
				// Trend
				smaFast = SMA(Fast);
				smaSlow = SMA(Slow);

				smaFast.Plots[0].Brush = Brushes.Goldenrod;
				smaSlow.Plots[0].Brush = Brushes.SeaGreen;
                if (UseTrend == true)
				AddChartIndicator(smaFast);
				if (UseTrend == true)
				AddChartIndicator(smaSlow);
				
				{ 
                    RealtimeErrorHandling = RealtimeErrorHandling.IgnoreAllErrors;
                }
					
				{
			        AddDataSeries(BarsPeriodType.Second,1);
				}
			}
			else if (State == State.DataLoaded)
			{
				{
				if( UseProtectiveStops )
				SetProfitTarget(@"ShortA", CalculationMode.Ticks, ProfitTarget);
				if( UseProtectiveStops )
				SetTrailStop(@"ShortA", CalculationMode.Ticks, StopLoss, false);
			    }

			LargeTradesSignal1 = bcomasLargeTradesV3(Close, Volume_, fix, Brushes.Transparent, Brushes.White, false, false, false, "Alert4.wav");
				                         
			    {
			       AddChartIndicator(LargeTradesSignal1);
			    }
	
			VolumeUpDown1 = bcomasVolumeUpDown(Close);
				
			    {
			       AddChartIndicator(VolumeUpDown1);
			    }
			}
		}
		
		// Email Alerts
		
	    protected override void OnPositionUpdate(Cbi.Position position, double averagePrice, int quantity, Cbi.MarketPosition marketPosition)
		{
			#region Alert for exits
			//Alert for exits
			if (Position.MarketPosition == MarketPosition.Flat && EnableExitAlert == true && SystemPerformance.RealTimeTrades.Count > 0) 
			{
		      // Check to make sure there is at least one trade in the collection
		      Trade lastTrade = SystemPerformance.RealTimeTrades[SystemPerformance.RealTimeTrades.Count - 1];
		 
		      // Calculate the PnL for the last completed real-time trade
		      double lastProfitCurrency = lastTrade.ProfitCurrency;
				
			  SendMail(toEmailAddress,"Position closed" + " " + Instrument.MasterInstrument.Description.ToString() + " " + this.Name,
				  "Date & Time: " + Times[0][0].ToString("dd/MM/yyyy") + " " + Times[0][0].ToString("HH:mm:ss") + "\n" +
				  "Instrument: " + Instrument.MasterInstrument.Description.ToString() + " " + Instrument.FullName.ToString() + "\n" +
				  "Account: " + Position.Account.Name.ToString() + "\n" +
				  "Exit name: " + lastTrade.Exit.Name.ToString() + "\n" +
				  "Exit price: " + lastTrade.Exit.Price.ToString() + "\n" + 
				  "Profit/Loss last trade: " + lastProfitCurrency.ToString("0.00"));
			}
			// Draw text TopRight - Last Profit / Loss
			if (Position.MarketPosition == MarketPosition.Flat && SystemPerformance.RealTimeTrades.Count > 0) 
			{
				Trade lastTrade = SystemPerformance.RealTimeTrades[SystemPerformance.RealTimeTrades.Count - 1];
		        double lastProfitCurrency = lastTrade.ProfitCurrency;
				Draw.TextFixed(this, "limitText", "Profit / Loss \nPnL: "+lastProfitCurrency.ToString("0.00")+"$", TextPosition.TopRight);
			}
			else
			    {
				RemoveDrawObject("limitText");
			    }
				
			#endregion
			
			#region Alert for entries
			if (EnableEntryAlert == true)
			{
				//Alert long entries
				if (Position.MarketPosition == MarketPosition.Long)
				{
					SendMail(toEmailAddress,"Long Entry: " + this.Name + " " + Instrument.MasterInstrument.Description.ToString(),
						"Date & Time: " + Times[0][0].ToString("dd/MM/yyyy") + " " + Times[0][0].ToString("HH:mm:ss") + "\n" +
						"Instrument: " + Instrument.MasterInstrument.Description.ToString() + " " + Instrument.FullName.ToString() + "\n" +
					 	"Account: " + Position.Account.Name.ToString() + "\n" +
						"Long Entry" + "\n" +
						"Quantity: " + Position.Quantity.ToString() + "\n" +
						"EntryPrice: " + Position.AveragePrice.ToString() + "\n");
				}
				
				//Alert short entries
				if (Position.MarketPosition == MarketPosition.Short)
				{
					SendMail(toEmailAddress,"Short Entry: " + this.Name + " " + Instrument.MasterInstrument.Description.ToString(),
						"Date & Time: " + Times[0][0].ToString("dd/MM/yyyy") + " " + Times[0][0].ToString("HH:mm:ss") + "\n" +
						"Instrument: " + Instrument.MasterInstrument.Description.ToString() + " " + Instrument.FullName.ToString() + "\n" +
					 	"Account: " + Position.Account.Name.ToString() + "\n" +
						"Short Entry" + "\n" +
						"Quantity: " + Position.Quantity.ToString() + "\n" +
						"EntryPrice: " + Position.AveragePrice.ToString() + "\n");
				}
			}
			#endregion
		}
		
			#region entry gates
			bool LongEntryValid = false;
			bool ShortEntryValid = false;
			bool LongEntryAllowed = true;
			bool ShortEntryAllowed = true;
			#endregion
		
		protected override void OnBarUpdate()
		{
			if (BarsInProgress != 0 || CurrentBars[0] < 1 || CurrentBar < BarsRequiredToTrade) 
				// Halt further processing of our strategy 
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
				Draw.TextFixed(this, "limitText", "Daily Loss / Profit reached"
				, TextPosition.BottomRight);
				
				// Halt further processing of our strategy 
				return;
			}	
			else
			    {
				RemoveDrawObject("limitText");
		    }
				
			// Times 
			if( !canTradeTime() ) {
				// Halt further processing of our strategy 
				return;
			}
			
			//bullish	
			if (UseTrend == false && (canTradeTime()) 
			&& LargeTradesSignal1.Direction == 1)
			EnterLong(Convert.ToInt32(Contracts), @"LongA");
			
			//bearish
			if (UseTrend == false && (canTradeTime())    
			&& LargeTradesSignal1.Direction == -1)  
			EnterShort(Convert.ToInt32(Contracts), @"ShortA");
			
			// Use Trend & execute once per signal
			if (UseTrend == true && CrossAbove(smaFast, smaSlow, 1)
			&& (canTradeTime()) 
			&& LargeTradesSignal1.Direction == 1) LongEntryValid = true;//bullish
			else LongEntryValid = false;
			if (UseTrend == true && CrossBelow(smaFast, smaSlow, 1)
			&& (canTradeTime()) 
			&& LargeTradesSignal1.Direction == -1) ShortEntryValid = true;//bearish
			else ShortEntryValid = false;

			if (LongEntryValid && LongEntryAllowed) {
			 //Condition the gates
			 LongEntryAllowed = false; 
			 ShortEntryAllowed = true; 

			 EnterLong(Convert.ToInt32(Contracts), @"LongA");
				
			} else if (ShortEntryValid && ShortEntryAllowed) {
			 //Condition the gates
			 LongEntryAllowed = true; 
			 ShortEntryAllowed = false; 

			 EnterShort(Convert.ToInt32(Contracts), @"ShortA");
			}
			
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
	
		[Display(ResourceType = typeof(Custom.Resource), Name = "Use protective stops?", Order = 0, GroupName = "Stops & Targets")]
		public bool UseProtectiveStops
		{ get; set; }
		
		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(ResourceType = typeof(Custom.Resource), Name="Stop loss", Description="Stop loss (ticks)", Order=1, GroupName="Stops & Targets")]
		public int StopLoss
		{ get; set; }
		
		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(ResourceType = typeof(Custom.Resource), Name="Profit target", Description="Profit target (in ticks)", Order=2, GroupName="Stops & Targets")]
		public int ProfitTarget
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
		[Display(ResourceType = typeof(Custom.Resource), Name="UseEmail", Description="Use Email", Order=1, GroupName="Mail Share Service")]
		public bool UseEmail
		{ get; set; }

		[NinjaScriptProperty]
		[Display(ResourceType = typeof(Custom.Resource), Name="EnableEntryAlert", Description="Enable email alert for Entries", Order=2, GroupName="Mail Share Service")]
		public bool EnableEntryAlert
		{ get; set; }

		[NinjaScriptProperty]
		[Display(ResourceType = typeof(Custom.Resource), Name="EnableExitAlert", Description="Enable email alert for Exits", Order=3, GroupName="Mail Share Service")]
		public bool EnableExitAlert
		{ get; set; }
		
		[NinjaScriptProperty]
        [Display(Description = "To Email id", GroupName = "Mail Share Service", Order = 4)]
        public string ToEmailAddress
        {
            get { return toEmailAddress; }
            set 
			{ 
				System.Text.RegularExpressions.Regex reg = new System.Text.RegularExpressions.Regex(@"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}\b");
				
				if (reg.IsMatch((string)value))
					toEmailAddress = value; 
			}
        }
		
		[NinjaScriptProperty]		
		[Display(Name = "Transaction volume", Description = "Transaction volume", GroupName = "Large Trades", Order = 1)]		
		public int Volume_
        {
            get { return vol; }
            set { vol = Math.Max(1, value); }
        }
        [NinjaScriptProperty]       
		[Display(Name = "Time of transation (seconds)", Description = "The time during which the transaction occurred", GroupName = "Large Trades", Order = 2)]       
		public int Time_
        {
            get { return fix; }
            set { fix = Math.Max(1, value); }
        }
		
		[Display(ResourceType = typeof(Custom.Resource), Name = "Use Trend?", Order = 0, GroupName = "Trend")]
		public bool UseTrend
		{ get; set; }

		[Range(1, int.MaxValue), NinjaScriptProperty]
		[Display(ResourceType = typeof(Custom.Resource), Name = "Fast", GroupName = "Trend", Order = 1)]
		public int Fast
		{ get; set; }

		[Range(1, int.MaxValue), NinjaScriptProperty]
		[Display(ResourceType = typeof(Custom.Resource), Name = "Slow", GroupName = "Trend", Order = 2)]
		public int Slow
		{ get; set; }
	}
}


    