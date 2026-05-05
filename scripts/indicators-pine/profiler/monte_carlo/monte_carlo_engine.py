import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import scipy.stats as stats
from datetime import datetime
import os
import pytz

PINE_TEMPLATE = """// This Pine Script code is subject to the terms of the Mozilla Public License 2.0
// Monte Carlo Projection Bands - Auto-Generated

//@version=6
indicator("MC Projection Bands [{range_name}]", shorttitle="MC Bands {range_name}", overlay=true, max_lines_count=500, max_polylines_count=50, max_labels_count=50)

// ══════════════════════════════════════════════════════════════════════════════
// MONTE CARLO DATA - AUTO-GENERATED FROM PYTHON
// Generated: {generation_date}
// Ticker: {ticker} | Range: {range_start}-{range_end} | Simulations: {n_sims}
// Sample Days: {sample_days} | Timeframe: {timeframe}
// ══════════════════════════════════════════════════════════════════════════════

// BULLISH BANDS - % deviation from RANGE HIGH
// Positive = above range high, Negative = below range high

var float[] BULL_P05 = array.from({bull_p05_values})
var float[] BULL_P10 = array.from({bull_p10_values})
var float[] BULL_P25 = array.from({bull_p25_values})
var float[] BULL_P50 = array.from({bull_p50_values})
var float[] BULL_P75 = array.from({bull_p75_values})
var float[] BULL_P90 = array.from({bull_p90_values})
var float[] BULL_P95 = array.from({bull_p95_values})

// BEARISH BANDS - % deviation from RANGE LOW
// Positive = below range low, Negative = above range low

var float[] BEAR_P05 = array.from({bear_p05_values})
var float[] BEAR_P10 = array.from({bear_p10_values})
var float[] BEAR_P25 = array.from({bear_p25_values})
var float[] BEAR_P50 = array.from({bear_p50_values})
var float[] BEAR_P75 = array.from({bear_p75_values})
var float[] BEAR_P90 = array.from({bear_p90_values})
var float[] BEAR_P95 = array.from({bear_p95_values})

var int MC_BARS_FORWARD = {n_bars_forward}

// ══════════════════════════════════════════════════════════════════════════════
// INPUTS
// ══════════════════════════════════════════════════════════════════════════════

grpRange = "═══ RANGE SETTINGS ═══"
i_timezone       = input.string("{timezone}", "Timezone", group=grpRange, options=["America/New_York", "America/Chicago", "UTC"])
i_rangeStart     = input.int({range_start_hhmm}, "Range Start (HHMM)", group=grpRange)
i_rangeEnd       = input.int({range_end_hhmm}, "Range End (HHMM)", group=grpRange)

grpBands = "═══ BAND DISPLAY ═══"
i_showBullish    = input.bool(true, "Show Bullish Projection (from High)", group=grpBands)
i_showBearish    = input.bool(true, "Show Bearish Projection (from Low)", group=grpBands)
i_showOuterBand  = input.bool(true, "Show Outer Band (5/95)", group=grpBands)
i_showMiddleBand = input.bool(true, "Show Middle Band (10/90)", group=grpBands)
i_showInnerBand  = input.bool(true, "Show Inner Band (25/75)", group=grpBands)
i_showMedian     = input.bool(true, "Show Median (50)", group=grpBands)

grpColors = "═══ COLORS ═══"
i_bullOuterColor  = input.color(color.new(color.blue, 90), "Bull Outer", inline="bo", group=grpColors)
i_bullMiddleColor = input.color(color.new(color.blue, 80), "Middle", inline="bo", group=grpColors)
i_bullInnerColor  = input.color(color.new(color.blue, 70), "Inner", inline="bo", group=grpColors)
i_bullMedianColor = input.color(color.new(color.blue, 40), "Median", inline="bo", group=grpColors)
i_bearOuterColor  = input.color(color.new(color.red, 90), "Bear Outer", inline="be", group=grpColors)
i_bearMiddleColor = input.color(color.new(color.red, 80), "Middle", inline="be", group=grpColors)
i_bearInnerColor  = input.color(color.new(color.red, 70), "Inner", inline="be", group=grpColors)
i_bearMedianColor = input.color(color.new(color.red, 40), "Median", inline="be", group=grpColors)
i_rangeBoxColor   = input.color(color.new(color.teal, 75), "Range Box", group=grpColors)

grpOptions = "═══ OPTIONS ═══"
i_showRangeBox   = input.bool(true, "Show Range Box", group=grpOptions)
i_showRefLines   = input.bool(true, "Show High/Low Reference Lines", group=grpOptions)
i_showTable      = input.bool(true, "Show Info Table", group=grpOptions)
i_tablePos       = input.string("top_right", "Table Position", group=grpOptions, options=["top_left", "top_right", "bottom_left", "bottom_right"])

// ══════════════════════════════════════════════════════════════════════════════
// TIME FUNCTIONS
// ══════════════════════════════════════════════════════════════════════════════

getHHMM(t, tz) =>
    hour(t, tz) * 100 + minute(t, tz)

isInRange(t, startHHMM, endHHMM, tz) =>
    hhmm = getHHMM(t, tz)
    hhmm >= startHHMM and hhmm < endHHMM

isNewDay(tz) =>
    dayofweek(time, tz) != dayofweek(time[1], tz)

// ══════════════════════════════════════════════════════════════════════════════
// STATE VARIABLES
// ══════════════════════════════════════════════════════════════════════════════

var float rangeHigh = na
var float rangeLow = na
var int rangeStartBar = na
var int rangeEndBar = na
var bool rangeFormed = false

// Drawing arrays
var line[] bandLines = array.new_line()
var linefill[] bandFills = array.new_linefill()
var box rangeBox = na
var line refLineHigh = na
var line refLineLow = na

// ══════════════════════════════════════════════════════════════════════════════
// RANGE DETECTION
// ══════════════════════════════════════════════════════════════════════════════

inRange = isInRange(time, i_rangeStart, i_rangeEnd, i_timezone)
rangeJustStarted = inRange and not inRange[1]
rangeJustEnded = not inRange and inRange[1]

// Reset on new day
if isNewDay(i_timezone)
    rangeHigh := na
    rangeLow := na
    rangeFormed := false

// Build range
if rangeJustStarted
    rangeHigh := high
    rangeLow := low
    rangeStartBar := bar_index

if inRange
    rangeHigh := na(rangeHigh) ? high : math.max(rangeHigh, high)
    rangeLow := na(rangeLow) ? low : math.min(rangeLow, low)

// ══════════════════════════════════════════════════════════════════════════════
// PROJECTION DRAWING
// ══════════════════════════════════════════════════════════════════════════════

// Clear old drawings
clearDrawings() =>
    for ln in bandLines
        line.delete(ln)
    array.clear(bandLines)
    for lf in bandFills
        linefill.delete(lf)
    array.clear(bandFills)
    box.delete(rangeBox)
    line.delete(refLineHigh)
    line.delete(refLineLow)

// Draw bullish band (from range high)
drawBullishBand(rngHigh, refBar, arrUpper, arrLower, fillColor) =>
    for i = 1 to math.min(MC_BARS_FORWARD - 1, array.size(arrUpper) - 1)
        pctU1 = array.get(arrUpper, i - 1)
        pctU2 = array.get(arrUpper, i)
        pctL1 = array.get(arrLower, i - 1)
        pctL2 = array.get(arrLower, i)
        
        priceU1 = rngHigh * (1 + pctU1)
        priceU2 = rngHigh * (1 + pctU2)
        priceL1 = rngHigh * (1 + pctL1)
        priceL2 = rngHigh * (1 + pctL2)
        
        lnU = line.new(refBar + i - 1, priceU1, refBar + i, priceU2, color=fillColor, width=1)
        lnL = line.new(refBar + i - 1, priceL1, refBar + i, priceL2, color=fillColor, width=1)
        array.push(bandLines, lnU)
        array.push(bandLines, lnL)
        
        lf = linefill.new(lnU, lnL, fillColor)
        array.push(bandFills, lf)

// Draw bearish band (from range low)
drawBearishBand(rngLow, refBar, arrUpper, arrLower, fillColor) =>
    for i = 1 to math.min(MC_BARS_FORWARD - 1, array.size(arrUpper) - 1)
        pctU1 = array.get(arrUpper, i - 1)
        pctU2 = array.get(arrUpper, i)
        pctL1 = array.get(arrLower, i - 1)
        pctL2 = array.get(arrLower, i)
        
        // Positive pct means BELOW low
        priceU1 = rngLow * (1 - pctU1)
        priceU2 = rngLow * (1 - pctU2)
        priceL1 = rngLow * (1 - pctL1)
        priceL2 = rngLow * (1 - pctL2)
        
        lnU = line.new(refBar + i - 1, priceL1, refBar + i, priceL2, color=fillColor, width=1)
        lnL = line.new(refBar + i - 1, priceU1, refBar + i, priceU2, color=fillColor, width=1)
        array.push(bandLines, lnU)
        array.push(bandLines, lnL)
        
        lf = linefill.new(lnU, lnL, fillColor)
        array.push(bandFills, lf)

drawBullishMedian(rngHigh, refBar, arrMedian, lineColor) =>
    for i = 1 to math.min(MC_BARS_FORWARD - 1, array.size(arrMedian) - 1)
        pct1 = array.get(arrMedian, i - 1)
        pct2 = array.get(arrMedian, i)
        price1 = rngHigh * (1 + pct1)
        price2 = rngHigh * (1 + pct2)
        ln = line.new(refBar + i - 1, price1, refBar + i, price2, color=lineColor, width=2, style=line.style_dashed)
        array.push(bandLines, ln)

drawBearishMedian(rngLow, refBar, arrMedian, lineColor) =>
    for i = 1 to math.min(MC_BARS_FORWARD - 1, array.size(arrMedian) - 1)
        pct1 = array.get(arrMedian, i - 1)
        pct2 = array.get(arrMedian, i)
        price1 = rngLow * (1 - pct1)
        price2 = rngLow * (1 - pct2)
        ln = line.new(refBar + i - 1, price1, refBar + i, price2, color=lineColor, width=2, style=line.style_dashed)
        array.push(bandLines, ln)

// When range ends, draw projections
if rangeJustEnded and not na(rangeHigh)
    rangeFormed := true
    rangeEndBar := bar_index
    
    // Clear previous drawings
    clearDrawings()
    
    // Draw range box
    if i_showRangeBox
        rangeBox := box.new(rangeStartBar, rangeHigh, bar_index, rangeLow, border_color=i_rangeBoxColor, bgcolor=i_rangeBoxColor)
    
    // Draw reference lines
    if i_showRefLines
        refLineHigh := line.new(bar_index, rangeHigh, bar_index + MC_BARS_FORWARD, rangeHigh, color=color.new(color.blue, 60), width=1, style=line.style_dotted)
        refLineLow := line.new(bar_index, rangeLow, bar_index + MC_BARS_FORWARD, rangeLow, color=color.new(color.red, 60), width=1, style=line.style_dotted)
    
    // Draw BULLISH bands
    if i_showBullish
        if i_showOuterBand
            drawBullishBand(rangeHigh, bar_index, BULL_P95, BULL_P90, i_bullOuterColor)
        if i_showMiddleBand
            drawBullishBand(rangeHigh, bar_index, BULL_P90, BULL_P75, i_bullMiddleColor)
        if i_showInnerBand
            drawBullishBand(rangeHigh, bar_index, BULL_P75, BULL_P50, i_bullInnerColor)
        if i_showMedian
            drawBullishMedian(rangeHigh, bar_index, BULL_P50, i_bullMedianColor)
    
    // Draw BEARISH bands
    if i_showBearish
        if i_showOuterBand
            drawBearishBand(rangeLow, bar_index, BEAR_P95, BEAR_P90, i_bearOuterColor)
        if i_showMiddleBand
            drawBearishBand(rangeLow, bar_index, BEAR_P90, BEAR_P75, i_bearMiddleColor)
        if i_showInnerBand
            drawBearishBand(rangeLow, bar_index, BEAR_P75, BEAR_P50, i_bearInnerColor)
        if i_showMedian
            drawBearishMedian(rangeLow, bar_index, BEAR_P50, i_bearMedianColor)

// ══════════════════════════════════════════════════════════════════════════════
// INFO TABLE
// ══════════════════════════════════════════════════════════════════════════════

var table infoTable = na

if i_showTable and barstate.islast
    table.delete(infoTable)
    
    pos = switch i_tablePos
        "top_left" => position.top_left
        "top_right" => position.top_right
        "bottom_left" => position.bottom_left
        => position.bottom_right
    
    infoTable := table.new(pos, 2, 7, bgcolor=color.new(color.black, 80), border_width=1, border_color=color.gray)
    
    table.cell(infoTable, 0, 0, "MC Bands", text_color=color.white, text_size=size.small, bgcolor=color.new(color.teal, 60))
    table.cell(infoTable, 1, 0, "{ticker}", text_color=color.white, text_size=size.small, bgcolor=color.new(color.teal, 60))
    
    table.cell(infoTable, 0, 1, "Range", text_color=color.gray, text_size=size.tiny)
    table.cell(infoTable, 1, 1, "{range_start}-{range_end}", text_color=color.white, text_size=size.tiny)
    
    table.cell(infoTable, 0, 2, "Simulations", text_color=color.gray, text_size=size.tiny)
    table.cell(infoTable, 1, 2, "{n_sims}", text_color=color.white, text_size=size.tiny)
    
    table.cell(infoTable, 0, 3, "Sample Days", text_color=color.gray, text_size=size.tiny)
    table.cell(infoTable, 1, 3, "{sample_days}", text_color=color.white, text_size=size.tiny)
    
    table.cell(infoTable, 0, 4, "Range High", text_color=color.gray, text_size=size.tiny)
    table.cell(infoTable, 1, 4, str.tostring(rangeHigh, format.mintick), text_color=color.blue, text_size=size.tiny)
    
    table.cell(infoTable, 0, 5, "Range Low", text_color=color.gray, text_size=size.tiny)
    table.cell(infoTable, 1, 5, str.tostring(rangeLow, format.mintick), text_color=color.red, text_size=size.tiny)
    
    table.cell(infoTable, 0, 6, "Generated", text_color=color.gray, text_size=size.tiny)
    table.cell(infoTable, 1, 6, "{generation_date}", text_color=color.white, text_size=size.tiny)

// Visual reference during range formation
bgcolor(inRange ? color.new(color.teal, 90) : na)
"""

class MonteCarloProjection:
    def __init__(self, data_path, config):
        self.data_path = data_path
        self.config = config
        self.ticker = config.get("ticker", "NQ")
        self.tz = pytz.timezone(config.get("timezone", "America/New_York"))
        
        self.df = self._load_data()
        self.daily_ranges = []
        self.bull_bands = {}
        self.bear_bands = {}
        self.bull_stats = []
        self.bear_stats = []
        
    def _load_data(self):
        print(f"Loading data from {self.data_path}...")
        df = pd.read_parquet(self.data_path)
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        if df.index.tz is None:
            df = df.tz_localize('UTC').tz_convert(self.tz)
        else:
            df = df.tz_convert(self.tz)
            
        tf = self.config.get("timeframe", "5min")
        if tf != "1min":
            print(f"Resampling to {tf}...")
            logic = {'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}
            agg_dict = {k: v for k, v in logic.items() if k in df.columns}
            df = df.resample(tf).agg(agg_dict).dropna()
        return df

    def extract_ranges(self):
        print("Extracting sessions for Dual Cone analysis...")
        range_start_str = self.config["range_start"]
        proj_end_str = self.config["projection_end"]
        range_end_str = self.config["range_end"]
        
        try:
            df_relevant = self.df.between_time(range_start_str, proj_end_str)
        except Exception as e:
            print(f"Error in between_time: {e}. Fallback to day iteration.")
            df_relevant = self.df
            
        grouped = df_relevant.groupby(df_relevant.index.date)
        valid_samples = []
        
        for date_obj, day_data in grouped:
            if day_data.empty: continue
            date_str = date_obj.strftime("%Y-%m-%d")
            
            try:
                t_start = pd.Timestamp(f"{date_str} {range_start_str}").tz_localize(self.tz)
                t_end = pd.Timestamp(f"{date_str} {range_end_str}").tz_localize(self.tz)
                t_proj = pd.Timestamp(f"{date_str} {proj_end_str}").tz_localize(self.tz)
            except:
                continue 
            
            ts = day_data.index
            mask_range = (ts >= t_start) & (ts < t_end)
            mask_proj = (ts >= t_end) & (ts <= t_proj)
            
            df_range = day_data[mask_range]
            df_proj = day_data[mask_proj]
            
            if df_range.empty or df_proj.empty: continue
            
            r_high = df_range['high'].max()
            r_low = df_range['low'].min()
            
            # BULLISH Moves: relative to High
            # (Close - r_high) / r_high
            # Note: Using Close for projections. 
            closes = df_proj['close'].values
            highs = df_proj['high'].values
            lows = df_proj['low'].values
            
            # We track High excursions for Bullish, or Close? 
            # User example: (bar_high - range_high). 
            # Standard backtest usually uses Close to avoid wick noise, but user asked for High for Bull.
            # "For BULLISH projection (from range high): For each bar after range, calculate: (bar_high - range_high) / range_high"
            bull_moves = (highs - r_high) / r_high
            
            # "For BEARISH projection (from range low): For each bar after range, calculate: (range_low - bar_low) / range_low"
            # Positive value means we are BELOW range low.
            bear_moves = (r_low - lows) / r_low
            
            valid_samples.append({
                "date": date_str,
                "r_high": r_high,
                "r_low": r_low,
                "bull_moves": bull_moves,
                "bear_moves": bear_moves,
                "length": len(closes)
            })
            
        self.daily_ranges = valid_samples
        print(f"Extracted valid ranges from {len(valid_samples)} days.")

    def run_simulation(self):
        # We employ Empircal Bootstrap directly for each step (simpler and robust)
        print(f"Running Dual Cone simulation (Calculating Percentiles)...")
        percentiles = self.config.get("percentiles", [5, 10, 25, 50, 75, 90, 95])
        
        if not self.daily_ranges: return

        max_len = max(d["length"] for d in self.daily_ranges)
        
        # Organize into matrices: [time_step][sample_idx]
        bull_matrix = [[] for _ in range(max_len)]
        bear_matrix = [[] for _ in range(max_len)]
        
        for d in self.daily_ranges:
            for t, val in enumerate(d["bull_moves"]):
                bull_matrix[t].append(val)
            for t, val in enumerate(d["bear_moves"]):
                bear_matrix[t].append(val)
                
        # Calculate Percentiles
        self.bull_bands = {f"p{int(p):02d}": [] for p in percentiles}
        self.bear_bands = {f"p{int(p):02d}": [] for p in percentiles}
        self.bull_stats = []
        self.bear_stats = []
        
        # Helper to calc stats
        def calc_step_stats(data, band_dict, stat_list, step):
            if len(data) < 10: 
                stat_list.append(None)
                return
            
            mu, std = np.mean(data), np.std(data)
            pcs = np.percentile(data, percentiles)
            
            for i, p in enumerate(percentiles):
                key = f"p{int(p):02d}"
                band_dict[key].append(pcs[i])
                
            stat_list.append({
                "step": step,
                "n": len(data),
                "mean": mu,
                "std": std
            })

        for t in range(max_len):
            calc_step_stats(bull_matrix[t], self.bull_bands, self.bull_stats, t)
            calc_step_stats(bear_matrix[t], self.bear_bands, self.bear_stats, t)
            
        print("Dual Cone simulation complete.")

    def plot_diagnostics(self, output_path):
        if not self.bull_bands or not self.bear_bands: return
        print(f"Generating diagnostic plot to {output_path}...")
        
        fig, ax = plt.subplots(figsize=(15, 8))
        
        # X Axis
        x_axis = range(len(self.bull_bands["p50"]))
        
        # Plot Bull Bands (Positive Y)
        # Convert all to % for plotting
        def get_bull(k): return np.array(self.bull_bands[k]) * 100
        
        ax.fill_between(x_axis, get_bull("p05"), get_bull("p95"), color='blue', alpha=0.1, label='Bull 5-95%')
        ax.fill_between(x_axis, get_bull("p25"), get_bull("p75"), color='blue', alpha=0.2)
        ax.plot(x_axis, get_bull("p50"), color='cyan', linestyle='--', label='Bull Median')
        
        # Plot Bear Bands (Negative Y for visual, but data is positive "distance from low")
        # We plot negative of Bear moves to show them going DOWN
        def get_bear(k): return -np.array(self.bear_bands[k]) * 100
        
        # Note: Bear P95 is the "largest" move (furthest down)
        # So -P95 will be the bottom line. -P05 will be top (closest to 0)
        ax.fill_between(x_axis, get_bear("p05"), get_bear("p95"), color='red', alpha=0.1, label='Bear 5-95%')
        ax.fill_between(x_axis, get_bear("p25"), get_bear("p75"), color='red', alpha=0.2)
        ax.plot(x_axis, get_bear("p50"), color='orange', linestyle='--', label='Bear Median')
        
        ax.set_title(f"Dual Cone Monte Carlo: {self.ticker} {self.config['range_start']}-{self.config['range_end']}")
        ax.set_xlabel("Bars Forward")
        ax.set_ylabel("% Move from Range High/Low")
        ax.grid(True, alpha=0.3)
        ax.legend()
        ax.axhline(0, color='white', linewidth=1)
        
        ax.set_facecolor('#1e1e1e')
        fig.patch.set_facecolor('#1e1e1e')
        ax.tick_params(colors='white')
        ax.yaxis.label.set_color('white')
        ax.xaxis.label.set_color('white')
        ax.title.set_color('white')
        
        plt.tight_layout()
        plt.savefig(output_path)
        plt.close()

    def generate_pinescript(self, output_path):
        if not self.bull_bands: return
        print(f"Generating Pine Script to {output_path}...")
        
        def format_array(arr):
            values = [f"{v:.6f}" for v in arr]
            return ", ".join(values)
        
        template = PINE_TEMPLATE
        range_start_clean = self.config["range_start"].replace(":", "")
        range_end_clean = self.config["range_end"].replace(":", "")
        
        replacements = {
            "{generation_date}": datetime.now().strftime("%Y-%m-%d"),
            "{ticker}": self.ticker,
            "{range_name}": f"{self.ticker} {self.config.get('range_name', 'Session')}",
            "{range_start}": self.config["range_start"],
            "{range_end}": self.config["range_end"],
            "{range_start_hhmm}": range_start_clean,
            "{range_end_hhmm}": range_end_clean,
            "{n_sims}": str(self.config["simulations"]),
            "{sample_days}": str(len(self.daily_ranges)),
            "{timeframe}": self.config.get("timeframe", "5min"),
            "{timezone}": self.config.get("timezone", "America/New_York"),
            "{n_bars_forward}": str(len(self.bull_bands["p50"])),
            
            # Bull
            "{bull_p05_values}": format_array(self.bull_bands["p05"]),
            "{bull_p10_values}": format_array(self.bull_bands["p10"]),
            "{bull_p25_values}": format_array(self.bull_bands["p25"]),
            "{bull_p50_values}": format_array(self.bull_bands["p50"]),
            "{bull_p75_values}": format_array(self.bull_bands["p75"]),
            "{bull_p90_values}": format_array(self.bull_bands["p90"]),
            "{bull_p95_values}": format_array(self.bull_bands["p95"]),
            
            # Bear
            "{bear_p05_values}": format_array(self.bear_bands["p05"]),
            "{bear_p10_values}": format_array(self.bear_bands["p10"]),
            "{bear_p25_values}": format_array(self.bear_bands["p25"]),
            "{bear_p50_values}": format_array(self.bear_bands["p50"]),
            "{bear_p75_values}": format_array(self.bear_bands["p75"]),
            "{bear_p90_values}": format_array(self.bear_bands["p90"]),
            "{bear_p95_values}": format_array(self.bear_bands["p95"]),
        }
        
        for placeholder, value in replacements.items():
            template = template.replace(placeholder, value)
            
        with open(output_path, "w", encoding='utf-8') as f:
            f.write(template)
        print(f"Generated Pine Script: {output_path}")

    def export_stats(self, output_path):
        if not self.bull_stats: return
        print(f"Exporting stats to {output_path}...")
        
        # We'll stack Bull then Bear
        rows = []
        for s in self.bull_stats:
            if s is None: continue
            r = {"type": "BULL", "bar": s["step"], "n": s["n"], "mean": s["mean"], "std": s["std"]}
            t = s["step"]
            for k, v in self.bull_bands.items():
                if t < len(v): r[k] = v[t]
            rows.append(r)
            
        for s in self.bear_stats:
            if s is None: continue
            r = {"type": "BEAR", "bar": s["step"], "n": s["n"], "mean": s["mean"], "std": s["std"]}
            t = s["step"]
            for k, v in self.bear_bands.items():
                if t < len(v): r[k] = v[t]
            rows.append(r)
            
        pd.DataFrame(rows).to_csv(output_path, index=False)
        print(f"Saved CSV.")
        
    def generate_report(self, output_path):
        if not self.daily_ranges: return
        print(f"Generating MD Report...")
        with open(output_path, "w") as f:
            f.write(f"# Dual Cone Monte Carlo: {self.ticker}\n\n")
            f.write(f"This system separately simulates Bullish (from High) and Bearish (from Low) volatility.\n\n")
            f.write(f"- Days Analyzed: {len(self.daily_ranges)}\n")
            f.write(f"- Sim Mode: Empirical Bootstrap of High/Low Excursions\n")
