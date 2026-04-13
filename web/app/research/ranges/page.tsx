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

function formatPct(value: number | null | undefined, digits = 1) {
  if (value == null || Number.isNaN(value)) return '--';
  return `${value.toFixed(digits)}%`;
}

function formatNumber(value: number | null | undefined, digits = 2) {
  if (value == null || Number.isNaN(value)) return '--';
  return value.toFixed(digits);
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
  const [meanReversionSummary, setMeanReversionSummary] = useState<MeanReversionSummary | null>(null);
  const [meanReversionRows, setMeanReversionRows] = useState<MeanReversionRow[]>([]);

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

      const [overviewRows, widthRows, breakoutRows, finalRows, extensionRows, strategyTableRows, equityRows, bothSidesOutcomeRows, bothSidesSummaryRows, meanReversionSummaryRows, meanReversionDirectionRows] = await Promise.all([
        runQuery<OverviewMetrics>(getOverviewSql(rangeWhere, tradeWhere)),
        runQuery<WidthDistributionRow>(getWidthDistributionSql(rangeWhere)),
        runQuery<DirectionRow>(getDirectionSql(rangeWhere, 'first_bo_direction')),
        runQuery<DirectionRow>(getDirectionSql(rangeWhere, 'final_direction')),
        runQuery<ExtensionRow>(getExtensionSql(rangeWhere)),
        runQuery<StrategyRow>(getStrategyTableSql(tradeWhereNoStrategy)),
        runQuery<EquityRow>(getEquitySql(tradeWhere)),
        runQuery<BothSidesOutcomeRow>(getBothSidesOutcomeSql(rangeWhere)),
        runQuery<BothSidesSummary>(getBothSidesSummarySql(rangeWhere)),
        runQuery<MeanReversionSummary>(getMeanReversionSummarySql(rangeWhere, tradeWhereNoStrategy)),
        runQuery<MeanReversionRow>(getMeanReversionDirectionSql(rangeWhere)),
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
      setMeanReversionSummary((meanReversionSummaryRows[0] as MeanReversionSummary) ?? null);
      setMeanReversionRows(meanReversionDirectionRows);
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
        </Card>
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