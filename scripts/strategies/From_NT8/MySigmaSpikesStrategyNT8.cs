
/*
Strategy based on SigmaSpikes
SigmaSpikes as described by Adam H Grimes. https://adamhgrimes.com/how-to-calculate-sigmaspikes/

 * standard deviation of daily returns over a period , searching price spikes.

 Parameter:
 * SigmaSpikesFactor  = 2.50 
*/

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
	public class MySigmaSpikesStrategyNT8 : Strategy
	{
		// SigmaSpikes indicator
		private SigmaSpikes SigmaSpikes1;
		
		// Daily Target 
		private int priorTradesCount        = 0;
		private double priorTradesCumProfit = 0;
		
		// Email
		private string toEmailAddress       = @""; 
		
		// Connection Loss Alert
		protected override void OnConnectionStatusUpdate(ConnectionStatusEventArgs connectionStatusUpdate)
        {
        if(connectionStatusUpdate.Status == ConnectionStatus.Connected)
        {
            Print("Connected at " + DateTime.Now);
		    Draw.TextFixed(this, "tag1", "Account " + Account.Name, TextPosition.TopLeft);
			{	
			if (UseEmail == true)
			SendMail(toEmailAddress, "* NT8 - Connection", "Connected at " + DateTime.Now);
			}		
        }
        else if(connectionStatusUpdate.Status == ConnectionStatus.ConnectionLost)
        {
            Print("Connection lost at: " + DateTime.Now);
			{
			if (UseEmail == true)
			SendMail(toEmailAddress, "* NT8 - Connect/Lost!!:-(", "Lost !!!! at " + DateTime.Now);
			}		
          }
        }

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description									= @"NT8 Strategy based on SigmaSpikes";
				Name										= "MySigmaSpikesStrategyNT8";
				Calculate									= Calculate.OnBarClose;
				EntriesPerDirection							= 1;
				EntryHandling								= EntryHandling.AllEntries;
				IsExitOnSessionCloseStrategy				= true;
				ExitOnSessionCloseSeconds					= 30;
				IsFillLimitOnTouch							= false;
				MaximumBarsLookBack							= MaximumBarsLookBack.TwoHundredFiftySix;
				OrderFillResolution							= OrderFillResolution.Standard;
				Slippage									= 0;
				StartBehavior								= StartBehavior.ImmediatelySubmit;
				TimeInForce									= TimeInForce.Day;
				TraceOrders									= false;
				RealtimeErrorHandling						= RealtimeErrorHandling.StopCancelClose;
				StopTargetHandling							= StopTargetHandling.PerEntryExecution;
				BarsRequiredToTrade							= 20;
				// Disable this property for performance gains in Strategy Analyzer optimizations
				// See the Help Guide for additional information
				IsInstantiatedOnEachOptimizationIteration	= true;
				
			    // Keeps the strategy running as if no disconnect occurred	
                ConnectionLossHandling                      = ConnectionLossHandling.KeepRunning;
				
				// SigmaSpikes Settings
				SigmaSpikesFactor                           = 2.50;
				UseSigmaSpikes                              = true;
				
				// StopLoss & ProfitTarget
				UseProtectiveStops		                    = true;
				StopLoss				                    = 100;
				ProfitTarget			                    = 100;
				
				// Daily Target
				Contracts                                   =   1;
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
				Session1Start =     0;   //    0
				Session1End = 235959;   //235959

				Session2 = false;
				Session2Start = 50000; // 90000
				Session2End = 080000; // 110000
				
				Session3 = false;
				Session3Start = 110000; //120000 -- Should have been 09 AM PST,
				Session3End = 125900; //125900  -- Should have been 10 AM PST. Lunch hour did not make sense.
				
			}
			else if (State == State.Configure)
			{
			//-------------------------------
			}
			else if (State == State.DataLoaded)
			{
			// SigmaSpikes indicator     

			SigmaSpikes1 = SigmaSpikes(Close, 30);
			
			if (UseSigmaSpikes == true)
				
			AddChartIndicator(SigmaSpikes1);
			
			}
		}
		
		// StopLoss & ProfitTarget
        protected override void OnExecutionUpdate( Cbi.Execution e, string executionId, double price, int quantity, 
												   Cbi.MarketPosition marketPosition, string orderId, DateTime time )
		{			
			if( UseProtectiveStops )
			{
				if( e.IsEntryStrategy )
				{
					if( e.Order.OrderAction == OrderAction.Buy )
					{
						// Set stop loss
						double stopOrderPrice = e.Order.AverageFillPrice - StopLoss * TickSize;
						ExitLongStopMarket( 0, true, 1, stopOrderPrice, "Stop loss", e.Order.FromEntrySignal ); // Quantity was 3. Not sure why.
						
						// Set profit target 1
						double profitTarget = e.Order.AverageFillPrice + ProfitTarget * TickSize;;
						ExitLongLimit( 0, true, 1, profitTarget, "Profit target", e.Order.FromEntrySignal );											
					}
					if( e.Order.OrderAction == OrderAction.SellShort )
					{
						// Set stop loss
						double stopOrderPrice = e.Order.AverageFillPrice + StopLoss * TickSize;
						ExitShortStopMarket( 0, true, 1, stopOrderPrice, "Stop loss", e.Order.FromEntrySignal ); // Quantity was 3. Not sure why
						
						// Set profit target 1
						double profitTarget = e.Order.AverageFillPrice - ProfitTarget * TickSize;;
						ExitShortLimit( 0, true, 1, profitTarget, "Profit target", e.Order.FromEntrySignal );
					}
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
				  //"Strategy : " + this.Name + "\n" +
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
					 	"Strategy : " + this.Name + "\n" +
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
					 	"Strategy : " + this.Name + "\n" +
						"Short Entry" + "\n" +
						"Quantity: " + Position.Quantity.ToString() + "\n" +
						"EntryPrice: " + Position.AveragePrice.ToString() + "\n");
				}
			}
			#endregion
		}
		
		protected override void OnBarUpdate()
		{
			if (BarsInProgress != 0 || CurrentBars[0] < 1 || CurrentBar < BarsRequiredToTrade) 
				// Halt further processing of our strategy 
				return;
			// Times 
			if( !canTradeTime() ) {
				// Halt further processing of our strategy 
				return;
			}
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
				
			// SigmaSpikes bullish 
			if ((SigmaSpikes1.SigmaSpike[0] >= SigmaSpikesFactor) 
				&& (UseSigmaSpikes == true))
				{
				  EnterLong(Contracts);
                }
				
			// SigmaSpikes bearish
		     if ((SigmaSpikes1.SigmaSpike[0] <= -SigmaSpikesFactor) 
				 && (UseSigmaSpikes == true))
			    {
				  EnterShort(Contracts);
			    }
		 }
		
		// Times
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
		// Properties
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
		//-------------------
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
		// Times
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
		//-------------------
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
		[Display(ResourceType = typeof(Custom.Resource), Name="UseSigmaSpikes", Description="Enter positions based on SigmaSpikes", Order=1, GroupName="SigmaSpikes")]
		public bool UseSigmaSpikes
		{ get; set; }
		
		[NinjaScriptProperty]
		[Range(0.01, double.MaxValue)]
		[Display(Name="SigmaSpikesFactor", Order=2, GroupName="SigmaSpikes")]
		public double SigmaSpikesFactor
		{ get; set; }
	}
}


    