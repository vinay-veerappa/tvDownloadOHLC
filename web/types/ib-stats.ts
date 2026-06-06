export interface IBFact {
  symbol: string;
  session_slot: string;
  time_basis: 'ET_fixed' | 'event_anchored';
  trading_day: string; // YYYY-MM-DD
  ib_high: number;
  ib_low: number;
  ib_open: number;
  ib_close: number;
  ib_mid: number;
  ib_range: number;
  range_pts: number;
  range_pct: number;
  range_atr: number;
  range_pctile_20: number;
  range_pctile_60: number;
  range_bucket_full: 'Small' | 'Medium' | 'Large';
  range_bucket_trailing: 'Small' | 'Medium' | 'Large';
  bias_formation_firstreach: number; // 1 | -1
  bias_formation_lasttouch: number; // 1 | -1
  bias_close_dir: number; // 1 | -1 | 0
  bias_fvg: number; // 1 | -1 | 0
  bias_fvg_ifvg: number; // 1 | -1 | 0
  bias_fvg_rth?: number; // 1 | -1 | 0
  bias_fvg_1011?: number; // 1 | -1 | 0
  fvg_low?: number | null;
  fvg_high?: number | null;
  fvg_1011_low?: number | null;
  fvg_1011_high?: number | null;
  fvg_broken_time?: string | null;
  prior_session_close: number;
  gap_pts: number;
  gap_pct: number;
  gap_dir: number; // 1 | -1 | 0
  gap_filled: boolean;
  gap_fill_minutes?: number | null;
  high_break_idx?: number | null;
  low_break_idx?: number | null;
  first_break_dir: number; // 1 | -1 | 0
  first_break_idx?: number | null;
  first_break_minutes?: number | null;
  double_break: boolean;
  double_break_order?: 'HL' | 'LH' | null;
  false_break_high: boolean;
  false_break_low: boolean;
  max_high: number;
  min_low: number;
  outcome_close: number;
  max_ext_up: number;
  max_ext_down: number;
  realized_dir_break: number; // 1 | -1 | 0
  realized_dir_close: number; // 1 | -1 | 0
  realized_dir_ext: number; // 1 | -1 | 0
  vix_close?: number | null;
  vix_bucket_full?: 'Low' | 'Medium' | 'High' | null;
  vix_bucket_trailing?: 'Low' | 'Medium' | 'High' | null;
  mid_lock_time: string;
  mid_end_ts: string;
  mid_start_ts: string;
  ib_duration_mins: number;
  mid_lock_frac: number;
  mid_touch_first_time?: string | null;
  mid_touch_first_phase?: 'formation_pre_lock' | 'formation_post_lock' | 'outcome' | 'outside' | null;
  mid_touch_first_formation_time?: string | null;
  mid_touch_first_outcome_time?: string | null;
  mid_touch_last_formation_time?: string | null;
  mid_touch_count_formation: number;
  mid_touch_count_outcome: number;
  mid_touched_again: boolean;
  mid_touch_count_post_lock: number;
  early_mid_event: boolean;
  play1_result: number; // 1 | -1 | 0
  play1_rr: number;
  play1_mfe: number;
  play1_mae: number;
  play1_timeout_loss: boolean;
  play2_result: number; // 1 | -1 | 0
  play2_rr: number;
  play2_mfe: number;
  play2_mae: number;
  play2_timeout_loss: boolean;
  play3_result: number; // 1 | -1 | 0
  play3_rr: number;
  play3_mfe: number;
  play3_mae: number;
  play3_timeout_loss: boolean;
  fvg_touch_first_formation_time?: string | null;
  fvg_touch_first_outcome_time?: string | null;
  fvg_1011_touch_first_formation_time?: string | null;
  fvg_1011_touch_first_outcome_time?: string | null;
  us_dst: boolean;
  uk_dst: boolean;
  et_window_offset_hours: number;
  dst_regime: 'aligned' | 'shifted';
  dow: string; // e.g. "Monday"
  prior_day_result?: number | null;
  first_break_time_val?: string | null;
  first_break_bucket?: string | null;
  mid_touch_bucket?: string | null;
  mid_touch_first_formation_bucket?: string | null;
  mid_touch_first_outcome_bucket?: string | null;
  fvg_touch_first_formation_bucket?: string | null;
  fvg_touch_first_outcome_bucket?: string | null;
  fvg_1011_touch_first_formation_bucket?: string | null;
  fvg_1011_touch_first_outcome_bucket?: string | null;
}

export interface IBExtDetail {
  symbol: string;
  trading_day: string;
  session_slot: string;
  time_basis: 'ET_fixed' | 'event_anchored';
  side: 'up' | 'down';
  level: number; // 0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0
  hit: boolean;
  minutes?: number | null;
}

export interface IBPlayDetail {
  symbol: string;
  trading_day: string;
  session_slot: string;
  time_basis: 'ET_fixed' | 'event_anchored';
  play: number; // 1, 2, 3
  result: number; // 1 | -1 | 0
  mfe: number;
  mae: number;
  realized_r: number;
  timeout_loss: boolean;
  loss_reason: 'no_setup' | 'target' | 'stop' | 'timeout' | 'unknown';
}

export interface IBLevelTouchDetail {
  symbol: string;
  trading_day: string;
  session_slot: string;
  time_basis: 'ET_fixed' | 'event_anchored';
  level_pct: number; // 0, 25, 50, 75, 100
  phase: 'formation_pre_lock' | 'formation_post_lock' | 'outcome';
  first_touch_time: string;
  last_touch_time: string;
  touch_count: number;
}

export interface IBFvgDetail {
  symbol: string;
  trading_day: string;
  session_slot: string;
  time_basis: 'ET_fixed' | 'event_anchored';
  fvg_id: number;
  touch_n: number;
  formed_time: string;
  dir: number; // 1 (bullish) | -1 (bearish)
  top: number;
  bot: number;
  formed_phase: 'formation' | 'outcome';
  touch_time?: string | null;
  touch_phase?: 'formation' | 'outcome' | null;
  reaction?: 'held' | 'closed_through' | null;
  inverted: boolean;
}
