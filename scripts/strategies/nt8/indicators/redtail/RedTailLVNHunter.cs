using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Core.FloatingPoint;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;

// Define enum in the global namespace for RedTail LVN Hunter
public enum LookbackModeRTLVN
{
	FixedBars,
	Session
}

namespace NinjaTrader.NinjaScript.Indicators
{
	public class RedTailLVNHunter : Indicator
	{
		#region Variables
		private ProfileData profile;
		#endregion
		
		#region ProfileData Class
		public class ProfileData
		{
			public List<double> BarHighs { get; set; }
			public List<double> BarLows { get; set; }
			public List<double> BarVolumes { get; set; }
			public List<bool> BarPolarities { get; set; }
			public double[] TotalVolume { get; set; }
			public List<VolumeNode> VolumeNodes { get; set; }
			public double ProfileHigh { get; set; }
			public double ProfileLow { get; set; }
			public double PriceStep { get; set; }
			
			public ProfileData(int numRows)
			{
				BarHighs = new List<double>(5000); // Pre-allocate capacity
				BarLows = new List<double>(5000);
				BarVolumes = new List<double>(5000);
				BarPolarities = new List<bool>(5000);
				TotalVolume = new double[numRows];
				VolumeNodes = new List<VolumeNode>(numRows);
			}
		}
		#endregion
		
		#region Volume Node Class
		public class VolumeNode
		{
			public double PriceLevel { get; set; }
			public double TotalVolume { get; set; }
			public bool IsTrough { get; set; }
			public int RowIndex { get; set; }
		}
		#endregion
		
		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description = @"RedTail LVN Hunter - Identifies Low Volume Nodes (LVNs) with infinite horizontal extension. These low-volume areas represent potential breakout zones and key support/resistance levels.";
				Name = "RedTailLVNHunter";
				Calculate = Calculate.OnBarClose;
				IsOverlay = true;
				DisplayInDataBox = true;
				DrawOnPricePanel = true;
				DrawHorizontalGridLines = true;
				DrawVerticalGridLines = true;
				PaintPriceMarkers = true;
				ScaleJustification = NinjaTrader.Gui.Chart.ScaleJustification.Right;
				IsSuspendedWhileInactive = true;
				
				// Lookback Settings
				LookbackModeRTLVN = LookbackModeRTLVN.FixedBars;
				ProfileLookbackLength = 500;
				ProfileNumberOfRows = 100;
				
				// LVN Settings
				LVNFillColor = Brushes.Gray;
				LVNFillOpacity = 40;
				LVNBorderColor = Brushes.DarkGray;
				LVNBorderOpacity = 100;
				LVNDetectionPercent = 5;
				ShowAdjacentLVNNodes = true;
			}
			else if (State == State.Configure)
			{
				profile = new ProfileData(ProfileNumberOfRows);
			}
			else if (State == State.DataLoaded)
			{
				ClearRender();
			}
		}
		
		protected override void OnBarUpdate()
		{
			if (CurrentBar < 20)
				return;
			
			// Handle lookback mode
			if (LookbackModeRTLVN == LookbackModeRTLVN.FixedBars)
			{
				if (CurrentBar < ProfileLookbackLength)
					return;
				
				if (CurrentBar == ProfileLookbackLength)
				{
					// Initialize with last ProfileLookbackLength bars
					for (int i = ProfileLookbackLength - 1; i >= 0; i--)
					{
						profile.BarHighs.Add(High[i]);
						profile.BarLows.Add(Low[i]);
						profile.BarVolumes.Add(Volume[i]);
						profile.BarPolarities.Add(Close[i] >= Open[i]);
					}
					
					if (profile.BarHighs.Count > 0)
					{
						profile.ProfileHigh = profile.BarHighs.Max();
						profile.ProfileLow = profile.BarLows.Min();
					}
				}
				else
				{
					// Add current bar
					profile.BarHighs.Add(High[0]);
					profile.BarLows.Add(Low[0]);
					profile.BarVolumes.Add(Volume[0]);
					profile.BarPolarities.Add(Close[0] >= Open[0]);
					
					// Remove oldest if exceeds
					if (profile.BarHighs.Count > ProfileLookbackLength)
					{
						profile.BarHighs.RemoveAt(0);
						profile.BarLows.RemoveAt(0);
						profile.BarVolumes.RemoveAt(0);
						profile.BarPolarities.RemoveAt(0);
					}
					
					// Update high and low
					if (profile.BarHighs.Count > 0)
					{
						profile.ProfileHigh = profile.BarHighs.Max();
						profile.ProfileLow = profile.BarLows.Min();
					}
				}
			}
			else // LookbackModeRTLVN.Session
			{
				if (CurrentBar == 0 || Bars.IsFirstBarOfSession)
				{
					profile.BarHighs.Clear();
					profile.BarLows.Clear();
					profile.BarVolumes.Clear();
					profile.BarPolarities.Clear();
					
					profile.BarHighs.Add(High[0]);
					profile.BarLows.Add(Low[0]);
					profile.BarVolumes.Add(Volume[0]);
					profile.BarPolarities.Add(Close[0] >= Open[0]);
					
					profile.ProfileHigh = High[0];
					profile.ProfileLow = Low[0];
				}
				else
				{
					profile.BarHighs.Add(High[0]);
					profile.BarLows.Add(Low[0]);
					profile.BarVolumes.Add(Volume[0]);
					profile.BarPolarities.Add(Close[0] >= Open[0]);
					
					profile.ProfileHigh = Math.Max(profile.ProfileHigh, High[0]);
					profile.ProfileLow = Math.Min(profile.ProfileLow, Low[0]);
				}
			}
			
			// Only calculate and draw when we're in real-time or on the last historical bar
			// This dramatically speeds up loading
			if (State == State.Realtime || CurrentBar >= Count - 2)
			{
				CalculateVolumeProfile();
				DrawLVNRectangles();
			}
		}
		
		private void CalculateVolumeProfile()
		{
			// Fast clear without reallocation
			Array.Clear(profile.TotalVolume, 0, profile.TotalVolume.Length);
			profile.VolumeNodes.Clear();
			
			profile.PriceStep = (profile.ProfileHigh - profile.ProfileLow) / ProfileNumberOfRows;
			
			if (profile.PriceStep <= 0 || double.IsNaN(profile.PriceStep) || double.IsInfinity(profile.PriceStep))
				return;
			
			// Pre-calculate inverse for division optimization
			double invPriceStep = 1.0 / profile.PriceStep;
			
			// Distribute volume across price levels
			for (int i = 0; i < profile.BarHighs.Count; i++)
			{
				double barHigh = profile.BarHighs[i];
				double barLow = profile.BarLows[i];
				double barVolume = profile.BarVolumes[i];
				
				double barRange = barHigh - barLow;
				if (barRange <= 0) continue;
				
				double invBarRange = 1.0 / barRange;
				
				int startSlot = Math.Max((int)Math.Floor((barLow - profile.ProfileLow) * invPriceStep), 0);
				int endSlot = Math.Min((int)Math.Floor((barHigh - profile.ProfileLow) * invPriceStep), ProfileNumberOfRows - 1);
				
				for (int slot = startSlot; slot <= endSlot; slot++)
				{
					double slotLow = profile.ProfileLow + slot * profile.PriceStep;
					double slotHigh = slotLow + profile.PriceStep;
					
					double volumeProportion;
					if (barLow >= slotLow && barHigh <= slotHigh)
						volumeProportion = 1.0;
					else if (barLow >= slotLow && barHigh > slotHigh)
						volumeProportion = (slotHigh - barLow) * invBarRange;
					else if (barLow < slotLow && barHigh <= slotHigh)
						volumeProportion = (barHigh - slotLow) * invBarRange;
					else
						volumeProportion = profile.PriceStep * invBarRange;
					
					double allocatedVolume = barVolume * volumeProportion;
					profile.TotalVolume[slot] += allocatedVolume;
				}
			}
			
			// Create volume nodes
			for (int i = 0; i < ProfileNumberOfRows; i++)
			{
				VolumeNode node = new VolumeNode
				{
					PriceLevel = profile.ProfileLow + (i + 0.5) * profile.PriceStep,
					TotalVolume = profile.TotalVolume[i],
					RowIndex = i
				};
				profile.VolumeNodes.Add(node);
			}
			
			// Detect LVNs
			DetectVolumeLVN();
		}
		
		private void DetectVolumeLVN()
		{
			int lvnNodes = (int)(ProfileNumberOfRows * (LVNDetectionPercent / 100.0));
			
			for (int i = lvnNodes; i < ProfileNumberOfRows - lvnNodes; i++)
			{
				// Skip completely empty rows
				if (profile.TotalVolume[i] <= 0)
					continue;
				
				bool isLVN = true;
				
				// Check left side - all values should be GREATER than current (current is a local minimum)
				for (int j = i - lvnNodes; j < i; j++)
				{
					if (profile.TotalVolume[j] <= profile.TotalVolume[i])
					{
						isLVN = false;
						break;
					}
				}
				
				// Check right side - all values should be GREATER than current (current is a local minimum)
				if (isLVN)
				{
					for (int j = i + 1; j <= i + lvnNodes && j < ProfileNumberOfRows; j++)
					{
						if (profile.TotalVolume[j] <= profile.TotalVolume[i])
						{
							isLVN = false;
							break;
						}
					}
				}
				
				if (isLVN)
					profile.VolumeNodes[i].IsTrough = true;
			}
		}
		
		private void DrawLVNRectangles()
		{
			ClearRender();
			
			// Get the leftmost and rightmost bar indices for infinite extension
			int leftmostBar = CurrentBar;  // Leftmost visible bar
			int rightmostBar = 0;  // Rightmost (current bar)
			
			// Draw LVN rectangles with infinite extension
			for (int i = 0; i < profile.VolumeNodes.Count; i++)
			{
				VolumeNode node = profile.VolumeNodes[i];
				if (node.IsTrough)
				{
					// Calculate the combined rectangle bounds if adjacent nodes are shown
					double levelTop, levelBottom;
					
					if (ShowAdjacentLVNNodes)
					{
						// Find the highest and lowest adjacent nodes
						int topIndex = Math.Min(i + 1, profile.VolumeNodes.Count - 1);
						int bottomIndex = Math.Max(i - 1, 0);
						
						VolumeNode topNode = profile.VolumeNodes[topIndex];
						VolumeNode bottomNode = profile.VolumeNodes[bottomIndex];
						
						// Calculate combined bounds
						levelTop = topNode.PriceLevel + profile.PriceStep * 0.4;
						levelBottom = bottomNode.PriceLevel - profile.PriceStep * 0.4;
					}
					else
					{
						// Just the main trough
						levelTop = node.PriceLevel + profile.PriceStep * 0.4;
						levelBottom = node.PriceLevel - profile.PriceStep * 0.4;
					}
					
					// Create opacity-adjusted border brush
					Brush borderBrush = LVNBorderColor.Clone();
					if (borderBrush is SolidColorBrush solidBorder)
					{
						Color borderColor = solidBorder.Color;
						byte borderAlpha = (byte)(255 * (LVNBorderOpacity / 100.0));
						borderBrush = new SolidColorBrush(Color.FromArgb(borderAlpha, borderColor.R, borderColor.G, borderColor.B));
					}
					
					// Draw rectangle extending infinitely left and right
					Draw.Rectangle(this, $"LVN{i}", false,
						leftmostBar, levelBottom,
						rightmostBar, levelTop,
						borderBrush, LVNFillColor, LVNFillOpacity);
				}
			}
		}
		
		private void ClearRender()
		{
			RemoveDrawObjects();
		}
		
		#region Properties
		
		[NinjaScriptProperty]
		[Display(Name = "Lookback Mode", Description = "Use fixed bars or session-based lookback", Order = 1, GroupName = "Settings")]
		public LookbackModeRTLVN LookbackModeRTLVN { get; set; }
		
		[NinjaScriptProperty]
		[Range(50, 5000)]
		[Display(Name = "Profile Lookback Length", Description = "Number of bars to analyze (when using Fixed Bars mode)", Order = 2, GroupName = "Settings")]
		public int ProfileLookbackLength { get; set; }
		
		[NinjaScriptProperty]
		[Range(20, 500)]
		[Display(Name = "Profile Number of Rows", Description = "Granularity of volume analysis. More rows = finer/noisier LVNs (e.g., 200). Fewer rows = broader/smoother zones (e.g., 50). Default 100 works well for most instruments.", Order = 3, GroupName = "Settings")]
		public int ProfileNumberOfRows { get; set; }
		
		// ============================================
		// LOW VOLUME NODES (LVN)
		// ============================================
		
		[XmlIgnore]
		[Display(Name = "LVN Fill Color", Description = "Fill color for LVN rectangles", Order = 1, GroupName = "LVN Display")]
		public Brush LVNFillColor { get; set; }
		
		[Browsable(false)]
		public string LVNFillColorSerializable
		{
			get { return Serialize.BrushToString(LVNFillColor); }
			set { LVNFillColor = Serialize.StringToBrush(value); }
		}
		
		[NinjaScriptProperty]
		[Range(0, 100)]
		[Display(Name = "LVN Fill Opacity %", Description = "Opacity of LVN fill color (0=transparent, 100=solid)", Order = 2, GroupName = "LVN Display")]
		public int LVNFillOpacity { get; set; }
		
		[XmlIgnore]
		[Display(Name = "LVN Border Color", Description = "Border color for LVN rectangles", Order = 3, GroupName = "LVN Display")]
		public Brush LVNBorderColor { get; set; }
		
		[Browsable(false)]
		public string LVNBorderColorSerializable
		{
			get { return Serialize.BrushToString(LVNBorderColor); }
			set { LVNBorderColor = Serialize.StringToBrush(value); }
		}
		
		[NinjaScriptProperty]
		[Range(0, 100)]
		[Display(Name = "LVN Border Opacity %", Description = "Opacity of LVN border (0=transparent, 100=solid)", Order = 4, GroupName = "LVN Display")]
		public int LVNBorderOpacity { get; set; }
		
		[NinjaScriptProperty]
		[Range(1, 50)]
		[Display(Name = "LVN Detection %", Description = "Percentage of rows used for LVN detection (lower = more sensitive)", Order = 1, GroupName = "LVN Detection")]
		public int LVNDetectionPercent { get; set; }
		
		[NinjaScriptProperty]
		[Display(Name = "Show Adjacent LVN Nodes", Description = "Include nodes above and below each LVN (creates wider zones)", Order = 2, GroupName = "LVN Detection")]
		public bool ShowAdjacentLVNNodes { get; set; }
		
		#endregion
	}
}

#region NinjaScript generated code. Neither change nor remove.

namespace NinjaTrader.NinjaScript.Indicators
{
	public partial class Indicator : NinjaTrader.Gui.NinjaScript.IndicatorRenderBase
	{
		private RedTailLVNHunter[] cacheRedTailLVNHunter;
		public RedTailLVNHunter RedTailLVNHunter(LookbackModeRTLVN lookbackModeRTLVN, int profileLookbackLength, int profileNumberOfRows, int lVNFillOpacity, int lVNBorderOpacity, int lVNDetectionPercent, bool showAdjacentLVNNodes)
		{
			return RedTailLVNHunter(Input, lookbackModeRTLVN, profileLookbackLength, profileNumberOfRows, lVNFillOpacity, lVNBorderOpacity, lVNDetectionPercent, showAdjacentLVNNodes);
		}

		public RedTailLVNHunter RedTailLVNHunter(ISeries<double> input, LookbackModeRTLVN lookbackModeRTLVN, int profileLookbackLength, int profileNumberOfRows, int lVNFillOpacity, int lVNBorderOpacity, int lVNDetectionPercent, bool showAdjacentLVNNodes)
		{
			if (cacheRedTailLVNHunter != null)
				for (int idx = 0; idx < cacheRedTailLVNHunter.Length; idx++)
					if (cacheRedTailLVNHunter[idx] != null && cacheRedTailLVNHunter[idx].LookbackModeRTLVN == lookbackModeRTLVN && cacheRedTailLVNHunter[idx].ProfileLookbackLength == profileLookbackLength && cacheRedTailLVNHunter[idx].ProfileNumberOfRows == profileNumberOfRows && cacheRedTailLVNHunter[idx].LVNFillOpacity == lVNFillOpacity && cacheRedTailLVNHunter[idx].LVNBorderOpacity == lVNBorderOpacity && cacheRedTailLVNHunter[idx].LVNDetectionPercent == lVNDetectionPercent && cacheRedTailLVNHunter[idx].ShowAdjacentLVNNodes == showAdjacentLVNNodes && cacheRedTailLVNHunter[idx].EqualsInput(input))
						return cacheRedTailLVNHunter[idx];
			return CacheIndicator<RedTailLVNHunter>(new RedTailLVNHunter(){ LookbackModeRTLVN = lookbackModeRTLVN, ProfileLookbackLength = profileLookbackLength, ProfileNumberOfRows = profileNumberOfRows, LVNFillOpacity = lVNFillOpacity, LVNBorderOpacity = lVNBorderOpacity, LVNDetectionPercent = lVNDetectionPercent, ShowAdjacentLVNNodes = showAdjacentLVNNodes }, input, ref cacheRedTailLVNHunter);
		}
	}
}

namespace NinjaTrader.NinjaScript.MarketAnalyzerColumns
{
	public partial class MarketAnalyzerColumn : MarketAnalyzerColumnBase
	{
		public Indicators.RedTailLVNHunter RedTailLVNHunter(LookbackModeRTLVN lookbackModeRTLVN, int profileLookbackLength, int profileNumberOfRows, int lVNFillOpacity, int lVNBorderOpacity, int lVNDetectionPercent, bool showAdjacentLVNNodes)
		{
			return indicator.RedTailLVNHunter(Input, lookbackModeRTLVN, profileLookbackLength, profileNumberOfRows, lVNFillOpacity, lVNBorderOpacity, lVNDetectionPercent, showAdjacentLVNNodes);
		}

		public Indicators.RedTailLVNHunter RedTailLVNHunter(ISeries<double> input , LookbackModeRTLVN lookbackModeRTLVN, int profileLookbackLength, int profileNumberOfRows, int lVNFillOpacity, int lVNBorderOpacity, int lVNDetectionPercent, bool showAdjacentLVNNodes)
		{
			return indicator.RedTailLVNHunter(input, lookbackModeRTLVN, profileLookbackLength, profileNumberOfRows, lVNFillOpacity, lVNBorderOpacity, lVNDetectionPercent, showAdjacentLVNNodes);
		}
	}
}

namespace NinjaTrader.NinjaScript.Strategies
{
	public partial class Strategy : NinjaTrader.Gui.NinjaScript.StrategyRenderBase
	{
		public Indicators.RedTailLVNHunter RedTailLVNHunter(LookbackModeRTLVN lookbackModeRTLVN, int profileLookbackLength, int profileNumberOfRows, int lVNFillOpacity, int lVNBorderOpacity, int lVNDetectionPercent, bool showAdjacentLVNNodes)
		{
			return indicator.RedTailLVNHunter(Input, lookbackModeRTLVN, profileLookbackLength, profileNumberOfRows, lVNFillOpacity, lVNBorderOpacity, lVNDetectionPercent, showAdjacentLVNNodes);
		}

		public Indicators.RedTailLVNHunter RedTailLVNHunter(ISeries<double> input , LookbackModeRTLVN lookbackModeRTLVN, int profileLookbackLength, int profileNumberOfRows, int lVNFillOpacity, int lVNBorderOpacity, int lVNDetectionPercent, bool showAdjacentLVNNodes)
		{
			return indicator.RedTailLVNHunter(input, lookbackModeRTLVN, profileLookbackLength, profileNumberOfRows, lVNFillOpacity, lVNBorderOpacity, lVNDetectionPercent, showAdjacentLVNNodes);
		}
	}
}

#endregion
