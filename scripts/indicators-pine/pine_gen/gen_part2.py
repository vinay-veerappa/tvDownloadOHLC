
    ind_header = f"""// © vveerappa
//@version=6
// 
// Daily Profiler [Semantic]
// 
// Based on the statistical analysis framework developed by:
//   • Pack Trade Group
//   • The Daily Profiler (https://thedailyprofiler.com/)
// 
// This indicator tracks session outcomes and calculates conditional
// probabilities based on historical data matching current market trajectory.
// 
// Credits:
//   Original Concepts: Pack Trade Group & The Daily Profiler
//   Pine Script Implementation: vveerappa
//
indicator("Daily Profiler [Semantic]", overlay=true, max_boxes_count=500, max_lines_count=500, max_labels_count=500)

// IMPORTANT: PUBLISH THESE LIBRARIES FIRST!
{chr(10).join(imports)}

// ————— LOAD DATA —————
// Dates
var int[] dates = LibAsia.get_dates()
// Stats
var int[] asia_stats = LibAsia.get_asia()
var int[] london_stats = LibLon.get_london()
var int[] ny1_stats = LibNY.get_ny1()
var int[] ny2_stats = LibNY.get_ny2()
// Broken
var int[] asia_bk = LibBroken.get_asia()
var int[] london_bk = LibBroken.get_london()
var int[] ny1_bk = LibBroken.get_ny1()
var int[] ny2_bk = LibBroken.get_ny2()
// Daily
var int[] hod_times = LibTimes.get_hod_time()
var int[] lod_times = LibTimes.get_lod_time()
var float[] hod_pcts = LibLevels.get_hod_pct()
var float[] lod_pcts = LibLevels.get_lod_pct()
// Touches
var int[] t_p12h = LibTouches.get_p12h()
var int[] t_p12m = LibTouches.get_p12m()
var int[] t_p12l = LibTouches.get_p12l()
var int[] t_asia_mid = LibTouches.get_asia_mid()
var int[] t_lon_mid = LibTouches.get_lon_mid()

type ModeRange
    string disp
    float min_val
    float max_val
    bool valid
"""
    
    ind_body_part1 = """
// ————— INPUTS —————
// 0. Theme Selection
grp_theme = "🎨 Theme"
theme_sel = input.string("Dark Pro", "Color Theme", options=["Default", "Dark Pro", "Light Pro", "Neon"], group=grp_theme)

// Theme color definitions
f_theme_asia_box() => theme_sel == "Dark Pro" ? color.new(#1E88E5, 85) : theme_sel == "Light Pro" ? color.new(#90CAF9, 85) : theme_sel == "Neon" ? color.new(#00BCD4, 85) : color.new(color.blue, 90)
f_theme_asia_bor() => theme_sel == "Dark Pro" ? color.new(#42A5F5, 40) : theme_sel == "Light Pro" ? color.new(#1976D2, 40) : theme_sel == "Neon" ? color.new(#00E5FF, 20) : color.new(color.blue, 50)
f_theme_lon_box() => theme_sel == "Dark Pro" ? color.new(#E53935, 85) : theme_sel == "Light Pro" ? color.new(#EF9A9A, 85) : theme_sel == "Neon" ? color.new(#FF1744, 85) : color.new(color.red, 90)
f_theme_lon_bor() => theme_sel == "Dark Pro" ? color.new(#EF5350, 40) : theme_sel == "Light Pro" ? color.new(#C62828, 40) : theme_sel == "Neon" ? color.new(#FF5252, 20) : color.new(color.red, 50)
f_theme_ny1_box() => theme_sel == "Dark Pro" ? color.new(#FB8C00, 85) : theme_sel == "Light Pro" ? color.new(#FFCC80, 85) : theme_sel == "Neon" ? color.new(#FF9100, 85) : color.new(color.orange, 90)
f_theme_ny1_bor() => theme_sel == "Dark Pro" ? color.new(#FFA726, 40) : theme_sel == "Light Pro" ? color.new(#E65100, 40) : theme_sel == "Neon" ? color.new(#FFAB40, 20) : color.new(color.orange, 50)
f_theme_ny2_box() => theme_sel == "Dark Pro" ? color.new(#8E24AA, 85) : theme_sel == "Light Pro" ? color.new(#CE93D8, 85) : theme_sel == "Neon" ? color.new(#EA80FC, 85) : color.new(color.purple, 90)
f_theme_ny2_bor() => theme_sel == "Dark Pro" ? color.new(#AB47BC, 40) : theme_sel == "Light Pro" ? color.new(#6A1B9A, 40) : theme_sel == "Neon" ? color.new(#E040FB, 20) : color.new(color.purple, 50)
f_theme_p12() => theme_sel == "Dark Pro" ? #FFD54F : theme_sel == "Light Pro" ? #F9A825 : theme_sel == "Neon" ? #FFEA00 : color.rgb(255, 235, 59)
f_theme_pd() => theme_sel == "Dark Pro" ? #9E9E9E : theme_sel == "Light Pro" ? #616161 : theme_sel == "Neon" ? #B0BEC5 : color.gray
f_theme_open() => theme_sel == "Dark Pro" ? #E0E0E0 : theme_sel == "Light Pro" ? #424242 : theme_sel == "Neon" ? #FFFFFF : color.white
f_theme_weekly() => theme_sel == "Dark Pro" ? #66BB6A : theme_sel == "Light Pro" ? #2E7D32 : theme_sel == "Neon" ? #00E676 : color.rgb(76, 175, 80)
f_theme_settle() => theme_sel == "Dark Pro" ? #FFA726 : theme_sel == "Light Pro" ? #E65100 : theme_sel == "Neon" ? #FF6D00 : color.rgb(255, 152, 0)

// 1. Tables
grp_tbl = "Table Settings"
p_res = input.string("Bottom Right", "Result Table Position", options=["Top Right", "Top Left", "Bottom Right", "Bottom Left", "Middle Right"], group=grp_tbl)
s_res = input.string("Tiny", "Result Table Size", options=["Tiny", "Small", "Normal", "Large"], group=grp_tbl)
p_stat = input.string("Middle Right", "Status Table Position", options=["Top Right", "Top Left", "Bottom Right", "Bottom Left", "Middle Right"], group=grp_tbl)

// 2. Boxes & Labels
grp_box = "Prediction Visuals"
show_boxes = input.bool(true, "Show Prediction Boxes", group=grp_box)
c_box_long  = input.color(color.new(color.green, 60), "Long Box Color", group=grp_box)
c_box_short = input.color(color.new(color.red, 60), "Short Box Color", group=grp_box)
c_box_false = input.color(color.new(color.gray, 60), "False/Neutral Box Color", group=grp_box)
t_box_fill  = input.int(60, "Box Fill Transparency (0-100)", minval=0, maxval=100, group=grp_box)
show_labels = input.bool(true, "Show Labels", group=grp_box)
c_lbl_text  = input.color(color.white, "Label Text Color", group=grp_box)
s_lbl       = input.string("Tiny", "Label Size", options=["Tiny", "Small", "Normal", "Large"], group=grp_box)

// 3. Session Visuals (uses Theme colors)
grp_vis = "Session Visuals"
c_asia_box = f_theme_asia_box()
c_asia_bor = f_theme_asia_bor()
c_lon_box  = f_theme_lon_box()
c_lon_bor  = f_theme_lon_bor()
c_ny1_box  = f_theme_ny1_box()
c_ny1_bor  = f_theme_ny1_bor()
c_ny2_box  = f_theme_ny2_box()
c_ny2_bor  = f_theme_ny2_bor()

// 4. Reference Levels (uses Theme colors)
grp_ref = "Reference Levels"
show_p12     = input.bool(true, "Show P12 (High/Mid/Low)", group=grp_ref)
c_p12        = f_theme_p12()
show_pd      = input.bool(true, "Show PDH/PDL/PDM", group=grp_ref)
c_pd         = f_theme_pd()
show_open    = input.bool(true, "Show Opens (Globex, Mid, 7:30)", group=grp_ref)
c_open       = f_theme_open()
show_weekly  = input.bool(true, "Show Weekly Close", group=grp_ref)
c_weekly     = f_theme_weekly()
show_settle  = input.bool(true, "Show Prior Settlement", group=grp_ref)
c_settle     = f_theme_settle()
show_ref_lbl = input.bool(true, "Show Labels", group=grp_ref)
line_ext_bars = input.int(20, "Line Extension (bars)", minval=1, maxval=100, group=grp_ref)

// Price Models
grp_pm = "Price Models"
show_pm     = input.bool(true, "Show Price Models", group=grp_pm)
pm_outcome  = input.string("Auto", "Outcome Model", options=["Auto", "Long True", "Long False", "Short True", "Short False"], group=grp_pm)
pm_anchor   = input.string("Prev Mid", "Anchor To", options=["Session Open", "Prev Mid"], group=grp_pm)
pm_opacity  = input.int(50, "Opacity (0-100)", minval=0, maxval=100, group=grp_pm)
c_pm_high   = input.color(color.green, "Model High Color", group=grp_pm)
c_pm_low    = input.color(color.red, "Model Low Color", group=grp_pm)

// 5. Histograms
grp_hist = "Time Histograms"
hist_outcome = input.string("None", "Show Histogram For", options=["None", "Long True", "Long False", "Short True", "Short False"], group=grp_hist)
hist_scale   = input.float(1.0, "Histogram Height Scale", step=0.1, group=grp_hist)
hist_disp    = input.float(0.5, "Histogram Y Displacement (%)", step=0.1, tooltip="Percentage of price to offset histogram from P12 Low/High", group=grp_hist)

get_pos(str) =>
    str == "Top Right" ? position.top_right : str == "Top Left" ? position.top_left : str == "Bottom Right" ? position.bottom_right : str == "Bottom Left" ? position.bottom_left : position.middle_right

get_size(str) =>
    str == "Tiny" ? size.tiny : str == "Small" ? size.small : str == "Large" ? size.large : size.normal

// ————— HELPER: GET END TIME (16:00 ET) —————
f_get_1600_et(start_time) =>
    y = year(start_time, "America/New_York")
    m = month(start_time, "America/New_York")
    d = dayofmonth(start_time, "America/New_York")
    h = hour(start_time, "America/New_York")
    day_shift = (h >= 17) ? 1 : 0
    target = timestamp("America/New_York", y, m, d + day_shift, 16, 0, 0)
    target

// ————— HELPER: DRAW LEVEL WITH LABEL (Bar-based extension) —————
f_draw_lev_bar(price, start_bi, col, style, txt, visible) =>
    if visible and not na(price) and start_bi > 0 and (bar_index - start_bi) < 500
        end_bi = bar_index + line_ext_bars
        line.new(start_bi, price, end_bi, price, xloc=xloc.bar_index, color=col, style=style)
        if show_ref_lbl
            label.new(end_bi, price, txt, xloc=xloc.bar_index, yloc=yloc.price, style=label.style_none, textcolor=col, size=size.small, textalign=text.align_left)

"""
