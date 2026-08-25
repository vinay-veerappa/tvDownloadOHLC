//+----------------------------------------------------------------------------------------------+
//| Copyright (c) 2026 LizardIndicators Re-engineering / Antigravity
//|
//| Current Day Median (Session-Anchored VWTPO / TPO Median with 6 Residual MAD Bands and Multi-Tiered Clouds)
//+----------------------------------------------------------------------------------------------+

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
using SharpDX;
using SharpDX.Direct2D1;
#endregion

namespace NinjaTrader.NinjaScript.Indicators.LizardIndicators
{
	public enum amaSessionTypeCDM
	{
		FullDay,
		RTH,
		Asia,
		London,
		NY_AM,
		NY_PM,
		CustomSession
	}

	[Gui.CategoryOrder("Input Parameters", 0)]
	[Gui.CategoryOrder("Session Settings", 5)]
	[Gui.CategoryOrder("Residual MAD Bands", 10)]
	[Gui.CategoryOrder("Cloud Fill", 20)]
	[Gui.CategoryOrder("Visual", 30)]
	[Gui.CategoryOrder("Plots", 40)]
	[Gui.CategoryOrder("Version", 80)]
	public class amaCurrentDayMedian : Indicator
	{
		private bool				isVWTPO						= true;
		private bool				interpolate					= true;
		private amaSessionTypeCDM	sessionType					= amaSessionTypeCDM.FullDay;
		private string				sessionStartTime			= "09:30";
		private string				sessionEndTime				= "16:00";
		private TimeSpan			startTimeSpan				= new TimeSpan(9, 30, 0);
		private TimeSpan			endTimeSpan					= new TimeSpan(16, 0, 0);

		private bool				showBands					= true;
		private double				bandMultiplier1				= 1.50; // Inner Value Area (68.3%)
		private double				bandMultiplier2				= 2.75; // Outer Channel (95.5%)
		private double				bandMultiplier3				= 4.00; // Extreme Tail (99.7%)
		private bool				showBand2					= true;
		private bool				showBand3					= true;
		private bool				showClouds					= true;
		private int					innerCloudOpacity			= 20;
		private int					midCloudOpacity				= 35;
		private int					outerCloudOpacity			= 55;

		private double 				high						= 0.0;
		private double 				low							= 0.0;
		private int 				fieldSize					= 0;
		private double				sessionVolume				= 0.0;
		private List<double> 		fList	 					= new List<double>();
		private bool				inCustomSession				= false;
		private bool				prevInCustomSession			= false;
		private string				versionString				= "v 1.4 - 6-Band Extreme Clouds";

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description					= "Current Day Median with 6 Residual MAD Bands (3 Upper + 3 Lower) and Multi-Tiered Cloud Fills.";
				Name						= "amaCurrentDayMedian";
				IsSuspendedWhileInactive	= true;
				IsOverlay					= true;
				Calculate					= Calculate.OnPriceChange;

				// Lizard Visual Color Scheme matching screenshot
				AddPlot(new Stroke(System.Windows.Media.Brushes.Blue, DashStyleHelper.Dash, 2), PlotStyle.Line, "Current Day Median");
				AddPlot(new Stroke(System.Windows.Media.Brushes.DarkCyan, 1), PlotStyle.Line, "Upper MAD Band 1");
				AddPlot(new Stroke(System.Windows.Media.Brushes.DarkCyan, 1), PlotStyle.Line, "Lower MAD Band 1");
				AddPlot(new Stroke(System.Windows.Media.Brushes.Teal, 1), PlotStyle.Line, "Upper MAD Band 2");
				AddPlot(new Stroke(System.Windows.Media.Brushes.Teal, 1), PlotStyle.Line, "Lower MAD Band 2");
				AddPlot(new Stroke(System.Windows.Media.Brushes.CadetBlue, DashStyleHelper.Dot, 1), PlotStyle.Line, "Upper MAD Band 3 (Extreme)");
				AddPlot(new Stroke(System.Windows.Media.Brushes.CadetBlue, DashStyleHelper.Dot, 1), PlotStyle.Line, "Lower MAD Band 3 (Extreme)");
				AddPlot(new Stroke(System.Windows.Media.Brushes.Transparent, 1), PlotStyle.Line, "MAD Value");
			}
			else if (State == State.Configure)
			{
				BarsRequiredToPlot = 1;
				UpdateTimeSpans();
			}
		}

		private void UpdateTimeSpans()
		{
			switch (sessionType)
			{
				case amaSessionTypeCDM.RTH:
					startTimeSpan = new TimeSpan(9, 30, 0);
					endTimeSpan   = new TimeSpan(16, 0, 0);
					break;
				case amaSessionTypeCDM.Asia:
					startTimeSpan = new TimeSpan(18, 0, 0);
					endTimeSpan   = new TimeSpan(2, 30, 0);
					break;
				case amaSessionTypeCDM.London:
					startTimeSpan = new TimeSpan(2, 30, 0);
					endTimeSpan   = new TimeSpan(7, 30, 0);
					break;
				case amaSessionTypeCDM.NY_AM:
					startTimeSpan = new TimeSpan(8, 30, 0);
					endTimeSpan   = new TimeSpan(11, 30, 0);
					break;
				case amaSessionTypeCDM.NY_PM:
					startTimeSpan = new TimeSpan(12, 30, 0);
					endTimeSpan   = new TimeSpan(16, 15, 0);
					break;
				case amaSessionTypeCDM.CustomSession:
					TimeSpan.TryParse(sessionStartTime, out startTimeSpan);
					TimeSpan.TryParse(sessionEndTime, out endTimeSpan);
					break;
			}
		}

		private bool IsTimeInSession(TimeSpan t, TimeSpan start, TimeSpan end)
		{
			if (start <= end)
				return t >= start && t <= end;
			else
				return t >= start || t <= end;
		}

		protected override void OnBarUpdate()
		{
			if (CurrentBar < 0) return;

			TimeSpan barTime = Time[0].TimeOfDay;
			bool isSessionStart = false;
			bool isActive = true;

			if (sessionType == amaSessionTypeCDM.FullDay)
			{
				isSessionStart = Bars.IsFirstBarOfSession;
				isActive = true;
			}
			else
			{
				inCustomSession = IsTimeInSession(barTime, startTimeSpan, endTimeSpan);
				isSessionStart = inCustomSession && (!prevInCustomSession || Bars.IsFirstBarOfSession);
				prevInCustomSession = inCustomSession;
				isActive = inCustomSession;
			}

			// Clean session reset: start accumulation fresh at the start of each session
			if (isSessionStart)
			{
				high = High[0];
				low = Low[0];
				fieldSize = 1 + Math.Max(0, Convert.ToInt32(Math.Round((high - low) / TickSize)));
				fList.Clear();
				for (int i = 0; i < fieldSize; i++)
					fList.Add(0.0);
				sessionVolume = 0.0;
			}

			if (!isActive)
			{
				if (CurrentBar > 0)
				{
					Values[0][0] = Values[0][1];
					Values[1][0] = Values[1][1];
					Values[2][0] = Values[2][1];
					Values[3][0] = Values[3][1];
					Values[4][0] = Values[4][1];
					Values[5][0] = Values[5][1];
					Values[6][0] = Values[6][1];
					Values[7][0] = Values[7][1];
				}
				return;
			}

			if (Low[0] < low)
			{
				int newLowFields = Convert.ToInt32(Math.Round((low - Low[0]) / TickSize));
				for (int i = 0; i < newLowFields; i++)
					fList.Insert(0, 0.0);
				low = Low[0];
				fieldSize += newLowFields;
			}

			if (High[0] > high)
			{
				int newHighFields = Convert.ToInt32(Math.Round((High[0] - high) / TickSize));
				for (int i = 0; i < newHighFields; i++)
					fList.Add(0.0);
				high = High[0];
				fieldSize += newHighFields;
			}

			int lowIndex = Math.Max(0, Math.Min(fieldSize - 1, Convert.ToInt32(Math.Round((Low[0] - low) / TickSize))));
			int highIndex = Math.Max(0, Math.Min(fieldSize - 1, Convert.ToInt32(Math.Round((High[0] - low) / TickSize))));
			int span = 1 + highIndex - lowIndex;

			double barVol = isVWTPO ? (Volume[0] > 0 ? Volume[0] : 1.0) : 1.0;
			double slice = barVol / span;

			for (int k = lowIndex; k <= highIndex; k++)
				fList[k] += slice;

			sessionVolume += barVol;

			if (sessionVolume <= 0 || fieldSize == 0)
			{
				Values[0][0] = (High[0] + Low[0]) * 0.5;
				return;
			}

			double targetVol = sessionVolume * 0.5;
			double sum = 0.0;
			double priorSum = 0.0;
			double calculatedMedian = (High[0] + Low[0]) * 0.5;

			for (int i = 0; i < fieldSize; i++)
			{
				double price = low + i * TickSize;
				sum += fList[i];

				if (sum >= targetVol)
				{
					if (interpolate && (sum - priorSum) > 0)
					{
						calculatedMedian = price + ((targetVol - priorSum) / (sum - priorSum) - 0.5) * TickSize;
					}
					else
					{
						calculatedMedian = price;
					}
					break;
				}
				priorSum = sum;
			}

			Values[0][0] = calculatedMedian;

			// Dynamic Median color: Blue when Price >= Median, Red when Price < Median
			if (Close[0] < calculatedMedian)
				PlotBrushes[0][0] = System.Windows.Media.Brushes.Red;
			else
				PlotBrushes[0][0] = System.Windows.Media.Brushes.Blue;

			if (showBands)
			{
				double madSum = 0.0;
				for (int i = 0; i < fieldSize; i++)
				{
					double price = low + i * TickSize;
					madSum += fList[i] * Math.Abs(price - calculatedMedian);
				}
				double mad = madSum / sessionVolume;

				// Band 1: Value Area
				Values[1][0] = calculatedMedian + bandMultiplier1 * mad;
				Values[2][0] = calculatedMedian - bandMultiplier1 * mad;

				// Band 2: Discovery Channel
				if (showBand2)
				{
					Values[3][0] = calculatedMedian + bandMultiplier2 * mad;
					Values[4][0] = calculatedMedian - bandMultiplier2 * mad;
				}

				// Band 3: Extreme Tail Zone
				if (showBand3)
				{
					Values[5][0] = calculatedMedian + bandMultiplier3 * mad;
					Values[6][0] = calculatedMedian - bandMultiplier3 * mad;
				}

				Values[7][0] = mad;
			}
		}

		protected override void OnRender(ChartControl chartControl, ChartScale chartScale)
		{
			base.OnRender(chartControl, chartScale);

			if (!showClouds || !showBands || ChartBars == null || RenderTarget == null)
				return;

			byte innerA = (byte)Math.Max(0, Math.Min(255, (int)(255 * (innerCloudOpacity / 100.0))));
			byte midA   = (byte)Math.Max(0, Math.Min(255, (int)(255 * (midCloudOpacity / 100.0))));
			byte outerA = (byte)Math.Max(0, Math.Min(255, (int)(255 * (outerCloudOpacity / 100.0))));

			var innerC = SharpDX.Color.MediumTurquoise;
			var midC   = SharpDX.Color.CadetBlue;
			var outerC = SharpDX.Color.DarkSlateGray;

			var innerDX = new SharpDX.Color4(innerC.R / 255f, innerC.G / 255f, innerC.B / 255f, innerA / 255f);
			var midDX   = new SharpDX.Color4(midC.R / 255f, midC.G / 255f, midC.B / 255f, midA / 255f);
			var outerDX = new SharpDX.Color4(outerC.R / 255f, outerC.G / 255f, outerC.B / 255f, outerA / 255f);

			using (var bInner = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, innerDX))
			using (var bMid   = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, midDX))
			using (var bOuter = new SharpDX.Direct2D1.SolidColorBrush(RenderTarget, outerDX))
			{
				int firstIdx = ChartBars.FromIndex;
				int lastIdx  = ChartBars.ToIndex;

				for (int barIdx = firstIdx; barIdx < lastIdx; barIdx++)
				{
					if (barIdx < 0 || barIdx >= Values[0].Count - 1) continue;

					float x1 = chartControl.GetXByBarIndex(ChartBars, barIdx);
					float x2 = chartControl.GetXByBarIndex(ChartBars, barIdx + 1);

					double u1_0 = Values[1].GetValueAt(barIdx);
					double u1_1 = Values[1].GetValueAt(barIdx + 1);
					double l1_0 = Values[2].GetValueAt(barIdx);
					double l1_1 = Values[2].GetValueAt(barIdx + 1);

					if (double.IsNaN(u1_0) || double.IsNaN(u1_1) || double.IsNaN(l1_0) || double.IsNaN(l1_1))
						continue;

					float y_u1_0 = chartScale.GetYByValue(u1_0);
					float y_u1_1 = chartScale.GetYByValue(u1_1);
					float y_l1_0 = chartScale.GetYByValue(l1_0);
					float y_l1_1 = chartScale.GetYByValue(l1_1);

					// 1. Inner Value Area Cloud (Upper 1 -> Lower 1)
					using (var pathGeo = new SharpDX.Direct2D1.PathGeometry(RenderTarget.Factory))
					{
						using (var sink = pathGeo.Open())
						{
							sink.BeginFigure(new SharpDX.Vector2(x1, y_u1_0), SharpDX.Direct2D1.FigureBegin.Filled);
							sink.AddLine(new SharpDX.Vector2(x2, y_u1_1));
							sink.AddLine(new SharpDX.Vector2(x2, y_l1_1));
							sink.AddLine(new SharpDX.Vector2(x1, y_l1_0));
							sink.EndFigure(SharpDX.Direct2D1.FigureEnd.Closed);
							sink.Close();
						}
						RenderTarget.FillGeometry(pathGeo, bInner);
					}

					// 2. Middle Channel Clouds (Upper 2 -> Upper 1 & Lower 1 -> Lower 2)
					if (showBand2)
					{
						double u2_0 = Values[3].GetValueAt(barIdx);
						double u2_1 = Values[3].GetValueAt(barIdx + 1);
						double l2_0 = Values[4].GetValueAt(barIdx);
						double l2_1 = Values[4].GetValueAt(barIdx + 1);

						if (!double.IsNaN(u2_0) && !double.IsNaN(u2_1))
						{
							float y_u2_0 = chartScale.GetYByValue(u2_0);
							float y_u2_1 = chartScale.GetYByValue(u2_1);

							using (var pathGeo = new SharpDX.Direct2D1.PathGeometry(RenderTarget.Factory))
							{
								using (var sink = pathGeo.Open())
								{
									sink.BeginFigure(new SharpDX.Vector2(x1, y_u2_0), SharpDX.Direct2D1.FigureBegin.Filled);
									sink.AddLine(new SharpDX.Vector2(x2, y_u2_1));
									sink.AddLine(new SharpDX.Vector2(x2, y_u1_1));
									sink.AddLine(new SharpDX.Vector2(x1, y_u1_0));
									sink.EndFigure(SharpDX.Direct2D1.FigureEnd.Closed);
									sink.Close();
								}
								RenderTarget.FillGeometry(pathGeo, bMid);
							}
						}

						if (!double.IsNaN(l2_0) && !double.IsNaN(l2_1))
						{
							float y_l2_0 = chartScale.GetYByValue(l2_0);
							float y_l2_1 = chartScale.GetYByValue(l2_1);

							using (var pathGeo = new SharpDX.Direct2D1.PathGeometry(RenderTarget.Factory))
							{
								using (var sink = pathGeo.Open())
								{
									sink.BeginFigure(new SharpDX.Vector2(x1, y_l1_0), SharpDX.Direct2D1.FigureBegin.Filled);
									sink.AddLine(new SharpDX.Vector2(x2, y_l1_1));
									sink.AddLine(new SharpDX.Vector2(x2, y_l2_1));
									sink.AddLine(new SharpDX.Vector2(x1, y_l2_0));
									sink.EndFigure(SharpDX.Direct2D1.FigureEnd.Closed);
									sink.Close();
								}
								RenderTarget.FillGeometry(pathGeo, bMid);
							}
						}

						// 3. Extreme Exhaustion Clouds (Upper 3 -> Upper 2 & Lower 2 -> Lower 3)
						if (showBand3)
						{
							double u3_0 = Values[5].GetValueAt(barIdx);
							double u3_1 = Values[5].GetValueAt(barIdx + 1);
							double l3_0 = Values[6].GetValueAt(barIdx);
							double l3_1 = Values[6].GetValueAt(barIdx + 1);

							if (!double.IsNaN(u3_0) && !double.IsNaN(u3_1))
							{
								float y_u3_0 = chartScale.GetYByValue(u3_0);
								float y_u3_1 = chartScale.GetYByValue(u3_1);
								float y_u2_0 = chartScale.GetYByValue(u2_0);
								float y_u2_1 = chartScale.GetYByValue(u2_1);

								using (var pathGeo = new SharpDX.Direct2D1.PathGeometry(RenderTarget.Factory))
								{
									using (var sink = pathGeo.Open())
									{
										sink.BeginFigure(new SharpDX.Vector2(x1, y_u3_0), SharpDX.Direct2D1.FigureBegin.Filled);
										sink.AddLine(new SharpDX.Vector2(x2, y_u3_1));
										sink.AddLine(new SharpDX.Vector2(x2, y_u2_1));
										sink.AddLine(new SharpDX.Vector2(x1, y_u2_0));
										sink.EndFigure(SharpDX.Direct2D1.FigureEnd.Closed);
										sink.Close();
									}
									RenderTarget.FillGeometry(pathGeo, bOuter);
								}
							}

							if (!double.IsNaN(l3_0) && !double.IsNaN(l3_1))
							{
								float y_l3_0 = chartScale.GetYByValue(l3_0);
								float y_l3_1 = chartScale.GetYByValue(l3_1);
								float y_l2_0 = chartScale.GetYByValue(l2_0);
								float y_l2_1 = chartScale.GetYByValue(l2_1);

								using (var pathGeo = new SharpDX.Direct2D1.PathGeometry(RenderTarget.Factory))
								{
									using (var sink = pathGeo.Open())
									{
										sink.BeginFigure(new SharpDX.Vector2(x1, y_l2_0), SharpDX.Direct2D1.FigureBegin.Filled);
										sink.AddLine(new SharpDX.Vector2(x2, y_l2_1));
										sink.AddLine(new SharpDX.Vector2(x2, y_l3_1));
										sink.AddLine(new SharpDX.Vector2(x1, y_l3_0));
										sink.EndFigure(SharpDX.Direct2D1.FigureEnd.Closed);
										sink.Close();
									}
									RenderTarget.FillGeometry(pathGeo, bOuter);
								}
							}
						}
					}
				}
			}
		}

		#region Properties
		[Browsable(false)]
		[XmlIgnore]
		public Series<double> MedianPlot => Values[0];

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> UpperBand1 => Values[1];

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> LowerBand1 => Values[2];

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> UpperBand2 => Values[3];

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> LowerBand2 => Values[4];

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> UpperBand3 => Values[5];

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> LowerBand3 => Values[6];

		[Browsable(false)]
		[XmlIgnore]
		public Series<double> MAD => Values[7];

		[NinjaScriptProperty]
		[Display(ResourceType = typeof(Custom.Resource), Name = "Volume-Weighted (VWTPO)", GroupName = "Input Parameters", Order = 0)]
		public bool IsVWTPO
		{
			get { return isVWTPO; }
			set { isVWTPO = value; }
		}

		[NinjaScriptProperty]
		[Display(ResourceType = typeof(Custom.Resource), Name = "Interpolate values", GroupName = "Input Parameters", Order = 1)]
		public bool Interpolate
		{
			get { return interpolate; }
			set { interpolate = value; }
		}

		[NinjaScriptProperty]
		[Display(ResourceType = typeof(Custom.Resource), Name = "Session Selection", GroupName = "Session Settings", Order = 0)]
		public amaSessionTypeCDM SessionType
		{
			get { return sessionType; }
			set { sessionType = value; UpdateTimeSpans(); }
		}

		[NinjaScriptProperty]
		[Display(ResourceType = typeof(Custom.Resource), Name = "Custom Start Time (HH:mm)", GroupName = "Session Settings", Order = 1)]
		public string SessionStartTime
		{
			get { return sessionStartTime; }
			set { sessionStartTime = value; UpdateTimeSpans(); }
		}

		[NinjaScriptProperty]
		[Display(ResourceType = typeof(Custom.Resource), Name = "Custom End Time (HH:mm)", GroupName = "Session Settings", Order = 2)]
		public string SessionEndTime
		{
			get { return sessionEndTime; }
			set { sessionEndTime = value; UpdateTimeSpans(); }
		}

		[NinjaScriptProperty]
		[Display(ResourceType = typeof(Custom.Resource), Name = "Show MAD Bands", GroupName = "Residual MAD Bands", Order = 0)]
		public bool ShowBands
		{
			get { return showBands; }
			set { showBands = value; }
		}

		[NinjaScriptProperty]
		[Range(0.1, double.MaxValue)]
		[Display(ResourceType = typeof(Custom.Resource), Name = "Band 1 Multiplier (Value Area)", GroupName = "Residual MAD Bands", Order = 1)]
		public double BandMultiplier1
		{
			get { return bandMultiplier1; }
			set { bandMultiplier1 = value; }
		}

		[NinjaScriptProperty]
		[Display(ResourceType = typeof(Custom.Resource), Name = "Show 2nd MAD Band (Channel)", GroupName = "Residual MAD Bands", Order = 2)]
		public bool ShowBand2
		{
			get { return showBand2; }
			set { showBand2 = value; }
		}

		[NinjaScriptProperty]
		[Range(0.1, double.MaxValue)]
		[Display(ResourceType = typeof(Custom.Resource), Name = "Band 2 Multiplier (Channel)", GroupName = "Residual MAD Bands", Order = 3)]
		public double BandMultiplier2
		{
			get { return bandMultiplier2; }
			set { bandMultiplier2 = value; }
		}

		[NinjaScriptProperty]
		[Display(ResourceType = typeof(Custom.Resource), Name = "Show 3rd MAD Band (Extreme)", GroupName = "Residual MAD Bands", Order = 4)]
		public bool ShowBand3
		{
			get { return showBand3; }
			set { showBand3 = value; }
		}

		[NinjaScriptProperty]
		[Range(0.1, double.MaxValue)]
		[Display(ResourceType = typeof(Custom.Resource), Name = "Band 3 Multiplier (Extreme)", GroupName = "Residual MAD Bands", Order = 5)]
		public double BandMultiplier3
		{
			get { return bandMultiplier3; }
			set { bandMultiplier3 = value; }
		}

		[NinjaScriptProperty]
		[Display(ResourceType = typeof(Custom.Resource), Name = "Show Cloud Fills", GroupName = "Cloud Fill", Order = 0)]
		public bool ShowClouds
		{
			get { return showClouds; }
			set { showClouds = value; }
		}

		[NinjaScriptProperty]
		[Range(0, 100)]
		[Display(ResourceType = typeof(Custom.Resource), Name = "Inner Value Cloud Opacity (%)", GroupName = "Cloud Fill", Order = 1)]
		public int InnerCloudOpacity
		{
			get { return innerCloudOpacity; }
			set { innerCloudOpacity = value; }
		}

		[NinjaScriptProperty]
		[Range(0, 100)]
		[Display(ResourceType = typeof(Custom.Resource), Name = "Middle Channel Opacity (%)", GroupName = "Cloud Fill", Order = 2)]
		public int MidCloudOpacity
		{
			get { return midCloudOpacity; }
			set { midCloudOpacity = value; }
		}

		[NinjaScriptProperty]
		[Range(0, 100)]
		[Display(ResourceType = typeof(Custom.Resource), Name = "Outer Extreme Opacity (%)", GroupName = "Cloud Fill", Order = 3)]
		public int OuterCloudOpacity
		{
			get { return outerCloudOpacity; }
			set { outerCloudOpacity = value; }
		}

		[XmlIgnore]
		[Display(ResourceType = typeof(Custom.Resource), Name = "Release and date", Description = "Release and date", GroupName = "Version", Order = 0)]
		public string VersionString
		{
			get { return versionString; }
			set { ; }
		}
		#endregion
		
		#region Miscellaneous
		public override string FormatPriceMarker(double price)
		{
			if(Instrument != null && Instrument.MasterInstrument != null)
				return Instrument.MasterInstrument.FormatPrice(Instrument.MasterInstrument.RoundToTickSize(price));
			return base.FormatPriceMarker(price);
		}
		#endregion	
	}
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
	public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
	{
		private LizardIndicators.amaCurrentDayMedian[] cacheamaCurrentDayMedian;
		public LizardIndicators.amaCurrentDayMedian amaCurrentDayMedian(bool isVWTPO, bool interpolate, LizardIndicators.amaSessionTypeCDM sessionType, string sessionStartTime, string sessionEndTime, bool showBands, double bandMultiplier1, bool showBand2, double bandMultiplier2, bool showBand3, double bandMultiplier3, bool showClouds, int innerCloudOpacity, int midCloudOpacity, int outerCloudOpacity)
		{
			return amaCurrentDayMedian(Input, isVWTPO, interpolate, sessionType, sessionStartTime, sessionEndTime, showBands, bandMultiplier1, showBand2, bandMultiplier2, showBand3, bandMultiplier3, showClouds, innerCloudOpacity, midCloudOpacity, outerCloudOpacity);
		}

		public LizardIndicators.amaCurrentDayMedian amaCurrentDayMedian(ISeries<double> input, bool isVWTPO, bool interpolate, LizardIndicators.amaSessionTypeCDM sessionType, string sessionStartTime, string sessionEndTime, bool showBands, double bandMultiplier1, bool showBand2, double bandMultiplier2, bool showBand3, double bandMultiplier3, bool showClouds, int innerCloudOpacity, int midCloudOpacity, int outerCloudOpacity)
		{
			if (cacheamaCurrentDayMedian != null)
				for (int idx = 0; idx < cacheamaCurrentDayMedian.Length; idx++)
					if (cacheamaCurrentDayMedian[idx] != null && cacheamaCurrentDayMedian[idx].IsVWTPO == isVWTPO && cacheamaCurrentDayMedian[idx].Interpolate == interpolate && cacheamaCurrentDayMedian[idx].SessionType == sessionType && cacheamaCurrentDayMedian[idx].SessionStartTime == sessionStartTime && cacheamaCurrentDayMedian[idx].SessionEndTime == sessionEndTime && cacheamaCurrentDayMedian[idx].ShowBands == showBands && cacheamaCurrentDayMedian[idx].BandMultiplier1 == bandMultiplier1 && cacheamaCurrentDayMedian[idx].ShowBand2 == showBand2 && cacheamaCurrentDayMedian[idx].BandMultiplier2 == bandMultiplier2 && cacheamaCurrentDayMedian[idx].ShowBand3 == showBand3 && cacheamaCurrentDayMedian[idx].BandMultiplier3 == bandMultiplier3 && cacheamaCurrentDayMedian[idx].ShowClouds == showClouds && cacheamaCurrentDayMedian[idx].InnerCloudOpacity == innerCloudOpacity && cacheamaCurrentDayMedian[idx].MidCloudOpacity == midCloudOpacity && cacheamaCurrentDayMedian[idx].OuterCloudOpacity == outerCloudOpacity && cacheamaCurrentDayMedian[idx].EqualsInput(input))
						return cacheamaCurrentDayMedian[idx];
			return CacheIndicator<LizardIndicators.amaCurrentDayMedian>(new LizardIndicators.amaCurrentDayMedian(){ IsVWTPO = isVWTPO, Interpolate = interpolate, SessionType = sessionType, SessionStartTime = sessionStartTime, SessionEndTime = sessionEndTime, ShowBands = showBands, BandMultiplier1 = bandMultiplier1, ShowBand2 = showBand2, BandMultiplier2 = bandMultiplier2, ShowBand3 = showBand3, BandMultiplier3 = bandMultiplier3, ShowClouds = showClouds, InnerCloudOpacity = innerCloudOpacity, MidCloudOpacity = midCloudOpacity, OuterCloudOpacity = outerCloudOpacity }, input, ref cacheamaCurrentDayMedian);
		}
	}
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
	public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
	{
		public Indicators.LizardIndicators.amaCurrentDayMedian amaCurrentDayMedian(bool isVWTPO, bool interpolate, Indicators.LizardIndicators.amaSessionTypeCDM sessionType, string sessionStartTime, string sessionEndTime, bool showBands, double bandMultiplier1, bool showBand2, double bandMultiplier2, bool showBand3, double bandMultiplier3, bool showClouds, int innerCloudOpacity, int midCloudOpacity, int outerCloudOpacity)
		{
			return indicator.amaCurrentDayMedian(Input, isVWTPO, interpolate, sessionType, sessionStartTime, sessionEndTime, showBands, bandMultiplier1, showBand2, bandMultiplier2, showBand3, bandMultiplier3, showClouds, innerCloudOpacity, midCloudOpacity, outerCloudOpacity);
		}

		public Indicators.LizardIndicators.amaCurrentDayMedian amaCurrentDayMedian(ISeries<double> input, bool isVWTPO, bool interpolate, Indicators.LizardIndicators.amaSessionTypeCDM sessionType, string sessionStartTime, string sessionEndTime, bool showBands, double bandMultiplier1, bool showBand2, double bandMultiplier2, bool showBand3, double bandMultiplier3, bool showClouds, int innerCloudOpacity, int midCloudOpacity, int outerCloudOpacity)
		{
			return indicator.amaCurrentDayMedian(input, isVWTPO, interpolate, sessionType, sessionStartTime, sessionEndTime, showBands, bandMultiplier1, showBand2, bandMultiplier2, showBand3, bandMultiplier3, showClouds, innerCloudOpacity, midCloudOpacity, outerCloudOpacity);
		}
	}
}

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		public Indicators.LizardIndicators.amaCurrentDayMedian amaCurrentDayMedian(bool isVWTPO, bool interpolate, Indicators.LizardIndicators.amaSessionTypeCDM sessionType, string sessionStartTime, string sessionEndTime, bool showBands, double bandMultiplier1, bool showBand2, double bandMultiplier2, bool showBand3, double bandMultiplier3, bool showClouds, int innerCloudOpacity, int midCloudOpacity, int outerCloudOpacity)
		{
			return indicator.amaCurrentDayMedian(Input, isVWTPO, interpolate, sessionType, sessionStartTime, sessionEndTime, showBands, bandMultiplier1, showBand2, bandMultiplier2, showBand3, bandMultiplier3, showClouds, innerCloudOpacity, midCloudOpacity, outerCloudOpacity);
		}

		public Indicators.LizardIndicators.amaCurrentDayMedian amaCurrentDayMedian(ISeries<double> input, bool isVWTPO, bool interpolate, Indicators.LizardIndicators.amaSessionTypeCDM sessionType, string sessionStartTime, string sessionEndTime, bool showBands, double bandMultiplier1, bool showBand2, double bandMultiplier2, bool showBand3, double bandMultiplier3, bool showClouds, int innerCloudOpacity, int midCloudOpacity, int outerCloudOpacity)
		{
			return indicator.amaCurrentDayMedian(input, isVWTPO, interpolate, sessionType, sessionStartTime, sessionEndTime, showBands, bandMultiplier1, showBand2, bandMultiplier2, showBand3, bandMultiplier3, showClouds, innerCloudOpacity, midCloudOpacity, outerCloudOpacity);
		}
	}
}

#endregion
