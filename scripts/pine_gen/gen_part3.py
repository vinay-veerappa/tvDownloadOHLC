
    ind_body_part2 = """
// ————— LIVE SESSION LOGIC & EXTENSIONS —————
t_asia = "1800-1929", t_lon = "0230-0329", t_ny1 = "0730-0829", t_ny2 = "1130-1229"
s_asia = "1930-0229", s_lon = "0330-0729", s_ny1 = "0830-1129", s_ny2 = "1230-1659"
bw_asia = "0230-1700:1234567", bw_lon  = "0730-1700:1234567", bw_ny1  = "1130-1700:1234567", bw_ny2  = "1600-1700:1234567"

var float asia_h = na, var float asia_l = na
var float lon_h = na,  var float lon_l = na
var float ny1_h = na,  var float ny1_l = na
var float ny2_h = na,  var float ny2_l = na

var int st_asia = 0, var int st_lon = 0, var int st_ny1 = 0, var int st_ny2 = 0
var bool bk_asia = false, var bool bk_lon = false, var bool bk_ny1 = false, var bool bk_ny2 = false

f_update_sess(_sess) =>
    bool in_sess = not na(time(timeframe.period, _sess + ":1234567", "America/New_York"))
    [in_sess, in_sess and not in_sess[1]]

[in_asia, start_asia] = f_update_sess(t_asia)
[in_lon, start_lon]   = f_update_sess(t_lon)
[in_ny1, start_ny1]   = f_update_sess(t_ny1)
[in_ny2, start_ny2]   = f_update_sess(t_ny2)

// Asia
var box b_asia = na
var line l_asia_mid = na
var label lb_asia_mid = na
var int asia_start_bi = 0
if start_asia
    if not na(b_asia)
        box.delete(b_asia)
    if not na(l_asia_mid)
        line.delete(l_asia_mid)
    if not na(lb_asia_mid)
        label.delete(lb_asia_mid)
    asia_h := high, asia_l := low, st_asia := 0, bk_asia := false
    st_lon := 0, bk_lon := false, lon_h := na, lon_l := na
    st_ny1 := 0, bk_ny1 := false, ny1_h := na, ny1_l := na
    st_ny2 := 0, bk_ny2 := false, ny2_h := na, ny2_l := na
    asia_start_bi := bar_index
    b_asia := box.new(bar_index, high, bar_index + 1, low, border_color=c_asia_bor, bgcolor=c_asia_box)
    l_asia_mid := line.new(bar_index, high, bar_index + line_ext_bars, high, xloc=xloc.bar_index, color=c_asia_bor, style=line.style_dotted)
    if show_ref_lbl
        lb_asia_mid := label.new(bar_index + line_ext_bars, high, "Asia Mid", xloc=xloc.bar_index, style=label.style_none, textcolor=c_asia_bor, size=size.small, textalign=text.align_left)

if in_asia
    asia_h := math.max(nz(asia_h, high), high)
    asia_l := math.min(nz(asia_l, low), low)
    box.set_top(b_asia, asia_h)
    box.set_bottom(b_asia, asia_l)
    box.set_right(b_asia, bar_index + 1)
    mid = (asia_h + asia_l) / 2
    line.set_y1(l_asia_mid, mid)
    line.set_y2(l_asia_mid, mid)
    if not na(lb_asia_mid)
        label.set_y(lb_asia_mid, mid)

if barstate.islast and not na(l_asia_mid)
    line.set_x2(l_asia_mid, bar_index + line_ext_bars)
    if not na(lb_asia_mid)
        label.set_x(lb_asia_mid, bar_index + line_ext_bars)

// London
var box b_lon = na
var line l_lon_mid = na
var label lb_lon_mid = na
if start_lon
    if not na(b_lon)
        box.delete(b_lon)
    if not na(l_lon_mid)
        line.delete(l_lon_mid)
    if not na(lb_lon_mid)
        label.delete(lb_lon_mid)
    lon_h := high, lon_l := low, st_lon := 0, bk_lon := false
    b_lon := box.new(bar_index, high, bar_index + 1, low, border_color=c_lon_bor, bgcolor=c_lon_box)
    l_lon_mid := line.new(bar_index, high, bar_index + line_ext_bars, high, xloc=xloc.bar_index, color=c_lon_bor, style=line.style_dotted)
    if show_ref_lbl
        lb_lon_mid := label.new(bar_index + line_ext_bars, high, "Lon Mid", xloc=xloc.bar_index, style=label.style_none, textcolor=c_lon_bor, size=size.small, textalign=text.align_left)

if in_lon
    lon_h := math.max(nz(lon_h, high), high)
    lon_l := math.min(nz(lon_l, low), low)
    box.set_top(b_lon, lon_h)
    box.set_bottom(b_lon, lon_l)
    box.set_right(b_lon, bar_index + 1)
    mid = (lon_h + lon_l) / 2
    line.set_y1(l_lon_mid, mid)
    line.set_y2(l_lon_mid, mid)
    if not na(lb_lon_mid)
        label.set_y(lb_lon_mid, mid)

if barstate.islast and not na(l_lon_mid)
    line.set_x2(l_lon_mid, bar_index + line_ext_bars)
    if not na(lb_lon_mid)
        label.set_x(lb_lon_mid, bar_index + line_ext_bars)

// NY1
var box b_ny1 = na
var line l_ny1_mid = na
var label lb_ny1_mid = na
if start_ny1
    if not na(b_ny1)
        box.delete(b_ny1)
    if not na(l_ny1_mid)
        line.delete(l_ny1_mid)
    if not na(lb_ny1_mid)
        label.delete(lb_ny1_mid)
    ny1_h := high, ny1_l := low, st_ny1 := 0, bk_ny1 := false
    b_ny1 := box.new(bar_index, high, bar_index + 1, low, border_color=c_ny1_bor, bgcolor=c_ny1_box)
    l_ny1_mid := line.new(bar_index, high, bar_index + line_ext_bars, high, xloc=xloc.bar_index, color=c_ny1_bor, style=line.style_dotted)
    if show_ref_lbl
        lb_ny1_mid := label.new(bar_index + line_ext_bars, high, "NY1 Mid", xloc=xloc.bar_index, style=label.style_none, textcolor=c_ny1_bor, size=size.small, textalign=text.align_left)

if in_ny1
    ny1_h := math.max(nz(ny1_h, high), high)
    ny1_l := math.min(nz(ny1_l, low), low)
    box.set_top(b_ny1, ny1_h)
    box.set_bottom(b_ny1, ny1_l)
    box.set_right(b_ny1, bar_index + 1)
    mid = (ny1_h + ny1_l) / 2
    line.set_y1(l_ny1_mid, mid)
    line.set_y2(l_ny1_mid, mid)
    if not na(lb_ny1_mid)
        label.set_y(lb_ny1_mid, mid)

if barstate.islast and not na(l_ny1_mid)
    line.set_x2(l_ny1_mid, bar_index + line_ext_bars)
    if not na(lb_ny1_mid)
        label.set_x(lb_ny1_mid, bar_index + line_ext_bars)

// NY2
var box b_ny2 = na
var line l_ny2_mid = na
if start_ny2
    if not na(b_ny2)
        box.delete(b_ny2)
    if not na(l_ny2_mid)
        line.delete(l_ny2_mid)
    ny2_h := high, ny2_l := low, st_ny2 := 0, bk_ny2 := false
    b_ny2 := box.new(bar_index, high, bar_index + 1, low, border_color=c_ny2_bor, bgcolor=c_ny2_box)
    l_ny2_mid := line.new(bar_index, high, bar_index + line_ext_bars, high, xloc=xloc.bar_index, color=c_ny2_bor, style=line.style_dotted)

if in_ny2
    ny2_h := math.max(nz(ny2_h, high), high)
    ny2_l := math.min(nz(ny2_l, low), low)
    box.set_top(b_ny2, ny2_h)
    box.set_bottom(b_ny2, ny2_l)
    box.set_right(b_ny2, bar_index + 1)
    mid = (ny2_h + ny2_l) / 2
    line.set_y1(l_ny2_mid, mid)
    line.set_y2(l_ny2_mid, mid)

if barstate.islast and not na(l_ny2_mid)
    line.set_x2(l_ny2_mid, bar_index + line_ext_bars)

// ————— REFERENCE LEVELS LOGIC —————
[pd_h, pd_l, pd_c] = request.security(syminfo.tickerid, "D", [high[1], low[1], close[1]], lookahead=barmerge.lookahead_on)
pd_m = (pd_h + pd_l) / 2
pw_c = request.security(syminfo.tickerid, "W", close[1], lookahead=barmerge.lookahead_on)

var float p12_h = na, var float p12_l = na, var float p12_m = na
var float open_mid = na, var float open_glob = na, var float open_0730 = na

var int bi_day_start = 0 
var int bi_midnight = 0 
var int bi_0730 = 0 
var int bi_0600 = 0 

var int trading_day = 0
bool is_1800 = (hour(time, "America/New_York") == 18) and (minute(time, "America/New_York") == 0)
bool start_p12 = is_1800 or (hour(time, "America/New_York") == 18 and not (hour(time[1], "America/New_York") == 18))

if start_p12
    trading_day := dayofmonth(time, "America/New_York")
    p12_h := high, p12_l := low, open_glob := open
    bi_day_start := bar_index

var int last_bar_trading_day = 0
if barstate.islast
    last_bar_trading_day := trading_day

bool in_p12 = not na(time(timeframe.period, "1800-0559:1234567", "America/New_York"))
if in_p12
    p12_h := math.max(nz(p12_h, high), high)
    p12_l := math.min(nz(p12_l, low), low)

bool is_0000 = (hour(time, "America/New_York") == 0) and (minute(time, "America/New_York") == 0)
if is_0000 or (hour(time, "America/New_York") == 0 and hour(time[1], "America/New_York") != 0)
    open_mid := open
    bi_midnight := bar_index

bool is_0730 = (hour(time, "America/New_York") == 7) and (minute(time, "America/New_York") == 30)
if is_0730 or (hour(time, "America/New_York") == 7 and minute(time, "America/New_York") >= 30 and minute(time[1], "America/New_York") < 30)
    open_0730 := open
    bi_0730 := bar_index

bool is_0600 = (hour(time, "America/New_York") == 6) and (minute(time, "America/New_York") == 0)
if is_0600 or (hour(time, "America/New_York") == 6 and hour(time[1], "America/New_York") != 6)
    bi_0600 := bar_index

if barstate.islast
    int start_ref = bi_day_start > 0 ? bi_day_start : bar_index
    if show_pd
        f_draw_lev_bar(pd_h, start_ref, c_pd, line.style_dashed, "PDH", true)
        f_draw_lev_bar(pd_l, start_ref, c_pd, line.style_dashed, "PDL", true)
        f_draw_lev_bar(pd_m, start_ref, c_pd, line.style_dotted, "PDM", true)
    if show_settle
        f_draw_lev_bar(pd_c, start_ref, c_settle, line.style_solid, "Settle", true)
    if show_weekly
        f_draw_lev_bar(pw_c, start_ref, c_weekly, line.style_solid, "Weekly", true)
    if show_open
        f_draw_lev_bar(open_glob, start_ref, c_open, line.style_dashed, "Globex", true)
        if not na(open_mid) and bi_midnight > 0
            f_draw_lev_bar(open_mid, bi_midnight, c_open, line.style_dashed, "Midnight", true)
        if not na(open_0730) and bi_0730 > 0
            f_draw_lev_bar(open_0730, bi_0730, c_open, line.style_dashed, "07:30", true)
    if show_p12 and not na(p12_h) and bi_0600 > 0
        p12_mid = (p12_h + p12_l) / 2
        f_draw_lev_bar(p12_h, bi_0600, c_p12, line.style_solid, "P12H", true)
        f_draw_lev_bar(p12_l, bi_0600, c_p12, line.style_solid, "P12L", true)
        f_draw_lev_bar(p12_mid, bi_0600, c_p12, line.style_dotted, "P12M", true)

// ————— CORE INDICATOR LOGIC —————
f_calc_status(s_sess, h, l, c_st) =>
    int mode = c_st
    if not na(time(timeframe.period, s_sess + ":1234567", "America/New_York")) and not na(h) and not na(l)
        b_h = high > h, b_l = low < l
        if mode == 0
            if b_h and not b_l
                mode := 1
            else if b_l and not b_h
                mode := 3
            else if b_h and b_l
                mode := 2
        else if mode == 1 and b_l
            mode := 2
        else if mode == 3 and b_h
            mode := 4
    mode
st_asia := f_calc_status(s_asia, asia_h, asia_l, st_asia)
st_lon := f_calc_status(s_lon, lon_h, lon_l, st_lon)
st_ny1 := f_calc_status(s_ny1, ny1_h, ny1_l, st_ny1)
st_ny2 := f_calc_status(s_ny2, ny2_h, ny2_l, st_ny2)

f_check_broken(s_win, h, l, c_bk) =>
    bool bk = c_bk
    if not bk and not na(time(timeframe.period, s_win, "America/New_York")) and not na(h) and not na(l)
        mid = (h + l) / 2
        if low <= mid and high >= mid
            bk := true
    bk
bk_asia := f_check_broken(bw_asia, asia_h, asia_l, bk_asia)
bk_lon  := f_check_broken(bw_lon, lon_h, lon_l, bk_lon)
bk_ny1  := f_check_broken(bw_ny1, ny1_h, ny1_l, bk_ny1)
bk_ny2  := f_check_broken(bw_ny2, ny2_h, ny2_l, bk_ny2)

// ————— PRICE MODEL DRAWING —————
f_draw_price_model(st_asia, st_lon, st_ny1, st_ny2, pd_m, open_glob) =>
    var polyline pm_h = na
    var polyline pm_l = na
    var label lbl_pm = na
    if show_pm
        string sel = pm_outcome
        if sel == "Auto"
            int code = st_ny2
            if code == 0 
                code := st_ny1
            if code == 0
                code := st_lon
            if code == 0 
                code := st_asia
            if code == 1 or code == 2
                sel := "Long " + (code == 1 ? "True" : "False")
            else if code == 3 or code == 4
                sel := "Short " + (code == 3 ? "True" : "False")
        
        int[] t_arr = array.new_int(0)
        float[] h_arr = array.new_float(0)
        float[] l_arr = array.new_float(0)
        
        if sel == "Long True"
            t_arr := LibModelLT.get_times(), h_arr := LibModelLT.get_high(), l_arr := LibModelLT.get_low()
        else if sel == "Long False"
            t_arr := LibModelLF.get_times(), h_arr := LibModelLF.get_high(), l_arr := LibModelLF.get_low()
        else if sel == "Short True"
            t_arr := LibModelST.get_times(), h_arr := LibModelST.get_high(), l_arr := LibModelST.get_low()
        else if sel == "Short False"
            t_arr := LibModelSF.get_times(), h_arr := LibModelSF.get_high(), l_arr := LibModelSF.get_low()
            
        if array.size(t_arr) > 0
            chart.point[] pts_h = array.new<chart.point>()
            chart.point[] pts_l = array.new<chart.point>()
            
            float anchor = na
            if pm_anchor == "Prev Mid" and not na(pd_m)
                anchor := pd_m
            else
                anchor := open_glob 
            
            if not na(anchor)
                int _ts_start = time("D")
                for i = 0 to array.size(t_arr) - 1
                    t_off = array.get(t_arr, i) * 60000 
                    t_pt = _ts_start + t_off
                    p_h = anchor * (1.0 + array.get(h_arr, i) / 100.0)
                    p_l = anchor * (1.0 + array.get(l_arr, i) / 100.0)
                    array.push(pts_h, chart.point.from_time(t_pt, p_h))
                    array.push(pts_l, chart.point.from_time(t_pt, p_l))
                
                polyline.delete(pm_h)
                polyline.delete(pm_l)
                pm_h := polyline.new(pts_h, line_color=color.new(c_pm_high, pm_opacity), xloc=xloc.bar_time, line_width=2)
                pm_l := polyline.new(pts_l, line_color=color.new(c_pm_low, pm_opacity), xloc=xloc.bar_time, line_width=2)
                
                label.delete(lbl_pm)
                lbl_pm := label.new(bar_index, high, "Model: " + sel, textcolor=color.white, color=color.new(color.blue, 50), style=label.style_label_down, size=size.small)

f_fmt_time(m) =>
    h = math.floor(m / 60)
    mm = m % 60
    str.format("{0,number,00}:{1,number,00}", h, mm)

f_calc_mode_time(arr_vals) =>
    ModeRange r = ModeRange.new("N/A", 0.0, 0.0, false)
    if array.size(arr_vals) > 0
        int b_size = 30
        var int[] buckets = array.new_int(48, 0)
        array.fill(buckets, 0)
        int max_c = 0
        int max_b = 0
        for i = 0 to array.size(arr_vals) - 1
            v = array.get(arr_vals, i)
            b_idx = math.min(math.floor(v / b_size), 47)
            c = array.get(buckets, b_idx) + 1
            array.set(buckets, b_idx, c)
            if c > max_c
                max_c := c
                max_b := b_idx
        start_t = max_b * b_size
        end_t = start_t + b_size
        r.disp := f_fmt_time(start_t) + "-" + f_fmt_time(end_t)
        r.min_val := start_t
        r.max_val := end_t
        r.valid := true
    r

f_calc_mode_pct(arr_vals) =>
    ModeRange r = ModeRange.new("N/A", 0.0, 0.0, false)
    if array.size(arr_vals) > 0
        float step = 0.25
        int n_b = 40
        var int[] buckets = array.new_int(40, 0)
        array.fill(buckets, 0)
        int max_c = 0
        int max_b = 0
        for i = 0 to array.size(arr_vals) - 1
            v = array.get(arr_vals, i)
            b_idx = math.min(math.max(math.floor((v + 5.0) / step), 0), n_b - 1)
            c = array.get(buckets, b_idx) + 1
            array.set(buckets, b_idx, c)
            if c > max_c
                max_c := c
                max_b := b_idx
        start_p = (max_b * step) - 5.0
        end_p = start_p + step
        r.disp := str.format("{0,number,#.#} to {1,number,#.#}%", start_p, end_p)
        r.min_val := start_p
        r.max_val := end_p
        r.valid := true
    r

f_draw_box(m_time, m_price, d_open, b_col, row_name, is_high) =>
    if show_boxes and not na(d_open) and m_time.valid and m_price.valid
        y = year(time("D")), m = month(time("D")), d = dayofmonth(time("D"))
        t_base = timestamp("America/New_York", y, m, d, 0, 0)
        t_start = t_base + int(m_time.min_val * 60000)
        t_end   = t_base + int(m_time.max_val * 60000)
        if m_time.min_val < 1080
            t_start := t_start + 86400000
        if m_time.max_val < 1080
            t_end := t_end + 86400000
        p_start = d_open * (1 + m_price.min_val / 100.0)
        p_end   = d_open * (1 + m_price.max_val / 100.0)
        fill_c = color.new(b_col, t_box_fill)
        box.new(t_start, p_end, t_end, p_start, xloc=xloc.bar_time, bgcolor=fill_c, border_color=b_col, border_style=line.style_solid)
        if show_labels
            txt = row_name + (is_high ? " HOD" : " LOD") + "\\n" + m_price.disp + "\\n" + m_time.disp
            label.new(int((t_start + t_end)/2), p_end, txt, xloc=xloc.bar_time, yloc=yloc.price, color=color.new(c_lbl_text, 100), style=label.style_label_down, textcolor=c_lbl_text, size=get_size(s_lbl))

f_draw_time_hist(arr_vals, baseline_price, scale_price, is_high) =>
    if array.size(arr_vals) > 0 and not na(baseline_price) and not na(scale_price)
        int b_size = 15  
        var int[] buckets = array.new_int(96, 0)
        array.fill(buckets, 0)
        int max_c = 0
        for i = 0 to array.size(arr_vals) - 1
            v = array.get(arr_vals, i)
            b_idx = math.min(math.floor(v / b_size), 95)
            c = array.get(buckets, b_idx) + 1
            array.set(buckets, b_idx, c)
            if c > max_c
                max_c := c
        
        y = year(time("D")), m = month(time("D")), d = dayofmonth(time("D"))
        t_base = timestamp("America/New_York", y, m, d, 0, 0)
        h_unit = scale_price * 0.005 * hist_scale
        col_bar = is_high ? color.new(color.green, 50) : color.new(color.red, 50)
        
        for i = 0 to 95
            cnt = array.get(buckets, i)
            if cnt > 0
                h_ratio = float(cnt) / float(max_c)
                val_h = h_ratio * h_unit
                t_s_min = i * b_size
                t_e_min = (i + 1) * b_size
                t_start = t_base + t_s_min * 60000
                t_end = t_base + t_e_min * 60000
                if t_s_min < 1080 
                    t_start := t_start + 86400000
                if t_e_min < 1080 
                    t_end := t_end + 86400000
                p_top = is_high ? (baseline_price + val_h) : baseline_price
                p_bot = is_high ? baseline_price : (baseline_price - val_h)
                box.new(t_start, p_top, t_end, p_bot, xloc=xloc.bar_time, bgcolor=col_bar, border_color=color.new(col_bar, 20))

f_render_row_adv(tbl, r, label, cnt, tot, bg_col, sz, arr_hod_t, arr_lod_t, arr_hod_p, arr_lod_p, cp12h, cp12m, cp12l, casia, clon, d_open, is_long, is_fls) =>
    b_col = is_fls ? c_box_false : (is_long ? c_box_long : c_box_short)
    if cnt > 0
        pct = 100.0 * cnt / tot
        m_hod_t = f_calc_mode_time(arr_hod_t)
        m_lod_t = f_calc_mode_time(arr_lod_t)
        m_hod_p = f_calc_mode_pct(arr_hod_p)
        m_lod_p = f_calc_mode_pct(arr_lod_p)

        f_draw_box(m_hod_t, m_hod_p, d_open, b_col, label, true)
        f_draw_box(m_lod_t, m_lod_p, d_open, b_col, label, false)
        
        if hist_outcome == label
            hod_baseline = not na(p12_h) ? p12_h + (d_open * hist_disp / 100) : d_open
            lod_baseline = not na(p12_l) ? p12_l - (d_open * hist_disp / 100) : d_open
            f_draw_time_hist(arr_hod_t, hod_baseline, d_open, true)
            f_draw_time_hist(arr_lod_t, lod_baseline, d_open, false)

        table.cell(tbl, 0, r, label, bgcolor=bg_col, text_color=color.white, text_size=sz)
        table.cell(tbl, 1, r, str.format("{0,number,#.#}% ({1} Days)", pct, cnt), bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 2, r, m_lod_t.disp, bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 3, r, m_hod_t.disp, bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 4, r, m_lod_p.disp, bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 5, r, m_hod_p.disp, bgcolor=color.black, text_color=color.white, text_size=sz)
        pp12h = cnt > 0 ? 100.0 * cp12h / cnt : 0.0
        pp12m = cnt > 0 ? 100.0 * cp12m / cnt : 0.0
        pp12l = cnt > 0 ? 100.0 * cp12l / cnt : 0.0
        pasia = cnt > 0 ? 100.0 * casia / cnt : 0.0
        plon  = cnt > 0 ? 100.0 * clon / cnt : 0.0
        table.cell(tbl, 6, r, str.format("{0,number,#.#}%", pp12h), bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 7, r, str.format("{0,number,#.#}%", pp12m), bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 8, r, str.format("{0,number,#.#}%", pp12l), bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 9, r, str.format("{0,number,#.#}%", pasia), bgcolor=color.black, text_color=color.white, text_size=sz)
        table.cell(tbl, 10, r, str.format("{0,number,#.#}%", plon), bgcolor=color.black, text_color=color.white, text_size=sz)


// ————— STATUS STRINGS & COLORS —————
f_status_str(c, is_active, is_broken) =>
    str = "Neutral"
    if c == 1 
        str := is_active ? "Long (Pending)" : "Long True"
    else if c == 2 
        str := "Long False"
    else if c == 3 
        str := is_active ? "Short (Pending)" : "Short True"
    else if c == 4 
        str := "Short False"
    if is_broken
        str := str + " (Broken)"
    str

f_status_col(c) =>
    c == 1 ? color.green : c == 2 ? color.gray : c == 3 ? color.red : c == 4 ? color.gray : color.gray

// ————— TABLES —————
var table tbl_res = table.new(get_pos(p_res), 12, 5, border_width = 1) 
var table tbl_stat = table.new(get_pos(p_stat), 2, 5, border_width = 1)

f_match(hist_code, hist_bk, live_code, live_bk) =>
    s_ok = false
    if live_code == 0 
        s_ok := true
    else if live_code == 1 
        s_ok := (hist_code == 1 or hist_code == 2)
    else if live_code == 3 
        s_ok := (hist_code == 3 or hist_code == 4)
    else 
        s_ok := (hist_code == live_code)
    b_ok = live_bk ? (hist_bk == 1) : true
    s_ok and b_ok
"""

    tail_logic = """
var int last_tgt_idx = -1
var int last_st_asia = -1
var int last_st_lon = -1
var int last_st_ny1 = -1
var int last_st_ny2 = -1
var bool last_bk_asia = false
var bool last_bk_lon = false
var bool last_bk_ny1 = false
var bool last_bk_ny2 = false

var int c_lt = 0, var int c_lf = 0, var int c_st = 0, var int c_sf = 0
var int total = 0
var string cached_title = "Loading..."

var int[] lt_ht = array.new_int(0), var int[] lt_lt = array.new_int(0), var float[] lt_hp = array.new_float(0), var float[] lt_lp = array.new_float(0)
var int[] lf_ht = array.new_int(0), var int[] lf_lt = array.new_int(0), var float[] lf_hp = array.new_float(0), var float[] lf_lp = array.new_float(0)
var int[] st_ht = array.new_int(0), var int[] st_lt = array.new_int(0), var float[] st_hp = array.new_float(0), var float[] st_lp = array.new_float(0)
var int[] sf_ht = array.new_int(0), var int[] sf_lt = array.new_int(0), var float[] sf_hp = array.new_float(0), var float[] sf_lp = array.new_float(0)

var int lt_t_p12h = 0, var int lt_t_p12m = 0, var int lt_t_p12l = 0, var int lt_t_asia = 0, var int lt_t_lon = 0
var int lf_t_p12h = 0, var int lf_t_p12m = 0, var int lf_t_p12l = 0, var int lf_t_asia = 0, var int lf_t_lon = 0
var int st_t_p12h = 0, var int st_t_p12m = 0, var int st_t_p12l = 0, var int st_t_asia = 0, var int st_t_lon = 0
var int sf_t_p12h = 0, var int sf_t_p12m = 0, var int sf_t_p12l = 0, var int sf_t_asia = 0, var int sf_t_lon = 0

d_open = request.security(syminfo.tickerid, "D", open, lookahead=barmerge.lookahead_on)

if barstate.islast
    sz_r = get_size(s_res)
    
    bool fin_asia = not na(time(timeframe.period, "0230-0329:1234567", "America/New_York")) or not na(time(timeframe.period, "0330-1700:1234567", "America/New_York"))
    bool fin_lon = not na(time(timeframe.period, "0730-0829:1234567", "America/New_York")) or not na(time(timeframe.period, "0830-1700:1234567", "America/New_York"))
    bool fin_ny1 = not na(time(timeframe.period, "1130-1229:1234567", "America/New_York")) or not na(time(timeframe.period, "1230-1700:1234567", "America/New_York"))
    bool fin_ny2 = not na(time(timeframe.period, "1615-1700:1234567", "America/New_York"))

    table.clear(tbl_stat, 0, 0, 1, 4)
    table.cell(tbl_stat, 0, 0, "Current Status", bgcolor=color.black, text_color=color.white, text_size=sz_r)
    table.cell(tbl_stat, 0, 1, "Asia: " + f_status_str(st_asia, not fin_asia, bk_asia), bgcolor=color.black, text_color=f_status_col(st_asia), text_size=sz_r)
    table.cell(tbl_stat, 0, 2, "London: " + f_status_str(st_lon, not fin_lon, bk_lon), bgcolor=color.black, text_color=f_status_col(st_lon), text_size=sz_r)
    table.cell(tbl_stat, 0, 3, "NY1: " + f_status_str(st_ny1, not fin_ny1, bk_ny1), bgcolor=color.black, text_color=f_status_col(st_ny1), text_size=sz_r)
    table.cell(tbl_stat, 0, 4, "NY2: " + f_status_str(st_ny2, not fin_ny2, bk_ny2), bgcolor=color.black, text_color=f_status_col(st_ny2), text_size=sz_r)

    int tgt_idx = 0 
    string title = "Asia Outcomes"
    bool t_asia_done = not na(time(timeframe.period, "0230-1700:1234567", "America/New_York"))
    bool t_lon_done  = not na(time(timeframe.period, "0730-1700:1234567", "America/New_York"))
    bool t_ny1_done  = not na(time(timeframe.period, "1130-1700:1234567", "America/New_York"))
    if t_asia_done 
        tgt_idx := 1
        title := "London Outcomes"
        if t_lon_done
            tgt_idx := 2
            title := "NY1 Outcomes"
            if t_ny1_done
                tgt_idx := 3
                title := "NY2 Outcomes"

    bool state_changed = (tgt_idx != last_tgt_idx) or (st_asia != last_st_asia) or (st_lon != last_st_lon) or (st_ny1 != last_st_ny1) or (st_ny2 != last_st_ny2) or (bk_asia != last_bk_asia) or (bk_lon != last_bk_lon) or (bk_ny1 != last_bk_ny1) or (bk_ny2 != last_bk_ny2)
    
    if state_changed
        c_lt := 0, c_lf := 0, c_st := 0, c_sf := 0, total := 0
        lt_t_p12h := 0, lt_t_p12m := 0, lt_t_p12l := 0, lt_t_asia := 0, lt_t_lon := 0
        lf_t_p12h := 0, lf_t_p12m := 0, lf_t_p12l := 0, lf_t_asia := 0, lf_t_lon := 0
        st_t_p12h := 0, st_t_p12m := 0, st_t_p12l := 0, st_t_asia := 0, st_t_lon := 0
        sf_t_p12h := 0, sf_t_p12m := 0, sf_t_p12l := 0, sf_t_asia := 0, sf_t_lon := 0
        
        array.clear(lt_ht), array.clear(lt_lt), array.clear(lt_hp), array.clear(lt_lp)
        array.clear(lf_ht), array.clear(lf_lt), array.clear(lf_hp), array.clear(lf_lp)
        array.clear(st_ht), array.clear(st_lt), array.clear(st_hp), array.clear(st_lp)
        array.clear(sf_ht), array.clear(sf_lt), array.clear(sf_hp), array.clear(sf_lp)

        cached_title := title
        
        for i = 0 to array.size(dates) - 1
            bool ok = true
            if tgt_idx > 0 and not f_match(array.get(asia_stats, i), array.get(asia_bk, i), st_asia, bk_asia)
                ok := false
            if tgt_idx > 1 and not f_match(array.get(london_stats, i), array.get(london_bk, i), st_lon, bk_lon)
                ok := false
            if tgt_idx > 2 and not f_match(array.get(ny1_stats, i), array.get(ny1_bk, i), st_ny1, bk_ny1)
                ok := false
            
            int hist_s =  tgt_idx == 0 ? array.get(asia_stats, i) : tgt_idx == 1 ? array.get(london_stats, i) : tgt_idx == 2 ? array.get(ny1_stats, i) : array.get(ny2_stats, i)
            int hist_b =  tgt_idx == 0 ? array.get(asia_bk, i) : tgt_idx == 1 ? array.get(london_bk, i) : tgt_idx == 2 ? array.get(ny1_bk, i) : array.get(ny2_bk, i)
            int live_s =  tgt_idx == 0 ? st_asia : tgt_idx == 1 ? st_lon : tgt_idx == 2 ? st_ny1 : st_ny2
            bool live_b = tgt_idx == 0 ? bk_asia : tgt_idx == 1 ? bk_lon : tgt_idx == 2 ? bk_ny1 : bk_ny2
                
            if ok and f_match(hist_s, hist_b, live_s, live_b)
                total += 1
                _ht = array.get(hod_times, i)
                _lt = array.get(lod_times, i)
                _hp = array.get(hod_pcts, i)
                _lp = array.get(lod_pcts, i)
                _p12h = array.get(t_p12h, i), _p12m = array.get(t_p12m, i), _p12l = array.get(t_p12l, i), _asia = array.get(t_asia_mid, i), _lon = array.get(t_lon_mid, i)

                if hist_s == 1 
                    c_lt += 1
                    array.push(lt_ht, _ht), array.push(lt_lt, _lt), array.push(lt_hp, _hp), array.push(lt_lp, _lp)
                    lt_t_p12h += _p12h, lt_t_p12m += _p12m, lt_t_p12l += _p12l, lt_t_asia += _asia, lt_t_lon += _lon
                else if hist_s == 2 
                    c_lf += 1
                    array.push(lf_ht, _ht), array.push(lf_lt, _lt), array.push(lf_hp, _hp), array.push(lf_lp, _lp)
                    lf_t_p12h += _p12h, lf_t_p12m += _p12m, lf_t_p12l += _p12l, lf_t_asia += _asia, lf_t_lon += _lon
                else if hist_s == 3 
                    c_st += 1
                    array.push(st_ht, _ht), array.push(st_lt, _lt), array.push(st_hp, _hp), array.push(st_lp, _lp)
                    st_t_p12h += _p12h, st_t_p12m += _p12m, st_t_p12l += _p12l, st_t_asia += _asia, st_t_lon += _lon
                else if hist_s == 4 
                    c_sf += 1
                    array.push(sf_ht, _ht), array.push(sf_lt, _lt), array.push(sf_hp, _hp), array.push(sf_lp, _lp)
                    sf_t_p12h += _p12h, sf_t_p12m += _p12m, sf_t_p12l += _p12l, sf_t_asia += _asia, sf_t_lon += _lon
        
        last_tgt_idx := tgt_idx
        last_st_asia := st_asia
        last_st_lon := st_lon
        last_st_ny1 := st_ny1
        last_st_ny2 := st_ny2
        last_bk_asia := bk_asia
        last_bk_lon := bk_lon
        last_bk_ny1 := bk_ny1
        last_bk_ny2 := bk_ny2
    
    table.clear(tbl_res, 0, 0, 11, 4)
    table.cell(tbl_res, 0, 0, cached_title, bgcolor=color.black, text_color=color.white, text_size=sz_r)
    table.cell(tbl_res, 1, 0, "Stats", bgcolor=color.black, text_color=color.white, text_size=sz_r)
    table.cell(tbl_res, 2, 0, "LOD Time", bgcolor=color.black, text_color=color.white, text_size=sz_r)
    table.cell(tbl_res, 3, 0, "HOD Time", bgcolor=color.black, text_color=color.white, text_size=sz_r)
    table.cell(tbl_res, 4, 0, "LOD Dist", bgcolor=color.black, text_color=color.white, text_size=sz_r)
    table.cell(tbl_res, 5, 0, "HOD Dist", bgcolor=color.black, text_color=color.white, text_size=sz_r)
    table.cell(tbl_res, 6, 0, "P12H", bgcolor=color.black, text_color=color.white, text_size=sz_r)
    table.cell(tbl_res, 7, 0, "P12M", bgcolor=color.black, text_color=color.white, text_size=sz_r)
    table.cell(tbl_res, 8, 0, "P12L", bgcolor=color.black, text_color=color.white, text_size=sz_r)
    table.cell(tbl_res, 9, 0, "Asia Mid", bgcolor=color.black, text_color=color.white, text_size=sz_r)
    table.cell(tbl_res, 10, 0, "Lon Mid", bgcolor=color.black, text_color=color.white, text_size=sz_r)

    f_render_row_adv(tbl_res, 1, "Long True", c_lt, total, color.green, sz_r, lt_ht, lt_lt, lt_hp, lt_lp, lt_t_p12h, lt_t_p12m, lt_t_p12l, lt_t_asia, lt_t_lon, d_open, true, false)
    f_render_row_adv(tbl_res, 2, "Long False", c_lf, total, color.gray, sz_r, lf_ht, lf_lt, lf_hp, lf_lp, lf_t_p12h, lf_t_p12m, lf_t_p12l, lf_t_asia, lf_t_lon, d_open, false, true)
    f_render_row_adv(tbl_res, 3, "Short True", c_st, total, color.red, sz_r, st_ht, st_lt, st_hp, st_lp, st_t_p12h, st_t_p12m, st_t_p12l, st_t_asia, st_t_lon, d_open, false, false)
    f_render_row_adv(tbl_res, 4, "Short False", c_sf, total, color.gray, sz_r, sf_ht, sf_lt, sf_hp, sf_lp, sf_t_p12h, sf_t_p12m, sf_t_p12l, sf_t_asia, sf_t_lon, d_open, false, true)

    // Draw Price Model
    f_draw_price_model(st_asia, st_lon, st_ny1, st_ny2, pd_m, d_open)
"""

    fname_ind = OUT_DIR / "ProfilerIndicator.pine"
    with open(fname_ind, "w", encoding='utf-8') as f:
        f.write(ind_header + ind_body_part1 + ind_body_part2 + tail_logic)
    print(f"Generated {fname_ind}")

def main():
    print("Loading data...")
    profiler, hod_lod, touches = load_data("NQ1")
    if not profiler:
        print("Warning: Profiler data missing")
        return

    print("Generating Pine Scripts...")
    generate_scripts(profiler, hod_lod, touches) 
    print("Success!")

if __name__ == "__main__":
    main()
