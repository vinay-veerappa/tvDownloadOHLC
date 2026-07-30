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
	public class SuperTrend : Strategy
	{
		private AuSuperTrendU11 AuSuperTrendU111;
		private AuSuperTrendU11 AuSuperTrendU112;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description									= @"Enter the description for your new custom Strategy here.";
				Name										= "SuperTrend";
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
			}
			else if (State == State.DataLoaded)
			{				
				AuSuperTrendU111				= AuSuperTrendU11(Close, AuSuperTrendU11BaseType.Median, AuSuperTrendU11OffsetType.Median, AuSuperTrendU11VolaType.True_Range, false, 3, 2.618, 10);
				AuSuperTrendU111.Plots[0].Brush = Brushes.Gray;
				AuSuperTrendU111.Plots[1].Brush = Brushes.Gray;
				AuSuperTrendU111.Plots[2].Brush = Brushes.Transparent;
				AddChartIndicator(AuSuperTrendU111);
				
				AuSuperTrendU112				= AuSuperTrendU11(Close, AuSuperTrendU11BaseType.Median, AuSuperTrendU11OffsetType.Median, AuSuperTrendU11VolaType.True_Range, false, 3, 2.618, 10);
				AuSuperTrendU112.Plots[0].Brush = Brushes.Gray;
				AuSuperTrendU112.Plots[1].Brush = Brushes.Gray;
				AuSuperTrendU112.Plots[2].Brush = Brushes.Transparent;
				AddChartIndicator(AuSuperTrendU112);
			}
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

			if (CurrentBars[0] < 1)
				return;
			
			// Times 
			if(!canTradeTime()) {
				// Halt further processing of our strategy 
				return;
			}

			 // Set 1
			if (Position.MarketPosition != MarketPosition.Long
				&& AuSuperTrendU111.Trend[0] > 0
				&& AuSuperTrendU111.StopLine[1]!=AuSuperTrendU111.StopLine[0] )
			{
				EnterLong(Convert.ToInt32(DefaultQuantity), @"BuyLong");
			}
			if (Position.MarketPosition == MarketPosition.Long
				&& AuSuperTrendU112.Trend[0] < 0)
			{
				ExitLong();
			}
			
			 // Set 2
			if (Position.MarketPosition != MarketPosition.Short
				&& AuSuperTrendU111.Trend[0] < 0
				&& AuSuperTrendU111.StopLine[1]!=AuSuperTrendU111.StopLine[0] )
			{
				EnterShort(Convert.ToInt32(DefaultQuantity), @"GoShort");
			}
			
			if (Position.MarketPosition == MarketPosition.Short
				&& AuSuperTrendU112.Trend[0] > 0)
			{
				ExitShort();
			}
		}
		#region Properties

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
		
		#endregion
	}
}
