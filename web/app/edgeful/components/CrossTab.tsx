'use client';

import * as React from 'react';
import { useState, useEffect, useCallback, useMemo } from 'react';
import { Card } from '@/components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { buildWhereClause, getCrossTabSql } from '../lib/queryBuilder';
import { runQuery } from '@/lib/duckdb';
import { MacroFilterState } from '../types';
import { Rows3 } from 'lucide-react';
import { cn } from '@/lib/utils';

interface CrossTabProps {
  filters: MacroFilterState;
  dbReady: boolean;
}

const DIMENSIONS = [
  { value: 'judas_classification', label: 'Judas Classification' },
  { value: 'vix_regime', label: 'VIX Regime' },
  { value: 'indicator_label', label: 'Indicator Label' },
  { value: 'day_of_week', label: 'Day of Week' },
  { value: 'instrument', label: 'Instrument' },
  { value: 'real_direction', label: 'Real Move Direction' },
];

export function CrossTab({ filters, dbReady }: CrossTabProps) {
  const [rowDim, setRowDim] = useState(DIMENSIONS[0].value);
  const [colDim, setColDim] = useState(DIMENSIONS[1].value);
  const [data, setData] = useState<{ row_val: string; col_val: string; count: number }[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchCrossTab = useCallback(async () => {
    if (!dbReady || rowDim === colDim) return;
    setLoading(true);
    try {
      const whereClause = buildWhereClause(filters);
      const sql = getCrossTabSql(rowDim, colDim, whereClause);
      const result = await runQuery(sql);
      setData(result);
    } catch (err) {
      console.error('Error fetching CrossTab:', err);
    } finally {
      setLoading(false);
    }
  }, [filters, rowDim, colDim, dbReady]);

  useEffect(() => {
    fetchCrossTab();
  }, [fetchCrossTab]);

  // Transform flat SQL results into a 2D matrix
  const { matrix, rowLabels, colLabels, maxCount } = useMemo(() => {
    const rSet = new Set<string>();
    const cSet = new Set<string>();
    let maximum = 0;

    data.forEach(d => {
      rSet.add(d.row_val);
      cSet.add(d.col_val);
      const countNum = Number(d.count);
      if (countNum > maximum) maximum = countNum;
    });

    const rows = Array.from(rSet).sort();
    const cols = Array.from(cSet).sort();

    const mat: Record<string, Record<string, number>> = {};
    rows.forEach(r => { mat[r] = {}; cols.forEach(c => mat[r][c] = 0); });

    data.forEach(d => { mat[d.row_val][d.col_val] = d.count; });

    return { matrix: mat, rowLabels: rows, colLabels: cols, maxCount: maximum };
  }, [data]);

  return (
    <Card className="bg-zinc-950 border-zinc-800 p-4 h-[400px] flex flex-col hover:border-zinc-700 transition-colors">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-zinc-900 rounded-md text-amber-500">
            <Rows3 className="h-4 w-4" />
          </div>
          <h2 className="text-xs font-bold uppercase tracking-widest text-zinc-400">Conditional Matrix</h2>
        </div>
        
        <div className="flex items-center gap-2">
          <Select value={rowDim} onValueChange={setRowDim}>
            <SelectTrigger className="w-[160px] h-8 text-xs border-zinc-800 bg-zinc-900/50">
              <SelectValue placeholder="Row Dimension" />
            </SelectTrigger>
            <SelectContent className="bg-zinc-950 border-zinc-800">
              {DIMENSIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value} className="text-xs hover:bg-zinc-900" disabled={opt.value === colDim}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <span className="text-zinc-600 text-xs font-bold">VS</span>

          <Select value={colDim} onValueChange={setColDim}>
            <SelectTrigger className="w-[160px] h-8 text-xs border-zinc-800 bg-zinc-900/50">
              <SelectValue placeholder="Col Dimension" />
            </SelectTrigger>
            <SelectContent className="bg-zinc-950 border-zinc-800">
              {DIMENSIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value} className="text-xs hover:bg-zinc-900" disabled={opt.value === rowDim}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex-1 overflow-auto relative rounded border border-zinc-800">
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-zinc-950/50 backdrop-blur-[1px]">
             <div className="w-5 h-5 border-2 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
          </div>
        )}
        
        <table className="w-full text-xs text-left border-collapse min-w-max">
          <thead className="sticky top-0 bg-zinc-950 z-20 shadow-sm border-b border-zinc-800">
            <tr>
              <th className="p-2 font-bold text-zinc-500 uppercase tracking-widest bg-zinc-950/90 whitespace-nowrap">
                {DIMENSIONS.find(d => d.value === rowDim)?.label} \ {DIMENSIONS.find(d => d.value === colDim)?.label}
              </th>
              {colLabels.map(c => (
                <th key={c} className="p-2 font-medium text-zinc-300 text-center uppercase whitespace-nowrap">{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rowLabels.map(r => (
              <tr key={r} className="border-b border-zinc-900/50 last:border-0 hover:bg-zinc-900/20 transition-colors">
                <td className="p-2 font-medium text-amber-500/80 whitespace-nowrap bg-zinc-950/50">{r}</td>
                {colLabels.map(c => {
                  const val = Number(matrix[r][c] || 0);
                  const intensity = maxCount > 0 ? val / maxCount : 0;
                  return (
                    <td key={c} className="p-2 text-center text-zinc-300 relative">
                      {/* Background Heatmap indicator */}
                      <div 
                        className="absolute inset-1 bg-emerald-500 rounded-sm opacity-10 pointer-events-none" 
                        style={{ opacity: intensity * 0.4 }}
                      />
                      <span className="relative z-10">{val.toLocaleString()}</span>
                    </td>
                  );
                })}
              </tr>
            ))}
            {rowLabels.length === 0 && !loading && (
              <tr>
                <td colSpan={colLabels.length + 1} className="p-8 text-center text-zinc-600">
                  No data to cross-tabulate for the current filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
