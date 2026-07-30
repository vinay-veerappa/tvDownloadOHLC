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
namespace NinjaTrader.NinjaScript.Strategies.Vinay
{
	public class ICTFVGBoS : Strategy
	{
		bool _breakHigh = false;
		double _breakHighBar;
		double _breakHighStructurePrice;
		bool _breakHighStructure = false;
		bool _tradedHighBreak;
		
		bool _breakLow = false;
		double _breakLowBar;
		double _breakLowStructurePrice;
		bool _breakLowStructure = false;
		bool _tradedLowBreak;

        //CurrentDayOHL today;
		//PriorDayOHLC daily;
		ZigZag zigzag;
		FVGICT fvg;

		
		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description									= @"This will take a trade based on a BoS + FVG formed on that BoS";
				Name										= "ICTFVGBoS";
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
				
				
				RFactor = 1;
				Lookback = 10;
				Gap = 1;
				
			}
			else if (State == State.Configure)
			{
				//daily = PriorDayOHLC();
				//today = CurrentDayOHL();
				zigzag = ZigZag(DeviationType.Points, 0.5, true);
				
				fvg =  FVGICT(false, FVGPeriodTypes.Minute, 1, 50 ,false, 1.1, 10, 0.1, false, FVGFillType.CLOSE_THROUGH, false, true, 
					false, new TimeSpan(0, 03, 00, 0, 0), 60,false, new TimeSpan(0, 03, 00, 0, 0), 60, false, new TimeSpan(0, 03, 00, 0, 0), 60,
					Brushes.LimeGreen, Brushes.LimeGreen, Brushes.Green, Brushes.Crimson, Brushes.Crimson, Brushes.Red, 20, 15, false,TextPosition.TopRight, new SimpleFont("Verdana", 12), Brushes.WhiteSmoke, Brushes.DimGray, Brushes.Blue,50);
				
				//AddChartIndicator(today);
				AddChartIndicator(zigzag);
				AddChartIndicator(fvg);
				
			}
		}

		protected override void OnBarUpdate()
		{
			if (Bars.BarsSinceNewTradingDay == 0)
			{
				_breakHigh = false;
				_breakHighStructure = false;
				_breakLow = false;
				_breakLowStructure = false;
				_tradedLowBreak = false;
				_tradedHighBreak = false;
			}
			
			if (CurrentBars[0] < 200)
				return;
			
			// Assuming today.Open -> This is 6 PM Opening price...
			//
			//if (today.Open[0] < today.CurrentHigh[0] && !_tradedHighBreak)
			{ //!_breakHigh && 
				int prevLow = zigzag.LowBar(1, 1, Lookback) ;
				Print("Previous Low =" + prevLow);
				if (prevLow > 0 && CrossBelow(Close, Low[prevLow], 1)) // this is the logic that requires change ... Need to add creation of FVG here???
				{
					Draw.TriangleDown(this, Bars.Count.ToString(), true, 0, Low[0] - 3*TickSize, Brushes.Red);
					int lastpivot = zigzag.HighBar(1, 1, Lookback);
					if(lastpivot > 0)
					{
						_breakHigh = true;				
						_breakHighStructurePrice = Low[zigzag.LowBar(1, 1, Lookback)];
						_breakHighBar = CurrentBar;
					}
				}
				//_breakHigh &&
				
				if ( Close[0] < _breakHighStructurePrice && CurrentBar > 3)
				{
					
					//if( FVGICT.getUpperPrice() > _breakHighBar)
					{
						_breakHighStructure = true;
						double entryPrice =0;// fvg.getLowerPrice();
						int lastHigh = zigzag.HighBar(1, 1, Lookback);
						Print("lastHigh =" + lastHigh);
						if(lastHigh > 0)
						{
							double stopprice = High[lastHigh];
							double stop = (stopprice - entryPrice) / TickSize +20;
							
							//double target = entryPrice - ((stop - entryPrice) * 2);
						
							EnterShortLimit(entryPrice);
							SetStopLoss(CalculationMode.Ticks, stop);
							SetProfitTarget(CalculationMode.Ticks, stop * RFactor);
							//SetStopLoss(CalculationMode.Ticks, stop);
							//SetProfitTarget(CalculationMode.Price, target);
						}
					}
				}
			}
			
			
			//if (today.Open[0] > today.CurrentLow[0] && !_tradedLowBreak)
			{//!_breakLow && 
				
				int prevHigh = zigzag.HighBar(1, 1, Lookback) ;
				Print("Previous High =" + prevHigh);
				if (prevHigh > 0 && CrossAbove(Close,High[prevHigh], 1))
				{
					Draw.TriangleUp(this, Bars.Count.ToString(), true, 0, High[0] + 3*TickSize, Brushes.DodgerBlue);
					int lastpivot = zigzag.LowBar(1, 1, Lookback);
					if(lastpivot > 0)
					{
						_breakLow = true;				
						_breakLowStructurePrice = High[zigzag.HighBar(1, 1, Lookback)];
						_breakLowBar = CurrentBar;
					}
				}
				
				if (_breakLow && Close[0] > _breakLowStructurePrice && CurrentBar > 3)
				{
					//double foo = gaps[0];
					//if(gaps.LastUpGap() > _breakLowBar)
					{
						_breakLowStructure = true;
						double entryPrice = 0; //fvg.getUpperPrice();
						int lastLow = zigzag.LowBar(1, 1, Lookback);
						Print("lastLowh =" + lastLow);
						if(lastLow > 0)
						{
							double stopprice = Low[lastLow];
							double stop = (entryPrice - stopprice) / TickSize - 20;
							//double target = entryPrice + ((entryPrice - stop) * 2);
						
							EnterLongLimit(entryPrice);
							SetStopLoss(CalculationMode.Ticks, stop);
							SetProfitTarget(CalculationMode.Ticks, stop * RFactor);
							//SetStopLoss(CalculationMode.Price, stop);
							//SetProfitTarget(CalculationMode.Price, target);
						}
					}
				}
			}
		}
		
		
		[NinjaScriptProperty]
		public int Lookback
		{ get; set; }
		
		[NinjaScriptProperty]
		public int Gap
		{ get; set; }
		
		[NinjaScriptProperty]
		public double RFactor
		{get; set; }
	}
}
