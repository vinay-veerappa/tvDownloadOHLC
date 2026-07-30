//
// Copyright (C) 2023, NinjaTrader LLC <www.ninjatrader.com>
// NinjaTrader reserves the right to modify or overwrite this NinjaScript component with each release
// Coded by NinjaTrader_Jesse
//
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
	public class WeeklyFactorStrategy : Strategy
	{
		private WeeklyFactorPattern		WeeklyFactorPattern1;
		private int						barCount;
		private int						dayCount;
		private bool					canTrade;
		private SessionIterator			sessionIterator;
		private DateTime				endTime;
		private bool					exitOnClose;
		private Order					longStopEntry;
		private Order					shortStopEntry;
		private string					ocoString;
		
		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description								= @"The WeeklyFactor strategy as published in the September 2023 Technical Analysis of Stocks and Commodities article 'The Weekly Factor Pattern' by Andrea Unger";
				Name									= "WeeklyFactorStrategy";
				Calculate								= Calculate.OnBarClose;
				IsExitOnSessionCloseStrategy			= false;
				IsFillLimitOnTouch						= false;
				StopTargetHandling						= StopTargetHandling.PerEntryExecution;
				IncludeTradeHistoryInBacktest 			= true;
				BarsRequiredToTrade						= 20;
				IsUnmanaged								= true;
				ExitMinutesBeforeSessionEnd				= 60;
				EntryOffsetInTicks						= 10;
				RangeFilter								= 1;
			}
			else if (State == State.DataLoaded)
			{
				barCount				= 1;
				dayCount				= 0;
				canTrade				= true;
				exitOnClose				= false;
				sessionIterator			= new SessionIterator(Bars);
				WeeklyFactorPattern1	= WeeklyFactorPattern(Close,RangeFilter * 0.1);
				AddChartIndicator(WeeklyFactorPattern1);
			}
		}
		
		protected override void OnBarUpdate()
		{
			if(State == State.Realtime) 
				return;
			
			if (BarsInProgress != 0) 
				return;

			if (CurrentBars[0] < 1)
				return;

			if ((NinjaTrader.Core.Globals.Now - Bars.GetTime(0)).Days < 14)
			{
				Draw.TextFixed(this, "Error text", "This strategy requires at least 2 weeks of data to calculate.\nchange Days to load in the data series menu to at least 14", TextPosition.BottomRight);
				return;
			}

			if (WeeklyFactorPattern1[0] > 0 && barCount > 1 && barCount < 91 && canTrade)
			{
				if (longStopEntry == null && shortStopEntry == null)
				{
					Bar daybar1 = Bars.GetDayBar(1);
					if(daybar1 != null)
					{
						ocoString		= string.Format("unmanagedentryoco{0}", DateTime.Now.ToString("hhmmssffff"));
						longStopEntry	= SubmitOrderUnmanaged(0, OrderAction.Buy, OrderType.StopMarket, 1, 0, daybar1.High + EntryOffsetInTicks * TickSize, ocoString, "Brkout_LE");
						shortStopEntry	= SubmitOrderUnmanaged(0, OrderAction.SellShort, OrderType.StopMarket, 1, 0, daybar1.Low - EntryOffsetInTicks * TickSize, ocoString, "Brkout_SE");
						Draw.Dot(this, @"WeeklyFactorStrategy " + Convert.ToString(CurrentBars[0]), true, 0, Close[0], Brushes.HotPink);
						canTrade = false;				
					}
				}				
			} 
			
			double pnl = Position.GetUnrealizedProfitLoss(PerformanceUnit.Currency, Close[0]); 
						
			// if one day has passed and the PnL is negative exit
			if(dayCount > 1 && Position.MarketPosition != MarketPosition.Flat && pnl < 0 )
			{
				if(Position.MarketPosition == MarketPosition.Long)  SubmitOrderUnmanaged(0, OrderAction.Sell, OrderType.Market, 1, 0, 0, null, "LongLossExit");
				if(Position.MarketPosition == MarketPosition.Short) SubmitOrderUnmanaged(0, OrderAction.Buy, OrderType.Market, 1, 0, 0, null, "ShortLossExit");
			}
			
			// if one day has passed and the PnL is positive set an exit to happen before the close at the specified endTime
			if(dayCount > 1 && Position.MarketPosition != MarketPosition.Flat && pnl > 0 )
			{
				exitOnClose = true;
			}
		
			if(exitOnClose && Time[0] >= endTime)
			{
				if(Position.MarketPosition == MarketPosition.Long)  SubmitOrderUnmanaged(0, OrderAction.Sell, OrderType.Market, 1, 0, 0, null, "LongExitOnClose");
				if(Position.MarketPosition == MarketPosition.Short) SubmitOrderUnmanaged(0, OrderAction.BuyToCover, OrderType.Market, 1, 0, 0, null, "ShortExitOnClose");
			}
			
			// wait until the end of OBU execution to reset for session, nothing should happen on the first bar of the session trading wise
			if (Bars.IsFirstBarOfSession)
			{
				barCount	= 1;		
				sessionIterator.GetNextSession(Time[0], true);
				endTime = sessionIterator.ActualSessionEnd.AddMinutes(-ExitMinutesBeforeSessionEnd);
				
				if(Position.MarketPosition == MarketPosition.Flat)
				{
					dayCount	= 0;
					canTrade	= true;
					exitOnClose	= false;
				} else {
					dayCount++;
					canTrade	= false;
				}				
			}
			else 
				barCount++;
		}
		
		protected override void OnOrderUpdate(Cbi.Order order, double limitPrice, double stopPrice, int quantity, int filled, double averageFillPrice, Cbi.OrderState orderState, DateTime time, Cbi.ErrorCode error, string comment)
		{
			if (longStopEntry != null && longStopEntry.IsBacktestOrder && State == State.Realtime)
				longStopEntry = GetRealtimeOrder(longStopEntry);

			if (shortStopEntry != null && shortStopEntry.IsBacktestOrder && State == State.Realtime)
				shortStopEntry = GetRealtimeOrder(shortStopEntry);

			if ((longStopEntry != null && (longStopEntry.OrderState == OrderState.Cancelled || longStopEntry.OrderState == OrderState.Filled)))
				longStopEntry	= null;
			
			if ((shortStopEntry != null && (shortStopEntry.OrderState == OrderState.Cancelled || shortStopEntry.OrderState == OrderState.Filled)))
				shortStopEntry	= null;
			
			if (order.Name == "Brkout_LE" && longStopEntry != order)
				longStopEntry = order;

			if (order.Name == "Brkout_SE" && shortStopEntry != order)
				shortStopEntry = order;
		}
		
		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name="Range Filter", Order=1, GroupName="Parameters")]
		public int RangeFilter
		{ get; set; }
		
		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name="Entry Offset In Ticks", Order=1, GroupName="Parameters")]
		public int EntryOffsetInTicks
		{ get; set; }
		
		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name="Exit Minutes Before Session End", Order=1, GroupName="Parameters")]
		public int ExitMinutesBeforeSessionEnd
		{ get; set; }
	}
}