import { MacroFilterState } from '../types';

/**
 * SQL Query Builder for the Edgeful Dashboard.
 * Maps the React filter state to optimized DuckDB SQL conditions.
 */

function isActiveRange(range: [number, number] | null, min: number, max: number): range is [number, number] {
  return !!range && (range[0] > min || range[1] < max);
}

function isBooleanFilter(value: boolean | null | undefined): value is boolean {
  return value === true || value === false;
}

// Columns that live exclusively in macro_records (used to qualify in JOIN contexts)
const MACRO_ONLY_COLS = [
  'instrument', 'macro_name_raw', 'ict_alias', 'judas_classification',
  'indicator_label', 'vix_regime', 'day_of_week', 'trading_date',
  'real_direction', 'has_fvg', 'is_complete', 'news_within_60m',
  'open_vs_midnight', 'open_vs_daily_open', 'macro_open_vs_rth_bar',
  'judas_first', 'is_opex_week', 'prior_macro_real_direction',
  'same_direction_as_prior', 'macro_streak', 'macro_range_pct',
  'judas_magnitude_pct', 'excursion_above_pct', 'excursion_below_pct',
  'judas_excursion_ratio', 'post_macro_retested_mid', 'mid_retest_win',
];

export function buildWhereClause(filters: MacroFilterState, tableAlias?: string): string {
  const conditions: string[] = [];

  // 1. Primary Filters
  if (filters.instruments.length > 0) {
    conditions.push(`instrument IN (${filters.instruments.map(i => `'${i}'`).join(',')})`);
  }
  
  if (filters.macroWindows.length > 0) {
    // Check both raw name and alias
    const windows = filters.macroWindows.map(m => `'${m}'`).join(',');
    conditions.push(`(macro_name_raw IN (${windows}) OR ict_alias IN (${windows}))`);
  }
  
  if (filters.judasClass.length > 0) {
    conditions.push(`judas_classification IN (${filters.judasClass.map(j => `'${j}'`).join(',')})`);
  }
  
  if (filters.indicatorClass.length > 0) {
    conditions.push(`indicator_label IN (${filters.indicatorClass.map(i => `'${i}'`).join(',')})`);
  }
  
  if (filters.vixRegimes.length > 0) {
    conditions.push(`vix_regime IN (${filters.vixRegimes.map(v => `'${v}'`).join(',')})`);
  }
  
  if (filters.daysOfWeek.length > 0) {
    conditions.push(`day_of_week IN (${filters.daysOfWeek.map(d => `'${d}'`).join(',')})`);
  }

  if (filters.ictAliases.length > 0) {
    conditions.push(`ict_alias IN (${filters.ictAliases.map(a => `'${a}'`).join(',')})`);
  }

  // 2. Date Range
  if (filters.dateRange.start) {
    conditions.push(`trading_date >= '${filters.dateRange.start}'`);
  }
  if (filters.dateRange.end) {
    conditions.push(`trading_date <= '${filters.dateRange.end}'`);
  }

  // 3. Advanced Filters
  if (filters.advanced.realDirection.length > 0) {
    conditions.push(`real_direction IN (${filters.advanced.realDirection.map(d => `'${d}'`).join(',')})`);
  }
  
  if (isBooleanFilter(filters.advanced.hasFVG)) {
    conditions.push(`has_fvg = ${filters.advanced.hasFVG}`);
  }

  if (isBooleanFilter(filters.advanced.isComplete)) {
    conditions.push(`is_complete = ${filters.advanced.isComplete}`);
  }
  
  if (filters.advanced.newsWithin60m === true) {
    conditions.push(`news_within_60m = true`);
  } else if (filters.advanced.newsWithin60m === false) {
    conditions.push(`news_within_60m = false`);
  }

  // Institutional Anchors (Simple absolute price comparison)
  if (filters.advanced.openVsMidnight.length > 0) {
    const values = filters.advanced.openVsMidnight.map(v => `'${v}'`).join(',');
    conditions.push(`open_vs_midnight IN (${values})`);
  }
  
  if (filters.advanced.openVsDailyOpen.length > 0) {
    conditions.push(`open_vs_daily_open IN (${filters.advanced.openVsDailyOpen.map(v => `'${v}'`).join(',')})`);
  }
  
  if (filters.advanced.openVsRthBar.length > 0) {
    conditions.push(`macro_open_vs_rth_bar IN (${filters.advanced.openVsRthBar.map(v => `'${v}'`).join(',')})`);
  }

  if (isBooleanFilter(filters.advanced.judasFirst)) {
    conditions.push(`judas_first = ${filters.advanced.judasFirst}`);
  }

  if (isBooleanFilter(filters.advanced.isOpExWeek)) {
    conditions.push(`is_opex_week = ${filters.advanced.isOpExWeek}`);
  }

  if (filters.advanced.priorMacroDirection.length > 0) {
    const values = filters.advanced.priorMacroDirection.map(d => `'${d}'`).join(',');
    conditions.push(`prior_macro_real_direction IN (${values})`);
  }

  if (isBooleanFilter(filters.advanced.sameDirectionAsPrior)) {
    conditions.push(`same_direction_as_prior = ${filters.advanced.sameDirectionAsPrior}`);
  }

  if (isActiveRange(filters.advanced.macroStreak, 1, 10)) {
    conditions.push(`macro_streak BETWEEN ${filters.advanced.macroStreak[0]} AND ${filters.advanced.macroStreak[1]}`);
  }

  if (isActiveRange(filters.advanced.macroRangePercentile, 0, 4)) {
    conditions.push(`macro_range_pct BETWEEN ${filters.advanced.macroRangePercentile[0]} AND ${filters.advanced.macroRangePercentile[1]}`);
  }

  // Multi-Range Filtering (PERCENTAGES)
  if (isActiveRange(filters.advanced.magnitudeRange, 0, 4)) {
    conditions.push(`judas_magnitude_pct BETWEEN ${filters.advanced.magnitudeRange[0]} AND ${filters.advanced.magnitudeRange[1]}`);
  }

  if (isActiveRange(filters.advanced.excursionRange, 0, 4)) {
    const [min, max] = filters.advanced.excursionRange;
    conditions.push(`((excursion_above_pct BETWEEN ${min} AND ${max}) OR (excursion_below_pct BETWEEN ${min} AND ${max}))`);
  }

  if (filters.advanced.judasExcursionThreshold !== null && filters.advanced.judasExcursionThreshold > 0) {
    conditions.push(`(judas_classification NOT IN ('bullish_judas', 'bearish_judas') OR judas_excursion_ratio >= ${filters.advanced.judasExcursionThreshold})`);
  }

  if (isBooleanFilter(filters.advanced.midRetested)) {
    conditions.push(`post_macro_retested_mid = ${filters.advanced.midRetested}`);
  }

  if (isBooleanFilter(filters.advanced.midRetestWin)) {
    if (filters.advanced.midRetestWin) {
      conditions.push(`mid_retest_win = true`);
    } else {
      conditions.push(`(mid_retest_win = false OR mid_retest_win IS NULL)`);
    }
  }

  if (conditions.length === 0) return '';

  let joined = conditions.join(' AND ');
  if (tableAlias) {
    for (const col of MACRO_ONLY_COLS) {
      joined = joined.replace(new RegExp(`\\b${col}\\b`, 'g'), `${tableAlias}.${col}`);
    }
  }

  return `WHERE ${joined}`;
}

/**
 * Generates the SQL for the Summary Metrics cards
 */
export function getSummarySql(whereClause: string): string {
  return `
    SELECT 
      CAST(COUNT(*) AS DOUBLE) as total,
      CAST(COUNT(CASE WHEN judas_classification IN ('bullish_judas', 'bearish_judas') THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) AS DOUBLE) as judas_rate,
      CAST(AVG(post_macro_continuation_pct) AS DOUBLE) as avg_continuation,
      CAST(COUNT(CASE WHEN post_macro_continuation_pct > post_macro_reversion_pct THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) AS DOUBLE) as continuation_win_rate,
      CAST(COUNT(CASE WHEN post_macro_reversion_pct > post_macro_continuation_pct THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) AS DOUBLE) as reversion_rate,
      CAST(AVG(post_macro_mfe_pct) AS DOUBLE) as avg_mfe,
      CAST(AVG(post_macro_mae_pct) AS DOUBLE) as avg_mae,
      CAST(COUNT(CASE WHEN post_macro_retested_mid THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) AS DOUBLE) as mid_retest_rate,
      CAST(AVG(CASE WHEN post_macro_retested_mid THEN CASE WHEN mid_retest_win THEN 1.0 ELSE 0.0 END END) * 100.0 AS DOUBLE) as mid_entry_win_rate,
      CAST(AVG(CASE WHEN post_macro_retested_mid THEN mid_retest_mfe_pct END) AS DOUBLE) as avg_mid_mfe,
      CAST(AVG(CASE WHEN post_macro_retested_mid THEN mid_retest_mae_pct END) AS DOUBLE) as avg_mid_mae,
      CAST(AVG(CASE WHEN post_macro_retested_mid THEN mid_retest_rr END) AS DOUBLE) as avg_mid_rr,
      CAST(AVG(CASE WHEN post_macro_retested_mid THEN mid_retest_time_m END) AS DOUBLE) as avg_retest_time_m
    FROM macro_records
    ${whereClause}
  `;
}

/**
 * Generates SQL for a histogram distribution
 */
export function getHistogramSql(column: string, whereClause: string, binWidth: number = 0.0001): string {
  const extraCondition = `${column} IS NOT NULL`;
  const finalWhere = whereClause ? `${whereClause} AND ${extraCondition}` : `WHERE ${extraCondition}`;

  return `
    SELECT 
      CAST(FLOOR(${column} / ${binWidth}) * ${binWidth} AS DOUBLE) as bin_start,
      CAST(COUNT(*) AS DOUBLE) as count
    FROM macro_records
    ${finalWhere}
    GROUP BY bin_start
    ORDER BY bin_start
  `;
}

/**
 * Generates SQL for summary statistics of a numeric distribution.
 */
export function getDistributionStatsSql(column: string, whereClause: string, extraCondition?: string): string {
  const conditions = [`${column} IS NOT NULL`];
  if (extraCondition) {
    conditions.push(extraCondition);
  }

  const mergedCondition = conditions.join(' AND ');
  const finalWhere = whereClause ? `${whereClause} AND ${mergedCondition}` : `WHERE ${mergedCondition}`;

  return `
    WITH filtered AS (
      SELECT ${column} AS val
      FROM macro_records
      ${finalWhere}
    ),
    mode_calc AS (
      SELECT val AS mode_val
      FROM (
        SELECT val, COUNT(*) AS c
        FROM filtered
        GROUP BY val
        ORDER BY c DESC, val ASC
        LIMIT 1
      ) m
    )
    SELECT
      CAST(COUNT(*) AS DOUBLE) AS n,
      CAST(AVG(val) AS DOUBLE) AS mean,
      CAST(PERCENTILE_CONT(0.10) WITHIN GROUP (ORDER BY val) AS DOUBLE) AS p10,
      CAST(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY val) AS DOUBLE) AS p25,
      CAST(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY val) AS DOUBLE) AS median,
      CAST(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY val) AS DOUBLE) AS p75,
      CAST(PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY val) AS DOUBLE) AS p90,
      CAST(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY val) AS DOUBLE) AS p95,
      CAST((SELECT mode_val FROM mode_calc) AS DOUBLE) AS mode,
      CAST(STDDEV(val) AS DOUBLE) AS std_dev,
      CAST(MIN(val) AS DOUBLE) AS min_val,
      CAST(MAX(val) AS DOUBLE) AS max_val
    FROM filtered
  `;
}

/**
 * Generates SQL for a Cross-Tabulation (Probability Matrix)
 */
export function getCrossTabSql(rowCol: string, colCol: string, whereClause: string): string {
  // We want to count occurrences for each intersecting cell
  const extraCondition = `${rowCol} IS NOT NULL AND ${colCol} IS NOT NULL`;
  const finalWhere = whereClause ? `${whereClause} AND ${extraCondition}` : `WHERE ${extraCondition}`;

  return `
    SELECT 
      ${rowCol} as row_val,
      ${colCol} as col_val,
      CAST(COUNT(*) AS DOUBLE) as count
    FROM macro_records
    ${finalWhere}
    GROUP BY ${rowCol}, ${colCol}
    ORDER BY ${rowCol}, ${colCol}
  `;
}

/**
 * Generates SQL for a metric-aware Cross-Tabulation (Probability Matrix)
 */
export function getCrossTabMetricSql(
  rowCol: string,
  colCol: string,
  metricExpr: string,
  whereClause: string
): string {
  const extraCondition = `${rowCol} IS NOT NULL AND ${colCol} IS NOT NULL`;
  const finalWhere = whereClause ? `${whereClause} AND ${extraCondition}` : `WHERE ${extraCondition}`;

  return `
    SELECT 
      ${rowCol} as row_val,
      ${colCol} as col_val,
      CAST(${metricExpr} AS DOUBLE) as value,
      CAST(COUNT(*) AS DOUBLE) as n
    FROM macro_records
    ${finalWhere}
    GROUP BY ${rowCol}, ${colCol}
    ORDER BY ${rowCol}, ${colCol}
  `;
}

/**
 * Generates SQL for Paginated Data Drill-Down
 */
export function getRecordsSql(whereClause: string, offset: number, limit: number, sortColumn: string = 'trading_date', sortDirection: 'asc' | 'desc' = 'desc'): string {
  // Prevent SQL injection on identifiers
  const cleanSortColumn = sortColumn.replace(/[^a-zA-Z0-9_]/g, '');
  const cleanSortDirection = sortDirection === 'asc' ? 'ASC' : 'DESC';

  return `
    SELECT 
      macro_id,
      trading_date,
      instrument,
      macro_name_raw,
      ict_alias,
      judas_classification,
      indicator_label,
      macro_range_pct,
      judas_magnitude_pct,
      real_move_magnitude_pct,
      post_macro_continuation_pct,
      post_macro_reversion_pct,
      fvg_count,
      has_fvg,
      is_opex_week
    FROM macro_records
    ${whereClause}
    ORDER BY ${cleanSortColumn} ${cleanSortDirection}
    LIMIT ${limit} OFFSET ${offset}
  `;
}
