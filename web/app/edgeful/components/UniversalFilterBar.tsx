'use client';

import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { MacroFilterState } from '../types';
import { SlidersHorizontal } from 'lucide-react';

type MultiSelectFilterKey =
  | 'instruments'
  | 'macroWindows'
  | 'ictAliases'
  | 'judasClass'
  | 'indicatorClass'
  | 'vixRegimes'
  | 'daysOfWeek'
  | 'gapDirections';

interface UniversalFilterBarProps {
  filters: MacroFilterState;
  updateFilter: (key: MultiSelectFilterKey, values: string[]) => void;
  updateLookback: (days: number | null) => void;
  updateAdvanced: (key: keyof MacroFilterState['advanced'], value: any) => void;
}

function labelValue(value: string): string {
  return value === 'ALL' ? 'All' : value;
}

export function UniversalFilterBar({
  filters,
  updateFilter,
  updateLookback,
  updateAdvanced,
}: UniversalFilterBarProps) {
  const selectedDow = filters.daysOfWeek[0] ?? 'ALL';
  const selectedVix = filters.vixRegimes[0] ?? 'ALL';
  const selectedGap = filters.gapDirections[0] ?? 'ALL';
  const selectedEvent =
    filters.advanced.isEventDay === true
      ? 'YES'
      : filters.advanced.isEventDay === false
        ? 'NO'
        : 'ALL';

  return (
    <Card className="border-zinc-800 bg-zinc-950/70 p-3">
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex items-center gap-2 pr-2">
          <div className="rounded-md bg-zinc-900 p-1.5 text-amber-500">
            <SlidersHorizontal className="h-3.5 w-3.5" />
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">Universal Filters</p>
            <p className="text-[10px] text-zinc-600">DOW, VIX, Gap, Event, Lookback</p>
          </div>
        </div>

        <label className="flex min-w-[130px] flex-col gap-1 text-[10px] uppercase tracking-widest text-zinc-500">
          <span>Day</span>
          <select
            value={selectedDow}
            onChange={(e) => {
              const value = e.target.value;
              updateFilter('daysOfWeek', value === 'ALL' ? [] : [value]);
            }}
            className="h-8 rounded border border-zinc-800 bg-zinc-900 px-2 text-xs text-zinc-200"
          >
            {['ALL', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'].map((value) => (
              <option key={value} value={value}>
                {labelValue(value)}
              </option>
            ))}
          </select>
        </label>

        <label className="flex min-w-[130px] flex-col gap-1 text-[10px] uppercase tracking-widest text-zinc-500">
          <span>VIX</span>
          <select
            value={selectedVix}
            onChange={(e) => {
              const value = e.target.value;
              updateFilter('vixRegimes', value === 'ALL' ? [] : [value]);
            }}
            className="h-8 rounded border border-zinc-800 bg-zinc-900 px-2 text-xs text-zinc-200"
          >
            {['ALL', 'low', 'medium', 'high', 'extreme'].map((value) => (
              <option key={value} value={value}>
                {labelValue(value)}
              </option>
            ))}
          </select>
        </label>

        <label className="flex min-w-[130px] flex-col gap-1 text-[10px] uppercase tracking-widest text-zinc-500">
          <span>Gap</span>
          <select
            value={selectedGap}
            onChange={(e) => {
              const value = e.target.value;
              updateFilter('gapDirections', value === 'ALL' ? [] : [value]);
            }}
            className="h-8 rounded border border-zinc-800 bg-zinc-900 px-2 text-xs text-zinc-200"
          >
            {['ALL', 'UP', 'DOWN', 'NONE'].map((value) => (
              <option key={value} value={value}>
                {labelValue(value)}
              </option>
            ))}
          </select>
        </label>

        <label className="flex min-w-[130px] flex-col gap-1 text-[10px] uppercase tracking-widest text-zinc-500">
          <span>Event Day</span>
          <select
            value={selectedEvent}
            onChange={(e) => {
              const value = e.target.value;
              updateAdvanced('isEventDay', value === 'YES' ? true : value === 'NO' ? false : null);
            }}
            className="h-8 rounded border border-zinc-800 bg-zinc-900 px-2 text-xs text-zinc-200"
          >
            {['ALL', 'YES', 'NO'].map((value) => (
              <option key={value} value={value}>
                {labelValue(value)}
              </option>
            ))}
          </select>
        </label>

        <label className="flex min-w-[130px] flex-col gap-1 text-[10px] uppercase tracking-widest text-zinc-500">
          <span>Lookback</span>
          <select
            value={filters.lookbackDays ?? 'ALL'}
            onChange={(e) => {
              const value = e.target.value;
              updateLookback(value === 'ALL' ? null : Number(value));
            }}
            className="h-8 rounded border border-zinc-800 bg-zinc-900 px-2 text-xs text-zinc-200"
          >
            <option value="ALL">All</option>
            <option value="30">30D</option>
            <option value="90">90D</option>
            <option value="180">180D</option>
            <option value="365">365D</option>
          </select>
        </label>

        <Button
          variant="outline"
          size="sm"
          className="h-8 border-zinc-800 bg-zinc-900 px-3 text-[10px] uppercase tracking-widest text-zinc-300 hover:bg-zinc-800"
          onClick={() => {
            updateFilter('daysOfWeek', []);
            updateFilter('vixRegimes', []);
            updateFilter('gapDirections', []);
            updateAdvanced('isEventDay', null);
            updateLookback(null);
          }}
        >
          Clear Universal
        </Button>
      </div>
    </Card>
  );
}
