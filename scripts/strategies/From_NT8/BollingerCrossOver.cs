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
	public class BollingerCrossOver : Strategy
	{
		private Bollinger Bollinger1;	
		private BandType1 bandUsed1 = BandType1.Lower;
		private BandType1BasedON basedON1 = BandType1BasedON.Close;		
		private Series <double> myBollinger1; 
		private Series <double> myOHLC; 
		
		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description									= @"Enter the description for your new custom Strategy here.";
				Name										= "BollingerCrossOver";
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
				IsInstantiatedOnEachOptimizationIteration	= true;
				Period										= 14;
				NumberofStandardDeviations					= 2;


			}
			else if (State == State.Configure)
			{
			
			}
			else if (State == State.DataLoaded)
			{				
				Bollinger1				  = Bollinger(Close, NumberofStandardDeviations, Convert.ToInt32(Period));
				myBollinger1 			  = new Series<double>(this);
				myOHLC  			      = new Series<double>(this); 
				AddChartIndicator(Bollinger1);
			}
		}

		protected override void OnBarUpdate()
		{
			
			
			if (BarsInProgress != 0) 
				return;

			if (CurrentBars[0] < 1)
			return;
			
			switch (bandUsed1)
			{
				case BandType1.Lower:
				{
					myBollinger1[0] = (Bollinger1.Lower[0]);
					break;
				}
				
				case BandType1.Middle:
				{
					myBollinger1[0] = (Bollinger1.Middle[0]);
					break;
				}
				
				case BandType1.Upper:
				{
					myBollinger1[0] = (Bollinger1.Upper[0]);
					break;
				}
				
			}
			
					

			switch (basedON1)
			{
				case BandType1BasedON.Close:
				{
					myOHLC[0] = Close[0];
					break;
				}
				
				case BandType1BasedON.Open:
				{
					myOHLC[0] = Open[0];
					break;
				}
				
				case BandType1BasedON.High:
				{
					myOHLC[0] = High[0];
					break;
				}
				
				case BandType1BasedON.Low:
				{
					myOHLC[0] = Low[0];
					break;
				}
				
			}
			
					
			
			if (CrossAbove(myBollinger1, myOHLC, 1))
			{
				EnterLong(Convert.ToInt32(DefaultQuantity), "");
			}
			
			if (CrossBelow(myBollinger1, myOHLC, 1))
			{
				EnterShort(Convert.ToInt32(DefaultQuantity), "");
			}
			
		}

		#region Properties
		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name="Period", Description="Period", Order=1, GroupName="Parameters")]
		public int Period
		{ get; set; }


		[NinjaScriptProperty]
		[Range(1, int.MaxValue)]
		[Display(Name="NumberofStandardDeviations", Description="Number of Standard Deviations", Order=3, GroupName="Parameters")]
		public int NumberofStandardDeviations
		{ get; set; }
		
		[Browsable(false)]
		[XmlIgnore()]
		public Series<double> Lower
		{
			get { return Values[2]; }
		}

		[Browsable(false)]
		[XmlIgnore()]
		public Series<double> Middle
		{
			get { return Values[1]; }
		}
		
		[Browsable(false)]
		[XmlIgnore()]
		public Series<double> Upper
		{
			get { return Values[0]; }
		}
		
		
		
		[Display(GroupName = "Band", Description="Choose a Band for plot 1.")]
		public BandType1 BandUsed1
		{
			get { return bandUsed1; }
			set { bandUsed1 = value; }
		}
		
		[Display(GroupName = "Based on (OHLC)", Description="Bollinger 1 based on")]
		public BandType1BasedON BasedON1
		{
			get { return basedON1; }
			set { basedON1 = value; }
		}
		
		#endregion
	
		

	}
}

public enum BandType1
{
	Lower,
	Middle,
	Upper,
	
}

public enum BandType1BasedON
{
	Close,
	Open,
	High,
	Low,
	
}
