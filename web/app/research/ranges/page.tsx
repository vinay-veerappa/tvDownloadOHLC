'use client';

import {
  startTransition,
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useState,
} from 'react';
import Link from 'next/link';
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  BarChart3,
  Database,
  LayoutDashboard,
  RefreshCcw,
  Target,
  TrendingUp,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { initDuckDB, loadParquet, resetDuckDB, runQuery } from '@/lib/duckdb';
import { QueryStatus } from '@/app/edgeful/components/QueryStatus';

type EngineStatus = 'loading' | 'ready' | 'error';

type FilterState = {
  symbol: string;
  rangeName: string;
  strategyName: string;
  breakoutDirection: string;
  startDate: string;
  endDate: string;
};

type FilterOptions = {
  symbols: string[];
  ranges: string[];
  strategies: string[];
};

type OverviewMetrics = {
  total_ranges: number;
  avg_width: number;
  avg_width_pct: number;
  aligned_close_rate: number;
  failed_breakout_rate: number;
  strategy_entries: number;
  strategy_win_rate: number;
  avg_r_multiple: number;
};

type WidthDistributionRow = {
  category: string;
  count: number;
};

type DirectionRow = {
  direction: string;
  count: number;
};

type ExtensionRow = {
  extension: string;
  hit_rate: number;
  avg_time_minutes: number | null;
};

type StrategyRow = {
  strategy_name: string;
  entries: number;
  entry_rate: number;
  win_rate: number;
  avg_r: number | null;
  avg_mfe_pct: number | null;
  avg_mae_pct: number | null;
  ambiguous_rate: number;
};

type EquityRow = {
  trading_date: string;
  equity_r: number;
  day_r: number;
};

type BothSidesOutcomeRow = {
  final_direction: string;
  count: number;
  failed_rate: number;
  aligned_close_rate: number;
  ext_1x_hit_rate: number;
};

type BothSidesSummary = {
  count: number;
  share_of_sample: number;
};

type BothSidesConditionRow = {
  dimension: string;
  bucket: string;
  sample_count: number;
  sweep_count: number;
  sweep_prob: number;
  baseline_prob: number;
  lift: number;
};

type MeanReversionSummary = {
  sample_count: number;
  mid_retest_rate: number;
  opposite_retest_rate: number;
  avg_mid_retest_time: number | null;
  failed_breakout_rate: number;
  mr_win_rate: number | null;
  mr_avg_r: number | null;
};

type MeanReversionRow = {
  direction: string;
  count: number;
  mid_retest_rate: number;
  opposite_retest_rate: number;
  avg_mid_retest_time: number | null;
};

type ExecutionQualitySummary = {
  sample_count: number;
  winner_count: number;
  loser_count: number;
  loss_median_min: number | null;
  loss_p90_min: number | null;
  mae_before_mfe_winner_pct: number | null;
};

type ExecutionQualityRow = {
  strategy_name: string;
  sample_count: number;
  loss_median_min: number | null;
  loss_p90_min: number | null;
  mae_before_mfe_winner_pct: number | null;
};

type SessionExpectancyRow = {
  session_segment: string;
  sample_count: number;
  win_rate: number | null;
  avg_r: number | null;
  median_r: number | null;
};

type SweepReclaimSummary = {
  sample_count: number;
  reclaim_rate: number | null;
  continuation_rate: number | null;
  median_follow_through_pct: number | null;
};

type SweepReclaimRow = {
  first_bo_direction: string;
  sample_count: number;
  reclaim_rate: number | null;
  continuation_rate: number | null;
  median_follow_through_pct: number | null;
};

type BreakoutAcceptanceSummary = {
  sample_count: number;
  hold_2bar_rate: number | null;
  retest_rate: number | null;
  fail_rate: number | null;
  continuation_rate: number | null;
};

type BreakoutAcceptanceRow = {
  first_bo_direction: string;
  sample_count: number;
  hold_2bar_rate: number | null;
  retest_rate: number | null;
  fail_rate: number | null;
  continuation_rate: number | null;
};

type VolatilityExcursionSummary = {
  sample_count: number;
  avg_directional_excursion_pct: number | null;
  avg_adverse_excursion_pct: number | null;
  excursion_efficiency_pct: number | null;
  directional_to_adverse_ratio: number | null;
};

type EdgeStabilitySummary = {
  trading_date: string;
  rolling_win_30: number | null;
  rolling_win_90: number | null;
  rolling_avg_r_30: number | null;
  win_rate_zscore_30: number | null;
};

type EdgeStabilityRow = {
  trading_date: string;
  rolling_win_30: number | null;
  rolling_win_90: number | null;
  rolling_avg_r_30: number | null;
};

type LatestRangeRow = {
  trading_date: string;
  range_high: number;
  range_low: number;
  range_mid: number;
  range_width: number;
};

type GexMacroData = {
  ticker: string;
  tradingDate: string;
  timestamp: string;
  spotPrice: number | null;
  levels: {
    zeroGamma: number | null;
    macroCallWall: number | null;
    macroPutWall: number | null;
  };
};

const DEFAULT_FILTERS: FilterState = {
  symbol: 'ALL',
  rangeName: 'ALL',
  strategyName: 'ALL',
  breakoutDirection: 'ALL',
  startDate: '',
  endDate: '',
};

const WIDTH_CATEGORY_COLORS: Record<string, string> = {
  NARROW: '#f59e0b',
  NORMAL: '#38bdf8',
  WIDE: '#fb7185',
};

function quote(value: string) {
  return `'${value.replace(/'/g, "''")}'`;
}

function buildRangeWhere(filters: FilterState, alias?: string) {
  const prefix = alias ? `${alias}.` : '';
  const conditions: string[] = [];

  if (filters.symbol !== 'ALL') {
    conditions.push(`${prefix}symbol = ${quote(filters.symbol)}`);
  }
  if (filters.rangeName !== 'ALL') {
    conditions.push(`${prefix}range_name = ${quote(filters.rangeName)}`);
  }
  if (filters.breakoutDirection !== 'ALL') {
    conditions.push(`${prefix}first_bo_direction = ${quote(filters.breakoutDirection)}`);
  }
  if (filters.startDate) {
    conditions.push(`${prefix}trading_date >= ${quote(filters.startDate)}`);
  }
  if (filters.endDate) {
    conditions.push(`${prefix}trading_date <= ${quote(filters.endDate)}`);
  }

  return conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
}

function buildTradeWhere(filters: FilterState, alias?: string, includeStrategy = true) {
  const prefix = alias ? `${alias}.` : '';
  const conditions: string[] = [];

  if (filters.symbol !== 'ALL') {
    conditions.push(`${prefix}symbol = ${quote(filters.symbol)}`);
  }
  if (filters.rangeName !== 'ALL') {
    conditions.push(`${prefix}range_name = ${quote(filters.rangeName)}`);
  }
  if (includeStrategy && filters.strategyName !== 'ALL') {
    conditions.push(`${prefix}strategy_name = ${quote(filters.strategyName)}`);
  }
  if (filters.startDate) {
    conditions.push(`${prefix}trading_date >= ${quote(filters.startDate)}`);
  }
  if (filters.endDate) {
    conditions.push(`${prefix}trading_date <= ${quote(filters.endDate)}`);
  }

  return conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
}

function getOverviewSql(rangeWhere: string, tradeWhere: string) {
  return `
    WITH rr AS (
      SELECT *
      FROM range_records
      ${rangeWhere}
    ),
    rt AS (
      SELECT *
      FROM range_trades
      ${tradeWhere}
    )
    SELECT
      CAST((SELECT COUNT(*) FROM rr) AS DOUBLE) AS total_ranges,
      CAST((SELECT AVG(range_width) FROM rr) AS DOUBLE) AS avg_width,
      CAST((SELECT AVG(range_width_pct) FROM rr) AS DOUBLE) AS avg_width_pct,
      CAST((SELECT AVG(CASE WHEN first_bo_direction IN ('UP', 'DOWN') AND first_bo_direction = final_direction THEN 1.0 ELSE 0.0 END) * 100 FROM rr) AS DOUBLE) AS aligned_close_rate,
      CAST((SELECT AVG(CASE WHEN first_bo_failed THEN 1.0 ELSE 0.0 END) * 100 FROM rr) AS DOUBLE) AS failed_breakout_rate,
      CAST((SELECT COUNT(*) FROM rt WHERE entry_triggered) AS DOUBLE) AS strategy_entries,
      CAST((SELECT AVG(CASE WHEN entry_triggered THEN CASE WHEN pnl_r_multiple > 0 THEN 1.0 ELSE 0.0 END END) * 100 FROM rt) AS DOUBLE) AS strategy_win_rate,
      CAST((SELECT AVG(CASE WHEN entry_triggered THEN pnl_r_multiple END) FROM rt) AS DOUBLE) AS avg_r_multiple
  `;
}

function getWidthDistributionSql(rangeWhere: string) {
  return `
    SELECT
      COALESCE(range_width_category, 'UNCLASSIFIED') AS category,
      CAST(COUNT(*) AS DOUBLE) AS count
    FROM range_records
    ${rangeWhere}
    GROUP BY 1
    ORDER BY CASE COALESCE(range_width_category, 'UNCLASSIFIED')
      WHEN 'NARROW' THEN 1
      WHEN 'NORMAL' THEN 2
      WHEN 'WIDE' THEN 3
      ELSE 4
    END
  `;
}

function getDirectionSql(rangeWhere: string, column: 'first_bo_direction' | 'final_direction') {
  return `
    SELECT
      COALESCE(${column}, 'NONE') AS direction,
      CAST(COUNT(*) AS DOUBLE) AS count
    FROM range_records
    ${rangeWhere}
    GROUP BY 1
    ORDER BY count DESC, direction ASC
  `;
}

function getExtensionSql(rangeWhere: string) {
  return `
    WITH filtered AS (
      SELECT *
      FROM range_records
      ${rangeWhere}
      ${rangeWhere ? 'AND' : 'WHERE'} first_bo_direction IN ('UP', 'DOWN')
    )
    SELECT * FROM (
      SELECT '0.5x' AS extension,
        CAST(AVG(CASE WHEN first_bo_direction = 'UP' THEN CASE WHEN ext_up_50_hit THEN 1.0 ELSE 0.0 END ELSE CASE WHEN ext_dn_50_hit THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS hit_rate,
        CAST(AVG(CASE WHEN first_bo_direction = 'UP' THEN ext_up_50_time_min ELSE ext_dn_50_time_min END) AS DOUBLE) AS avg_time_minutes
      FROM filtered
      UNION ALL
      SELECT '1.0x' AS extension,
        CAST(AVG(CASE WHEN first_bo_direction = 'UP' THEN CASE WHEN ext_up_100_hit THEN 1.0 ELSE 0.0 END ELSE CASE WHEN ext_dn_100_hit THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS hit_rate,
        CAST(AVG(CASE WHEN first_bo_direction = 'UP' THEN ext_up_100_time_min ELSE ext_dn_100_time_min END) AS DOUBLE) AS avg_time_minutes
      FROM filtered
      UNION ALL
      SELECT '1.5x' AS extension,
        CAST(AVG(CASE WHEN first_bo_direction = 'UP' THEN CASE WHEN ext_up_150_hit THEN 1.0 ELSE 0.0 END ELSE CASE WHEN ext_dn_150_hit THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS hit_rate,
        CAST(AVG(CASE WHEN first_bo_direction = 'UP' THEN ext_up_150_time_min ELSE ext_dn_150_time_min END) AS DOUBLE) AS avg_time_minutes
      FROM filtered
      UNION ALL
      SELECT '2.0x' AS extension,
        CAST(AVG(CASE WHEN first_bo_direction = 'UP' THEN CASE WHEN ext_up_200_hit THEN 1.0 ELSE 0.0 END ELSE CASE WHEN ext_dn_200_hit THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS hit_rate,
        CAST(AVG(CASE WHEN first_bo_direction = 'UP' THEN ext_up_200_time_min ELSE ext_dn_200_time_min END) AS DOUBLE) AS avg_time_minutes
      FROM filtered
      UNION ALL
      SELECT '3.0x' AS extension,
        CAST(AVG(CASE WHEN first_bo_direction = 'UP' THEN CASE WHEN ext_up_300_hit THEN 1.0 ELSE 0.0 END ELSE CASE WHEN ext_dn_300_hit THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS hit_rate,
        CAST(AVG(CASE WHEN first_bo_direction = 'UP' THEN ext_up_300_time_min ELSE ext_dn_300_time_min END) AS DOUBLE) AS avg_time_minutes
      FROM filtered
    ) ext
  `;
}

function getStrategyTableSql(tradeWhereWithoutStrategy: string) {
  return `
    SELECT
      strategy_name,
      CAST(SUM(CASE WHEN entry_triggered THEN 1 ELSE 0 END) AS DOUBLE) AS entries,
      CAST(AVG(CASE WHEN entry_triggered THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS entry_rate,
      CAST(AVG(CASE WHEN entry_triggered THEN CASE WHEN pnl_r_multiple > 0 THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS win_rate,
      CAST(AVG(CASE WHEN entry_triggered THEN pnl_r_multiple END) AS DOUBLE) AS avg_r,
      CAST(AVG(CASE WHEN entry_triggered THEN mfe_pct_of_range END) AS DOUBLE) AS avg_mfe_pct,
      CAST(AVG(CASE WHEN entry_triggered THEN mae_pct_of_range END) AS DOUBLE) AS avg_mae_pct,
      CAST(AVG(CASE WHEN entry_triggered AND ambiguous_bar THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS ambiguous_rate
    FROM range_trades
    ${tradeWhereWithoutStrategy}
    GROUP BY strategy_name
    ORDER BY win_rate DESC NULLS LAST, avg_r DESC NULLS LAST
  `;
}

function getEquitySql(tradeWhere: string) {
  return `
    WITH filtered AS (
      SELECT trading_date, COALESCE(pnl_r_multiple, 0) AS pnl_r_multiple
      FROM range_trades
      ${tradeWhere}
      ${tradeWhere ? 'AND' : 'WHERE'} entry_triggered
    ),
    daily AS (
      SELECT trading_date, CAST(SUM(pnl_r_multiple) AS DOUBLE) AS day_r
      FROM filtered
      GROUP BY trading_date
    )
    SELECT
      trading_date,
      CAST(day_r AS DOUBLE) AS day_r,
      CAST(SUM(day_r) OVER (ORDER BY trading_date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS DOUBLE) AS equity_r
    FROM daily
    ORDER BY trading_date
  `;
}

function getBothSidesOutcomeSql(rangeWhere: string) {
  return `
    WITH rr AS (
      SELECT *
      FROM range_records
      ${rangeWhere}
    ),
    both_sides AS (
      SELECT *
      FROM rr
      WHERE broke_high_first AND broke_low_first
    )
    SELECT
      COALESCE(final_direction, 'NONE') AS final_direction,
      CAST(COUNT(*) AS DOUBLE) AS count,
      CAST(AVG(CASE WHEN first_bo_failed THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS failed_rate,
      CAST(AVG(CASE WHEN first_bo_direction IN ('UP', 'DOWN') AND first_bo_direction = final_direction THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS aligned_close_rate,
      CAST(AVG(
        CASE
          WHEN final_direction = 'UP' THEN CASE WHEN ext_up_100_hit THEN 1.0 ELSE 0.0 END
          WHEN final_direction = 'DOWN' THEN CASE WHEN ext_dn_100_hit THEN 1.0 ELSE 0.0 END
          ELSE 0.0
        END
      ) * 100 AS DOUBLE) AS ext_1x_hit_rate
    FROM both_sides
    GROUP BY COALESCE(final_direction, 'NONE')
    ORDER BY count DESC, final_direction ASC
  `;
}

function getBothSidesSummarySql(rangeWhere: string) {
  return `
    WITH rr AS (
      SELECT *
      FROM range_records
      ${rangeWhere}
    )
    SELECT
      CAST(SUM(CASE WHEN broke_high_first AND broke_low_first THEN 1 ELSE 0 END) AS DOUBLE) AS count,
      CAST(AVG(CASE WHEN broke_high_first AND broke_low_first THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS share_of_sample
    FROM rr
  `;
}

function getBothSidesConditionSql(rangeWhere: string) {
  return `
    WITH rr AS (
      SELECT *
      FROM range_records
      ${rangeWhere}
    ),
    base AS (
      SELECT
        CAST(AVG(CASE WHEN broke_high_first AND broke_low_first THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS baseline_prob
      FROM rr
    ),
    by_dow AS (
      SELECT
        'Day Of Week' AS dimension,
        CASE day_of_week
          WHEN 0 THEN 'Mon'
          WHEN 1 THEN 'Tue'
          WHEN 2 THEN 'Wed'
          WHEN 3 THEN 'Thu'
          WHEN 4 THEN 'Fri'
          ELSE 'Unknown'
        END AS bucket,
        CAST(COUNT(*) AS DOUBLE) AS sample_count,
        CAST(SUM(CASE WHEN broke_high_first AND broke_low_first THEN 1 ELSE 0 END) AS DOUBLE) AS sweep_count,
        CAST(AVG(CASE WHEN broke_high_first AND broke_low_first THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS sweep_prob
      FROM rr
      GROUP BY 1, 2
    ),
    by_width AS (
      SELECT
        'Range Width' AS dimension,
        COALESCE(range_width_category, 'UNCLASSIFIED') AS bucket,
        CAST(COUNT(*) AS DOUBLE) AS sample_count,
        CAST(SUM(CASE WHEN broke_high_first AND broke_low_first THEN 1 ELSE 0 END) AS DOUBLE) AS sweep_count,
        CAST(AVG(CASE WHEN broke_high_first AND broke_low_first THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS sweep_prob
      FROM rr
      GROUP BY 1, 2
    ),
    by_vix AS (
      SELECT
        'VIX Regime' AS dimension,
        COALESCE(vix_regime, 'UNKNOWN') AS bucket,
        CAST(COUNT(*) AS DOUBLE) AS sample_count,
        CAST(SUM(CASE WHEN broke_high_first AND broke_low_first THEN 1 ELSE 0 END) AS DOUBLE) AS sweep_count,
        CAST(AVG(CASE WHEN broke_high_first AND broke_low_first THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS sweep_prob
      FROM rr
      GROUP BY 1, 2
    ),
    by_gap AS (
      SELECT
        'Gap Direction' AS dimension,
        COALESCE(gap_direction, 'UNKNOWN') AS bucket,
        CAST(COUNT(*) AS DOUBLE) AS sample_count,
        CAST(SUM(CASE WHEN broke_high_first AND broke_low_first THEN 1 ELSE 0 END) AS DOUBLE) AS sweep_count,
        CAST(AVG(CASE WHEN broke_high_first AND broke_low_first THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS sweep_prob
      FROM rr
      GROUP BY 1, 2
    ),
    by_open_loc AS (
      SELECT
        'Open vs PD' AS dimension,
        COALESCE(open_vs_pd_range, 'UNKNOWN') AS bucket,
        CAST(COUNT(*) AS DOUBLE) AS sample_count,
        CAST(SUM(CASE WHEN broke_high_first AND broke_low_first THEN 1 ELSE 0 END) AS DOUBLE) AS sweep_count,
        CAST(AVG(CASE WHEN broke_high_first AND broke_low_first THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS sweep_prob
      FROM rr
      GROUP BY 1, 2
    ),
    combined AS (
      SELECT * FROM by_dow
      UNION ALL SELECT * FROM by_width
      UNION ALL SELECT * FROM by_vix
      UNION ALL SELECT * FROM by_gap
      UNION ALL SELECT * FROM by_open_loc
    )
    SELECT
      c.dimension,
      c.bucket,
      c.sample_count,
      c.sweep_count,
      c.sweep_prob,
      b.baseline_prob,
      CAST(c.sweep_prob - b.baseline_prob AS DOUBLE) AS lift
    FROM combined c
    CROSS JOIN base b
    WHERE c.sample_count >= 30
    ORDER BY lift DESC, c.sample_count DESC, c.dimension ASC, c.bucket ASC
  `;
}

function getMeanReversionSummarySql(rangeWhere: string, tradeWhereWithoutStrategy: string) {
  return `
    WITH rr AS (
      SELECT *
      FROM range_records
      ${rangeWhere}
      ${rangeWhere ? 'AND' : 'WHERE'} first_bo_direction IN ('UP', 'DOWN')
    ),
    mr_trades AS (
      SELECT *
      FROM range_trades
      ${tradeWhereWithoutStrategy}
      ${tradeWhereWithoutStrategy ? 'AND' : 'WHERE'} strategy_name = 'MR_TO_MID'
    )
    SELECT
      CAST(COUNT(*) AS DOUBLE) AS sample_count,
      CAST(AVG(
        CASE
          WHEN first_bo_direction = 'UP' THEN CASE WHEN retest_mid_after_high_break THEN 1.0 ELSE 0.0 END
          WHEN first_bo_direction = 'DOWN' THEN CASE WHEN retest_mid_after_low_break THEN 1.0 ELSE 0.0 END
          ELSE NULL
        END
      ) * 100 AS DOUBLE) AS mid_retest_rate,
      CAST(AVG(
        CASE
          WHEN first_bo_direction = 'UP' THEN CASE WHEN retest_opposite_after_high_break THEN 1.0 ELSE 0.0 END
          WHEN first_bo_direction = 'DOWN' THEN CASE WHEN retest_opposite_after_low_break THEN 1.0 ELSE 0.0 END
          ELSE NULL
        END
      ) * 100 AS DOUBLE) AS opposite_retest_rate,
      CAST(AVG(
        CASE
          WHEN first_bo_direction = 'UP' THEN retest_mid_after_high_break_time_min
          WHEN first_bo_direction = 'DOWN' THEN retest_mid_after_low_break_time_min
          ELSE NULL
        END
      ) AS DOUBLE) AS avg_mid_retest_time,
      CAST(AVG(CASE WHEN first_bo_failed THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS failed_breakout_rate,
      CAST((SELECT AVG(CASE WHEN entry_triggered THEN CASE WHEN pnl_r_multiple > 0 THEN 1.0 ELSE 0.0 END END) * 100 FROM mr_trades) AS DOUBLE) AS mr_win_rate,
      CAST((SELECT AVG(CASE WHEN entry_triggered THEN pnl_r_multiple END) FROM mr_trades) AS DOUBLE) AS mr_avg_r
    FROM rr
  `;
}

function getMeanReversionDirectionSql(rangeWhere: string) {
  return `
    WITH rr AS (
      SELECT *
      FROM range_records
      ${rangeWhere}
      ${rangeWhere ? 'AND' : 'WHERE'} first_bo_direction IN ('UP', 'DOWN')
    )
    SELECT
      first_bo_direction AS direction,
      CAST(COUNT(*) AS DOUBLE) AS count,
      CAST(AVG(CASE WHEN first_bo_direction = 'UP' THEN CASE WHEN retest_mid_after_high_break THEN 1.0 ELSE 0.0 END ELSE CASE WHEN retest_mid_after_low_break THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS mid_retest_rate,
      CAST(AVG(CASE WHEN first_bo_direction = 'UP' THEN CASE WHEN retest_opposite_after_high_break THEN 1.0 ELSE 0.0 END ELSE CASE WHEN retest_opposite_after_low_break THEN 1.0 ELSE 0.0 END END) * 100 AS DOUBLE) AS opposite_retest_rate,
      CAST(AVG(CASE WHEN first_bo_direction = 'UP' THEN retest_mid_after_high_break_time_min ELSE retest_mid_after_low_break_time_min END) AS DOUBLE) AS avg_mid_retest_time
    FROM rr
    GROUP BY first_bo_direction
    ORDER BY CASE first_bo_direction WHEN 'UP' THEN 1 WHEN 'DOWN' THEN 2 ELSE 3 END
  `;
}

function getLatestRangeSql(rangeWhere: string) {
  return `
    SELECT
      trading_date,
      CAST(range_high AS DOUBLE) AS range_high,
      CAST(range_low AS DOUBLE) AS range_low,
      CAST(range_mid AS DOUBLE) AS range_mid,
      CAST(range_width AS DOUBLE) AS range_width
    FROM range_records
    ${rangeWhere}
    ORDER BY trading_date DESC
    LIMIT 1
  `;
}

function getExecutionQualitySummarySql(tradeWhere: string) {
  return `
    WITH rt AS (
      SELECT
        *,
        CAST(DATEDIFF('minute', entry_time, exit_time) AS DOUBLE) AS hold_minutes
      FROM range_trades
      ${tradeWhere}
      ${tradeWhere ? 'AND' : 'WHERE'} entry_triggered
        AND entry_time IS NOT NULL
        AND exit_time IS NOT NULL
    )
    SELECT
      CAST(COUNT(*) AS DOUBLE) AS sample_count,
      CAST(SUM(CASE WHEN pnl_r_multiple > 0 THEN 1 ELSE 0 END) AS DOUBLE) AS winner_count,
      CAST(SUM(CASE WHEN pnl_r_multiple <= 0 THEN 1 ELSE 0 END) AS DOUBLE) AS loser_count,
      CAST(quantile_cont(CASE WHEN pnl_r_multiple <= 0 THEN hold_minutes END, 0.5) AS DOUBLE) AS loss_median_min,
      CAST(quantile_cont(CASE WHEN pnl_r_multiple <= 0 THEN hold_minutes END, 0.9) AS DOUBLE) AS loss_p90_min,
      CAST(
        AVG(
          CASE
            WHEN pnl_r_multiple > 0 AND mae_time_minutes IS NOT NULL AND mfe_time_minutes IS NOT NULL
              THEN CASE WHEN mae_time_minutes < mfe_time_minutes THEN 1.0 ELSE 0.0 END
            ELSE NULL
          END
        ) * 100 AS DOUBLE
      ) AS mae_before_mfe_winner_pct
    FROM rt
  `;
}

function getExecutionQualityByStrategySql(tradeWhereWithoutStrategy: string) {
  return `
    WITH rt AS (
      SELECT
        *,
        CAST(DATEDIFF('minute', entry_time, exit_time) AS DOUBLE) AS hold_minutes
      FROM range_trades
      ${tradeWhereWithoutStrategy}
      ${tradeWhereWithoutStrategy ? 'AND' : 'WHERE'} entry_triggered
        AND entry_time IS NOT NULL
        AND exit_time IS NOT NULL
    )
    SELECT
      strategy_name,
      CAST(COUNT(*) AS DOUBLE) AS sample_count,
      CAST(quantile_cont(CASE WHEN pnl_r_multiple <= 0 THEN hold_minutes END, 0.5) AS DOUBLE) AS loss_median_min,
      CAST(quantile_cont(CASE WHEN pnl_r_multiple <= 0 THEN hold_minutes END, 0.9) AS DOUBLE) AS loss_p90_min,
      CAST(
        AVG(
          CASE
            WHEN pnl_r_multiple > 0 AND mae_time_minutes IS NOT NULL AND mfe_time_minutes IS NOT NULL
              THEN CASE WHEN mae_time_minutes < mfe_time_minutes THEN 1.0 ELSE 0.0 END
            ELSE NULL
          END
        ) * 100 AS DOUBLE
      ) AS mae_before_mfe_winner_pct
    FROM rt
    GROUP BY strategy_name
    ORDER BY sample_count DESC, strategy_name ASC
  `;
}

function getSessionExpectancySql(tradeWhere: string) {
  return `
    WITH rt AS (
      SELECT
        *,
        CASE
          WHEN entry_time IS NULL THEN 'UNKNOWN'
          WHEN EXTRACT(hour FROM entry_time) * 60 + EXTRACT(minute FROM entry_time) < 690 THEN 'OPEN_DRIVE'
          WHEN EXTRACT(hour FROM entry_time) * 60 + EXTRACT(minute FROM entry_time) < 810 THEN 'LATE_MORNING'
          WHEN EXTRACT(hour FROM entry_time) * 60 + EXTRACT(minute FROM entry_time) < 870 THEN 'LUNCH'
          WHEN EXTRACT(hour FROM entry_time) * 60 + EXTRACT(minute FROM entry_time) < 900 THEN 'PRE_POWER_HOUR'
          WHEN EXTRACT(hour FROM entry_time) * 60 + EXTRACT(minute FROM entry_time) < 960 THEN 'POWER_HOUR'
          ELSE 'OTHER'
        END AS session_segment
      FROM range_trades
      ${tradeWhere}
      ${tradeWhere ? 'AND' : 'WHERE'} entry_triggered
        AND pnl_r_multiple IS NOT NULL
    )
    SELECT
      session_segment,
      CAST(COUNT(*) AS DOUBLE) AS sample_count,
      CAST(AVG(CASE WHEN pnl_r_multiple > 0 THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS win_rate,
      CAST(AVG(pnl_r_multiple) AS DOUBLE) AS avg_r,
      CAST(quantile_cont(pnl_r_multiple, 0.5) AS DOUBLE) AS median_r
    FROM rt
    GROUP BY session_segment
    ORDER BY CASE session_segment
      WHEN 'OPEN_DRIVE' THEN 1
      WHEN 'LATE_MORNING' THEN 2
      WHEN 'LUNCH' THEN 3
      WHEN 'PRE_POWER_HOUR' THEN 4
      WHEN 'POWER_HOUR' THEN 5
      WHEN 'OTHER' THEN 6
      ELSE 7
    END
  `;
}

function getSweepReclaimSummarySql(rangeWhere: string) {
  return `
    WITH rr AS (
      SELECT *
      FROM range_records
      ${rangeWhere}
      ${rangeWhere ? 'AND' : 'WHERE'} first_bo_direction IN ('UP', 'DOWN')
    )
    SELECT
      CAST(COUNT(*) AS DOUBLE) AS sample_count,
      CAST(AVG(CASE WHEN first_bo_retested_boundary THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS reclaim_rate,
      CAST(AVG(CASE WHEN final_direction = first_bo_direction THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS continuation_rate,
      CAST(
        quantile_cont(
          CASE
            WHEN first_bo_direction = 'UP' THEN max_excursion_up_pct
            WHEN first_bo_direction = 'DOWN' THEN max_excursion_dn_pct
            ELSE NULL
          END,
          0.5
        ) AS DOUBLE
      ) AS median_follow_through_pct
    FROM rr
  `;
}

function getSweepReclaimDirectionSql(rangeWhere: string) {
  return `
    WITH rr AS (
      SELECT *
      FROM range_records
      ${rangeWhere}
      ${rangeWhere ? 'AND' : 'WHERE'} first_bo_direction IN ('UP', 'DOWN')
    )
    SELECT
      first_bo_direction,
      CAST(COUNT(*) AS DOUBLE) AS sample_count,
      CAST(AVG(CASE WHEN first_bo_retested_boundary THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS reclaim_rate,
      CAST(AVG(CASE WHEN final_direction = first_bo_direction THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS continuation_rate,
      CAST(
        quantile_cont(
          CASE
            WHEN first_bo_direction = 'UP' THEN max_excursion_up_pct
            WHEN first_bo_direction = 'DOWN' THEN max_excursion_dn_pct
            ELSE NULL
          END,
          0.5
        ) AS DOUBLE
      ) AS median_follow_through_pct
    FROM rr
    GROUP BY first_bo_direction
    ORDER BY CASE first_bo_direction WHEN 'UP' THEN 1 WHEN 'DOWN' THEN 2 ELSE 3 END
  `;
}

function getBreakoutAcceptanceSummarySql(rangeWhere: string) {
  return `
    WITH rr AS (
      SELECT *
      FROM range_records
      ${rangeWhere}
      ${rangeWhere ? 'AND' : 'WHERE'} first_bo_direction IN ('UP', 'DOWN')
    )
    SELECT
      CAST(COUNT(*) AS DOUBLE) AS sample_count,
      CAST(AVG(CASE WHEN first_bo_held THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS hold_2bar_rate,
      CAST(AVG(CASE WHEN first_bo_retested_boundary THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS retest_rate,
      CAST(AVG(CASE WHEN first_bo_failed THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS fail_rate,
      CAST(AVG(CASE WHEN final_direction = first_bo_direction THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS continuation_rate
    FROM rr
  `;
}

function getBreakoutAcceptanceDirectionSql(rangeWhere: string) {
  return `
    WITH rr AS (
      SELECT *
      FROM range_records
      ${rangeWhere}
      ${rangeWhere ? 'AND' : 'WHERE'} first_bo_direction IN ('UP', 'DOWN')
    )
    SELECT
      first_bo_direction,
      CAST(COUNT(*) AS DOUBLE) AS sample_count,
      CAST(AVG(CASE WHEN first_bo_held THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS hold_2bar_rate,
      CAST(AVG(CASE WHEN first_bo_retested_boundary THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS retest_rate,
      CAST(AVG(CASE WHEN first_bo_failed THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS fail_rate,
      CAST(AVG(CASE WHEN final_direction = first_bo_direction THEN 1.0 ELSE 0.0 END) * 100 AS DOUBLE) AS continuation_rate
    FROM rr
    GROUP BY first_bo_direction
    ORDER BY CASE first_bo_direction WHEN 'UP' THEN 1 WHEN 'DOWN' THEN 2 ELSE 3 END
  `;
}

function getVolatilityExcursionSql(rangeWhere: string) {
  return `
    WITH rr AS (
      SELECT *
      FROM range_records
      ${rangeWhere}
      ${rangeWhere ? 'AND' : 'WHERE'} first_bo_direction IN ('UP', 'DOWN')
    ),
    scored AS (
      SELECT
        CASE
          WHEN first_bo_direction = 'UP' THEN max_excursion_up_pct
          WHEN first_bo_direction = 'DOWN' THEN max_excursion_dn_pct
          ELSE NULL
        END AS directional_excursion_pct,
        CASE
          WHEN first_bo_direction = 'UP' THEN max_excursion_dn_pct
          WHEN first_bo_direction = 'DOWN' THEN max_excursion_up_pct
          ELSE NULL
        END AS adverse_excursion_pct
      FROM rr
    )
    SELECT
      CAST(COUNT(*) AS DOUBLE) AS sample_count,
      CAST(AVG(directional_excursion_pct) AS DOUBLE) AS avg_directional_excursion_pct,
      CAST(AVG(adverse_excursion_pct) AS DOUBLE) AS avg_adverse_excursion_pct,
      CAST(AVG(directional_excursion_pct) - AVG(adverse_excursion_pct) AS DOUBLE) AS excursion_efficiency_pct,
      CAST(AVG(directional_excursion_pct) / NULLIF(AVG(adverse_excursion_pct), 0) AS DOUBLE) AS directional_to_adverse_ratio
    FROM scored
  `;
}

function getEdgeStabilitySummarySql(tradeWhere: string) {
  return `
    WITH rt AS (
      SELECT *
      FROM range_trades
      ${tradeWhere}
      ${tradeWhere ? 'AND' : 'WHERE'} entry_triggered
        AND pnl_r_multiple IS NOT NULL
    ),
    daily AS (
      SELECT
        trading_date,
        CAST(AVG(CASE WHEN pnl_r_multiple > 0 THEN 1.0 ELSE 0.0 END) AS DOUBLE) AS day_win_rate,
        CAST(AVG(pnl_r_multiple) AS DOUBLE) AS day_avg_r
      FROM rt
      GROUP BY trading_date
    ),
    rolling AS (
      SELECT
        trading_date,
        CAST(AVG(day_win_rate) OVER (ORDER BY trading_date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) * 100 AS DOUBLE) AS rolling_win_30,
        CAST(AVG(day_win_rate) OVER (ORDER BY trading_date ROWS BETWEEN 89 PRECEDING AND CURRENT ROW) * 100 AS DOUBLE) AS rolling_win_90,
        CAST(AVG(day_avg_r) OVER (ORDER BY trading_date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS DOUBLE) AS rolling_avg_r_30,
        day_win_rate
      FROM daily
    ),
    baseline AS (
      SELECT
        AVG(day_win_rate) AS baseline_win,
        STDDEV_SAMP(day_win_rate) AS baseline_win_std
      FROM daily
    )
    SELECT
      r.trading_date,
      r.rolling_win_30,
      r.rolling_win_90,
      r.rolling_avg_r_30,
      CAST((r.day_win_rate - b.baseline_win) / NULLIF(b.baseline_win_std, 0) AS DOUBLE) AS win_rate_zscore_30
    FROM rolling r
    CROSS JOIN baseline b
    ORDER BY r.trading_date DESC
    LIMIT 1
  `;
}

function getEdgeStabilitySeriesSql(tradeWhere: string) {
  return `
    WITH rt AS (
      SELECT *
      FROM range_trades
      ${tradeWhere}
      ${tradeWhere ? 'AND' : 'WHERE'} entry_triggered
        AND pnl_r_multiple IS NOT NULL
    ),
    daily AS (
      SELECT
        trading_date,
        CAST(AVG(CASE WHEN pnl_r_multiple > 0 THEN 1.0 ELSE 0.0 END) AS DOUBLE) AS day_win_rate,
        CAST(AVG(pnl_r_multiple) AS DOUBLE) AS day_avg_r
      FROM rt
      GROUP BY trading_date
    )
    SELECT
      trading_date,
      CAST(AVG(day_win_rate) OVER (ORDER BY trading_date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) * 100 AS DOUBLE) AS rolling_win_30,
      CAST(AVG(day_win_rate) OVER (ORDER BY trading_date ROWS BETWEEN 89 PRECEDING AND CURRENT ROW) * 100 AS DOUBLE) AS rolling_win_90,
      CAST(AVG(day_avg_r) OVER (ORDER BY trading_date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS DOUBLE) AS rolling_avg_r_30
    FROM daily
    ORDER BY trading_date DESC
    LIMIT 20
  `;
}

function formatPct(value: number | null | undefined, digits = 1) {
  if (value == null || Number.isNaN(value)) return '--';
  return `${value.toFixed(digits)}%`;
}

function formatNumber(value: number | null | undefined, digits = 2) {
  if (value == null || Number.isNaN(value)) return '--';
  return value.toFixed(digits);
}

function describeLevelOverlap(level: number | null, latestRange: LatestRangeRow | null) {
  if (level == null || latestRange == null || latestRange.range_width <= 0) {
    return { location: '--', widthUnits: '--' };
  }

  const { range_low: low, range_high: high, range_width: width } = latestRange;
  if (level >= low && level <= high) {
    return { location: 'Inside range', widthUnits: '0.00x' };
  }

  if (level > high) {
    const units = (level - high) / width;
    return { location: 'Above range', widthUnits: `${units.toFixed(2)}x` };
  }

  const units = (low - level) / width;
  return { location: 'Below range', widthUnits: `${units.toFixed(2)}x` };
}

function StatCard({
  label,
  value,
  accent,
  sublabel,
}: {
  label: string;
  value: string;
  accent: string;
  sublabel?: string;
}) {
  return (
    <Card className="border-zinc-800 bg-zinc-950/80 p-4">
      <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-500">{label}</div>
      <div className={`mt-2 text-2xl font-semibold ${accent}`}>{value}</div>
      {sublabel ? <div className="mt-1 text-xs text-zinc-500">{sublabel}</div> : null}
    </Card>
  );
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex min-w-[150px] flex-col gap-2 text-xs uppercase tracking-[0.22em] text-zinc-500">
      <span>{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-10 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm tracking-normal text-zinc-100 outline-none transition focus:border-cyan-400"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option === 'ALL' ? 'All' : option}
          </option>
        ))}
      </select>
    </label>
  );
}

export default function RangeAnalyticsPage() {
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const deferredFilters = useDeferredValue(filters);

  const [dbStatus, setDbStatus] = useState<EngineStatus>('loading');
  const [lastDataUpdate, setLastDataUpdate] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [queryTimeMs, setQueryTimeMs] = useState<number>();

  const [options, setOptions] = useState<FilterOptions>({ symbols: [], ranges: [], strategies: [] });
  const [overview, setOverview] = useState<OverviewMetrics | null>(null);
  const [widthDistribution, setWidthDistribution] = useState<WidthDistributionRow[]>([]);
  const [breakoutDistribution, setBreakoutDistribution] = useState<DirectionRow[]>([]);
  const [finalDistribution, setFinalDistribution] = useState<DirectionRow[]>([]);
  const [extensionStats, setExtensionStats] = useState<ExtensionRow[]>([]);
  const [strategyRows, setStrategyRows] = useState<StrategyRow[]>([]);
  const [equityCurve, setEquityCurve] = useState<EquityRow[]>([]);
  const [bothSidesRows, setBothSidesRows] = useState<BothSidesOutcomeRow[]>([]);
  const [bothSidesSummary, setBothSidesSummary] = useState<BothSidesSummary | null>(null);
  const [bothSidesConditionRows, setBothSidesConditionRows] = useState<BothSidesConditionRow[]>([]);
  const [meanReversionSummary, setMeanReversionSummary] = useState<MeanReversionSummary | null>(null);
  const [meanReversionRows, setMeanReversionRows] = useState<MeanReversionRow[]>([]);
  const [executionQualitySummary, setExecutionQualitySummary] = useState<ExecutionQualitySummary | null>(null);
  const [executionQualityRows, setExecutionQualityRows] = useState<ExecutionQualityRow[]>([]);
  const [sessionExpectancyRows, setSessionExpectancyRows] = useState<SessionExpectancyRow[]>([]);
  const [sweepReclaimSummary, setSweepReclaimSummary] = useState<SweepReclaimSummary | null>(null);
  const [sweepReclaimRows, setSweepReclaimRows] = useState<SweepReclaimRow[]>([]);
  const [breakoutAcceptanceSummary, setBreakoutAcceptanceSummary] = useState<BreakoutAcceptanceSummary | null>(null);
  const [breakoutAcceptanceRows, setBreakoutAcceptanceRows] = useState<BreakoutAcceptanceRow[]>([]);
  const [volatilityExcursionSummary, setVolatilityExcursionSummary] = useState<VolatilityExcursionSummary | null>(null);
  const [edgeStabilitySummary, setEdgeStabilitySummary] = useState<EdgeStabilitySummary | null>(null);
  const [edgeStabilityRows, setEdgeStabilityRows] = useState<EdgeStabilityRow[]>([]);
  const [latestRange, setLatestRange] = useState<LatestRangeRow | null>(null);
  const [gexMacro, setGexMacro] = useState<GexMacroData | null>(null);
  const [gexSymbolOverride, setGexSymbolOverride] = useState('NQ1');

  const [gexLoading, setGexLoading] = useState(false);

  const loadEngine = useCallback(async () => {
    setDbStatus('loading');
    try {
      await initDuckDB();
      const version = Date.now();
      await loadParquet('range_records.parquet', `/api/data/range_records.parquet?v=${version}`);
      await loadParquet('range_trades.parquet', `/api/data/range_trades.parquet?v=${version}`);

      const metaResponse = await fetch(`/api/data/range_records.parquet?v=${version}`, {
        headers: { Range: 'bytes=0-0' },
      });
      setLastDataUpdate(metaResponse.headers.get('last-modified'));
      setDbStatus('ready');
    } catch (error) {
      console.error('Failed to initialize range analytics engine:', error);
      setDbStatus('error');
    }
  }, []);

  useEffect(() => {
    loadEngine();
  }, [loadEngine]);

  useEffect(() => {
    if (dbStatus !== 'ready') return;

    const fetchOptions = async () => {
      const [symbols, ranges, strategies] = await Promise.all([
        runQuery<{ symbol: string }>(`SELECT DISTINCT symbol FROM range_records ORDER BY symbol`),
        runQuery<{ range_name: string }>(`SELECT DISTINCT range_name FROM range_records ORDER BY range_name`),
        runQuery<{ strategy_name: string }>(`SELECT DISTINCT strategy_name FROM range_trades ORDER BY strategy_name`),
      ]);

      setOptions({
        symbols: ['ALL', ...symbols.map((row) => row.symbol)],
        ranges: ['ALL', ...ranges.map((row) => row.range_name)],
        strategies: ['ALL', ...strategies.map((row) => row.strategy_name)],
      });
    };

    fetchOptions().catch((error) => {
      console.error('Failed to load range filter options:', error);
    });
  }, [dbStatus]);

  const fetchDashboard = useCallback(async () => {
    if (dbStatus !== 'ready') return;

    setLoading(true);
    const startedAt = performance.now();
    try {
      const rangeWhere = buildRangeWhere(deferredFilters);
      const tradeWhere = buildTradeWhere(deferredFilters);
      const tradeWhereNoStrategy = buildTradeWhere(deferredFilters, undefined, false);

      const [overviewRows, widthRows, breakoutRows, finalRows, extensionRows, strategyTableRows, equityRows, bothSidesOutcomeRows, bothSidesSummaryRows, bothSidesConditionLiftRows, meanReversionSummaryRows, meanReversionDirectionRows, executionSummaryRows, executionByStrategyRows, sessionExpectancyTableRows, sweepReclaimSummaryRows, sweepReclaimDirectionRows, breakoutAcceptanceSummaryRows, breakoutAcceptanceDirectionRows, volatilityExcursionRows, edgeStabilitySummaryRows, edgeStabilitySeriesRows, latestRangeRows] = await Promise.all([
        runQuery<OverviewMetrics>(getOverviewSql(rangeWhere, tradeWhere)),
        runQuery<WidthDistributionRow>(getWidthDistributionSql(rangeWhere)),
        runQuery<DirectionRow>(getDirectionSql(rangeWhere, 'first_bo_direction')),
        runQuery<DirectionRow>(getDirectionSql(rangeWhere, 'final_direction')),
        runQuery<ExtensionRow>(getExtensionSql(rangeWhere)),
        runQuery<StrategyRow>(getStrategyTableSql(tradeWhereNoStrategy)),
        runQuery<EquityRow>(getEquitySql(tradeWhere)),
        runQuery<BothSidesOutcomeRow>(getBothSidesOutcomeSql(rangeWhere)),
        runQuery<BothSidesSummary>(getBothSidesSummarySql(rangeWhere)),
        runQuery<BothSidesConditionRow>(getBothSidesConditionSql(rangeWhere)),
        runQuery<MeanReversionSummary>(getMeanReversionSummarySql(rangeWhere, tradeWhereNoStrategy)),
        runQuery<MeanReversionRow>(getMeanReversionDirectionSql(rangeWhere)),
        runQuery<ExecutionQualitySummary>(getExecutionQualitySummarySql(tradeWhere)),
        runQuery<ExecutionQualityRow>(getExecutionQualityByStrategySql(tradeWhereNoStrategy)),
        runQuery<SessionExpectancyRow>(getSessionExpectancySql(tradeWhere)),
        runQuery<SweepReclaimSummary>(getSweepReclaimSummarySql(rangeWhere)),
        runQuery<SweepReclaimRow>(getSweepReclaimDirectionSql(rangeWhere)),
        runQuery<BreakoutAcceptanceSummary>(getBreakoutAcceptanceSummarySql(rangeWhere)),
        runQuery<BreakoutAcceptanceRow>(getBreakoutAcceptanceDirectionSql(rangeWhere)),
        runQuery<VolatilityExcursionSummary>(getVolatilityExcursionSql(rangeWhere)),
        runQuery<EdgeStabilitySummary>(getEdgeStabilitySummarySql(tradeWhere)),
        runQuery<EdgeStabilityRow>(getEdgeStabilitySeriesSql(tradeWhere)),
        runQuery<LatestRangeRow>(getLatestRangeSql(rangeWhere)),
      ]);

      setOverview((overviewRows[0] as OverviewMetrics) ?? null);
      setWidthDistribution(widthRows);
      setBreakoutDistribution(breakoutRows);
      setFinalDistribution(finalRows);
      setExtensionStats(extensionRows);
      setStrategyRows(strategyTableRows);
      setEquityCurve(equityRows);
      setBothSidesRows(bothSidesOutcomeRows);
      setBothSidesSummary((bothSidesSummaryRows[0] as BothSidesSummary) ?? null);
      setBothSidesConditionRows(bothSidesConditionLiftRows);
      setMeanReversionSummary((meanReversionSummaryRows[0] as MeanReversionSummary) ?? null);
      setMeanReversionRows(meanReversionDirectionRows);
      setExecutionQualitySummary((executionSummaryRows[0] as ExecutionQualitySummary) ?? null);
      setExecutionQualityRows(executionByStrategyRows);
      setSessionExpectancyRows(sessionExpectancyTableRows);
      setSweepReclaimSummary((sweepReclaimSummaryRows[0] as SweepReclaimSummary) ?? null);
      setSweepReclaimRows(sweepReclaimDirectionRows);
      setBreakoutAcceptanceSummary((breakoutAcceptanceSummaryRows[0] as BreakoutAcceptanceSummary) ?? null);
      setBreakoutAcceptanceRows(breakoutAcceptanceDirectionRows);
      setVolatilityExcursionSummary((volatilityExcursionRows[0] as VolatilityExcursionSummary) ?? null);
      setEdgeStabilitySummary((edgeStabilitySummaryRows[0] as EdgeStabilitySummary) ?? null);
      setEdgeStabilityRows(edgeStabilitySeriesRows);
      setLatestRange((latestRangeRows[0] as LatestRangeRow) ?? null);
      setQueryTimeMs(performance.now() - startedAt);
    } catch (error) {
      console.error('Failed to query range analytics dashboard:', error);
    } finally {
      setLoading(false);
    }
  }, [dbStatus, deferredFilters]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  const refreshData = useCallback(async () => {
    setOverview(null);
    setStrategyRows([]);
    setEquityCurve([]);
    setMeanReversionSummary(null);
    setMeanReversionRows([]);
    await resetDuckDB();
    await loadEngine();
  }, [loadEngine]);

  const focusStrategy = useMemo(() => {
    if (filters.strategyName !== 'ALL') return filters.strategyName;
    return options.strategies.find((strategy) => strategy !== 'ALL') ?? 'ALL';
  }, [filters.strategyName, options.strategies]);

  const focusStrategyMetrics = useMemo(() => {
    return strategyRows.find((row) => row.strategy_name === focusStrategy) ?? strategyRows[0] ?? null;
  }, [focusStrategy, strategyRows]);

  const sweepLiftPositive = useMemo(
    () => bothSidesConditionRows.filter((row) => row.lift > 0),
    [bothSidesConditionRows],
  );

  const topSweepLift = useMemo(
    () => sweepLiftPositive[0] ?? null,
    [sweepLiftPositive],
  );

  useEffect(() => {
    const candidates = options.symbols.filter((symbol) => symbol !== 'ALL');
    if (candidates.length === 0) return;
    if (candidates.includes(gexSymbolOverride)) return;
    if (candidates.includes('NQ1')) {
      setGexSymbolOverride('NQ1');
      return;
    }
    setGexSymbolOverride(candidates[0]);
  }, [options.symbols, gexSymbolOverride]);

  const gexSymbol = useMemo(() => {
    if (deferredFilters.symbol !== 'ALL') return deferredFilters.symbol;
    return gexSymbolOverride;
  }, [deferredFilters.symbol, gexSymbolOverride]);

  useEffect(() => {
    if (!gexSymbol) return;

    const loadGexMacro = async () => {
      setGexLoading(true);
      try {
        const res = await fetch(`/api/options-live/v3/macro?symbol=${encodeURIComponent(gexSymbol)}`, {
          cache: 'no-store',
        });
        const payload = await res.json();
        if (payload?.success && payload?.data) {
          setGexMacro(payload.data as GexMacroData);
        } else {
          setGexMacro(null);
        }
      } catch (error) {
        console.error('Failed to load GEX macro overlay:', error);
        setGexMacro(null);
      } finally {
        setGexLoading(false);
      }
    };

    loadGexMacro().catch((error) => {
      console.error('Failed to trigger GEX macro fetch:', error);
    });
  }, [gexSymbol]);

  const zeroGammaOverlap = useMemo(
    () => describeLevelOverlap(gexMacro?.levels?.zeroGamma ?? null, latestRange),
    [gexMacro, latestRange],
  );

  const callWallOverlap = useMemo(
    () => describeLevelOverlap(gexMacro?.levels?.macroCallWall ?? null, latestRange),
    [gexMacro, latestRange],
  );

  const putWallOverlap = useMemo(
    () => describeLevelOverlap(gexMacro?.levels?.macroPutWall ?? null, latestRange),
    [gexMacro, latestRange],
  );

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(34,211,238,0.12),_transparent_32%),radial-gradient(circle_at_bottom_right,_rgba(245,158,11,0.12),_transparent_28%),#050816] text-zinc-100">
      <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-8 px-6 py-8">
        <div className="flex flex-col gap-5 border-b border-zinc-900 pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-3">
            <Link
              href="/research"
              className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.24em] text-zinc-500 transition hover:text-cyan-300"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Research Hub
            </Link>
            <div className="flex items-center gap-3">
              <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/10 p-3 text-cyan-300">
                <LayoutDashboard className="h-6 w-6" />
              </div>
              <div>
                <h1 className="text-3xl font-semibold tracking-tight">Range Analytics</h1>
                <p className="mt-1 max-w-2xl text-sm text-zinc-400">
                  Phase 4 dashboard slice for opening-range and initial-balance research, backed directly by
                  range records and simulated trades.
                </p>
              </div>
            </div>
          </div>

          <div className="flex flex-col items-start gap-3 lg:items-end">
            <QueryStatus
              dbStatus={dbStatus}
              queryTimeMs={queryTimeMs}
              totalRecords={overview?.total_ranges}
              lastDataUpdate={lastDataUpdate}
            />
            <div className="flex gap-2">
              <Link
                href="/research/range-comparison"
                className="inline-flex items-center rounded-lg border border-zinc-800 bg-zinc-950 px-3 py-2 text-sm text-zinc-100 transition hover:bg-zinc-900"
              >
                Compare Ranges
              </Link>
              <Button
                variant="outline"
                size="sm"
                className="border-zinc-800 bg-zinc-950 text-zinc-100 hover:bg-zinc-900"
                disabled={dbStatus === 'loading' || loading}
                onClick={refreshData}
              >
                <RefreshCcw className={`mr-2 h-4 w-4 ${dbStatus === 'loading' ? 'animate-spin' : ''}`} />
                Refresh Parquet
              </Button>
            </div>
          </div>
        </div>

        <Card className="border-zinc-900 bg-black/30 p-5 backdrop-blur-sm">
          <div className="grid gap-4 lg:grid-cols-[repeat(4,minmax(0,1fr))_140px_140px]">
            <FilterSelect
              label="Symbol"
              value={filters.symbol}
              options={options.symbols.length > 0 ? options.symbols : ['ALL']}
              onChange={(value) => startTransition(() => setFilters((current) => ({ ...current, symbol: value })))}
            />
            <FilterSelect
              label="Range"
              value={filters.rangeName}
              options={options.ranges.length > 0 ? options.ranges : ['ALL']}
              onChange={(value) => startTransition(() => setFilters((current) => ({ ...current, rangeName: value })))}
            />
            <FilterSelect
              label="Strategy"
              value={filters.strategyName}
              options={options.strategies.length > 0 ? options.strategies : ['ALL']}
              onChange={(value) => startTransition(() => setFilters((current) => ({ ...current, strategyName: value })))}
            />
            <FilterSelect
              label="Breakout"
              value={filters.breakoutDirection}
              options={['ALL', 'UP', 'DOWN', 'NONE']}
              onChange={(value) => startTransition(() => setFilters((current) => ({ ...current, breakoutDirection: value })))}
            />
            <label className="flex flex-col gap-2 text-xs uppercase tracking-[0.22em] text-zinc-500">
              <span>Start</span>
              <input
                type="date"
                value={filters.startDate}
                onChange={(event) => startTransition(() => setFilters((current) => ({ ...current, startDate: event.target.value })))}
                className="h-10 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm tracking-normal text-zinc-100 outline-none transition focus:border-cyan-400"
              />
            </label>
            <label className="flex flex-col gap-2 text-xs uppercase tracking-[0.22em] text-zinc-500">
              <span>End</span>
              <input
                type="date"
                value={filters.endDate}
                onChange={(event) => startTransition(() => setFilters((current) => ({ ...current, endDate: event.target.value })))}
                className="h-10 rounded-lg border border-zinc-800 bg-zinc-950 px-3 text-sm tracking-normal text-zinc-100 outline-none transition focus:border-cyan-400"
              />
            </label>
          </div>
        </Card>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Institutional Sample"
            value={overview ? `${Math.round(overview.total_ranges).toLocaleString()} ranges` : '--'}
            accent="text-cyan-300"
            sublabel="Rows after current filter stack"
          />
          <StatCard
            label="Average Width"
            value={overview ? `${formatNumber(overview.avg_width, 1)} pts` : '--'}
            accent="text-amber-300"
            sublabel={overview ? `${formatPct(overview.avg_width_pct, 3)} of instrument price` : undefined}
          />
          <StatCard
            label="Breakout Follow-Through"
            value={overview ? formatPct(overview.aligned_close_rate) : '--'}
            accent="text-emerald-300"
            sublabel={overview ? `${formatPct(overview.failed_breakout_rate)} failed breakout rate` : undefined}
          />
          <StatCard
            label="Focused Strategy"
            value={focusStrategyMetrics ? formatPct(focusStrategyMetrics.win_rate) : '--'}
            accent="text-fuchsia-300"
            sublabel={focusStrategyMetrics ? `${focusStrategyMetrics.strategy_name} · avg R ${formatNumber(focusStrategyMetrics.avg_r)}` : 'No strategy rows'}
          />
        </div>

        <Card className="border-zinc-900 bg-black/30 p-5">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-500">GEX Overlap</div>
              <h2 className="mt-1 text-lg font-semibold">Dealer levels vs latest filtered range</h2>
            </div>
            {deferredFilters.symbol === 'ALL' ? (
              <div className="min-w-[180px]">
                <FilterSelect
                  label="GEX Symbol"
                  value={gexSymbolOverride}
                  options={options.symbols.filter((symbol) => symbol !== 'ALL')}
                  onChange={(value) => setGexSymbolOverride(value)}
                />
              </div>
            ) : (
              <div className="text-right text-xs text-zinc-500">
                <div className="uppercase tracking-[0.18em]">Symbol</div>
                <div className="mt-1 text-sm text-cyan-300">{gexSymbol}</div>
              </div>
            )}
          </div>

          <div className="mb-5 grid gap-4 md:grid-cols-3">
            <StatCard
              label="Latest Range Date"
              value={latestRange?.trading_date ?? '--'}
              accent="text-zinc-200"
              sublabel={latestRange ? `H ${formatNumber(latestRange.range_high)} / L ${formatNumber(latestRange.range_low)}` : 'No filtered range rows'}
            />
            <StatCard
              label="Spot vs Mid"
              value={gexMacro?.spotPrice != null && latestRange ? `${formatNumber(gexMacro.spotPrice)} vs ${formatNumber(latestRange.range_mid)}` : '--'}
              accent="text-amber-300"
              sublabel={gexLoading ? 'Loading dealer snapshot...' : (gexMacro ? `Ticker ${gexMacro.ticker}` : 'No dealer snapshot available')}
            />
            <StatCard
              label="Range Width"
              value={latestRange ? `${formatNumber(latestRange.range_width, 2)} pts` : '--'}
              accent="text-emerald-300"
              sublabel="Used to normalize wall distance"
            />
          </div>

          <div className="overflow-hidden rounded-xl border border-zinc-900">
            <table className="min-w-full divide-y divide-zinc-900 text-sm">
              <thead className="bg-zinc-950/80 text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                <tr>
                  <th className="px-4 py-3 text-left">Dealer Level</th>
                  <th className="px-4 py-3 text-right">Price</th>
                  <th className="px-4 py-3 text-right">Location vs Range</th>
                  <th className="px-4 py-3 text-right">Distance (range widths)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900 bg-black/20">
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">Zero Gamma</td>
                  <td className="px-4 py-3 text-right text-zinc-300">{formatNumber(gexMacro?.levels?.zeroGamma ?? null)}</td>
                  <td className="px-4 py-3 text-right text-cyan-300">{zeroGammaOverlap.location}</td>
                  <td className="px-4 py-3 text-right text-zinc-300">{zeroGammaOverlap.widthUnits}</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">Macro Call Wall</td>
                  <td className="px-4 py-3 text-right text-zinc-300">{formatNumber(gexMacro?.levels?.macroCallWall ?? null)}</td>
                  <td className="px-4 py-3 text-right text-emerald-300">{callWallOverlap.location}</td>
                  <td className="px-4 py-3 text-right text-zinc-300">{callWallOverlap.widthUnits}</td>
                </tr>
                <tr>
                  <td className="px-4 py-3 font-medium text-zinc-200">Macro Put Wall</td>
                  <td className="px-4 py-3 text-right text-zinc-300">{formatNumber(gexMacro?.levels?.macroPutWall ?? null)}</td>
                  <td className="px-4 py-3 text-right text-rose-300">{putWallOverlap.location}</td>
                  <td className="px-4 py-3 text-right text-zinc-300">{putWallOverlap.widthUnits}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </Card>

        <div className="grid gap-6 xl:grid-cols-[1.2fr_1fr]">
          <Card className="border-zinc-900 bg-black/30 p-5">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-500">Range Profile</div>
                <h2 className="mt-1 text-lg font-semibold">Width distribution and directional bias</h2>
              </div>
              <BarChart3 className="h-5 w-5 text-cyan-300" />
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <div className="h-72 rounded-xl border border-zinc-900 bg-zinc-950/60 p-3">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={widthDistribution}>
                    <CartesianGrid vertical={false} stroke="#18181b" />
                    <XAxis dataKey="category" tick={{ fill: '#a1a1aa', fontSize: 12 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: '#71717a', fontSize: 12 }} axisLine={false} tickLine={false} allowDecimals={false} />
                    <Tooltip
                      cursor={{ fill: 'rgba(255,255,255,0.02)' }}
                      contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 12 }}
                    />
                    <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                      {widthDistribution.map((row) => (
                        <Cell key={row.category} fill={WIDTH_CATEGORY_COLORS[row.category] ?? '#94a3b8'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="grid gap-4">
                <DirectionPanel title="First Breakout" rows={breakoutDistribution} />
                <DirectionPanel title="Close Direction" rows={finalDistribution} />
              </div>
            </div>
          </Card>

          <Card className="border-zinc-900 bg-black/30 p-5">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-500">Extension Probability</div>
                <h2 className="mt-1 text-lg font-semibold">Directional hit rates after first break</h2>
              </div>
              <Target className="h-5 w-5 text-amber-300" />
            </div>

            <div className="space-y-3">
              {extensionStats.map((row) => (
                <div key={row.extension} className="rounded-xl border border-zinc-900 bg-zinc-950/60 p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-medium text-zinc-200">{row.extension} extension</div>
                      <div className="text-xs text-zinc-500">Probability aligned to the first breakout direction</div>
                    </div>
                    <div className="text-right">
                      <div className="text-xl font-semibold text-amber-300">{formatPct(row.hit_rate)}</div>
                      <div className="text-xs text-zinc-500">
                        Avg hit time {row.avg_time_minutes != null ? `${row.avg_time_minutes.toFixed(1)}m` : '--'}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        <Card className="border-zinc-900 bg-black/30 p-5">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-500">Mean Reversion</div>
              <h2 className="mt-1 text-lg font-semibold">Midpoint and opposite-side retests after the first break</h2>
            </div>
            <div className="text-right text-xs text-zinc-500">
              <div className="uppercase tracking-[0.18em]">MR_TO_MID</div>
              <div className="mt-1 text-sm text-fuchsia-300">
                {meanReversionSummary ? `${formatPct(meanReversionSummary.mr_win_rate)} · avg R ${formatNumber(meanReversionSummary.mr_avg_r)}` : '--'}
              </div>
            </div>
          </div>

          <div className="mb-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Mid Retest Rate"
              value={meanReversionSummary ? formatPct(meanReversionSummary.mid_retest_rate) : '--'}
              accent="text-cyan-300"
              sublabel={meanReversionSummary ? `${Math.round(meanReversionSummary.sample_count).toLocaleString()} breakout samples` : undefined}
            />
            <StatCard
              label="Opposite Boundary Test"
              value={meanReversionSummary ? formatPct(meanReversionSummary.opposite_retest_rate) : '--'}
              accent="text-amber-300"
              sublabel={meanReversionSummary ? `${formatPct(meanReversionSummary.failed_breakout_rate)} failed breakout rate` : undefined}
            />
            <StatCard
              label="Avg Mid Retest Time"
              value={meanReversionSummary && meanReversionSummary.avg_mid_retest_time != null ? `${meanReversionSummary.avg_mid_retest_time.toFixed(1)}m` : '--'}
              accent="text-emerald-300"
            />
            <StatCard
              label="MR_TO_MID Win Rate"
              value={meanReversionSummary ? formatPct(meanReversionSummary.mr_win_rate) : '--'}
              accent="text-fuchsia-300"
              sublabel={meanReversionSummary ? `Avg R ${formatNumber(meanReversionSummary.mr_avg_r)}` : undefined}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
            <div className="h-72 rounded-xl border border-zinc-900 bg-zinc-950/60 p-3">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={meanReversionRows}>
                  <CartesianGrid vertical={false} stroke="#18181b" />
                  <XAxis dataKey="direction" tick={{ fill: '#a1a1aa', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#71717a', fontSize: 12 }} axisLine={false} tickLine={false} domain={[0, 100]} />
                  <Tooltip
                    cursor={{ fill: 'rgba(255,255,255,0.02)' }}
                    contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 12 }}
                    formatter={(v: number, key: string) => {
                      if (key === 'mid_retest_rate') return [formatPct(v), 'Mid retest'];
                      if (key === 'opposite_retest_rate') return [formatPct(v), 'Opposite-side test'];
                      return [Math.round(v).toLocaleString(), 'Count'];
                    }}
                  />
                  <Bar dataKey="mid_retest_rate" name="mid_retest_rate" fill="#22d3ee" radius={[8, 8, 0, 0]} />
                  <Bar dataKey="opposite_retest_rate" name="opposite_retest_rate" fill="#f59e0b" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="overflow-hidden rounded-xl border border-zinc-900">
              <table className="min-w-full divide-y divide-zinc-900 text-sm">
                <thead className="bg-zinc-950/80 text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                  <tr>
                    <th className="px-4 py-3 text-left">Break Dir</th>
                    <th className="px-4 py-3 text-right">N</th>
                    <th className="px-4 py-3 text-right">Mid Retest %</th>
                    <th className="px-4 py-3 text-right">Opposite %</th>
                    <th className="px-4 py-3 text-right">Avg Mid Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-900 bg-black/20">
                  {meanReversionRows.map((row) => (
                    <tr key={`mr-${row.direction}`}>
                      <td className="px-4 py-3 font-medium text-zinc-200">{row.direction}</td>
                      <td className="px-4 py-3 text-right text-zinc-300">{Math.round(row.count).toLocaleString()}</td>
                      <td className="px-4 py-3 text-right text-cyan-300">{formatPct(row.mid_retest_rate)}</td>
                      <td className="px-4 py-3 text-right text-amber-300">{formatPct(row.opposite_retest_rate)}</td>
                      <td className="px-4 py-3 text-right text-emerald-300">{row.avg_mid_retest_time != null ? `${row.avg_mid_retest_time.toFixed(1)}m` : '--'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </Card>

        <Card className="border-zinc-900 bg-black/30 p-5">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-500">Strategy Simulator</div>
              <h2 className="mt-1 text-lg font-semibold">Performance by preset and rolling equity</h2>
            </div>
            <Activity className="h-5 w-5 text-fuchsia-300" />
          </div>

          <div className="mb-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Median Minutes to Loss"
              value={executionQualitySummary && executionQualitySummary.loss_median_min != null ? `${executionQualitySummary.loss_median_min.toFixed(1)}m` : '--'}
              accent="text-rose-300"
              sublabel={executionQualitySummary ? `${Math.round(executionQualitySummary.loser_count).toLocaleString()} losing trades` : undefined}
            />
            <StatCard
              label="P90 Minutes to Loss"
              value={executionQualitySummary && executionQualitySummary.loss_p90_min != null ? `${executionQualitySummary.loss_p90_min.toFixed(1)}m` : '--'}
              accent="text-amber-300"
              sublabel="Tail of slow-failing losers"
            />
            <StatCard
              label="MAE Before MFE (Winners)"
              value={executionQualitySummary ? formatPct(executionQualitySummary.mae_before_mfe_winner_pct) : '--'}
              accent="text-cyan-300"
              sublabel={executionQualitySummary ? `${Math.round(executionQualitySummary.winner_count).toLocaleString()} winning trades` : undefined}
            />
            <StatCard
              label="Execution Sample"
              value={executionQualitySummary ? Math.round(executionQualitySummary.sample_count).toLocaleString() : '--'}
              accent="text-emerald-300"
              sublabel="Entry-triggered trades with valid timestamps"
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <div className="overflow-hidden rounded-xl border border-zinc-900">
              <table className="min-w-full divide-y divide-zinc-900 text-sm">
                <thead className="bg-zinc-950/80 text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                  <tr>
                    <th className="px-4 py-3 text-left">Strategy</th>
                    <th className="px-4 py-3 text-right">Entries</th>
                    <th className="px-4 py-3 text-right">Entry %</th>
                    <th className="px-4 py-3 text-right">Win %</th>
                    <th className="px-4 py-3 text-right">Avg R</th>
                    <th className="px-4 py-3 text-right">MFE %</th>
                    <th className="px-4 py-3 text-right">MAE %</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-900 bg-black/20">
                  {strategyRows.map((row) => (
                    <tr key={row.strategy_name} className={row.strategy_name === focusStrategy ? 'bg-cyan-500/5' : ''}>
                      <td className="px-4 py-3 font-medium text-zinc-200">{row.strategy_name}</td>
                      <td className="px-4 py-3 text-right text-zinc-300">{Math.round(row.entries).toLocaleString()}</td>
                      <td className="px-4 py-3 text-right text-zinc-300">{formatPct(row.entry_rate)}</td>
                      <td className="px-4 py-3 text-right text-zinc-300">{formatPct(row.win_rate)}</td>
                      <td className="px-4 py-3 text-right text-zinc-300">{formatNumber(row.avg_r)}</td>
                      <td className="px-4 py-3 text-right text-emerald-300">{formatPct(row.avg_mfe_pct)}</td>
                      <td className="px-4 py-3 text-right text-rose-300">{formatPct(row.avg_mae_pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="rounded-xl border border-zinc-900 bg-zinc-950/60 p-4">
              <div className="mb-4 flex items-start justify-between gap-4">
                <div>
                  <div className="text-sm font-medium text-zinc-200">Equity Curve</div>
                  <div className="text-xs text-zinc-500">
                    {filters.strategyName === 'ALL'
                      ? 'Aggregated by day across all visible strategies'
                      : `Daily cumulative R for ${filters.strategyName}`}
                  </div>
                </div>
                <div className="text-right text-xs text-zinc-500">
                  <div className="uppercase tracking-[0.18em]">Focus</div>
                  <div className="mt-1 text-sm text-fuchsia-300">{filters.strategyName === 'ALL' ? 'All strategies' : filters.strategyName}</div>
                </div>
              </div>

              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={equityCurve}>
                    <CartesianGrid vertical={false} stroke="#18181b" />
                    <XAxis dataKey="trading_date" tick={{ fill: '#71717a', fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={24} />
                    <YAxis tick={{ fill: '#71717a', fontSize: 11 }} axisLine={false} tickLine={false} width={40} />
                    <Tooltip
                      cursor={{ stroke: '#22d3ee', strokeOpacity: 0.18 }}
                      contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 12 }}
                    />
                    <Line type="monotone" dataKey="equity_r" stroke="#e879f9" strokeWidth={2.5} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              <div className="mt-4 grid grid-cols-3 gap-3 text-xs">
                <MiniMetric
                  label="Selected Trades"
                  value={overview ? Math.round(overview.strategy_entries).toLocaleString() : '--'}
                  icon={<Database className="h-3.5 w-3.5" />}
                />
                <MiniMetric
                  label="Win Rate"
                  value={overview ? formatPct(overview.strategy_win_rate) : '--'}
                  icon={<TrendingUp className="h-3.5 w-3.5" />}
                />
                <MiniMetric
                  label="Avg R"
                  value={overview ? formatNumber(overview.avg_r_multiple) : '--'}
                  icon={<Activity className="h-3.5 w-3.5" />}
                />
              </div>
            </div>
          </div>

          <div className="mt-6 overflow-hidden rounded-xl border border-zinc-900">
            <table className="min-w-full divide-y divide-zinc-900 text-sm">
              <thead className="bg-zinc-950/80 text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                <tr>
                  <th className="px-4 py-3 text-left">Strategy</th>
                  <th className="px-4 py-3 text-right">N</th>
                  <th className="px-4 py-3 text-right">Median Loss Min</th>
                  <th className="px-4 py-3 text-right">P90 Loss Min</th>
                  <th className="px-4 py-3 text-right">MAE→MFE Winner %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900 bg-black/20">
                {executionQualityRows.map((row) => (
                  <tr key={`exec-${row.strategy_name}`}>
                    <td className="px-4 py-3 font-medium text-zinc-200">{row.strategy_name}</td>
                    <td className="px-4 py-3 text-right text-zinc-300">{Math.round(row.sample_count).toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-rose-300">{row.loss_median_min != null ? `${row.loss_median_min.toFixed(1)}m` : '--'}</td>
                    <td className="px-4 py-3 text-right text-amber-300">{row.loss_p90_min != null ? `${row.loss_p90_min.toFixed(1)}m` : '--'}</td>
                    <td className="px-4 py-3 text-right text-cyan-300">{formatPct(row.mae_before_mfe_winner_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-6 overflow-hidden rounded-xl border border-zinc-900">
            <table className="min-w-full divide-y divide-zinc-900 text-sm">
              <thead className="bg-zinc-950/80 text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                <tr>
                  <th className="px-4 py-3 text-left">Entry Session Segment</th>
                  <th className="px-4 py-3 text-right">N</th>
                  <th className="px-4 py-3 text-right">Win %</th>
                  <th className="px-4 py-3 text-right">Avg R</th>
                  <th className="px-4 py-3 text-right">Median R</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900 bg-black/20">
                {sessionExpectancyRows.map((row) => (
                  <tr key={`session-exp-${row.session_segment}`}>
                    <td className="px-4 py-3 font-medium text-zinc-200">{row.session_segment}</td>
                    <td className="px-4 py-3 text-right text-zinc-300">{Math.round(row.sample_count).toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-cyan-300">{formatPct(row.win_rate)}</td>
                    <td className={`px-4 py-3 text-right ${row.avg_r != null && row.avg_r >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                      {formatNumber(row.avg_r)}
                    </td>
                    <td className={`px-4 py-3 text-right ${row.median_r != null && row.median_r >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                      {formatNumber(row.median_r)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="border-zinc-900 bg-black/30 p-5">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-500">Both-Sides Sweep</div>
              <h2 className="mt-1 text-lg font-semibold">When both boundaries are taken, what happens next?</h2>
            </div>
            <div className="text-right text-xs text-zinc-500">
              <div className="uppercase tracking-[0.18em]">Incidence</div>
              <div className="mt-1 text-sm text-cyan-300">
                {bothSidesSummary ? `${Math.round(bothSidesSummary.count).toLocaleString()} (${formatPct(bothSidesSummary.share_of_sample)})` : '--'}
              </div>
            </div>
          </div>

          <div className="mb-6 grid gap-4 md:grid-cols-3">
            <StatCard
              label="Sweep Probability"
              value={bothSidesSummary ? formatPct(bothSidesSummary.share_of_sample) : '--'}
              accent="text-cyan-300"
              sublabel={bothSidesSummary ? `${Math.round(bothSidesSummary.count).toLocaleString()} sweep days` : undefined}
            />
            <StatCard
              label="Top Lift Condition"
              value={topSweepLift ? `${topSweepLift.dimension}: ${topSweepLift.bucket}` : '--'}
              accent="text-amber-300"
              sublabel={topSweepLift ? `${formatPct(topSweepLift.sweep_prob)} (${topSweepLift.lift >= 0 ? '+' : ''}${topSweepLift.lift.toFixed(1)}pp vs base)` : 'Need >=30 sample rows'}
            />
            <StatCard
              label="Top Condition Sample"
              value={topSweepLift ? Math.round(topSweepLift.sample_count).toLocaleString() : '--'}
              accent="text-emerald-300"
              sublabel={topSweepLift ? `Sweeps: ${Math.round(topSweepLift.sweep_count).toLocaleString()}` : undefined}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
            <div className="h-72 rounded-xl border border-zinc-900 bg-zinc-950/60 p-3">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={bothSidesRows}>
                  <CartesianGrid vertical={false} stroke="#18181b" />
                  <XAxis dataKey="final_direction" tick={{ fill: '#a1a1aa', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#71717a', fontSize: 12 }} axisLine={false} tickLine={false} domain={[0, 100]} />
                  <Tooltip
                    cursor={{ fill: 'rgba(255,255,255,0.02)' }}
                    contentStyle={{ background: '#09090b', border: '1px solid #27272a', borderRadius: 12 }}
                    formatter={(v: number, key: string) => {
                      if (key === 'failed_rate') return [formatPct(v), 'Failed breakout'];
                      if (key === 'aligned_close_rate') return [formatPct(v), 'Close aligns with first break'];
                      if (key === 'ext_1x_hit_rate') return [formatPct(v), '1.0x extension hit'];
                      return [Math.round(v).toLocaleString(), 'Count'];
                    }}
                  />
                  <Bar dataKey="failed_rate" name="failed_rate" fill="#fb7185" radius={[8, 8, 0, 0]} />
                  <Bar dataKey="ext_1x_hit_rate" name="ext_1x_hit_rate" fill="#38bdf8" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="overflow-hidden rounded-xl border border-zinc-900">
              <table className="min-w-full divide-y divide-zinc-900 text-sm">
                <thead className="bg-zinc-950/80 text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                  <tr>
                    <th className="px-4 py-3 text-left">Final Dir</th>
                    <th className="px-4 py-3 text-right">N</th>
                    <th className="px-4 py-3 text-right">Failed %</th>
                    <th className="px-4 py-3 text-right">Align Close %</th>
                    <th className="px-4 py-3 text-right">1.0x Hit %</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-900 bg-black/20">
                  {bothSidesRows.map((row) => (
                    <tr key={`both-${row.final_direction}`}>
                      <td className="px-4 py-3 font-medium text-zinc-200">{row.final_direction}</td>
                      <td className="px-4 py-3 text-right text-zinc-300">{Math.round(row.count).toLocaleString()}</td>
                      <td className="px-4 py-3 text-right text-rose-300">{formatPct(row.failed_rate)}</td>
                      <td className="px-4 py-3 text-right text-emerald-300">{formatPct(row.aligned_close_rate)}</td>
                      <td className="px-4 py-3 text-right text-cyan-300">{formatPct(row.ext_1x_hit_rate)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="mt-6 overflow-hidden rounded-xl border border-zinc-900">
            <table className="min-w-full divide-y divide-zinc-900 text-sm">
              <thead className="bg-zinc-950/80 text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                <tr>
                  <th className="px-4 py-3 text-left">Condition</th>
                  <th className="px-4 py-3 text-left">Bucket</th>
                  <th className="px-4 py-3 text-right">N</th>
                  <th className="px-4 py-3 text-right">Sweep %</th>
                  <th className="px-4 py-3 text-right">Lift vs Base</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900 bg-black/20">
                {bothSidesConditionRows.slice(0, 12).map((row) => (
                  <tr key={`${row.dimension}-${row.bucket}`}>
                    <td className="px-4 py-3 font-medium text-zinc-200">{row.dimension}</td>
                    <td className="px-4 py-3 text-zinc-300">{row.bucket}</td>
                    <td className="px-4 py-3 text-right text-zinc-300">{Math.round(row.sample_count).toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-cyan-300">{formatPct(row.sweep_prob)}</td>
                    <td className={`px-4 py-3 text-right ${row.lift >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                      {`${row.lift >= 0 ? '+' : ''}${row.lift.toFixed(1)}pp`}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="border-zinc-900 bg-black/30 p-5">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-500">Sweep → Reclaim Efficiency</div>
              <h2 className="mt-1 text-lg font-semibold">Boundary reclaim quality after first sweep</h2>
            </div>
            <ArrowRight className="h-5 w-5 text-cyan-300" />
          </div>

          <div className="mb-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Sweep Sample"
              value={sweepReclaimSummary ? Math.round(sweepReclaimSummary.sample_count).toLocaleString() : '--'}
              accent="text-zinc-200"
            />
            <StatCard
              label="Reclaim Rate"
              value={sweepReclaimSummary ? formatPct(sweepReclaimSummary.reclaim_rate) : '--'}
              accent="text-cyan-300"
              sublabel="Retested broken boundary"
            />
            <StatCard
              label="Continuation Rate"
              value={sweepReclaimSummary ? formatPct(sweepReclaimSummary.continuation_rate) : '--'}
              accent="text-emerald-300"
              sublabel="Final direction matched first break"
            />
            <StatCard
              label="Median Follow-Through"
              value={sweepReclaimSummary && sweepReclaimSummary.median_follow_through_pct != null ? `${sweepReclaimSummary.median_follow_through_pct.toFixed(1)}%` : '--'}
              accent="text-amber-300"
              sublabel="Directional excursion (% of range width)"
            />
          </div>

          <div className="overflow-hidden rounded-xl border border-zinc-900">
            <table className="min-w-full divide-y divide-zinc-900 text-sm">
              <thead className="bg-zinc-950/80 text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                <tr>
                  <th className="px-4 py-3 text-left">First Sweep Direction</th>
                  <th className="px-4 py-3 text-right">N</th>
                  <th className="px-4 py-3 text-right">Reclaim %</th>
                  <th className="px-4 py-3 text-right">Continuation %</th>
                  <th className="px-4 py-3 text-right">Median Follow-Through %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900 bg-black/20">
                {sweepReclaimRows.map((row) => (
                  <tr key={`sweep-reclaim-${row.first_bo_direction}`}>
                    <td className="px-4 py-3 font-medium text-zinc-200">{row.first_bo_direction}</td>
                    <td className="px-4 py-3 text-right text-zinc-300">{Math.round(row.sample_count).toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-cyan-300">{formatPct(row.reclaim_rate)}</td>
                    <td className="px-4 py-3 text-right text-emerald-300">{formatPct(row.continuation_rate)}</td>
                    <td className="px-4 py-3 text-right text-amber-300">{row.median_follow_through_pct != null ? `${row.median_follow_through_pct.toFixed(1)}%` : '--'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="border-zinc-900 bg-black/30 p-5">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-500">Breakout Acceptance</div>
              <h2 className="mt-1 text-lg font-semibold">Hold quality after boundary break</h2>
            </div>
            <Target className="h-5 w-5 text-amber-300" />
          </div>

          <div className="mb-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="2-Bar Hold Rate"
              value={breakoutAcceptanceSummary ? formatPct(breakoutAcceptanceSummary.hold_2bar_rate) : '--'}
              accent="text-cyan-300"
              sublabel={breakoutAcceptanceSummary ? `${Math.round(breakoutAcceptanceSummary.sample_count).toLocaleString()} breakout rows` : undefined}
            />
            <StatCard
              label="Retest Rate"
              value={breakoutAcceptanceSummary ? formatPct(breakoutAcceptanceSummary.retest_rate) : '--'}
              accent="text-amber-300"
              sublabel="Broken boundary revisited"
            />
            <StatCard
              label="Failure Rate"
              value={breakoutAcceptanceSummary ? formatPct(breakoutAcceptanceSummary.fail_rate) : '--'}
              accent="text-rose-300"
              sublabel="Break failed back inside"
            />
            <StatCard
              label="Continuation Rate"
              value={breakoutAcceptanceSummary ? formatPct(breakoutAcceptanceSummary.continuation_rate) : '--'}
              accent="text-emerald-300"
              sublabel="Close aligned with first break"
            />
          </div>

          <div className="overflow-hidden rounded-xl border border-zinc-900">
            <table className="min-w-full divide-y divide-zinc-900 text-sm">
              <thead className="bg-zinc-950/80 text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                <tr>
                  <th className="px-4 py-3 text-left">Break Direction</th>
                  <th className="px-4 py-3 text-right">N</th>
                  <th className="px-4 py-3 text-right">2-Bar Hold %</th>
                  <th className="px-4 py-3 text-right">Retest %</th>
                  <th className="px-4 py-3 text-right">Failure %</th>
                  <th className="px-4 py-3 text-right">Continuation %</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-900 bg-black/20">
                {breakoutAcceptanceRows.map((row) => (
                  <tr key={`accept-${row.first_bo_direction}`}>
                    <td className="px-4 py-3 font-medium text-zinc-200">{row.first_bo_direction}</td>
                    <td className="px-4 py-3 text-right text-zinc-300">{Math.round(row.sample_count).toLocaleString()}</td>
                    <td className="px-4 py-3 text-right text-cyan-300">{formatPct(row.hold_2bar_rate)}</td>
                    <td className="px-4 py-3 text-right text-amber-300">{formatPct(row.retest_rate)}</td>
                    <td className="px-4 py-3 text-right text-rose-300">{formatPct(row.fail_rate)}</td>
                    <td className="px-4 py-3 text-right text-emerald-300">{formatPct(row.continuation_rate)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <div className="grid gap-6 xl:grid-cols-2">
          <Card className="border-zinc-900 bg-black/30 p-5">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-500">Volatility-Normalized Excursion</div>
                <h2 className="mt-1 text-lg font-semibold">Directional vs adverse excursion efficiency</h2>
              </div>
              <BarChart3 className="h-5 w-5 text-cyan-300" />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <StatCard
                label="Avg Directional Excursion"
                value={volatilityExcursionSummary && volatilityExcursionSummary.avg_directional_excursion_pct != null ? `${volatilityExcursionSummary.avg_directional_excursion_pct.toFixed(1)}%` : '--'}
                accent="text-emerald-300"
                sublabel="% of range width"
              />
              <StatCard
                label="Avg Adverse Excursion"
                value={volatilityExcursionSummary && volatilityExcursionSummary.avg_adverse_excursion_pct != null ? `${volatilityExcursionSummary.avg_adverse_excursion_pct.toFixed(1)}%` : '--'}
                accent="text-rose-300"
                sublabel="% of range width"
              />
              <StatCard
                label="Excursion Efficiency"
                value={volatilityExcursionSummary && volatilityExcursionSummary.excursion_efficiency_pct != null ? `${volatilityExcursionSummary.excursion_efficiency_pct.toFixed(1)}%` : '--'}
                accent="text-cyan-300"
                sublabel="Directional minus adverse"
              />
              <StatCard
                label="Directional/Adverse Ratio"
                value={volatilityExcursionSummary ? formatNumber(volatilityExcursionSummary.directional_to_adverse_ratio) : '--'}
                accent="text-amber-300"
                sublabel={volatilityExcursionSummary ? `${Math.round(volatilityExcursionSummary.sample_count).toLocaleString()} rows` : undefined}
              />
            </div>
          </Card>

          <Card className="border-zinc-900 bg-black/30 p-5">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <div className="text-[10px] uppercase tracking-[0.24em] text-zinc-500">Edge Stability</div>
                <h2 className="mt-1 text-lg font-semibold">Rolling performance health checks</h2>
              </div>
              <TrendingUp className="h-5 w-5 text-fuchsia-300" />
            </div>

            <div className="mb-5 grid gap-4 md:grid-cols-2">
              <StatCard
                label="Rolling Win 30"
                value={edgeStabilitySummary ? formatPct(edgeStabilitySummary.rolling_win_30) : '--'}
                accent="text-cyan-300"
                sublabel={edgeStabilitySummary ? `As of ${edgeStabilitySummary.trading_date}` : undefined}
              />
              <StatCard
                label="Rolling Win 90"
                value={edgeStabilitySummary ? formatPct(edgeStabilitySummary.rolling_win_90) : '--'}
                accent="text-emerald-300"
              />
              <StatCard
                label="Rolling Avg R 30"
                value={edgeStabilitySummary ? formatNumber(edgeStabilitySummary.rolling_avg_r_30) : '--'}
                accent="text-amber-300"
              />
              <StatCard
                label="Win-Rate Z-Score"
                value={edgeStabilitySummary ? formatNumber(edgeStabilitySummary.win_rate_zscore_30) : '--'}
                accent="text-fuchsia-300"
                sublabel="Daily win-rate standard deviations from baseline"
              />
            </div>

            <div className="overflow-hidden rounded-xl border border-zinc-900">
              <table className="min-w-full divide-y divide-zinc-900 text-sm">
                <thead className="bg-zinc-950/80 text-[10px] uppercase tracking-[0.2em] text-zinc-500">
                  <tr>
                    <th className="px-4 py-3 text-left">Date</th>
                    <th className="px-4 py-3 text-right">Win30 %</th>
                    <th className="px-4 py-3 text-right">Win90 %</th>
                    <th className="px-4 py-3 text-right">AvgR30</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-900 bg-black/20">
                  {edgeStabilityRows.slice(0, 10).map((row) => (
                    <tr key={`edge-${row.trading_date}`}>
                      <td className="px-4 py-3 font-medium text-zinc-200">{row.trading_date}</td>
                      <td className="px-4 py-3 text-right text-cyan-300">{formatPct(row.rolling_win_30)}</td>
                      <td className="px-4 py-3 text-right text-emerald-300">{formatPct(row.rolling_win_90)}</td>
                      <td className={`px-4 py-3 text-right ${row.rolling_avg_r_30 != null && row.rolling_avg_r_30 >= 0 ? 'text-amber-300' : 'text-rose-300'}`}>
                        {formatNumber(row.rolling_avg_r_30)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function DirectionPanel({ title, rows }: { title: string; rows: DirectionRow[] }) {
  return (
    <Card className="border-zinc-900 bg-zinc-950/60 p-4">
      <div className="mb-3 text-sm font-medium text-zinc-200">{title}</div>
      <div className="space-y-3">
        {rows.map((row) => (
          <div key={`${title}-${row.direction}`}>
            <div className="mb-1 flex items-center justify-between text-xs text-zinc-400">
              <span>{row.direction}</span>
              <span>{Math.round(row.count).toLocaleString()}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-zinc-900">
              <div
                className={`h-full rounded-full ${row.direction === 'UP' ? 'bg-emerald-400' : row.direction === 'DOWN' ? 'bg-rose-400' : 'bg-zinc-500'}`}
                style={{ width: `${rows.length > 0 ? (row.count / rows.reduce((sum, item) => sum + item.count, 0)) * 100 : 0}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function MiniMetric({ label, value, icon }: { label: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-zinc-900 bg-black/30 p-3">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.18em] text-zinc-500">
        {icon}
        <span>{label}</span>
      </div>
      <div className="mt-2 text-lg font-semibold text-zinc-100">{value}</div>
    </div>
  );
}