#region Using declarations
using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.ComponentModel.DataAnnotations;
using System.Linq;
using System.Windows;
using System.Windows.Media;
using System.Xml.Serialization;
using NinjaTrader.Cbi;
using NinjaTrader.Core;
using NinjaTrader.Data;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Chart;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.DrawingTools;
using SharpDX;
using SharpDX.Direct2D1;
using SharpDX.DirectWrite;
#endregion

namespace NinjaTrader.NinjaScript.Indicators
{
	/// <summary>
	/// Session Opening Bar Range - Plots the first bar's high/low/mid of a selected session
	/// with optional statistical levels, range extensions, and OR rotation levels.
	/// 
	/// Original Pine Script by @notprofessorgreen
	/// NinjaTrader 8 conversion by @_hawkeye_13 (RedTail Indicators)
	/// </summary>
	public class SessionOpeningBarRange : Indicator
	{
		#region Private Classes
		
		private class SessionData
		{
			public double ORHigh;
			public double ORLow;
			public double ORMid;
			public bool   IsBullish;
			public bool   IsValid;
			public int    StartBarIndex;		// bar where OR was captured
			public int    SessionEndBarIndex;	// bar at session close (e.g. 4pm)
			public bool   SessionEnded;			// true once session time has passed
			
			// Statistical levels
			public double Stat1Up, Stat1Dn, Stat2Up, Stat2Dn;
			
			// Range extension increment
			public double RangeIncrement;
			
			// Rotation levels (5 up, 5 down)
			public double[] RotUp = new double[5];
			public double[] RotDn = new double[5];
		}
		
		#endregion
		
		#region Private Variables
		
		private SessionData currentSession;
		private List<SessionData> historicalSessions = new List<SessionData>();
		private List<double> rangeHistory = new List<double>();
		
		private int sessionStartMinutes, sessionEndMinutes;
		private bool sessionSpansMidnight;
		private TimeZoneInfo sessionTZ;
		
		private bool orCapturedThisSession;
		private DateTime lastSessionDate = DateTime.MinValue;
		
		// SharpDX
		private SharpDX.Direct2D1.SolidColorBrush dxBullishBrush, dxBearishBrush;
		private SharpDX.Direct2D1.SolidColorBrush dxBullishFillBrush, dxBearishFillBrush;
		private SharpDX.Direct2D1.SolidColorBrush dxStatsLineBrush, dxStatsLabelBrush;
		private SharpDX.Direct2D1.SolidColorBrush dxRangeLineBrush, dxRangeLabelBrush;
		private SharpDX.Direct2D1.SolidColorBrush dxRotationLineBrush, dxRotationLabelBrush;
		private SharpDX.Direct2D1.StrokeStyle strokeSolid, strokeDash, strokeDot;
		private SharpDX.DirectWrite.TextFormat textFormatNormal, textFormatSmall, textFormatTiny, textFormatLarge;
		private bool resourcesCreated;
		
		#endregion
		
		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description = @"Session Opening Bar Range. Original Pine Script by @notprofgreen. NinjaTrader 8 conversion by @_hawkeye_13 (RedTail Indicators).";
				Name = "SessionOpeningBarRange";
				Calculate = Calculate.OnBarClose;
				IsOverlay = true;
				DisplayInDataBox = false;
				DrawOnPricePanel = true;
				IsSuspendedWhileInactive = true;
				
				SessionChoice = SessionOption.NewYorkRTH;
				CustomSessionStart = "0930"; CustomSessionEnd = "1600";
				SessionTimezone = "America/New_York";
				OBRTimeframe = 5;
				ShowMidLine = true; ShowHistorical = true;
				MaxHistory = 20; ProjectionOffset = 50;
				ShowLabels = true; ShowPrices = false;
				LabelPosition = LabelPositionOption.Left;
				RangeLineStyle = DashStyleHelper.Solid; RangeLineWidth = 1;
				MidLineStyle = DashStyleHelper.Dash; MidLineWidth = 1;
				BullishColor = Brushes.Lime; BearishColor = Brushes.Magenta;
				BullishFillOpacity = 85; BearishFillOpacity = 85;
				LookbackPeriods = 60;
				ShowStatLevels = false; ShowStatLabels = false;
				StdDevMult1 = 1.0; StdDevMult2 = 2.0;
				StatsLineColor = Brushes.Purple; StatsLineWidth = 1;
				StatsLabelColor = Brushes.Purple; StatsLabelSize = TextSizeOption.Normal;
				ShowRangeExtensions = false; RangeMultiplier = 1.0;
				NumExtensionLevels = 5; ShowRangeExtLabels = false;
				RangeExtLineColor = Brushes.Teal; RangeExtLineWidth = 1;
				RangeExtLabelColor = Brushes.Teal; RangeExtLabelSize = TextSizeOption.Normal;
				ShowRotations = true; RotationIncrement = 65.0;
				ShowRotationLabels = true;
				RotationLineColor = Brushes.Gray; RotationLineStyle = DashStyleHelper.Dot;
				RotationLineWidth = 1; RotationLabelColor = Brushes.Gray;
				RotationLabelSize = TextSizeOption.Small;
			}
			else if (State == State.Configure)
			{
				AddDataSeries(BarsPeriodType.Minute, OBRTimeframe);
				ParseSessionTimes();
			}
			else if (State == State.DataLoaded)
			{
				currentSession = null;
				historicalSessions.Clear();
				rangeHistory.Clear();
				orCapturedThisSession = false;
				lastSessionDate = DateTime.MinValue;
			}
			else if (State == State.Terminated)
			{
				DisposeResources();
			}
		}
		
		#region Session Time Parsing
		
		private void ParseSessionTimes()
		{
			string startStr, endStr;
			switch (SessionChoice)
			{
				case SessionOption.NewYorkRTH:       startStr = "0930"; endStr = "1600"; break;
				case SessionOption.NewYorkFutures:    startStr = "0800"; endStr = "1700"; break;
				case SessionOption.London:            startStr = "0200"; endStr = "0800"; break;
				case SessionOption.Asia:              startStr = "1900"; endStr = "0200"; break;
				case SessionOption.MidnightTo5pm:     startStr = "0000"; endStr = "1700"; break;
				case SessionOption.ZBGoldSilverOR:    startStr = "0820"; endStr = "1600"; break;
				case SessionOption.CLOR:              startStr = "0900"; endStr = "1600"; break;
				case SessionOption.Custom:            startStr = CustomSessionStart; endStr = CustomSessionEnd; break;
				default:                              startStr = "0930"; endStr = "1600"; break;
			}
			sessionStartMinutes = int.Parse(startStr.Substring(0, 2)) * 60 + int.Parse(startStr.Substring(2, 2));
			sessionEndMinutes   = int.Parse(endStr.Substring(0, 2)) * 60 + int.Parse(endStr.Substring(2, 2));
			sessionSpansMidnight = sessionEndMinutes <= sessionStartMinutes;
			
			try
			{
				string tzId = SessionTimezone;
				if (tzId == "America/New_York")     tzId = "Eastern Standard Time";
				else if (tzId == "America/Chicago")  tzId = "Central Standard Time";
				else if (tzId == "Europe/London")    tzId = "GMT Standard Time";
				else if (tzId == "Asia/Tokyo")       tzId = "Tokyo Standard Time";
				else if (tzId == "US/Eastern")       tzId = "Eastern Standard Time";
				else if (tzId == "US/Central")       tzId = "Central Standard Time";
				sessionTZ = TimeZoneInfo.FindSystemTimeZoneById(tzId);
			}
			catch { sessionTZ = TimeZoneInfo.FindSystemTimeZoneById("Eastern Standard Time"); }
		}
		
		private int MinutesOfDay(DateTime dt) { return dt.Hour * 60 + dt.Minute; }
		
		private bool IsInSession(DateTime barTime)
		{
			int mins = MinutesOfDay(barTime);
			return sessionSpansMidnight
				? (mins >= sessionStartMinutes || mins < sessionEndMinutes)
				: (mins >= sessionStartMinutes && mins < sessionEndMinutes);
		}
		
		private DateTime GetSessionDate(DateTime barTime)
		{
			int mins = MinutesOfDay(barTime);
			if (sessionSpansMidnight && mins < sessionEndMinutes)
				return barTime.Date.AddDays(-1);
			return barTime.Date;
		}
		
		#endregion
		
		protected override void OnBarUpdate()
		{
			// ── Secondary (OR timeframe) series ──
			if (BarsInProgress == 1)
			{
				int tfMins = MinutesOfDay(Time[0]);
				int orCloseMinute = sessionStartMinutes + OBRTimeframe;
				
				bool isORBar = sessionSpansMidnight && orCloseMinute >= 1440
					? tfMins == (orCloseMinute % 1440)
					: tfMins == orCloseMinute;
				
				if (!isORBar) return;
				
				DateTime sessionDate = GetSessionDate(Time[0]);
				if (sessionDate == lastSessionDate && orCapturedThisSession) return;
				
				double orHigh = High[0], orLow = Low[0], orOpen = Open[0], orClose = Close[0];
				double range = orHigh - orLow;
				if (range <= 0) return;
				
				// Archive current → historical
				if (currentSession != null && currentSession.IsValid)
				{
					currentSession.SessionEnded = true;
					historicalSessions.Add(currentSession);
					if (historicalSessions.Count > MaxHistory)
						historicalSessions.RemoveAt(0);
				}
				
				lastSessionDate = sessionDate;
				orCapturedThisSession = true;
				
				rangeHistory.Add(range);
				if (rangeHistory.Count > LookbackPeriods)
					rangeHistory.RemoveAt(0);
				
				int pIdx = CurrentBars[0];
				
				currentSession = new SessionData
				{
					ORHigh = orHigh, ORLow = orLow, ORMid = (orHigh + orLow) / 2.0,
					IsBullish = orClose >= orOpen, IsValid = true,
					StartBarIndex = pIdx, SessionEndBarIndex = pIdx, SessionEnded = false,
					RangeIncrement = range * RangeMultiplier
				};
				
				if (rangeHistory.Count > 1)
				{
					double avg = rangeHistory.Average();
					double sd  = Math.Sqrt(rangeHistory.Select(r => Math.Pow(r - avg, 2)).Average());
					currentSession.Stat1Up = orHigh + avg + sd * StdDevMult1;
					currentSession.Stat1Dn = orLow  - (avg + sd * StdDevMult1);
					currentSession.Stat2Up = orHigh + avg + sd * StdDevMult2;
					currentSession.Stat2Dn = orLow  - (avg + sd * StdDevMult2);
				}
				
				for (int i = 0; i < 5; i++)
				{
					currentSession.RotUp[i] = orHigh + RotationIncrement * (i + 1);
					currentSession.RotDn[i] = orLow  - RotationIncrement * (i + 1);
				}
				return;
			}
			
			// ── Primary series ──
			if (BarsInProgress != 0 || CurrentBar < 1 || currentSession == null || !currentSession.IsValid)
				return;
			
			// Track session end: once we see a bar PAST session end, lock SessionEndBarIndex
			if (!currentSession.SessionEnded)
			{
				if (IsInSession(Time[0]))
				{
					// Still in session — update the end bar
					currentSession.SessionEndBarIndex = CurrentBar;
				}
				else if (currentSession.SessionEndBarIndex > currentSession.StartBarIndex)
				{
					currentSession.SessionEnded = true;
				}
			}
		}
		
		#region SharpDX Rendering
		
		private void CreateResources(RenderTarget rt)
		{
			if (resourcesCreated || rt == null) return;
			
			dxBullishBrush     = BrushFromWpf(rt, BullishColor, (byte)255);
			dxBearishBrush     = BrushFromWpf(rt, BearishColor, (byte)255);
			dxBullishFillBrush = BrushFromWpf(rt, BullishColor, (byte)(255 * BullishFillOpacity / 100));
			dxBearishFillBrush = BrushFromWpf(rt, BearishColor, (byte)(255 * BearishFillOpacity / 100));
			dxStatsLineBrush   = BrushFromWpf(rt, StatsLineColor, (byte)255);
			dxStatsLabelBrush  = BrushFromWpf(rt, StatsLabelColor, (byte)255);
			dxRangeLineBrush   = BrushFromWpf(rt, RangeExtLineColor, (byte)255);
			dxRangeLabelBrush  = BrushFromWpf(rt, RangeExtLabelColor, (byte)255);
			dxRotationLineBrush  = BrushFromWpf(rt, RotationLineColor, (byte)255);
			dxRotationLabelBrush = BrushFromWpf(rt, RotationLabelColor, (byte)255);
			
			var dw = Core.Globals.DirectWriteFactory;
			textFormatTiny   = new SharpDX.DirectWrite.TextFormat(dw, "Arial", SharpDX.DirectWrite.FontWeight.Normal, SharpDX.DirectWrite.FontStyle.Normal, 9f);
			textFormatSmall  = new SharpDX.DirectWrite.TextFormat(dw, "Arial", SharpDX.DirectWrite.FontWeight.Normal, SharpDX.DirectWrite.FontStyle.Normal, 11f);
			textFormatNormal = new SharpDX.DirectWrite.TextFormat(dw, "Arial", SharpDX.DirectWrite.FontWeight.Normal, SharpDX.DirectWrite.FontStyle.Normal, 13f);
			textFormatLarge  = new SharpDX.DirectWrite.TextFormat(dw, "Arial", SharpDX.DirectWrite.FontWeight.Normal, SharpDX.DirectWrite.FontStyle.Normal, 16f);
			
			strokeSolid = new SharpDX.Direct2D1.StrokeStyle(Core.Globals.D2DFactory, new StrokeStyleProperties { DashStyle = SharpDX.Direct2D1.DashStyle.Solid });
			strokeDash  = new SharpDX.Direct2D1.StrokeStyle(Core.Globals.D2DFactory, new StrokeStyleProperties { DashStyle = SharpDX.Direct2D1.DashStyle.Dash });
			// DashStyle.Dot is invisible at width 1 in SharpDX. Use a custom dash pattern instead: 2px on, 4px off
			strokeDot   = new SharpDX.Direct2D1.StrokeStyle(Core.Globals.D2DFactory, new StrokeStyleProperties { DashStyle = SharpDX.Direct2D1.DashStyle.Custom }, new float[] { 2f, 4f });
			
			resourcesCreated = true;
		}
		
		private SharpDX.Direct2D1.SolidColorBrush BrushFromWpf(RenderTarget rt, System.Windows.Media.Brush wpf, byte alpha)
		{
			if (wpf is System.Windows.Media.SolidColorBrush scb)
				return new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color(scb.Color.R, scb.Color.G, scb.Color.B, alpha));
			return new SharpDX.Direct2D1.SolidColorBrush(rt, new SharpDX.Color((byte)128, (byte)128, (byte)128, alpha));
		}
		
		private void DisposeResources()
		{
			void D(ref SharpDX.Direct2D1.SolidColorBrush b) { if (b != null) { b.Dispose(); b = null; } }
			void DS(ref SharpDX.Direct2D1.StrokeStyle s) { if (s != null) { s.Dispose(); s = null; } }
			void DT(ref SharpDX.DirectWrite.TextFormat t) { if (t != null) { t.Dispose(); t = null; } }
			
			D(ref dxBullishBrush); D(ref dxBearishBrush);
			D(ref dxBullishFillBrush); D(ref dxBearishFillBrush);
			D(ref dxStatsLineBrush); D(ref dxStatsLabelBrush);
			D(ref dxRangeLineBrush); D(ref dxRangeLabelBrush);
			D(ref dxRotationLineBrush); D(ref dxRotationLabelBrush);
			DS(ref strokeSolid); DS(ref strokeDash); DS(ref strokeDot);
			DT(ref textFormatTiny); DT(ref textFormatSmall); DT(ref textFormatNormal); DT(ref textFormatLarge);
			
			resourcesCreated = false;
		}
		
		public override void OnRenderTargetChanged() { DisposeResources(); }
		
		private SharpDX.DirectWrite.TextFormat GetTF(TextSizeOption s)
		{
			switch (s) { case TextSizeOption.Tiny: return textFormatTiny; case TextSizeOption.Small: return textFormatSmall; case TextSizeOption.Large: return textFormatLarge; default: return textFormatNormal; }
		}
		
		private SharpDX.Direct2D1.StrokeStyle GetSS(DashStyleHelper s)
		{
			switch (s) { case DashStyleHelper.Dash: return strokeDash; case DashStyleHelper.Dot: return strokeDot; default: return strokeSolid; }
		}
		
		protected override void OnRender(ChartControl cc, ChartScale cs)
		{
			base.OnRender(cc, cs);
			if (cc == null || cs == null || RenderTarget == null || ChartBars == null) return;
			CreateResources(RenderTarget);
			if (!resourcesCreated) return;
			
			if (ShowHistorical)
				foreach (var s in historicalSessions)
					RenderSession(cc, cs, s, false);
			
			if (currentSession != null && currentSession.IsValid)
				RenderSession(cc, cs, currentSession, true);
		}
		
		private void RenderSession(ChartControl cc, ChartScale cs, SessionData s, bool isCurrent)
		{
			if (s == null || !s.IsValid) return;
			
			int visFrom = ChartBars.FromIndex;
			int visTo   = ChartBars.ToIndex;
			
			// ── X coordinate logic ──
			// Historical: draw from StartBar to SessionEndBar (the 4pm bar)
			// Current: draw from StartBar to current bar + projection
			float xStart, xEnd;
			
			if (isCurrent)
			{
				// Current session: start at OR bar, extend to latest bar + projection
				int startIdx = Math.Max(s.StartBarIndex, visFrom);
				int endIdx   = s.SessionEndBarIndex + ProjectionOffset;
				
				if (startIdx > visTo) return;
				
				xStart = cc.GetXByBarIndex(ChartBars, Math.Min(startIdx, visTo));
				
				if (endIdx <= visTo)
					xEnd = cc.GetXByBarIndex(ChartBars, endIdx);
				else
					xEnd = cc.GetXByBarIndex(ChartBars, visTo) + (endIdx - visTo) * (float)cc.Properties.BarDistance;
			}
			else
			{
				// Historical session: draw from StartBar to SessionEndBar
				// But clamp to visible range
				int startIdx = s.StartBarIndex;
				int endIdx   = s.SessionEndBarIndex;
				
				// If completely off-screen, skip
				if (endIdx < visFrom || startIdx > visTo) return;
				
				// Clamp to visible
				startIdx = Math.Max(startIdx, visFrom);
				endIdx   = Math.Min(endIdx, visTo);
				
				xStart = cc.GetXByBarIndex(ChartBars, startIdx);
				xEnd   = cc.GetXByBarIndex(ChartBars, endIdx);
			}
			
			if (xEnd <= xStart + 1) return;
			
			// Y coordinates
			float yH = cs.GetYByValue(s.ORHigh);
			float yL = cs.GetYByValue(s.ORLow);
			float yM = cs.GetYByValue(s.ORMid);
			
			var lnBr = s.IsBullish ? dxBullishBrush : dxBearishBrush;
			var flBr = s.IsBullish ? dxBullishFillBrush : dxBearishFillBrush;
			
			// ── Fill ──
			float top = Math.Min(yH, yL);
			float ht  = Math.Max(Math.Abs(yL - yH), 1f);
			RenderTarget.FillRectangle(new SharpDX.RectangleF(xStart, top, xEnd - xStart, ht), flBr);
			
			// ── OR Lines ──
			RenderTarget.DrawLine(new Vector2(xStart, yH), new Vector2(xEnd, yH), lnBr, RangeLineWidth, GetSS(RangeLineStyle));
			RenderTarget.DrawLine(new Vector2(xStart, yL), new Vector2(xEnd, yL), lnBr, RangeLineWidth, GetSS(RangeLineStyle));
			
			// ── Midline ──
			if (ShowMidLine)
				RenderTarget.DrawLine(new Vector2(xStart, yM), new Vector2(xEnd, yM), lnBr, MidLineWidth, GetSS(MidLineStyle));
			
			// ── Labels ──
			float lblX = (LabelPosition == LabelPositionOption.Left) ? xStart : xEnd;
			bool lblLeft = (LabelPosition == LabelPositionOption.Left);
			
			if (ShowLabels)
			{
				string pf = Core.Globals.GetTickFormatString(TickSize);
				DrawLabel(lblX, yH, "High" + (ShowPrices ? " (" + s.ORHigh.ToString(pf) + ")" : ""), lnBr, textFormatNormal, lblLeft);
				DrawLabel(lblX, yL, "Low"  + (ShowPrices ? " (" + s.ORLow.ToString(pf) + ")"  : ""), lnBr, textFormatNormal, lblLeft);
				if (ShowMidLine)
					DrawLabel(lblX, yM, "Mid" + (ShowPrices ? " (" + s.ORMid.ToString(pf) + ")" : ""), lnBr, textFormatNormal, lblLeft);
			}
			
			// ── Stat Levels ──
			if (ShowStatLevels && s.Stat1Up != 0)
			{
				float y1u = cs.GetYByValue(s.Stat1Up), y1d = cs.GetYByValue(s.Stat1Dn);
				float y2u = cs.GetYByValue(s.Stat2Up), y2d = cs.GetYByValue(s.Stat2Dn);
				RenderTarget.DrawLine(new Vector2(xStart, y1u), new Vector2(xEnd, y1u), dxStatsLineBrush, StatsLineWidth, strokeDash);
				RenderTarget.DrawLine(new Vector2(xStart, y1d), new Vector2(xEnd, y1d), dxStatsLineBrush, StatsLineWidth, strokeDash);
				RenderTarget.DrawLine(new Vector2(xStart, y2u), new Vector2(xEnd, y2u), dxStatsLineBrush, StatsLineWidth, strokeDot);
				RenderTarget.DrawLine(new Vector2(xStart, y2d), new Vector2(xEnd, y2d), dxStatsLineBrush, StatsLineWidth, strokeDot);
				if (ShowStatLabels)
				{
					var tf = GetTF(StatsLabelSize);
					DrawLabel(lblX, y1u, "+" + StdDevMult1.ToString("0.0") + "σ", dxStatsLabelBrush, tf, lblLeft);
					DrawLabel(lblX, y1d, "-" + StdDevMult1.ToString("0.0") + "σ", dxStatsLabelBrush, tf, lblLeft);
					DrawLabel(lblX, y2u, "+" + StdDevMult2.ToString("0.0") + "σ", dxStatsLabelBrush, tf, lblLeft);
					DrawLabel(lblX, y2d, "-" + StdDevMult2.ToString("0.0") + "σ", dxStatsLabelBrush, tf, lblLeft);
				}
			}
			
			// ── Range Extensions ──
			if (ShowRangeExtensions && s.RangeIncrement > 0)
			{
				var tf = GetTF(RangeExtLabelSize);
				string pf = Core.Globals.GetTickFormatString(TickSize);
				for (int i = 1; i <= NumExtensionLevels; i++)
				{
					float yu = cs.GetYByValue(s.ORHigh + s.RangeIncrement * i);
					float yd = cs.GetYByValue(s.ORLow  - s.RangeIncrement * i);
					RenderTarget.DrawLine(new Vector2(xStart, yu), new Vector2(xEnd, yu), dxRangeLineBrush, RangeExtLineWidth, strokeSolid);
					RenderTarget.DrawLine(new Vector2(xStart, yd), new Vector2(xEnd, yd), dxRangeLineBrush, RangeExtLineWidth, strokeSolid);
					if (ShowRangeExtLabels)
					{
						DrawLabel(lblX, yu, "R+" + i + " (" + (s.RangeIncrement * i).ToString(pf) + ")", dxRangeLabelBrush, tf, lblLeft);
						DrawLabel(lblX, yd, "R-" + i + " (" + (s.RangeIncrement * i).ToString(pf) + ")", dxRangeLabelBrush, tf, lblLeft);
					}
				}
			}
			
			// ── Rotation Levels ──
			if (ShowRotations && RotationIncrement > 0)
			{
				var tf = GetTF(RotationLabelSize);
				for (int i = 0; i < 5; i++)
				{
					float yu = cs.GetYByValue(s.RotUp[i]);
					float yd = cs.GetYByValue(s.RotDn[i]);
					
					// Draw the LINE first, then label
					RenderTarget.DrawLine(new Vector2(xStart, yu), new Vector2(xEnd, yu), dxRotationLineBrush, RotationLineWidth, GetSS(RotationLineStyle));
					RenderTarget.DrawLine(new Vector2(xStart, yd), new Vector2(xEnd, yd), dxRotationLineBrush, RotationLineWidth, GetSS(RotationLineStyle));
					
					if (ShowRotationLabels)
					{
						string ut = "R+" + (i+1) + " (" + (RotationIncrement*(i+1)).ToString("#.##") + ")";
						string dt2 = "R-" + (i+1) + " (" + (RotationIncrement*(i+1)).ToString("#.##") + ")";
						DrawLabel(lblX, yu, ut, dxRotationLabelBrush, tf, lblLeft);
						DrawLabel(lblX, yd, dt2, dxRotationLabelBrush, tf, lblLeft);
					}
				}
			}
		}
		
		private void DrawLabel(float x, float y, string text, SharpDX.Direct2D1.Brush brush, SharpDX.DirectWrite.TextFormat fmt, bool rightAligned)
		{
			if (fmt == null || brush == null || string.IsNullOrEmpty(text)) return;
			using (var layout = new SharpDX.DirectWrite.TextLayout(Core.Globals.DirectWriteFactory, text, fmt, 400, 30))
			{
				float dx = rightAligned ? x - layout.Metrics.Width - 4 : x + 4;
				RenderTarget.DrawTextLayout(new Vector2(dx, y - layout.Metrics.Height / 2), layout, brush);
			}
		}
		
		#endregion
		
		#region Properties
		
		[Display(Name = "Session", Order = 1, GroupName = "1. Session Settings")]
		public SessionOption SessionChoice { get; set; }
		[NinjaScriptProperty][Display(Name = "Custom Start (HHMM)", Order = 2, GroupName = "1. Session Settings")]
		public string CustomSessionStart { get; set; }
		[NinjaScriptProperty][Display(Name = "Custom End (HHMM)", Order = 3, GroupName = "1. Session Settings")]
		public string CustomSessionEnd { get; set; }
		[NinjaScriptProperty][Display(Name = "Timezone", Order = 4, GroupName = "1. Session Settings")]
		public string SessionTimezone { get; set; }
		
		[NinjaScriptProperty][Range(1, int.MaxValue)][Display(Name = "Timeframe (Minutes)", Order = 1, GroupName = "2. Opening Bar Format")]
		public int OBRTimeframe { get; set; }
		[NinjaScriptProperty][Display(Name = "Show Midline", Order = 2, GroupName = "2. Opening Bar Format")]
		public bool ShowMidLine { get; set; }
		[NinjaScriptProperty][Display(Name = "Show Historical", Order = 3, GroupName = "2. Opening Bar Format")]
		public bool ShowHistorical { get; set; }
		[NinjaScriptProperty][Range(1, 500)][Display(Name = "Max History", Order = 4, GroupName = "2. Opening Bar Format")]
		public int MaxHistory { get; set; }
		[NinjaScriptProperty][Range(0, int.MaxValue)][Display(Name = "Projection Offset (Bars)", Order = 5, GroupName = "2. Opening Bar Format")]
		public int ProjectionOffset { get; set; }
		[NinjaScriptProperty][Display(Name = "Show Labels", Order = 6, GroupName = "2. Opening Bar Format")]
		public bool ShowLabels { get; set; }
		[NinjaScriptProperty][Display(Name = "Show Prices", Order = 7, GroupName = "2. Opening Bar Format")]
		public bool ShowPrices { get; set; }
		[Display(Name = "Label Position", Order = 8, GroupName = "2. Opening Bar Format")]
		public LabelPositionOption LabelPosition { get; set; }
		[Display(Name = "Range Line Style", Order = 9, GroupName = "2. Opening Bar Format")]
		public DashStyleHelper RangeLineStyle { get; set; }
		[NinjaScriptProperty][Range(1, 10)][Display(Name = "Range Line Width", Order = 10, GroupName = "2. Opening Bar Format")]
		public int RangeLineWidth { get; set; }
		[Display(Name = "MidLine Style", Order = 11, GroupName = "2. Opening Bar Format")]
		public DashStyleHelper MidLineStyle { get; set; }
		[NinjaScriptProperty][Range(1, 10)][Display(Name = "MidLine Width", Order = 12, GroupName = "2. Opening Bar Format")]
		public int MidLineWidth { get; set; }
		
		[XmlIgnore][Display(Name = "Bullish Color", Order = 1, GroupName = "3. Colors")]
		public System.Windows.Media.Brush BullishColor { get; set; }
		[Browsable(false)] public string BullishColorSerializable { get { return Serialize.BrushToString(BullishColor); } set { BullishColor = Serialize.StringToBrush(value); } }
		[XmlIgnore][Display(Name = "Bearish Color", Order = 2, GroupName = "3. Colors")]
		public System.Windows.Media.Brush BearishColor { get; set; }
		[Browsable(false)] public string BearishColorSerializable { get { return Serialize.BrushToString(BearishColor); } set { BearishColor = Serialize.StringToBrush(value); } }
		[NinjaScriptProperty][Range(0,100)][Display(Name = "Bullish Fill Transparency %", Order = 3, GroupName = "3. Colors")]
		public int BullishFillOpacity { get; set; }
		[NinjaScriptProperty][Range(0,100)][Display(Name = "Bearish Fill Transparency %", Order = 4, GroupName = "3. Colors")]
		public int BearishFillOpacity { get; set; }
		
		[NinjaScriptProperty][Range(1, int.MaxValue)][Display(Name = "Lookback Periods", Order = 1, GroupName = "4. Statistical Levels")]
		public int LookbackPeriods { get; set; }
		[NinjaScriptProperty][Display(Name = "Show Stat Levels", Order = 2, GroupName = "4. Statistical Levels")]
		public bool ShowStatLevels { get; set; }
		[NinjaScriptProperty][Display(Name = "Show Stat Labels", Order = 3, GroupName = "4. Statistical Levels")]
		public bool ShowStatLabels { get; set; }
		[NinjaScriptProperty][Range(0, double.MaxValue)][Display(Name = "Std Dev Mult 1", Order = 4, GroupName = "4. Statistical Levels")]
		public double StdDevMult1 { get; set; }
		[NinjaScriptProperty][Range(0, double.MaxValue)][Display(Name = "Std Dev Mult 2", Order = 5, GroupName = "4. Statistical Levels")]
		public double StdDevMult2 { get; set; }
		[XmlIgnore][Display(Name = "Stats Line Color", Order = 6, GroupName = "4. Statistical Levels")]
		public System.Windows.Media.Brush StatsLineColor { get; set; }
		[Browsable(false)] public string StatsLineColorSerializable { get { return Serialize.BrushToString(StatsLineColor); } set { StatsLineColor = Serialize.StringToBrush(value); } }
		[NinjaScriptProperty][Range(1, 10)][Display(Name = "Stats Line Width", Order = 7, GroupName = "4. Statistical Levels")]
		public int StatsLineWidth { get; set; }
		[XmlIgnore][Display(Name = "Stats Label Color", Order = 8, GroupName = "4. Statistical Levels")]
		public System.Windows.Media.Brush StatsLabelColor { get; set; }
		[Browsable(false)] public string StatsLabelColorSerializable { get { return Serialize.BrushToString(StatsLabelColor); } set { StatsLabelColor = Serialize.StringToBrush(value); } }
		[Display(Name = "Stats Label Size", Order = 9, GroupName = "4. Statistical Levels")]
		public TextSizeOption StatsLabelSize { get; set; }
		
		[NinjaScriptProperty][Display(Name = "Show Range Ext", Order = 1, GroupName = "5. Range Extensions")]
		public bool ShowRangeExtensions { get; set; }
		[NinjaScriptProperty][Range(0.1, double.MaxValue)][Display(Name = "Range Multiplier", Order = 2, GroupName = "5. Range Extensions")]
		public double RangeMultiplier { get; set; }
		[NinjaScriptProperty][Range(1, 20)][Display(Name = "Num Levels", Order = 3, GroupName = "5. Range Extensions")]
		public int NumExtensionLevels { get; set; }
		[NinjaScriptProperty][Display(Name = "Show Ext Labels", Order = 4, GroupName = "5. Range Extensions")]
		public bool ShowRangeExtLabels { get; set; }
		[XmlIgnore][Display(Name = "Range Line Color", Order = 5, GroupName = "5. Range Extensions")]
		public System.Windows.Media.Brush RangeExtLineColor { get; set; }
		[Browsable(false)] public string RangeExtLineColorSerializable { get { return Serialize.BrushToString(RangeExtLineColor); } set { RangeExtLineColor = Serialize.StringToBrush(value); } }
		[NinjaScriptProperty][Range(1, 10)][Display(Name = "Range Line Width", Order = 6, GroupName = "5. Range Extensions")]
		public int RangeExtLineWidth { get; set; }
		[XmlIgnore][Display(Name = "Range Label Color", Order = 7, GroupName = "5. Range Extensions")]
		public System.Windows.Media.Brush RangeExtLabelColor { get; set; }
		[Browsable(false)] public string RangeExtLabelColorSerializable { get { return Serialize.BrushToString(RangeExtLabelColor); } set { RangeExtLabelColor = Serialize.StringToBrush(value); } }
		[Display(Name = "Range Label Size", Order = 8, GroupName = "5. Range Extensions")]
		public TextSizeOption RangeExtLabelSize { get; set; }
		
		[NinjaScriptProperty][Display(Name = "Show Rotations", Order = 1, GroupName = "6. OR Rotations")]
		public bool ShowRotations { get; set; }
		[NinjaScriptProperty][Range(0.01, double.MaxValue)][Display(Name = "Rotation Increment", Description = "e.g. 65 NQ, 15 ES", Order = 2, GroupName = "6. OR Rotations")]
		public double RotationIncrement { get; set; }
		[NinjaScriptProperty][Display(Name = "Show Rotation Labels", Order = 3, GroupName = "6. OR Rotations")]
		public bool ShowRotationLabels { get; set; }
		[XmlIgnore][Display(Name = "Rotation Line Color", Order = 4, GroupName = "6. OR Rotations")]
		public System.Windows.Media.Brush RotationLineColor { get; set; }
		[Browsable(false)] public string RotationLineColorSerializable { get { return Serialize.BrushToString(RotationLineColor); } set { RotationLineColor = Serialize.StringToBrush(value); } }
		[Display(Name = "Rotation Line Style", Order = 5, GroupName = "6. OR Rotations")]
		public DashStyleHelper RotationLineStyle { get; set; }
		[NinjaScriptProperty][Range(1, 10)][Display(Name = "Rotation Line Width", Order = 6, GroupName = "6. OR Rotations")]
		public int RotationLineWidth { get; set; }
		[XmlIgnore][Display(Name = "Rotation Label Color", Order = 7, GroupName = "6. OR Rotations")]
		public System.Windows.Media.Brush RotationLabelColor { get; set; }
		[Browsable(false)] public string RotationLabelColorSerializable { get { return Serialize.BrushToString(RotationLabelColor); } set { RotationLabelColor = Serialize.StringToBrush(value); } }
		[Display(Name = "Rotation Label Size", Order = 8, GroupName = "6. OR Rotations")]
		public TextSizeOption RotationLabelSize { get; set; }
		
		#endregion
	}
	
	#region Enums
	public enum SessionOption
	{
		[Description("New York RTH (9:30am - 4pm)")] NewYorkRTH,
		[Description("New York Futures (8am - 5pm)")] NewYorkFutures,
		[Description("London (2am - 8am)")] London,
		[Description("Asia (7pm - 2am)")] Asia,
		[Description("Midnight to 5pm")] MidnightTo5pm,
		[Description("ZB/Gold/Silver OR (8:20am - 4pm)")] ZBGoldSilverOR,
		[Description("CL OR (9am - 4pm)")] CLOR,
		[Description("Custom")] Custom
	}
	public enum LabelPositionOption { Left, Right }
	public enum TextSizeOption { Tiny, Small, Normal, Large }
	#endregion
}
