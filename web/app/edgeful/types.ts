export interface MacroFilterState {
  instruments: string[];
  macroWindows: string[];
  ictAliases: string[];
  judasClass: string[];
  indicatorClass: string[];
  vixRegimes: string[];
  daysOfWeek: string[];
  dateRange: {
    start: string | null;
    end: string | null;
  };
  advanced: {
    realDirection: string[];
    hasFVG: boolean | null;
    isComplete: boolean | null;
    newsWithin60m: boolean | null;
    isOpExWeek: boolean | null;
    openVsMidnight: string[];
    openVsDailyOpen: string[];
    openVsRthBar: string[];
    priorMacroDirection: string[];
    sameDirectionAsPrior: boolean | null;
    macroStreak: [number, number] | null;
    macroRangePercentile: [number, number] | null;
    magnitudeRange: [number, number] | null;
    excursionRange: [number, number] | null;
    judasFirst: boolean | null;
    judasExcursionThreshold: number | null;
    midRetested: boolean | null;
    midRetestWin: boolean | null;
  };
}

export interface SummaryMetrics {
  total: number;
  judas_rate: number;
  avg_continuation: number;
  avg_reversion: number;
  continuation_win_rate: number;
  reversion_rate: number;
  avg_mfe: number;
  avg_mae: number;
  query_time_ms: number;
  // Strategy 2 — Mid Retest Performance
  mid_retest_rate: number;
  mid_entry_win_rate: number;
  avg_mid_mfe: number;
  avg_mid_mae: number;
  avg_mid_rr: number;
  avg_retest_time_m: number;
}

export interface MacroRecord {
  macro_id: string;
  trading_date: string;
  instrument: string;
  macro_name_raw: string;
  ict_alias: string;
  judas_classification: string;
  indicator_label: string;
  macro_range_pct: number;
  judas_magnitude_pct: number;
  real_move_magnitude_pct: number;
  post_macro_continuation_pct: number;
  post_macro_reversion_pct: number;
  fvg_count: number;
  has_fvg: boolean;
}
