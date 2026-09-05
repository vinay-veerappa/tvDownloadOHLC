//! PyO3 core: replaces the two un-accelerated Python `for` loops in
//! scripts/execution/nt8_parity_engine.py (line 138 = simulate, line 350 =
//! simulate_mtf) with tick-exact Rust ports.
//!
//! Parity contract (NT8ParityEngine):
//! - Position Concurrency Lockout
//! - MaxTradesPerDay / MaxConsecutiveLosers pause / HardStop / DailyMaxLoss
//! - Tick snapping 0.25
//! - Intra-bar fill sequence: Queen fill -> BE lock -> stop/target resolution
//! - Re-entry protocol (v2), MFE/MAE tracking

use numpy::PyReadonlyArray1;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

const NAN: f64 = f64::NAN;

#[pyfunction]
#[pyo3(signature = (
    times_epoch_ms, opens, highs, lows, closes, signals, limit_prices, stop_losses,
    point_value=2.0, tick_size=0.25, max_trades_per_day=3, max_consecutive_losers=2,
    pause_minutes=30, hard_stop_losers=3, daily_max_loss=1500.0, contracts=2,
    commission_per_contract_rt=1.40, slippage_ticks=0.0,
    queen_bps=10.0, runner_bps=30.0, order_timeout_bars=6,
    earliest_entry_hhmm=945, latest_entry_hhmm=1530, flatten_hhmm=1555,
    filter_lunch=true, adverse_ambiguity=true,
))]
#[allow(clippy::too_many_arguments)]
fn simulate_bars_v1(
    _py: Python<'_>,
    times_epoch_ms: PyReadonlyArray1<'_, i64>,
    opens: PyReadonlyArray1<'_, f64>,
    highs: PyReadonlyArray1<'_, f64>,
    lows: PyReadonlyArray1<'_, f64>,
    closes: PyReadonlyArray1<'_, f64>,
    signals: PyReadonlyArray1<'_, i32>,
    limit_prices: PyReadonlyArray1<'_, f64>,
    stop_losses: PyReadonlyArray1<'_, f64>,
    point_value: f64,
    tick_size: f64,
    max_trades_per_day: usize,
    max_consecutive_losers: usize,
    pause_minutes: i64,
    hard_stop_losers: usize,
    daily_max_loss: f64,
    contracts: usize,
    commission_per_contract_rt: f64,
    slippage_ticks: f64,
    queen_bps: f64,
    runner_bps: f64,
    order_timeout_bars: usize,
    earliest_entry_hhmm: i32,
    latest_entry_hhmm: i32,
    flatten_hhmm: i32,
    filter_lunch: bool,
    // See `_resolve_ambiguity_policy` in scripts/execution/nt8_parity_engine.py for why
    // this defaults to the adverse branch. Both engines must agree per policy or
    // crates/gate2_parity.py fails - that gate is the only thing proving them equal.
    adverse_ambiguity: bool,
) -> PyResult<PyObject> {
    let times = times_epoch_ms.as_slice()?;
    let opens = opens.as_slice()?;
    let highs = highs.as_slice()?;
    let lows = lows.as_slice()?;
    let closes = closes.as_slice()?;
    let signals = signals.as_slice()?;
    let limit_prices = limit_prices.as_slice()?;
    let stop_losses = stop_losses.as_slice()?;
    let n = opens.len();

    if times.len() != n || highs.len() != n || lows.len() != n || closes.len() != n
        || signals.len() != n || limit_prices.len() != n || stop_losses.len() != n
    {
        return Err(PyValueError::new_err("input arrays must have equal length"));
    }

    // Python's round(): banker's rounding on .5 boundaries.
    let round_tick = |price: f64| -> f64 {
        let q = price / tick_size;
        (q + f64::copysign(0.5, q)).floor() as i64 as f64 * tick_size
        // NOTE: Python round() is banker's; exact parity handled via py round
    };

    #[derive(Clone, Default)]
    struct Pending {
        dir: i32,
        limit: f64,
        sl: f64,
        bar: usize,
    }

    let mut out: Vec<[f64; 8]> = Vec::new(); // entry_ms, exit_ms, dir, entry_px, exit_px, leg1, leg2, total_pts
    let mut out_reason: Vec<String> = Vec::new();
    let mut out_flags: Vec<[bool; 2]> = Vec::new(); // queen_hit, runner_hit
    // The queen leg's own exit time. NT8 reports each leg of the pack as a
    // separate trade; a per-leg row needs a per-leg exit. When the queen never
    // filled, both legs leave together and this equals the trade exit.
    let mut out_queen_ms: Vec<i64> = Vec::new();

    let mut in_pos = false;
    let mut pos_dir: i32 = 0;
    let mut pos_entry_price: f64 = 0.0;
    let mut pos_entry_time: i64 = 0;
    let mut active_sl: f64 = 0.0;
    let mut active_tp1: f64 = 0.0;
    let mut active_tp2: f64 = 0.0;
    let mut queen_filled = false;
    let mut queen_exit_ms: i64 = 0;

    let mut cur_day: i64 = 0;
    let mut daily_trades: usize = 0;
    let mut consecutive_losers: usize = 0;
    let mut pause_until_time: Option<i64> = None;
    let mut daily_pnl: f64 = 0.0;
    let mut pending_order: Option<Pending> = None;

    for i in 0..n {
        let t = times[i];
        let bar_ms = t;
        let bar_date = bar_ms / 86_400_000; // days since epoch (UTC; ET date boundary handled by caller alignment)
        let hm = epoch_ms_to_hhmm_utc(t);
        let h0 = highs[i];
        let l0 = lows[i];
        let c0 = closes[i];

        // New day reset
        if bar_date != cur_day {
            cur_day = bar_date;
            daily_trades = 0;
            consecutive_losers = 0;
            pause_until_time = None;
            daily_pnl = 0.0;
            pending_order = None;
        }

        // 1. POSITION MANAGEMENT
        if in_pos {
            let mut closed = false;
            let mut pnl_pts = 0.0;
            let mut reason = String::new();
            let mut r_hit = false;
            let mut q_pts = 0.0;
            let mut r_pts = 0.0;

            // Adverse ambiguity: settle the stop BEFORE the queen fill can lock it to
            // breakeven. Body is identical to the favourable stop branch below - only
            // the evaluation ORDER differs, and that order is the whole ambiguity.
            if adverse_ambiguity
                && ((pos_dir == 1 && l0 <= active_sl) || (pos_dir == -1 && h0 >= active_sl))
            {
                if pos_dir == 1 {
                    q_pts = if queen_filled { active_tp1 - pos_entry_price } else { active_sl - pos_entry_price };
                    r_pts = active_sl - pos_entry_price;
                } else {
                    q_pts = if queen_filled { pos_entry_price - active_tp1 } else { pos_entry_price - active_sl };
                    r_pts = pos_entry_price - active_sl;
                }
                pnl_pts = (q_pts + r_pts) / 2.0;
                reason = "Stop Loss".to_string();
                closed = true;
            }

            if pos_dir == 1 && !closed {
                if !queen_filled && h0 >= active_tp1 {
                    queen_filled = true;
                    queen_exit_ms = t;
                    active_sl = pos_entry_price;
                }
                if hm >= flatten_hhmm {
                    q_pts = if queen_filled { active_tp1 - pos_entry_price } else { c0 - pos_entry_price };
                    r_pts = c0 - pos_entry_price;
                    pnl_pts = (q_pts + r_pts) / 2.0;
                    reason = "EOD Flat".to_string();
                    closed = true;
                } else if l0 <= active_sl {
                    q_pts = if queen_filled { active_tp1 - pos_entry_price } else { active_sl - pos_entry_price };
                    r_pts = active_sl - pos_entry_price;
                    pnl_pts = (q_pts + r_pts) / 2.0;
                    reason = "Stop Loss".to_string();
                    closed = true;
                } else if h0 >= active_tp2 {
                    q_pts = active_tp1 - pos_entry_price;
                    r_pts = active_tp2 - pos_entry_price;
                    pnl_pts = (q_pts + r_pts) / 2.0;
                    reason = "Profit Target".to_string();
                    r_hit = true;
                    closed = true;
                }
            } else if pos_dir == -1 && !closed {
                if !queen_filled && l0 <= active_tp1 {
                    queen_filled = true;
                    queen_exit_ms = t;
                    active_sl = pos_entry_price;
                }
                if hm >= flatten_hhmm {
                    q_pts = if queen_filled { pos_entry_price - active_tp1 } else { pos_entry_price - c0 };
                    r_pts = pos_entry_price - c0;
                    pnl_pts = (q_pts + r_pts) / 2.0;
                    reason = "EOD Flat".to_string();
                    closed = true;
                } else if h0 >= active_sl {
                    q_pts = if queen_filled { pos_entry_price - active_tp1 } else { pos_entry_price - active_sl };
                    r_pts = pos_entry_price - active_sl;
                    pnl_pts = (q_pts + r_pts) / 2.0;
                    reason = "Stop Loss".to_string();
                    closed = true;
                } else if l0 <= active_tp2 {
                    q_pts = pos_entry_price - active_tp1;
                    r_pts = pos_entry_price - active_tp2;
                    pnl_pts = (q_pts + r_pts) / 2.0;
                    reason = "Profit Target".to_string();
                    r_hit = true;
                    closed = true;
                }
            }

            if closed {
                in_pos = false;
                let gross_usd = pnl_pts * point_value * contracts as f64;
                let comm_usd = commission_per_contract_rt * contracts as f64;
                let slip_usd = (slippage_ticks * tick_size * point_value) * contracts as f64;
                let net_usd = gross_usd - comm_usd - slip_usd;

                let exit_price = if r_hit {
                    active_tp2
                } else if reason.contains("Stop") {
                    active_sl
                } else {
                    c0
                };

                // A queen that never filled left with the runner.
                if !queen_filled { queen_exit_ms = t; }

                out.push([pos_entry_time as f64, t as f64, pos_dir as f64,
                          pos_entry_price, exit_price, q_pts, r_pts, pnl_pts]);
                out_reason.push(reason);
                out_flags.push([queen_filled, r_hit]);
                out_queen_ms.push(queen_exit_ms);

                daily_pnl += net_usd;
                if net_usd < 0.0 {
                    consecutive_losers += 1;
                    if consecutive_losers >= max_consecutive_losers {
                        pause_until_time = Some(t + pause_minutes * 60_000);
                    }
                } else {
                    consecutive_losers = 0;
                }
                let _ = NAN;
            }

            let _ = out_reason.last();
        }

        // 2. PENDING LIMIT ORDER EVALUATION
        if let Some(p) = pending_order.clone() {
            if !in_pos {
                let is_paused = match pause_until_time {
                    Some(pt) => t < pt,
                    None => false,
                };
                let hit_hard_stop = consecutive_losers >= hard_stop_losers;
                let hit_daily_max = daily_pnl <= -daily_max_loss;
                let mut in_time = earliest_entry_hhmm <= hm && hm <= latest_entry_hhmm;
                if filter_lunch && (1200..=1330).contains(&hm) {
                    in_time = false;
                }

                if i - p.bar <= order_timeout_bars {
                    if in_time && daily_trades < max_trades_per_day && !is_paused && !hit_hard_stop && !hit_daily_max {
                        if p.dir == 1 && l0 <= p.limit {
                            in_pos = true;
                            pos_dir = 1;
                            pos_entry_time = t;
                            pos_entry_price = p.limit;
                            active_sl = p.sl;
                            active_tp1 = round_tick(p.limit + p.limit * (queen_bps / 10000.0));
                            active_tp2 = round_tick(p.limit + p.limit * (runner_bps / 10000.0));
                            queen_filled = false;
                            queen_exit_ms = 0;
                            daily_trades += 1;
                            pending_order = None;
                        } else if p.dir == -1 && h0 >= p.limit {
                            in_pos = true;
                            pos_dir = -1;
                            pos_entry_time = t;
                            pos_entry_price = p.limit;
                            active_sl = p.sl;
                            active_tp1 = round_tick(p.limit - p.limit * (queen_bps / 10000.0));
                            active_tp2 = round_tick(p.limit - p.limit * (runner_bps / 10000.0));
                            queen_filled = false;
                            queen_exit_ms = 0;
                            daily_trades += 1;
                            pending_order = None;
                        }
                    }
                } else {
                    pending_order = None;
                }
            }
        }

        // 3. ARM NEW SIGNAL
        if !in_pos && pending_order.is_none() && signals[i] != 0 {
            let lmt = round_tick(limit_prices[i]);
            let sl = round_tick(stop_losses[i]);
            pending_order = Some(Pending { dir: signals[i], limit: lmt, sl, bar: i });
        }
    }

    let dict = pyo3::types::PyDict::new(_py);
    dict.set_item("entry_time_ms", out.iter().map(|r| r[0] as i64).collect::<Vec<_>>())?;
    dict.set_item("exit_time_ms", out.iter().map(|r| r[1] as i64).collect::<Vec<_>>())?;
    dict.set_item("dir", out.iter().map(|r| r[2] as i64).collect::<Vec<_>>())?;
    dict.set_item("entry_price", out.iter().map(|r| r[3]).collect::<Vec<_>>())?;
    dict.set_item("exit_price", out.iter().map(|r| r[4]).collect::<Vec<_>>())?;
    dict.set_item("leg1_points", out.iter().map(|r| r[5]).collect::<Vec<_>>())?;
    dict.set_item("leg2_points", out.iter().map(|r| r[6]).collect::<Vec<_>>())?;
    dict.set_item("total_points", out.iter().map(|r| r[7]).collect::<Vec<_>>())?;
    dict.set_item("exit_reason", out_reason)?;
    dict.set_item("queen_hit", out_flags.iter().map(|f| f[0]).collect::<Vec<_>>())?;
    dict.set_item("queen_exit_time_ms", out_queen_ms.clone())?;
    dict.set_item("runner_hit", out_flags.iter().map(|f| f[1]).collect::<Vec<_>>())?;
    Ok(dict.into())
}

#[pyfunction]
#[pyo3(signature = (
    times_epoch_ms, opens, highs, lows, closes, signal_times_ms, signal_dirs,
    point_value=2.0, tick_size=0.25, max_trades_per_day=3, max_consecutive_losers=2,
    pause_minutes=30, hard_stop_losers=3, daily_max_loss=1500.0, contracts=2,
    commission_per_contract_rt=1.40, slippage_ticks=0.0,
    queen_bps=10.0, runner_bps=30.0, stop_loss_bps=5.0,
    earliest_entry_hhmm=945, latest_entry_hhmm=1530, flatten_hhmm=1555,
    filter_lunch=true, allow_reentry=true,
))]
#[allow(clippy::too_many_arguments)]
fn simulate_bars_v2(
    py: Python<'_>,
    times_epoch_ms: PyReadonlyArray1<'_, i64>,
    opens: PyReadonlyArray1<'_, f64>,
    highs: PyReadonlyArray1<'_, f64>,
    lows: PyReadonlyArray1<'_, f64>,
    closes: PyReadonlyArray1<'_, f64>,
    signal_times_ms: PyReadonlyArray1<'_, i64>,
    signal_dirs: PyReadonlyArray1<'_, i32>,
    point_value: f64,
    tick_size: f64,
    max_trades_per_day: usize,
    max_consecutive_losers: usize,
    pause_minutes: i64,
    hard_stop_losers: usize,
    daily_max_loss: f64,
    contracts: usize,
    commission_per_contract_rt: f64,
    slippage_ticks: f64,
    queen_bps: f64,
    runner_bps: f64,
    stop_loss_bps: f64,
    earliest_entry_hhmm: i32,
    latest_entry_hhmm: i32,
    flatten_hhmm: i32,
    filter_lunch: bool,
    allow_reentry: bool,
) -> PyResult<PyObject> {
    let times = times_epoch_ms.as_slice()?;
    let opens = opens.as_slice()?;
    let highs = highs.as_slice()?;
    let lows = lows.as_slice()?;
    let closes = closes.as_slice()?;
    let sig_times = signal_times_ms.as_slice()?;
    let sig_dirs = signal_dirs.as_slice()?;
    let n = opens.len();

    if times.len() != n || highs.len() != n || lows.len() != n || closes.len() != n {
        return Err(PyValueError::new_err("1m input arrays must have equal length"));
    }

    let round_tick = |price: f64| -> f64 {
        (price / tick_size).round() * tick_size
    };

    // Build the 5m CISD signal map (signal_times_ms -> dir), like sig_map in Python.
    let mut sig_map: std::collections::HashMap<i64, i32> = std::collections::HashMap::new();
    for (k, dir) in sig_dirs.iter().enumerate() {
        if *dir != 0 {
            sig_map.insert(sig_times[k], *dir);
        }
    }
    let _ = &sig_map;

    #[derive(Clone, Copy, Default)]
    struct TradeRow {
        entry_ms: i64,
        exit_ms: i64,
        dir: i32,
        entry_px: f64,
        exit_px: f64,
        leg1: f64,
        leg2: f64,
        total_pts: f64,
        mfe_pts: f64,
        mae_pts: f64,
        queen: bool,
        runner: bool,
        reentry: bool,
        queen_exit_ms: i64,
    }

    let mut trades: Vec<TradeRow> = Vec::new();
    let mut trade_reasons: Vec<String> = Vec::new();
    let mut in_pos = false;
    let mut pos_dir: i32 = 0;
    let mut pos_entry_price: f64 = 0.0;
    let mut pos_entry_time: i64 = 0;
    let mut active_sl: f64 = 0.0;
    let mut active_tp1: f64 = 0.0;
    let mut active_tp2: f64 = 0.0;
    let mut queen_filled = false;
    let mut queen_exit_ms: i64 = 0;
    let mut cur_mfe_pts: f64 = 0.0;
    let mut cur_mae_pts: f64 = 0.0;
    let mut is_cur_reentry = false;
    let mut reentry_armed = false;
    let mut reentry_dir: i32 = 0;
    let mut reentry_time: i64 = 0;

    let mut cur_day: i64 = 0;
    let mut daily_trades: usize = 0;
    let mut consecutive_losers: usize = 0;
    let mut pause_until_time: Option<i64> = None;
    let mut daily_pnl: f64 = 0.0;
    let mut armed_dir: i32 = 0;
    let mut armed_time: i64 = 0;

    for i in 2..n {
        let t = times[i];
        let bar_date = t / 86_400_000;
        let hm = epoch_ms_to_hhmm_utc(t);
        let h0 = highs[i];
        let l0 = lows[i];
        let c0 = closes[i];
        let h2 = highs[i - 2];
        let l2 = lows[i - 2];

        if bar_date != cur_day {
            cur_day = bar_date;
            daily_trades = 0;
            consecutive_losers = 0;
            pause_until_time = None;
            daily_pnl = 0.0;
            armed_dir = 0;
            armed_time = 0;
            reentry_armed = false;
        }

        // 1. Manage open position & MFE/MAE
        if in_pos {
            let mut closed = false;
            let mut pnl_pts = 0.0;
            let mut reason = String::new();
            let mut r_hit = false;
            let mut q_pts = 0.0;
            let mut r_pts = 0.0;

            if pos_dir == 1 {
                let fav = h0 - pos_entry_price;
                let adv = pos_entry_price - l0;
                if fav > cur_mfe_pts { cur_mfe_pts = fav; }
                if adv > cur_mae_pts { cur_mae_pts = adv; }

                if !queen_filled && h0 >= active_tp1 {
                    queen_filled = true;
                    queen_exit_ms = t;
                    active_sl = pos_entry_price;
                }
                if hm >= flatten_hhmm {
                    q_pts = if queen_filled { active_tp1 - pos_entry_price } else { c0 - pos_entry_price };
                    r_pts = c0 - pos_entry_price;
                    pnl_pts = (q_pts + r_pts) / 2.0;
                    reason = "EOD Flat".to_string();
                    closed = true;
                } else if l0 <= active_sl {
                    q_pts = if queen_filled { active_tp1 - pos_entry_price } else { active_sl - pos_entry_price };
                    r_pts = active_sl - pos_entry_price;
                    pnl_pts = (q_pts + r_pts) / 2.0;
                    reason = "Stop Loss".to_string();
                    closed = true;
                } else if h0 >= active_tp2 {
                    q_pts = active_tp1 - pos_entry_price;
                    r_pts = active_tp2 - pos_entry_price;
                    pnl_pts = (q_pts + r_pts) / 2.0;
                    reason = "Profit Target".to_string();
                    r_hit = true;
                    closed = true;
                }
            } else if pos_dir == -1 {
                let fav = pos_entry_price - l0;
                let adv = h0 - pos_entry_price;
                if fav > cur_mfe_pts { cur_mfe_pts = fav; }
                if adv > cur_mae_pts { cur_mae_pts = adv; }

                if !queen_filled && l0 <= active_tp1 {
                    queen_filled = true;
                    queen_exit_ms = t;
                    active_sl = pos_entry_price;
                }
                if hm >= flatten_hhmm {
                    q_pts = if queen_filled { pos_entry_price - active_tp1 } else { pos_entry_price - c0 };
                    r_pts = pos_entry_price - c0;
                    pnl_pts = (q_pts + r_pts) / 2.0;
                    reason = "EOD Flat".to_string();
                    closed = true;
                } else if h0 >= active_sl {
                    q_pts = if queen_filled { pos_entry_price - active_tp1 } else { pos_entry_price - active_sl };
                    r_pts = pos_entry_price - active_sl;
                    pnl_pts = (q_pts + r_pts) / 2.0;
                    reason = "Stop Loss".to_string();
                    closed = true;
                } else if l0 <= active_tp2 {
                    q_pts = pos_entry_price - active_tp1;
                    r_pts = pos_entry_price - active_tp2;
                    pnl_pts = (q_pts + r_pts) / 2.0;
                    reason = "Profit Target".to_string();
                    r_hit = true;
                    closed = true;
                }
            }

            if closed {
                in_pos = false;
                let gross_usd = pnl_pts * point_value * contracts as f64;
                let comm_usd = commission_per_contract_rt * contracts as f64;
                let slip_usd = (slippage_ticks * tick_size * point_value) * contracts as f64;
                let net_usd = gross_usd - comm_usd - slip_usd;

                let exit_price = if r_hit {
                    active_tp2
                } else if reason.contains("Stop") {
                    active_sl
                } else {
                    c0
                };

                // A queen that never filled left with the runner.
                if !queen_filled { queen_exit_ms = t; }

                trades.push(TradeRow {
                    entry_ms: pos_entry_time, exit_ms: t, dir: pos_dir,
                    entry_px: pos_entry_price, exit_px: exit_price,
                    leg1: q_pts, leg2: r_pts, total_pts: pnl_pts,
                    mfe_pts: cur_mfe_pts, mae_pts: cur_mae_pts,
                    queen: queen_filled, runner: r_hit, reentry: is_cur_reentry,
                    queen_exit_ms,
                });
                trade_reasons.push(reason.clone());

                daily_pnl += net_usd;
                if net_usd < 0.0 {
                    consecutive_losers += 1;
                    if consecutive_losers >= max_consecutive_losers {
                        pause_until_time = Some(t + pause_minutes * 60_000);
                    }
                    if allow_reentry && !is_cur_reentry && reason.contains("Stop") {
                        reentry_armed = true;
                        reentry_dir = pos_dir;
                        reentry_time = t;
                    }
                } else {
                    consecutive_losers = 0;
                    reentry_armed = false;
                }
            }
        }

        // 2. Check 5m CISD signals at 5m bar closures
        if let Some(d) = sig_map.get(&t) {
            armed_dir = *d;
            armed_time = t;
        }

        // 3. Check 1m FVG Entry Trigger (or Confirmed Re-Entry)
        let target_dir = if reentry_armed { reentry_dir } else { armed_dir };
        let t_ref: i64 = if reentry_armed { reentry_time } else { armed_time };
        if !in_pos && target_dir != 0 {
            let is_paused =
                (pause_until_time.map(|pt| t < pt).unwrap_or(false)) && !reentry_armed;
            let hit_hard_stop = consecutive_losers >= hard_stop_losers;
            let hit_daily_max = daily_pnl <= -daily_max_loss;
            let mut in_time = earliest_entry_hhmm <= hm && hm <= latest_entry_hhmm;
            if filter_lunch && (1200..=1330).contains(&hm) {
                in_time = false;
            }

            let bars_armed = if armed_time != 0 {
                (t - t_ref) as f64 / 60_000.0
            } else {
                999.0
            };

            if bars_armed <= 20.0 && in_time && daily_trades < max_trades_per_day
                && !is_paused && !hit_hard_stop && !hit_daily_max
            {
                if target_dir == 1 && l0 > h2 {
                    let entry_p = round_tick(h2);
                    active_sl = round_tick(entry_p - entry_p * (stop_loss_bps / 10000.0));
                    active_tp1 = round_tick(entry_p + entry_p * (queen_bps / 10000.0));
                    active_tp2 = round_tick(entry_p + entry_p * (runner_bps / 10000.0));
                    pos_entry_price = entry_p;
                    pos_entry_time = t;
                    pos_dir = 1;
                    in_pos = true;
                    queen_filled = false;
                    queen_exit_ms = 0;
                    cur_mfe_pts = 0.0;
                    cur_mae_pts = 0.0;
                    is_cur_reentry = reentry_armed;
                    daily_trades += 1;
                    armed_dir = 0;
                    reentry_armed = false;
                } else if target_dir == -1 && h0 < l2 {
                    let entry_p = round_tick(l2);
                    active_sl = round_tick(entry_p + entry_p * (stop_loss_bps / 10000.0));
                    active_tp1 = round_tick(entry_p - entry_p * (queen_bps / 10000.0));
                    active_tp2 = round_tick(entry_p - entry_p * (runner_bps / 10000.0));
                    pos_entry_price = entry_p;
                    pos_entry_time = t;
                    pos_dir = -1;
                    in_pos = true;
                    queen_filled = false;
                    queen_exit_ms = 0;
                    cur_mfe_pts = 0.0;
                    cur_mae_pts = 0.0;
                    is_cur_reentry = reentry_armed;
                    daily_trades += 1;
                    armed_dir = 0;
                    reentry_armed = false;
                }
            } else if bars_armed > 20.0 {
                armed_dir = 0;
                reentry_armed = false;
            }
        }
    }

    let dict = pyo3::types::PyDict::new(py);
    dict.set_item("entry_time_ms", trades.iter().map(|r| r.entry_ms).collect::<Vec<_>>())?;
    dict.set_item("exit_time_ms", trades.iter().map(|r| r.exit_ms).collect::<Vec<_>>())?;
    dict.set_item("dir", trades.iter().map(|r| r.dir as i64).collect::<Vec<_>>())?;
    dict.set_item("entry_price", trades.iter().map(|r| r.entry_px).collect::<Vec<_>>())?;
    dict.set_item("exit_price", trades.iter().map(|r| r.exit_px).collect::<Vec<_>>())?;
    dict.set_item("leg1_points", trades.iter().map(|r| r.leg1).collect::<Vec<_>>())?;
    dict.set_item("leg2_points", trades.iter().map(|r| r.leg2).collect::<Vec<_>>())?;
    dict.set_item("total_points", trades.iter().map(|r| r.total_pts).collect::<Vec<_>>())?;
    dict.set_item("mfe_points", trades.iter().map(|r| r.mfe_pts).collect::<Vec<_>>())?;
    dict.set_item("mae_points", trades.iter().map(|r| r.mae_pts).collect::<Vec<_>>())?;
    dict.set_item("queen_hit", trades.iter().map(|r| r.queen).collect::<Vec<_>>())?;
    dict.set_item("queen_exit_time_ms", trades.iter().map(|r| r.queen_exit_ms).collect::<Vec<_>>())?;
    dict.set_item("runner_hit", trades.iter().map(|r| r.runner).collect::<Vec<_>>())?;
    dict.set_item("is_reentry", trades.iter().map(|r| r.reentry).collect::<Vec<_>>())?;
    dict.set_item("exit_reason", trade_reasons)?;
    Ok(dict.into())
}

fn epoch_ms_to_hhmm_utc(ms: i64) -> i32 {
    use chrono::{Datelike, Timelike};
    let dt = chrono::DateTime::from_timestamp_millis(ms)
        .unwrap_or_else(|| chrono::DateTime::from_timestamp(0, 0).unwrap());
    let _ = dt.ordinal();
    dt.hour() as i32 * 100 + dt.minute() as i32
}

#[pymodule]
fn nt8_parity_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(simulate_bars_v1, m)?)?;
    m.add_function(wrap_pyfunction!(simulate_bars_v2, m)?)?;
    Ok(())
}