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
using NinjaTrader.NinjaScript.DrawingTools;
#endregion

//This namespace holds Indicators in this folder and is required. Do not change it. 
namespace NinjaTrader.NinjaScript.Indicators
{
	public class ORB_V6_Indicator : Indicator
	{
		private double rHigh = double.MinValue;
		private double rLow = double.MaxValue;
		private bool rDefined = false;
		private DateTime lastDate = DateTime.MinValue;
		private double activeSL = double.NaN;
		private double activeTP = double.NaN;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description									= @"9:30 AM ORB V6 [Unified Specification]";
				Name										= "ORB_V6_Indicator";
				Calculate									= Calculate.OnBarClose;
				IsOverlay									= true;
				DisplayInDataBox							= true;
				DrawOnPricePanel							= true;
				DrawHorizontalGridLines						= true;
				DrawVerticalGridLines						= true;
				PaintPriceMarkers							= true;
				ScaleJustification							= NinjaTrader.Gui.Chart.ScaleJustification.Right;
				//Disable this property if your indicator requires custom values that cumulate with each new bar
				IsSuspendedWhileInactive					= true;
				
				// Inputs
				SessionStart = "09:30";
				SessionEnd = "09:31";
				
				EntryModel = "Shallow (25%)";
				UseRegime = true;
				UseVVIX = true;
				UseTuesday = true;
				UseTimeExit = true;
				HardExitTime = DateTime.Parse("10:00", System.Globalization.CultureInfo.InvariantCulture);
				VVIX_Open = 100.0;
				MAE_Threshold = 0.12;
				RiskPercent = 1.0;
				InitialCapital = 100000.0;
				ShowExits = true;
				TPSetting = 0.35;
				UseSweetSpot = true;
				// PointValue is now retrieved dynamically from Instrument.MasterInstrument.PointValue

				AddPlot(new Stroke(Brushes.Gray, DashStyleHelper.Dash, 2), PlotStyle.Line, "RangeHigh");
				AddPlot(new Stroke(Brushes.Gray, DashStyleHelper.Dash, 1), PlotStyle.Line, "Level25");
				AddPlot(new Stroke(Brushes.Gray, DashStyleHelper.Dash, 1), PlotStyle.Line, "Level50");
				AddPlot(new Stroke(Brushes.Gray, DashStyleHelper.Dash, 1), PlotStyle.Line, "Level75");
				AddPlot(new Stroke(Brushes.Gray, DashStyleHelper.Dash, 2), PlotStyle.Line, "RangeLow");
				AddPlot(new Stroke(Brushes.Gray, DashStyleHelper.Dash, 1), PlotStyle.Line, "BufferUpper");
				AddPlot(new Stroke(Brushes.Gray, DashStyleHelper.Dash, 1), PlotStyle.Line, "BufferLower");
			}
			else if (State == State.Configure)
			{
				AddDataSeries(BarsPeriodType.Day, 1); // Secondary series for Regime (SMA20)
			}
		}

		protected override void OnBarUpdate()
		{
			if (CurrentBar < 20) return;

			// Logic to capture 9:30 OR
			if (Bars.IsFirstBarOfSession)
			{
				rHigh = double.MinValue;
				rLow = double.MaxValue;
				rDefined = false;
			}

			// Capture Range (Assuming ET time)
			if (Time[0].Hour == 9 && Time[0].Minute == 30)
			{
				rHigh = High[0];
				rLow = Low[0];
				rDefined = true;
			}

			if (rDefined)
			{
				double rSize = rHigh - rLow;
				Values[0][0] = rHigh;
				Values[1][0] = rHigh - (rSize * 0.25);
				Values[2][0] = rHigh - (rSize * 0.50);
				Values[3][0] = rHigh - (rSize * 0.75);
				Values[4][0] = rLow;

				// 0.10% Buffer Lines (of Price, offset from boundaries)
				Values[5][0] = rHigh + (Close[0] * 0.001);
				Values[6][0] = rLow - (Close[0] * 0.001);
			}

			// Dashboard & Signals Logic
			if (IsFirstTickOfBar && rDefined)
			{
				bool isBull = true;
				if (BarsArray[1].Count >= 20)
				{
					double sma20_daily = SMA(BarsArray[1], 20)[0];
					double close_daily = BarsArray[1].GetClose(0);
					isBull = close_daily > sma20_daily;
				}
				
				bool isTuesday = Time[0].DayOfWeek == DayOfWeek.Tuesday;
				bool isFiltered = (UseVVIX && VVIX_Open > 115) || (UseRegime && !isBull) || (UseTuesday && isTuesday);
				bool isTradingClosed = UseTimeExit && ToTime(Time[0]) >= ToTime(HardExitTime);
				bool canTrade = rDefined && !isFiltered && !isTradingClosed;

				// Visual Signals (Triangles)
				if (canTrade)
				{
					if (Close[0] > rHigh) 
						Draw.TriangleUp(this, "Buy" + CurrentBar, true, 0, Low[0] - TickSize, Brushes.SpringGreen);
					else if (Close[0] < rLow)
						Draw.TriangleDown(this, "Sell" + CurrentBar, true, 0, High[0] + TickSize, Brushes.Red);
				}

				if (CurrentBar == BarsArray[0].Count - 1)
				{
					string status = isTradingClosed ? "TRADING CLOSED" : isFiltered ? "SKIP (Filtered)" : (EntryModel == "Breakout (Close)" ? "READY: Breakout" : "WAIT: Pullback");
					Brush statusColor = isTradingClosed ? Brushes.Gray : isFiltered ? Brushes.Red : Brushes.SpringGreen;

					double rSize = rHigh - rLow;
					double rPct = (rSize / BarsArray[0].GetOpen(0)) * 100;
					int contracts = (int)Math.Max(1, Math.Floor((InitialCapital * (RiskPercent / 100)) / (rSize * Instrument.MasterInstrument.PointValue)));

					bool isSweetSpot = UseSweetSpot && VVIX_Open >= 98 && VVIX_Open <= 115;
					string vvixStatus = isSweetSpot ? "SWEET SPOT" : (VVIX_Open > 115 ? "EXTREME" : "NORMAL");

					string diagInfo = string.Format("{0} / {1}", isFiltered ? "FILT" : "OK", canTrade ? "YES" : "NO");
					string hud = string.Format("REGIME: {0}\nVVIX: {1:F1} ({2})\nRANGE: {3:F2} pts ({4:F3}%)\nMODEL: {5}\nSIZE: {6} Lots\nSTATUS: {7}\nDIAG: {8}", 
						isBull ? "BULL" : "BEAR", VVIX_Open, vvixStatus, rSize, rPct, EntryModel, contracts, status, diagInfo);
					
					Draw.TextFixed(this, "HUD", hud, TextPosition.TopRight, Brushes.White, new Gui.Tools.SimpleFont("Arial", 11), Brushes.Black, Brushes.DimGray, 90);

					// Sweet Spot Highlight
					if (isSweetSpot)
					{
						Draw.Rectangle(this, "SweetSpot", true, 20, rHigh, 0, rLow, Brushes.Transparent, Brushes.Orange, 10);
					}
				}
			}

			// Visual SL/TP Plotting logic
			if (rDefined)
			{
				bool isLongSignal = Close[0] > rHigh;
				bool isShortSignal = Close[0] < rLow;

				if (isLongSignal && (EntryModel == "Breakout (Close)" || (canTrade && Low[0] <= rHigh - (rHigh-rLow) * 0.25))) // Approximation for PB
				{
					activeSL = rLow;
					activeTP = Close[0] * (1 + TPSetting / 100);
				}
				else if (isShortSignal)
				{
					activeSL = rHigh;
					activeTP = Close[0] * (1 - TPSetting / 100);
				}

				if (ShowExits && !double.IsNaN(activeSL))
				{
					Draw.Line(this, "SL_Line", true, 10, activeSL, -5, activeSL, Brushes.Red, DashStyleHelper.Dash, 2);
					Draw.Line(this, "TP_Line", true, 10, activeTP, -5, activeTP, Brushes.SpringGreen, DashStyleHelper.Dash, 2);
				}
			}
		}

		#region Properties
		[NinjaScriptProperty]
		[Display(Name="Entry Model", Order=0, GroupName="Core")]
		public string EntryModel { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Session Start (ET)", Order=1, GroupName="Core")]
		public string SessionStart { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Session End (ET)", Order=2, GroupName="Core")]
		public string SessionEnd { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Use Regime Filter", Order=3, GroupName="Addons")]
		public bool UseRegime { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Use VVIX Filter", Order=4, GroupName="Addons")]
		public bool UseVVIX { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Use Tuesday Skip", Order=5, GroupName="Addons")]
		public bool UseTuesday { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Use Time Exit", Order=6, GroupName="Addons")]
		public bool UseTimeExit { get; set; }

		[NinjaScriptProperty]
		[PropertyEditor("NinjaTrader.Gui.Tools.TimeEditorKey")]
		[Display(Name="Hard Exit Time", Order=7, GroupName="Addons")]
		public DateTime HardExitTime { get; set; }

		[NinjaScriptProperty]
		[Display(Name="VVIX Open Value", Order=8, GroupName="Addons")]
		public double VVIX_Open { get; set; }

		[NinjaScriptProperty]
		[Display(Name="MAE % Threshold", Order=9, GroupName="Addons")]
		public double MAE_Threshold { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Risk Percent (%)", Order=7, GroupName="Risk")]
		public double RiskPercent { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Initial Capital ($)", Order=8, GroupName="Risk")]
		public double InitialCapital { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Use Sweet Spot Highlight", Order=9, GroupName="Addons")]
		public bool UseSweetSpot { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Show Projected Exits", Order=10, GroupName="Addons")]
		public bool ShowExits { get; set; }

		[NinjaScriptProperty]
		[Display(Name="Projected TP (%)", Order=11, GroupName="Core")]
		public double TPSetting { get; set; }

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> RangeHigh { get { return Values[0]; } }

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> Level25 { get { return Values[1]; } }

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> Level50 { get { return Values[2]; } }

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> Level75 { get { return Values[3]; } }

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> RangeLow { get { return Values[4]; } }

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> BufferUpper { get { return Values[5]; } }

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> BufferLower { get { return Values[6]; } }
		#endregion
	}
}
