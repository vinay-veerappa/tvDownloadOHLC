import { MacroFilterState } from '../types';

/**
 * SQL Query Builder for the Edgeful Dashboard.
 * Maps the React filter state to optimized DuckDB SQL conditions.
 */

export function buildWhereClause(filters: MacroFilterState): string {
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
  
  if (filters.advanced.hasFVG !== null) {
    conditions.push(`has_fvg = ${filters.advanced.hasFVG}`);
  }
  
  if (filters.advanced.isComplete !== null) {
    conditions.push(`is_complete = ${filters.advanced.isComplete}`);
  }
  
  if (filters.advanced.newsWithin60m !== null) {
    conditions.push(`news_within_60m = ${filters.advanced.newsWithin60m}`);
  }

  // Institutional Anchors (Simple absolute price comparison)
  if (filters.advanced.openVsMidnight.length > 0) {
    conditions.push(`open_vs_midnight IN (${filters.advanced.openVsMidnight.map(v => `'${v}'`).join(',')})`);
  }
  
  if (filters.advanced.openVsDailyOpen.length > 0) {
    conditions.push(`open_vs_daily_open IN (${filters.advanced.openVsDailyOpen.map(v => `'${v}'`).join(',')})`);
  }
  
  if (filters.advanced.openVsRthBar.length > 0) {
    conditions.push(`macro_open_vs_rth_bar IN (${filters.advanced.openVsRthBar.map(v => `'${v}'`).join(',')})`);
  }

  if (filters.advanced.judasFirst !== null) {
    conditions.push(`judas_first = ${filters.advanced.judasFirst}`);
  }

  return conditions.length > 0 ? `WHERE ${conditions.join(' AND ')}` : '';
}

/**
 * Generates the SQL for the Summary Metrics cards
 */
export function getSummarySql(whereClause: string): string {
  return `
    SELECT 
      COUNT(*) as total,
      COUNT(CASE WHEN judas_classification IN ('bullish_judas', 'bearish_judas') THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) as judas_rate,
      AVG(post_macro_continuation_pct) as avg_continuation,
      AVG(post_macro_reversion_pct) as avg_reversion,
      COUNT(CASE WHEN post_macro_continuation_pct > post_macro_reversion_pct THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0) as continuation_win_rate,
      AVG(post_macro_mfe_pct) as avg_mfe
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
      FLOOR(${column} / ${binWidth}) * ${binWidth} as bin_start,
      COUNT(*) as count
    FROM macro_records
    ${finalWhere}
    GROUP BY bin_start
    ORDER BY bin_start
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
      COUNT(*) as count
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
      has_fvg
    FROM macro_records
    ${whereClause}
    ORDER BY ${cleanSortColumn} ${cleanSortDirection}
    LIMIT ${limit} OFFSET ${offset}
  `;
}
