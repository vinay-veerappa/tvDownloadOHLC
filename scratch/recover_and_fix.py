import re

recovered_text = r'''
// ── Table Helper Functions ──────────────────────────────────────────────────

// Compute streak stats for a boolean array (win/loss)
f_get_boolean_streak_stats(array<bool> wins) =>
    int n = array.size(wins)
    int current = 0
    bool current_is_win = n > 0 ? array.get(wins, n - 1) : false
    int best_win = 0
    int worst_fail = 0
    int total_win_streaks = 0
    int total_fail_streaks = 0
    int sum_win_streak = 0
    int sum_fail_streak = 0
    
    int cur_streak = 0
    if n > 0
        bool prev = array.get(wins, 0)
        cur_streak := 1
        for i = 1 to n - 1
            bool val = array.get(wins, i)
            if val == prev
                cur_streak += 1
            else
                if prev
                    best_win := math.max(best_win, cur_streak)
                    total_win_streaks += 1
                    sum_win_streak += cur_streak
                else
                    worst_fail := math.max(worst_fail, cur_streak)
                    total_fail_streaks += 1
                    sum_fail_streak += cur_streak
                cur_streak := 1
                prev := val
        
        // Final streak
        if prev
            best_win := math.max(best_win, cur_streak)
            total_win_streaks += 1
            sum_win_streak += cur_streak
        else
            worst_fail := math.max(worst_fail, cur_streak)
            total_fail_streaks += 1
            sum_fail_streak += cur_streak
        
        // Current streak
        current := cur_streak
        current_is_win := prev

    avg_win = total_win_streaks > 0 ? float(sum_win_streak) / total_win_streaks : 0.0
    avg_fail = total_fail_streaks > 0 ? float(sum_fail_streak) / total_fail_streaks : 0.0
    [current, current_is_win, best_win, worst_fail, avg_win, avg_fail]

// Compute conditional probability: P(Win | prior sequence)
f_prob_after_streak(array<bool> wins, bool look_for_win, int streak_len) =>
    int n = array.size(wins)
    int count_condition = 0
    int count_success = 0
    if n > streak_len
        for i = 0 to n - (streak_len + 1)
            bool match = true
            for j = 0 to streak_len - 1
                if array.get(wins, i + j) != look_for_win
                    match := false
                    break
            if match
                count_condition += 1
                if array.get(wins, i + streak_len) == true // We always look for next outcome being a WIN
                    count_success += 1
    count_condition == 0 ? na : (float(count_success) / float(count_condition)) * 100.0

// ── Diagnostic Table Modules ────────────────────────────────────────────────

f_draw_summary_table(int idx, string pos, color bg, color border, color header_bg, color header_txt, color body_txt, color bull_clr, color bear_clr, float target_pct) =>
    RSL.RangeSpec sp = array.get(specs, idx)
    RSL.RangeState st = array.get(states, idx)
    STL.ExcursionHistory hist = array.get(histories, idx)
    
    // Combine bull/bear wins for total metrics
    array<bool> all_wins = array.new_bool(0)
    int n_sessions = array.size(hist.dow) // Sample size based on committed days
    if n_sessions > 0
        for i = 0 to n_sessions - 1
            bool day_win = array.get(hist.ev_win_bull, i) or array.get(hist.ev_win_bear, i)
            array.push(all_wins, day_win)
    
    int total_n = array.size(all_wins)
    int total_full = 0
    if total_n > 0
        for i = 0 to total_n - 1
            if array.get(all_wins, i)
                total_full += 1
    int total_failed = total_n - total_full
    float full_rate = total_n > 0 ? (float(total_full) / total_n) * 100.0 : na
    
    // MAE Stats
    array<float> all_mae = array.new_float(0)
    array<float> m_bull = STL.f_build_filtered(hist.mae_bull_abs)
    array<float> m_bear = STL.f_build_filtered(hist.mae_bear_abs)
    if array.size(m_bull) > 0
        for i = 0 to array.size(m_bull) - 1
            array.push(all_mae, array.get(m_bull, i))
    if array.size(m_bear) > 0
        for i = 0 to array.size(m_bear) - 1
            array.push(all_mae, array.get(m_bear, i))
            
    float p50_mae_bull = array.size(m_bull) > 0 ? array.percentile_nearest_rank(m_bull, 50) : na
    float p50_mae_bear = array.size(m_bear) > 0 ? array.percentile_nearest_rank(m_bear, 50) : na

    // Streak Stats
    [cur_s, cur_win, best_w, worst_f, avg_w, avg_f] = f_get_boolean_streak_stats(all_wins)
    
    // Create Table (2 columns)
    // Rows: Header(1) + Summary(6) + Session(7) + Streaks(6) + FrontRun(6) + AfterStreak(7) + Rolling(4) = 37 rows
    table t = Tables.f_new_table(pos, 2, 40, color.new(bg, 90), color.new(border, 75), 1)
    
    int r = 0
    // Header
    Tables.f_draw_header_cell(t, 0, r, "♦ " + sp.name + " ♦", color.new(header_bg, 80), header_txt, "Small", 2, text.align_center)
    r += 1
    
    // Section: SUMMARY
    Tables.f_draw_header_cell(t, 0, r, "♦ SUMMARY ♦", color.new(header_bg, 90), header_txt, "Tiny", 2, text.align_center)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› FULL: " + str.tostring(total_full), na, bull_clr, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, "FAILED: " + str.tostring(total_failed), na, bear_clr, "Small", 1, text.align_left)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› FULL%: " + str.tostring(full_rate, "#.#") + "%", na, bull_clr, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, "N=" + str.tostring(total_n), na, body_txt, "Small", 1, text.align_left)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› p50 MAE ▲", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, STL.f_pct_fmt(p50_mae_bull), na, body_txt, "Small", 1, text.align_left)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› p50 MAE ▼", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, STL.f_pct_fmt(p50_mae_bear), na, body_txt, "Small", 1, text.align_left)
    r += 1
    
    // Section: LIVE SESSION
    Tables.f_draw_header_cell(t, 0, r, "♦ LIVE SESSION ♦", color.new(header_bg, 90), header_txt, "Tiny", 2, text.align_center)
    r += 1
    string status_txt = st.or_building ? "Building" : st.or_complete ? "Active" : "Wait"
    Tables.f_draw_value_cell(t, 0, r, "› Status", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, status_txt, na, body_txt, "Small", 1, text.align_left)
    r += 1
    
    int live_bias = array.get(phase2_live_bias, idx)
    string bearing_txt = live_bias == 1 ? "UP" : live_bias == -1 ? "DOWN" : "NEUTRAL"
    color bearing_clr = live_bias == 1 ? bull_clr : live_bias == -1 ? bear_clr : body_txt
    Tables.f_draw_value_cell(t, 0, r, "› Bearing", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, bearing_txt, na, bearing_clr, "Small", 1, text.align_left)
    r += 1
    
    // Placeholders
    Tables.f_draw_value_cell(t, 0, r, "› FR Zone", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, "---", na, body_txt, "Small", 1, text.align_left)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› FR Price", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, "---", na, body_txt, "Small", 1, text.align_left)
    r += 1
    
    bool is_full = st.daily_bull_mfe >= target_pct or st.daily_bear_mfe >= target_pct
    string res_txt = is_full ? "FULL" : "PENDING"
    color res_clr = is_full ? bull_clr : body_txt
    Tables.f_draw_value_cell(t, 0, r, "› Result", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, res_txt, na, res_clr, "Small", 1, text.align_left)
    r += 1
    
    float entry_px = array.get(phase2_breakout_price, idx)
    Tables.f_draw_value_cell(t, 0, r, "› Entry Price", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, na(entry_px) ? "---" : str.tostring(entry_px, syminfo.format == format.price ? "#.##" : "#.#####"), na, body_txt, "Small", 1, text.align_left)
    r += 1

    // Section: STREAKS
    Tables.f_draw_header_cell(t, 0, r, "♦ STREAKS ♦", color.new(header_bg, 90), header_txt, "Tiny", 2, text.align_center)
    r += 1
    string cur_s_txt = str.tostring(cur_s) + (cur_win ? " Full" : " Failed")
    color cur_s_clr = cur_win ? bull_clr : bear_clr
    Tables.f_draw_value_cell(t, 0, r, "› Current", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, cur_s_txt, na, cur_s_clr, "Small", 1, text.align_left)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› Best Full Run", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, str.tostring(best_w), na, bull_clr, "Small", 1, text.align_left)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› Worst Fail Run", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, str.tostring(worst_f), na, bear_clr, "Small", 1, text.align_left)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› Avg Full Run", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, str.tostring(avg_w, "#.#"), na, bull_clr, "Small", 1, text.align_left)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› Avg Fail Run", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, str.tostring(avg_f, "#.#"), na, bear_clr, "Small", 1, text.align_left)
    r += 1

    // Section: FRONT RUN (Placeholder)
    Tables.f_draw_header_cell(t, 0, r, "♦ FRONT RUN ♦", color.new(header_bg, 90), header_txt, "Tiny", 2, text.align_center)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› Current", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, "---", na, body_txt, "Small", 1, text.align_left)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› Best Full Run", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, "---", na, body_txt, "Small", 1, text.align_left)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› Worst Fail Run", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, "---", na, body_txt, "Small", 1, text.align_left)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› Avg Full Run", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, "---", na, body_txt, "Small", 1, text.align_left)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› Avg Fail Run", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, "---", na, body_txt, "Small", 1, text.align_left)
    r += 1

    // Section: AFTER STREAK
    Tables.f_draw_header_cell(t, 0, r, "♦ AFTER STREAK ♦", color.new(header_bg, 90), header_txt, "Tiny", 2, text.align_center)
    r += 1
    float p_f1 = f_prob_after_streak(all_wins, false, 1)
    float p_f2 = f_prob_after_streak(all_wins, false, 2)
    float p_f3 = f_prob_after_streak(all_wins, false, 3)
    float p_w1 = f_prob_after_streak(all_wins, true, 1)
    float p_w2 = f_prob_after_streak(all_wins, true, 2)
    float p_w3 = f_prob_after_streak(all_wins, true, 3)
    
    Tables.f_draw_value_cell(t, 0, r, "› After 1 Fail", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, STL.f_pct_fmt(p_f1) + " nxt Full", na, not na(p_f1) and p_f1 > 50 ? bull_clr : bear_clr, "Small", 1, text.align_left)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› After 2 Fail", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, STL.f_pct_fmt(p_f2) + " nxt Full", na, not na(p_f2) and p_f2 > 50 ? bull_clr : bear_clr, "Small", 1, text.align_left)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› After 3+ Fail", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, STL.f_pct_fmt(p_f3) + " nxt Full", na, not na(p_f3) and p_f3 > 50 ? bull_clr : bear_clr, "Small", 1, text.align_left)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› After 1 Full", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, STL.f_pct_fmt(p_w1) + " nxt Full", na, not na(p_w1) and p_w1 > 50 ? bull_clr : bear_clr, "Small", 1, text.align_left)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› After 2 Full", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, STL.f_pct_fmt(p_w2) + " nxt Full", na, not na(p_w2) and p_w2 > 50 ? bull_clr : bear_clr, "Small", 1, text.align_left)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› After 3+ Full", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, STL.f_pct_fmt(p_w3) + " nxt Full", na, not na(p_w3) and p_w3 > 50 ? bull_clr : bear_clr, "Small", 1, text.align_left)
    r += 1
    
    // Section: ROLLING (Placeholder)
    Tables.f_draw_header_cell(t, 0, r, "♦ ROLLING ♦", color.new(header_bg, 90), header_txt, "Tiny", 2, text.align_center)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› Last 5", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, "---", na, body_txt, "Small", 1, text.align_left)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› Last 10", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, "---", na, body_txt, "Small", 1, text.align_left)
    r += 1
    Tables.f_draw_value_cell(t, 0, r, "› Last 20", na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, r, "---", na, body_txt, "Small", 1, text.align_left)
    r += 1
    
f_draw_dow_table(int idx, string pos, color bg, color border, color header_bg, color header_txt, color body_txt, color bull_clr, color bear_clr, float target_pct) =>
    RSL.RangeSpec sp = array.get(specs, idx)
    STL.ExcursionHistory hist = array.get(histories, idx)
    
    // Header row + 8 rows (N, Full%, p50 MAE, p75 MAE, p90 MAE, p25 MFE, p50 MFE, p75 MFE)
    // Header col + SUN-FRI (6 cols) = 7 columns
    table t = Tables.f_new_table(pos, 7, 10, color.new(bg, 90), color.new(border, 75), 1)
    
    Tables.f_draw_header_cell(t, 0, 0, "♦ " + sp.name + " — DAY OF WEEK ♦", color.new(header_bg, 80), header_txt, "Small", 7, text.align_center)
    
    array<string> metrics = array.from("METRIC", "› N", "› Full%", "› p50 MAE", "› p75 MAE", "› p90 MAE", "› p25 MFE", "› p50 MFE", "› p75 MFE")
    for mi = 0 to 8
        Tables.f_draw_value_cell(t, 0, mi + 1, array.get(metrics, mi), na, body_txt, "Tiny", 1, text.align_left)
    
    for d = 1 to 6 // SUN to FRI
        string d_name = STL.f_day_full(d)
        Tables.f_draw_header_cell(t, d, 1, d_name, na, header_txt, "Tiny", 1, text.align_center)
        
        // Collect filtered metrics for this day
        array<bool> d_wins = array.new_bool(0)
        array<float> d_mae = array.new_float(0)
        array<float> d_mfe = array.new_float(0)
        
        int n_all = array.size(hist.dow)
        if n_all > 0
            for i = 0 to n_all - 1
                if array.get(hist.dow, i) == d
                    bool win = array.get(hist.ev_win_bull, i) or array.get(hist.ev_win_bear, i)
                    array.push(d_wins, win)
                    float m_b = array.get(hist.mae_bull_abs, i)
                    float m_s = array.get(hist.mae_bear_abs, i)
                    if not na(m_b) and m_b > 0
                        array.push(d_mae, m_b)
                    if not na(m_s) and m_s > 0
                        array.push(d_mae, m_s)
                    float f_b = array.get(hist.mfe_bull, i)
                    float f_s = array.get(hist.mfe_bear, i)
                    if not na(f_b) and f_b > 0
                        array.push(d_mfe, f_b)
                    if not na(f_s) and f_s > 0
                        array.push(d_mfe, f_s)
        
        int n = array.size(d_wins)
        int win_cnt = 0
        if n > 0
            for i = 0 to n - 1
                if array.get(d_wins, i)
                    win_cnt += 1
        float rate = n > 0 ? (float(win_cnt) / n) * 100.0 : 0.0
        
        Tables.f_draw_value_cell(t, d, 2, str.tostring(n), na, body_txt, "Tiny", 1, text.align_center)
        Tables.f_draw_value_cell(t, d, 3, str.tostring(rate, "#.#") + "%", na, rate >= 50 ? bull_clr : bear_clr, "Tiny", 1, text.align_center)
        
        float p50m = array.size(d_mae) > 0 ? array.percentile_nearest_rank(d_mae, 50) : na
        float p75m = array.size(d_mae) > 0 ? array.percentile_nearest_rank(d_mae, 75) : na
        float p90m = array.size(d_mae) > 0 ? array.percentile_nearest_rank(d_mae, 90) : na
        
        float p25f = array.size(d_mfe) > 0 ? array.percentile_nearest_rank(d_mfe, 25) : na
        float p50f = array.size(d_mfe) > 0 ? array.percentile_nearest_rank(d_mfe, 50) : na
        float p75f = array.size(d_mfe) > 0 ? array.percentile_nearest_rank(d_mfe, 75) : na
        
        Tables.f_draw_value_cell(t, d, 4, na(p50m) ? "---" : str.tostring(p50m, "#.###") + "%", na, body_txt, "Tiny", 1, text.align_center)
        Tables.f_draw_value_cell(t, d, 5, na(p75m) ? "---" : str.tostring(p75m, "#.###") + "%", na, body_txt, "Tiny", 1, text.align_center)
        Tables.f_draw_value_cell(t, d, 6, na(p90m) ? "---" : str.tostring(p90m, "#.###") + "%", na, bear_clr, "Tiny", 1, text.align_center)
        
        Tables.f_draw_value_cell(t, d, 7, na(p25f) ? "---" : str.tostring(p25f, "#.###") + "%", na, bull_clr, "Tiny", 1, text.align_center)
        Tables.f_draw_value_cell(t, d, 8, na(p50f) ? "---" : str.tostring(p50f, "#.###") + "%", na, bull_clr, "Tiny", 1, text.align_center)
        Tables.f_draw_value_cell(t, d, 9, na(p75f) ? "---" : str.tostring(p75f, "#.###") + "%", na, bull_clr, "Tiny", 1, text.align_center)

f_draw_updown_table(int idx, string pos, color bg, color border, color header_bg, color header_txt, color body_txt, color bull_clr, color bear_clr, float target_pct) =>
    RSL.RangeSpec sp = array.get(specs, idx)
    STL.ExcursionHistory hist = array.get(histories, idx)
    
    // 2 columns (UP vs DOWN)
    table t = Tables.f_new_table(pos, 2, 10, color.new(bg, 90), color.new(border, 75), 1)
    
    Tables.f_draw_header_cell(t, 0, 0, "♦ " + sp.name + " ♦", color.new(header_bg, 80), header_txt, "Small", 2, text.align_center)
    Tables.f_draw_header_cell(t, 0, 1, "♦ SUMMARY ♦", color.new(header_bg, 90), header_txt, "Tiny", 2, text.align_center)
    
    Tables.f_draw_value_cell(t, 0, 2, "↑ UP", na, bull_clr, "Normal", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, 2, "↓ DOWN", na, bear_clr, "Normal", 1, text.align_left)
    
    int n_bull = array.size(STL.f_build_filtered(hist.mfe_bull))
    int n_bear = array.size(STL.f_build_filtered(hist.mfe_bear))
    int w_bull = 0
    int l_bull = 0
    if array.size(hist.ev_win_bull) > 0
        for i = 0 to array.size(hist.ev_win_bull) - 1
            if array.get(hist.ev_win_bull, i)
                w_bull += 1
            else
                l_bull += 1
    int w_bear = 0
    int l_bear = 0
    if array.size(hist.ev_win_bear) > 0
        for i = 0 to array.size(hist.ev_win_bear) - 1
            if array.get(hist.ev_win_bear, i)
                w_bear += 1
            else
                l_bear += 1
                
    float r_bull = n_bull > 0 ? (float(w_bull) / (w_bull + l_bull)) * 100.0 : 0.0
    float r_bear = n_bear > 0 ? (float(w_bear) / (w_bear + l_bear)) * 100.0 : 0.0
    
    Tables.f_draw_value_cell(t, 0, 3, "› Full  " + str.tostring(w_bull), na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, 3, "› Full  " + str.tostring(w_bear), na, body_txt, "Small", 1, text.align_left)
    int y0 = 4
    Tables.f_draw_value_cell(t, 0, y0, "› Failed " + str.tostring(l_bull), na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, y0, "› Failed " + str.tostring(l_bear), na, body_txt, "Small", 1, text.align_left)
    y0 += 1
    Tables.f_draw_value_cell(t, 0, y0, "› Rate  " + str.tostring(r_bull, "#.#") + "%", na, bull_clr, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, y0, "› Rate  " + str.tostring(r_bear, "#.#") + "%", na, bull_clr, "Small", 1, text.align_left)
    y0 += 1
    
    array<float> mfe_b = STL.f_build_filtered(hist.mfe_bull)
    array<float> mfe_s = STL.f_build_filtered(hist.mfe_bear)
    float p20f_b = array.size(mfe_b) > 0 ? array.percentile_nearest_rank(mfe_b, 20) : na
    float p20f_s = array.size(mfe_s) > 0 ? array.percentile_nearest_rank(mfe_s, 20) : na
    Tables.f_draw_value_cell(t, 0, y0, "› p20 MFE " + STL.f_pct_fmt(p20f_b), na, bull_clr, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, y0, "› p20 MFE " + STL.f_pct_fmt(p20f_s), na, bull_clr, "Small", 1, text.align_left)
    y0 += 1
    
    array<float> mae_b = STL.f_build_filtered(hist.mae_bull_abs)
    array<float> mae_s = STL.f_build_filtered(hist.mae_bear_abs)
    float p50m_b = array.size(mae_b) > 0 ? array.percentile_nearest_rank(mae_b, 50) : na
    float p50m_s = array.size(mae_s) > 0 ? array.percentile_nearest_rank(mae_s, 50) : na
    Tables.f_draw_value_cell(t, 0, y0, "› p50 MAE " + STL.f_pct_fmt(p50m_b), na, body_txt, "Small", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, y0, "› p50 MAE " + STL.f_pct_fmt(p50m_s), na, body_txt, "Small", 1, text.align_left)
    y0 += 1
    
    Tables.f_draw_value_cell(t, 0, y0, "〚N=" + str.tostring(w_bull+l_bull) + "〛", na, body_txt, "Tiny", 1, text.align_left)
    Tables.f_draw_value_cell(t, 1, y0, "〚TF=" + str.tostring(timeframe.multiplier) + "〛", na, body_txt, "Tiny", 1, text.align_left)


if barstate.islast and i_show_table and array.size(specs) > 0
    int idx = f_focus_idx()
    RSL.RangeSpec sp = array.get(specs, idx)
    STL.ExcursionHistory hist = array.get(histories, idx)
    RSL.RangeState st = array.get(states, idx)

    if i_table_view == "Summary"
        f_draw_summary_table(idx, Tables.f_table_pos(i_table_pos), table_bg_color_resolved, table_border_color_resolved, table_header_bg_color_resolved, table_header_text_color_resolved, table_body_text_color, table_bull_color, table_bear_color, i_ev_target_pct)
    else if i_table_view == "DOW Diagnostic"
        f_draw_dow_table(idx, Tables.f_table_pos(i_table_pos), table_bg_color_resolved, table_border_color_resolved, table_header_bg_color_resolved, table_header_text_color_resolved, table_body_text_color, table_bull_color, table_bear_color, i_ev_target_pct)
    else if i_table_view == "Up/Down"
        f_draw_updown_table(idx, Tables.f_table_pos(i_table_pos), table_bg_color_resolved, table_border_color_resolved, table_header_bg_color_resolved, table_header_text_color_resolved, table_body_text_color, table_bull_color, table_bear_color, i_ev_target_pct)
    else
        // Legacy Views
        bool is_dow = i_table_view == "DOW View"
        int n_cols = is_dow ? 3 : 6
        int n_rows = is_dow ? 6 : 3
        table t = Tables.f_new_table(Tables.f_table_pos(i_table_pos), n_cols, n_rows, color.new(table_bg_color_resolved, 85), color.new(table_border_color_resolved, 70), 1)

        // Header row
        Tables.f_draw_header_cell(t, 0, 0, sp.name + " - " + i_table_view, color.new(table_header_bg_color_resolved, 70), table_header_text_color_resolved, "Small", 1, text.align_center)
        if is_dow
            Tables.f_draw_header_cell(t, 1, 0, "Count", color.new(table_header_bg_color_resolved, 70), table_header_text_color_resolved, "Small", 1, text.align_center)
            Tables.f_draw_header_cell(t, 2, 0, "Avg MFE", color.new(table_header_bg_color_resolved, 70), table_header_text_color_resolved, "Small", 1, text.align_center)
        else
            Tables.f_draw_header_cell(t, 1, 0, "Count", color.new(table_header_bg_color_resolved, 70), table_header_text_color_resolved, "Small", 1, text.align_center)
            Tables.f_draw_header_cell(t, 2, 0, "P50", color.new(table_header_bg_color_resolved, 70), table_header_text_color_resolved, "Small", 1, text.align_center)
            Tables.f_draw_header_cell(t, 3, 0, "P75", color.new(table_header_bg_color_resolved, 70), table_header_text_color_resolved, "Small", 1, text.align_center)
            Tables.f_draw_header_cell(t, 4, 0, "P90", color.new(table_header_bg_color_resolved, 70), table_header_text_color_resolved, "Small", 1, text.align_center)
            Tables.f_draw_header_cell(t, 5, 0, "Rate", color.new(table_header_bg_color_resolved, 70), table_header_text_color_resolved, "Small", 1, text.align_center)

        if i_table_view == "MFE View"
            array<float> bull = STL.f_build_filtered(hist.mfe_bull)
            array<float> bear = STL.f_build_filtered(hist.mfe_bear)
            float b50 = array.size(bull) > 0 ? array.percentile_nearest_rank(bull, 50) : na
            float b75 = array.size(bull) > 0 ? array.percentile_nearest_rank(bull, 75) : na
            float b90 = array.size(bull) > 0 ? array.percentile_nearest_rank(bull, 90) : na
            float s50 = array.size(bear) > 0 ? array.percentile_nearest_rank(bear, 50) : na
            float s75 = array.size(bear) > 0 ? array.percentile_nearest_rank(bear, 75) : na
            float s90 = array.size(bear) > 0 ? array.percentile_nearest_rank(bear, 90) : na
            Tables.f_draw_value_cell(t, 0, 1, "Bull", na, table_bull_color, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 1, 1, str.tostring(array.size(bull)), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 2, 1, STL.f_pct_fmt(b50), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 3, 1, STL.f_pct_fmt(b75), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 4, 1, STL.f_pct_fmt(b90), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 5, 1, "-", na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 0, 2, "Bear", na, table_bear_color, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 1, 2, str.tostring(array.size(bear)), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 2, 2, STL.f_pct_fmt(s50), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 3, 2, STL.f_pct_fmt(s75), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 4, 2, STL.f_pct_fmt(s90), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 5, 2, "-", na, na, "Normal", 1, text.align_center)
        else if i_table_view == "MAE View"
            array<float> mab = STL.f_build_filtered(hist.mae_bull_abs)
            array<float> mas = STL.f_build_filtered(hist.mae_bear_abs)
            array<float> mpb = STL.f_build_filtered(hist.mae_bull_pb)
            array<float> mps = STL.f_build_filtered(hist.mae_bear_pb)
            float rb = array.size(hist.r_multiple_bull) > 0 ? array.avg(hist.r_multiple_bull) : na
            float rs = array.size(hist.r_multiple_bear) > 0 ? array.avg(hist.r_multiple_bear) : na
            Tables.f_draw_value_cell(t, 0, 1, "Bull Abs/PB", na, table_bull_color, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 1, 1, str.tostring(array.size(mab)), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 2, 1, STL.f_pct_fmt(array.size(mab) > 0 ? array.percentile_nearest_rank(mab, 50) : na), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 3, 1, STL.f_pct_fmt(array.size(mab) > 0 ? array.percentile_nearest_rank(mab, 75) : na), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 4, 1, STL.f_pct_fmt(array.size(mpb) > 0 ? array.percentile_nearest_rank(mpb, 50) : na), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 5, 1, na(rb) ? "n/a" : str.tostring(rb, "#.##"), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 0, 2, "Bear Abs/PB", na, table_bear_color, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 1, 2, str.tostring(array.size(mas)), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 2, 2, STL.f_pct_fmt(array.size(mas) > 0 ? array.percentile_nearest_rank(mas, 50) : na), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 3, 2, STL.f_pct_fmt(array.size(mas) > 0 ? array.percentile_nearest_rank(mas, 75) : na), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 4, 2, STL.f_pct_fmt(array.size(mps) > 0 ? array.percentile_nearest_rank(mps, 50) : na), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 5, 2, na(rs) ? "n/a" : str.tostring(rs, "#.##"), na, na, "Normal", 1, text.align_center)
        else if i_table_view == "Fake View"
            array<float> fake_mfe_bull = STL.f_build_filtered(hist.fake_mfe_bull)
            array<float> fake_mfe_bear = STL.f_build_filtered(hist.fake_mfe_bear)
            array<float> fake_mae_bull = STL.f_build_filtered(hist.fake_mae_bull)
            array<float> fake_mae_bear = STL.f_build_filtered(hist.fake_mae_bear)
            float b25 = array.size(fake_mfe_bull) > 0 ? array.percentile_nearest_rank(fake_mfe_bull, 25) : na
            float b50 = array.size(fake_mfe_bull) > 0 ? array.percentile_nearest_rank(fake_mfe_bull, 50) : na
            float b75 = array.size(fake_mfe_bull) > 0 ? array.percentile_nearest_rank(fake_mfe_bull, 75) : na
            float b90 = array.size(fake_mfe_bull) > 0 ? array.percentile_nearest_rank(fake_mfe_bull, 90) : na
            float s25 = array.size(fake_mfe_bear) > 0 ? array.percentile_nearest_rank(fake_mfe_bear, 25) : na
            float s50 = array.size(fake_mfe_bear) > 0 ? array.percentile_nearest_rank(fake_mfe_bear, 50) : na
            float s75 = array.size(fake_mfe_bear) > 0 ? array.percentile_nearest_rank(fake_mfe_bear, 75) : na
            float s90 = array.size(fake_mfe_bear) > 0 ? array.percentile_nearest_rank(fake_mfe_bear, 90) : na
            float rb25 = array.size(fake_mae_bull) > 0 ? array.percentile_nearest_rank(fake_mae_bull, 25) : na
            float rb50 = array.size(fake_mae_bull) > 0 ? array.percentile_nearest_rank(fake_mae_bull, 50) : na
            float rb75 = array.size(fake_mae_bull) > 0 ? array.percentile_nearest_rank(fake_mae_bull, 75) : na
            float rb90 = array.size(fake_mae_bull) > 0 ? array.percentile_nearest_rank(fake_mae_bull, 90) : na
            float rs25 = array.size(fake_mae_bear) > 0 ? array.percentile_nearest_rank(fake_mae_bear, 25) : na
            float rs50 = array.size(fake_mae_bear) > 0 ? array.percentile_nearest_rank(fake_mae_bear, 50) : na
            float rs75 = array.size(fake_mae_bear) > 0 ? array.percentile_nearest_rank(fake_mae_bear, 75) : na
            float rs90 = array.size(fake_mae_bear) > 0 ? array.percentile_nearest_rank(fake_mae_bear, 90) : na
            float dbr = STL.f_double_break_rate(hist.double_break, hist.entry_triggered_bull, hist.entry_triggered_bear)
            Tables.f_draw_value_cell(t, 0, 1, "Bull Fake", na, table_bull_color, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 1, 1, STL.f_pct_fmt(b50), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 2, 1, STL.f_pct_fmt(b75), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 3, 1, STL.f_pct_fmt(rb50), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 4, 1, STL.f_pct_fmt(rb90), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 5, 1, STL.f_pct_fmt(dbr), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 0, 2, "Bear Fake", na, table_bear_color, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 1, 2, STL.f_pct_fmt(s50), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 2, 2, STL.f_pct_fmt(s75), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 3, 2, STL.f_pct_fmt(rs50), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 4, 2, STL.f_pct_fmt(rs90), na, na, "Normal", 1, text.align_center)
            Tables.f_draw_value_cell(t, 5, 2, STL.f_pct_fmt(dbr), na, na, "Normal", 1, text.align_center)
        else if i_table_view == "DOW View"
            for d = 1 to 6
                string d_name = STL.f_day_full(d)
                Tables.f_draw_header_cell(t, 0, d, d_name, na, table_header_text_color_resolved, "Small", 1, text.align_center)
                int cnt = 0
                float sum_b = 0.0
                float sum_s = 0.0
                int n_all = array.size(hist.dow)
                if n_all > 0
                    for j = 0 to n_all - 1
                        if array.get(hist.dow, j) == d
                            cnt += 1
                            sum_b += array.get(hist.mfe_bull, j)
                            sum_s += array.get(hist.mfe_bear, j)
                float avg_net = cnt == 0 ? na : (sum_b + sum_s) / float(2 * cnt)
                Tables.f_draw_value_cell(t, 1, d, str.tostring(cnt), na, na, "Small", 1, text.align_center)
                Tables.f_draw_value_cell(t, 2, d, STL.f_pct_fmt(avg_net), na, na, "Small", 1, text.align_center)
'''

with open(r'c:\Users\vinay\tvDownloadOHLC\scripts\indicators\daily-ny-levels\DailyNYLevelsAnalytics.pine', 'r', encoding='utf-8') as f:
    text = f.read()

idx = text.find('if barstate.islast and i_show_table and array.size(specs) > 0')
if idx != -1:
    # Just to be safe, find if it starts somewhere earlier like focus
    focus_idx = text.find('f_focus_idx() =>')
    if focus_idx != -1:
        # We need to splice out everything after f_focus_idx / or the previous block
        idx = focus_idx
        # wait! f_focus_idx() => ... needs to be included before my recovered text!
        pass
    
    # We will replace from "if barstate.islast and i_show_table and array.size(specs) > 0"
    # Actually wait. `recovered_text` does not include `f_focus_idx() =>`. 
    # Let me check my recovered text: wait, I didn't include `f_focus_idx` because it's BEFORE the injection point `// ── Table Helper Functions`
    pass

    split_str = '// ── Table Helper Functions'
    target_idx = text.find(split_str)
    if target_idx == -1:
        # It's an older version of the file without this comment.
        # Actually in the 1121 line file, it currently has line 1005 `if barstate.islast...`
        target_idx = text.find('if barstate.islast and i_show_table and array.size(specs) > 0')

    # splice
    text = text[:target_idx] + recovered_text
    
    with open(r'c:\Users\vinay\tvDownloadOHLC\scripts\indicators\daily-ny-levels\DailyNYLevelsAnalytics.pine', 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"Rescue successful. Target idx: {target_idx}")
else:
    print("Could not find the injection point.")

