'use client';

import * as React from 'react';
import { useState, useEffect, useCallback } from 'react';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { buildWhereClause, getRecordsSql } from '../lib/queryBuilder';
import { runQuery } from '@/lib/duckdb';
import { MacroFilterState, MacroRecord } from '../types';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { ChevronDown, ChevronUp, ChevronLeft, ChevronRight, LayoutList, Download } from 'lucide-react';
import { getSummarySql } from '../lib/queryBuilder';
import { formatLabel } from '../lib/formatters';
import { cn } from '@/lib/utils';



interface DrillDownTableProps {
  filters: MacroFilterState;
  dbReady: boolean;
}

const PAGE_SIZE = 50;

export function DrillDownTable({ filters, dbReady }: DrillDownTableProps) {
  const [data, setData] = useState<MacroRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(0);
  const [totalRecords, setTotalRecords] = useState(0);
  
  const [sortCol, setSortCol] = useState<string>('trading_date');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  // Fetch total count to handle pagination correctly
  const fetchTotal = useCallback(async () => {
    if (!dbReady) return;
    try {
      const whereClause = buildWhereClause(filters);
      const sql = getSummarySql(whereClause);
      const result = await runQuery(sql);
      if (result.length > 0) {
        setTotalRecords(Number(result[0].total));
      } else {
        setTotalRecords(0);
      }
    } catch (err) {
      console.error('Error fetching total records:', err);
    }
  }, [filters, dbReady]);

  const fetchRecords = useCallback(async () => {
    if (!dbReady) return;
    setLoading(true);
    try {
      const whereClause = buildWhereClause(filters);
      const offset = page * PAGE_SIZE;
      const sql = getRecordsSql(whereClause, offset, PAGE_SIZE, sortCol, sortDir);
      const result = await runQuery<MacroRecord>(sql);
      setData(result);
    } catch (err) {
      console.error('Error fetching records:', err);
    } finally {
      setLoading(false);
    }
  }, [filters, page, sortCol, sortDir, dbReady]);

  const handleExportCSV = useCallback(async () => {
    if (!dbReady) return;
    try {
      const whereClause = buildWhereClause(filters);
      // Limit export to 10k to prevent browser crash
      const sql = getRecordsSql(whereClause, 0, 10000, sortCol, sortDir);
      const result = await runQuery(sql);
      
      if (result.length === 0) return;
      
      const keys = Object.keys(result[0]);
      const csvContent = [
        keys.join(','),
        ...result.map((row: Record<string, unknown>) => keys.map(k => {
          const val = row[k];
          if (val === null || val === undefined) return '';
          if (typeof val === 'string') return `"${val.replace(/"/g, '""')}"`;
          return val;
        }).join(','))
      ].join('\n');
      
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `edgeful_export_${new Date().toISOString().split('T')[0]}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Error exporting CSV:', err);
    }
  }, [filters, sortCol, sortDir, dbReady]);

  // Reset page to 0 when filters or sorting change
  useEffect(() => {
    setPage(0);
  }, [filters, sortCol, sortDir]);

  useEffect(() => {
    fetchTotal();
    fetchRecords();
  }, [fetchTotal, fetchRecords, page]);

  const toggleSort = (col: string) => {
    if (sortCol === col) {
      setSortDir(prev => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortCol(col);
      setSortDir('asc');
    }
  };

  const SortIcon = ({ col }: { col: string }) => {
    if (sortCol !== col) return <div className="w-4 h-4 ml-1 inline-block opacity-0 group-hover:opacity-30"><ChevronUp className="w-3 h-3" /></div>;
    return sortDir === 'asc' ? <ChevronUp className="w-3 h-3 ml-1 inline-block text-amber-500" /> : <ChevronDown className="w-3 h-3 ml-1 inline-block text-amber-500" />;
  };

  const totalPages = Math.ceil(totalRecords / PAGE_SIZE);

  return (
    <Card className="bg-zinc-950 border-zinc-800 p-4 min-h-[400px] flex flex-col hover:border-zinc-700 transition-colors">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <div className="p-1.5 bg-zinc-900 rounded-md text-amber-500">
            <LayoutList className="h-4 w-4" />
          </div>
          <h2 className="text-xs font-bold uppercase tracking-widest text-zinc-400">Macro Record Drill-Down</h2>
        </div>
        
        <div className="flex items-center gap-4">
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportCSV}
            disabled={loading || totalRecords === 0}
            className="h-7 px-2 text-[10px] border-zinc-800 bg-zinc-900/50 hover:bg-zinc-800 text-zinc-400 gap-1 uppercase font-bold tracking-widest"
          >
            <Download className="h-3 w-3" />
            Export CSV
          </Button>
          <span className="text-xs text-zinc-500 font-medium border-l border-zinc-800 pl-4">
            {totalRecords.toLocaleString()} Records
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="outline"
              size="sm"
              className="h-7 w-7 p-0 border-zinc-800 bg-zinc-900/50 hover:bg-zinc-800"
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0 || loading}
            >
              <ChevronLeft className="h-3 w-3" />
            </Button>
            <span className="text-xs font-bold px-2 text-zinc-400">
              {page + 1} <span className="text-zinc-600 font-normal">/ {Math.max(1, totalPages)}</span>
            </span>
            <Button
              variant="outline"
              size="sm"
              className="h-7 w-7 p-0 border-zinc-800 bg-zinc-900/50 hover:bg-zinc-800"
              onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1 || loading}
            >
              <ChevronRight className="h-3 w-3" />
            </Button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto relative rounded border border-zinc-800">
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-zinc-950/50 backdrop-blur-[1px]">
             <div className="w-5 h-5 border-2 border-amber-500 border-t-transparent rounded-full animate-spin"></div>
          </div>
        )}
        
        <Table className="min-w-max">
          <TableHeader className="sticky top-0 bg-zinc-950 z-20 shadow-sm border-b border-zinc-800">
            <TableRow className="border-b-zinc-800 hover:bg-transparent">
              <TableHead className="cursor-pointer group select-none whitespace-nowrap bg-zinc-950/90 text-[10px] uppercase font-bold tracking-widest text-zinc-500" onClick={() => toggleSort('trading_date')}>
                Date <SortIcon col="trading_date" />
              </TableHead>
              <TableHead className="cursor-pointer group select-none whitespace-nowrap bg-zinc-950/90 text-[10px] uppercase font-bold tracking-widest text-zinc-500" onClick={() => toggleSort('instrument')}>
                Instrument <SortIcon col="instrument" />
              </TableHead>
              <TableHead className="cursor-pointer group select-none whitespace-nowrap bg-zinc-950/90 text-[10px] uppercase font-bold tracking-widest text-zinc-500" onClick={() => toggleSort('macro_name_raw')}>
                Macro Window <SortIcon col="macro_name_raw" />
              </TableHead>
              <TableHead className="cursor-pointer group select-none whitespace-nowrap bg-zinc-950/90 text-[10px] uppercase font-bold tracking-widest text-zinc-500" onClick={() => toggleSort('judas_classification')}>
                Judas Class <SortIcon col="judas_classification" />
              </TableHead>
              <TableHead className="text-right cursor-pointer group select-none whitespace-nowrap bg-zinc-950/90 text-[10px] uppercase font-bold tracking-widest text-zinc-500" onClick={() => toggleSort('post_macro_continuation_pct')}>
                Continuation % <SortIcon col="post_macro_continuation_pct" />
              </TableHead>
              <TableHead className="text-right cursor-pointer group select-none whitespace-nowrap bg-zinc-950/90 text-[10px] uppercase font-bold tracking-widest text-zinc-500" onClick={() => toggleSort('post_macro_reversion_pct')}>
                Reversion % <SortIcon col="post_macro_reversion_pct" />
              </TableHead>
              <TableHead className="text-right cursor-pointer group select-none whitespace-nowrap bg-zinc-950/90 text-[10px] uppercase font-bold tracking-widest text-zinc-500" onClick={() => toggleSort('macro_range_pct')}>
                Range % <SortIcon col="macro_range_pct" />
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.length === 0 && !loading ? (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center text-xs text-zinc-600">
                  No records found for the current filters.
                </TableCell>
              </TableRow>
            ) : (
              data.map((row) => (
                <TableRow key={row.macro_id} className="border-b border-zinc-900/50 last:border-0 hover:bg-zinc-900/20 transition-colors py-1">
                  <TableCell className="py-2 text-[11px] font-medium text-zinc-300">
                    {row.trading_date ? new Date(Number(row.trading_date)).toISOString().split('T')[0] : '--'}
                  </TableCell>
                  <TableCell className="py-2 text-[11px] font-bold text-amber-500/90">{formatLabel(row.instrument)}</TableCell>
                  <TableCell className="py-2 text-[11px] text-zinc-400 font-medium">{formatLabel(row.ict_alias || row.macro_name_raw)}</TableCell>
                  <TableCell className="py-2 text-[11px] text-zinc-400">
                    <span className={
                      row.judas_classification === 'bullish_judas' ? 'text-emerald-500/80 bg-emerald-500/10 px-1.5 py-0.5 rounded' : 
                      row.judas_classification === 'bearish_judas' ? 'text-rose-500/80 bg-rose-500/10 px-1.5 py-0.5 rounded' : ''
                    }>
                      {formatLabel(row.judas_classification)}
                    </span>
                  </TableCell>
                  <TableCell className="py-2 text-[11px] text-right font-medium text-emerald-500/90">
                    {row.post_macro_continuation_pct != null ? Number(row.post_macro_continuation_pct).toFixed(2) : '--'}
                  </TableCell>
                  <TableCell className="py-2 text-[11px] text-right font-medium text-rose-500/90">
                    {row.post_macro_reversion_pct != null ? Number(row.post_macro_reversion_pct).toFixed(2) : '--'}
                  </TableCell>
                  <TableCell className="py-2 text-[11px] text-right text-zinc-400">
                    {row.macro_range_pct != null ? Number(row.macro_range_pct).toFixed(2) : '--'}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </Card>
  );
}
