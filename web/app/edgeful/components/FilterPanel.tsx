'use client';

import * as React from 'react';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Separator } from '@/components/ui/separator';
import { Checkbox } from '@/components/ui/checkbox';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ChevronDown, Filter, RotateCcw, X } from 'lucide-react';
import { MacroFilterState } from '../types';
import { cn } from '@/lib/utils';
import { Slider } from '@/components/ui/slider';
import { formatLabel, getICTSessionValues } from '../lib/formatters';

const ICT_ALIASES = getICTSessionValues();

interface MultiSelectProps {
  label: string;
  options: string[];
  selected: string[];
  onChange: (values: string[]) => void;
  className?: string;
}

const MultiSelect = ({ label, options, selected = [], onChange, className }: MultiSelectProps) => {
  const safeSelected = Array.isArray(selected) ? selected : [];

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button 
          variant="outline" 
          size="sm" 
          className={cn(
            "h-8 w-full justify-between text-xs font-normal border-zinc-800 bg-zinc-900/50 hover:bg-zinc-800 hover:text-zinc-100",
            safeSelected.length > 0 && "border-amber-500/50 text-amber-500 bg-amber-500/5",
            className
          )}
        >
          <div className="flex items-center gap-2 truncate">
            <span className="text-zinc-500">{label}:</span>
            <span className="truncate">
              {safeSelected.length === 0 ? 'All' : 
               safeSelected.length === 1 ? formatLabel(safeSelected[0]) : 
               `${safeSelected.length} selected`}
            </span>
          </div>
          <ChevronDown className="h-3 w-3 opacity-50 shrink-0" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[240px] p-0 bg-zinc-950 border-zinc-800" align="start">
        <ScrollArea className="h-[280px]">
          <div className="p-2 space-y-1">
            {options.map((option) => (
              <div
                key={option}
                className="flex items-center space-x-2 rounded-sm px-2 py-1.5 hover:bg-zinc-900 cursor-pointer"
                onClick={() => {
                  const newSelected = safeSelected.includes(option)
                    ? safeSelected.filter((s) => s !== option)
                    : [...safeSelected, option];
                  onChange(newSelected);
                }}
              >
                <Checkbox
                  checked={safeSelected.includes(option)}
                  className="border-zinc-700 data-[state=checked]:bg-amber-500 data-[state=checked]:border-amber-500"
                />
                <span className="text-xs font-medium text-zinc-300 pointer-events-none">
                  {formatLabel(option)}
                </span>
              </div>
            ))}
          </div>
        </ScrollArea>
        {safeSelected.length > 0 && (
          <div className="p-2 border-t border-zinc-900 bg-zinc-950/50">
            <Button 
              variant="ghost" 
              size="sm" 
              className="w-full h-8 text-[10px] text-zinc-500 hover:text-red-400 hover:bg-red-400/5"
              onClick={() => onChange([])}
            >
              Clear selection
            </Button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
};

interface MultiToggleProps {
  label: string;
  value: boolean | null;
  onChange: (value: boolean | null) => void;
  className?: string;
}

const MultiToggle = ({ label, value, onChange, className }: MultiToggleProps) => {
  return (
    <div className={cn("flex flex-col gap-1.5 px-1", className)}>
      <div className="flex items-center justify-between">
        <span className="text-xs text-zinc-400">{label}</span>
        <div className="flex bg-zinc-900 rounded-md p-0.5 border border-zinc-800">
          <button
            onClick={() => onChange(true)}
            className={cn(
              "px-2 py-0.5 rounded-sm text-[10px] uppercase font-bold transition-all",
              value === true ? "bg-amber-500 text-zinc-950" : "text-zinc-500 hover:text-zinc-300"
            )}
          >
            Yes
          </button>
          <button
            onClick={() => onChange(false)}
            className={cn(
              "px-2 py-0.5 rounded-sm text-[10px] uppercase font-bold transition-all",
              value === false ? "bg-zinc-800 text-zinc-100" : "text-zinc-500 hover:text-zinc-300"
            )}
          >
            No
          </button>
          <button
            onClick={() => onChange(null)}
            className={cn(
              "px-2 py-0.5 rounded-sm text-[10px] uppercase font-bold transition-all",
              value === null ? "bg-zinc-950 text-amber-500/50" : "text-zinc-500 hover:text-zinc-300"
            )}
          >
            Any
          </button>
        </div>
      </div>
    </div>
  );
};

interface FilterPanelProps {
  filters: MacroFilterState;
  updateFilter: (key: keyof Omit<MacroFilterState, 'dateRange' | 'advanced'>, values: string[]) => void;
  updateDateRange: (start: string | null, end: string | null) => void;
  updateAdvanced: (key: keyof MacroFilterState['advanced'], value: any) => void;
  resetFilters: () => void;
}

export function FilterPanel({ filters, updateFilter, updateDateRange, updateAdvanced, resetFilters }: FilterPanelProps) {
  const [showAdvanced, setShowAdvanced] = React.useState(false);

  return (
    <Card className="flex flex-col h-full bg-zinc-950 border-zinc-800 rounded-none border-y-0 border-l-0">
      <div className="p-4 flex items-center justify-between border-b border-zinc-900">
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-amber-500" />
          <h2 className="text-xs font-bold uppercase tracking-widest text-zinc-400">Filters</h2>
        </div>
        <Button 
          variant="ghost" 
          size="icon" 
          className="h-6 w-6 text-zinc-600 hover:text-zinc-100"
          onClick={resetFilters}
          title="Reset All"
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="p-4 space-y-6">
          {/* Section: Primary */}
          <div className="space-y-3">
            <h3 className="text-[10px] font-bold text-zinc-600 uppercase tracking-tighter">Core Dimensions</h3>
            <MultiSelect 
              label="Asset" 
              options={['ES1', 'NQ1', 'YM1', 'RTY1', 'CL1', 'GC1']} 
              selected={filters.instruments}
              onChange={(v) => updateFilter('instruments', v)}
            />
            <MultiSelect 
              label="Macro Window" 
              options={[
                'Macro_0050', 'Macro_0150', 'Macro_0250', 'Macro_0350', 'Macro_0450', 'Macro_0550',
                'Macro_0650', 'Macro_0750', 'Macro_0850', 'Macro_0950', 'Macro_1050', 'Macro_1150',
                'Macro_1250', 'Macro_1350', 'Macro_1450', 'Macro_1550', 'Macro_1650', 'Macro_1750',
                'Macro_1850', 'Macro_1950', 'Macro_2050', 'Macro_2150', 'Macro_2250', 'Macro_2350',
                'Hydra_1', 'Hydra_2', 'Hydra_3'
              ]} 
              selected={filters.macroWindows}
              onChange={(v) => updateFilter('macroWindows', v)}
            />
            <MultiSelect 
              label="Judas" 
              options={['bullish_judas', 'bearish_judas', 'trend_up', 'trend_down']} 
              selected={filters.judasClass}
              onChange={(v) => updateFilter('judasClass', v)}
            />
            <MultiSelect 
              label="Indicator" 
              options={['Accum', 'Expansion', 'Manip']} 
              selected={filters.indicatorClass}
              onChange={(v) => updateFilter('indicatorClass', v)}
            />
            <MultiSelect 
              label="VIX Regime" 
              options={['low', 'medium', 'high', 'extreme']} 
              selected={filters.vixRegimes}
              onChange={(v) => updateFilter('vixRegimes', v)}
            />
            <MultiSelect 
              label="Day of Week" 
              options={['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']} 
              selected={filters.daysOfWeek}
              onChange={(v) => updateFilter('daysOfWeek', v)}
            />
            <MultiSelect 
              label="ICT Session" 
              options={ICT_ALIASES} 
              selected={filters.ictAliases}
              onChange={(v) => updateFilter('ictAliases', v)}
            />
            <div className="space-y-2 px-1">
              <h3 className="text-[10px] font-bold text-zinc-600 uppercase tracking-tighter">Date Range</h3>
              <div className="grid grid-cols-2 gap-2">
                <input 
                  type="date" 
                  className="bg-zinc-900 border border-zinc-800 text-[10px] p-1 rounded text-zinc-300" 
                  value={filters.dateRange.start || ''}
                  onChange={(e) => updateDateRange(e.target.value || null, filters.dateRange.end)}
                />
                <input 
                  type="date" 
                  className="bg-zinc-900 border border-zinc-800 text-[10px] p-1 rounded text-zinc-300" 
                  value={filters.dateRange.end || ''}
                  onChange={(e) => updateDateRange(filters.dateRange.start, e.target.value || null)}
                />
              </div>
            </div>
          </div>

          <Separator className="bg-zinc-900" />

          <div className="flex items-center justify-between">
            <h3 className="text-[10px] font-bold text-zinc-600 uppercase tracking-tighter">Advanced Filters</h3>
            <Button
              variant="ghost"
              size="sm"
              className="h-7 px-2 text-[10px] text-zinc-500 hover:text-zinc-200"
              onClick={() => setShowAdvanced(prev => !prev)}
            >
              {showAdvanced ? 'Hide' : 'Show'}
            </Button>
          </div>

          {showAdvanced && (
            <>
              {/* Section: Institutional Anchors */}
              <div className="space-y-3">
                <h3 className="text-[10px] font-bold text-zinc-600 uppercase tracking-tighter">Institutional Anchors</h3>
                
                <MultiSelect 
                  label="vs Midnight" 
                  options={['above', 'below']} 
                  selected={filters.advanced.openVsMidnight}
                  onChange={(v) => updateAdvanced('openVsMidnight', v)}
                />
                
                <MultiSelect 
                  label="vs Daily Open" 
                  options={['above', 'below']} 
                  selected={filters.advanced.openVsDailyOpen}
                  onChange={(v) => updateAdvanced('openVsDailyOpen', v)}
                />

                <MultiSelect 
                  label="vs RTH Range" 
                  options={['above', 'below', 'inside']} 
                  selected={filters.advanced.openVsRthBar}
                  onChange={(v) => updateAdvanced('openVsRthBar', v)}
                />
              </div>

              <Separator className="bg-zinc-900" />

              <div className="space-y-4">
                <h3 className="text-[10px] font-bold text-zinc-600 uppercase tracking-tighter px-1">Secondary Filters</h3>
                
                <MultiToggle 
                  label="Has FVG"
                  value={filters.advanced.hasFVG}
                  onChange={(v) => updateAdvanced('hasFVG', v)}
                />

                <MultiToggle 
                  label="Is Complete"
                  value={filters.advanced.isComplete}
                  onChange={(v) => updateAdvanced('isComplete', v)}
                />

                <MultiToggle 
                  label="News Within 60m"
                  value={filters.advanced.newsWithin60m}
                  onChange={(v) => updateAdvanced('newsWithin60m', v)}
                />

                <MultiToggle 
                  label="Is OpEx Week"
                  value={filters.advanced.isOpExWeek}
                  onChange={(v) => updateAdvanced('isOpExWeek', v)}
                />

                <MultiToggle 
                  label="Same Direction as Prior"
                  value={filters.advanced.sameDirectionAsPrior}
                  onChange={(v) => updateAdvanced('sameDirectionAsPrior', v)}
                />

                <MultiToggle 
                  label="Judas First"
                  value={filters.advanced.judasFirst}
                  onChange={(v) => updateAdvanced('judasFirst', v)}
                />

                <MultiToggle 
                  label="Mid Retested"
                  value={filters.advanced.midRetested}
                  onChange={(v) => updateAdvanced('midRetested', v)}
                />

                <MultiToggle 
                  label="Mid Retest Win"
                  value={filters.advanced.midRetestWin}
                  onChange={(v) => updateAdvanced('midRetestWin', v)}
                />

                <Separator className="bg-zinc-900 mx-1" />

                <MultiSelect 
                  label="Real Direction" 
                  options={['up', 'down']} 
                  selected={filters.advanced.realDirection}
                  onChange={(v) => updateAdvanced('realDirection', v)}
                />

                <MultiSelect 
                  label="Prior Direction" 
                  options={['up', 'down']} 
                  selected={filters.advanced.priorMacroDirection}
                  onChange={(v) => updateAdvanced('priorMacroDirection', v)}
                />
              </div>

              <Separator className="bg-zinc-900" />

              {/* Section: Magnitude & Volatility */}
              <div className="space-y-4 px-1 pb-4">
                <h3 className="text-[10px] font-bold text-zinc-600 uppercase tracking-tighter">Magnitude & Volatility</h3>
                
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-[10px] uppercase font-bold text-zinc-500">
                    <span>Judas Magnitude</span>
                    <span className="text-amber-500">{(filters.advanced.magnitudeRange?.[0] ?? 0).toFixed(2)}% - {(filters.advanced.magnitudeRange?.[1] ?? 4).toFixed(2)}%</span>
                  </div>
                  <Slider
                    max={4.0}
                    step={0.01}
                    value={[filters.advanced.magnitudeRange?.[0] ?? 0, filters.advanced.magnitudeRange?.[1] ?? 4]}
                    onValueChange={(v) => updateAdvanced('magnitudeRange', v)}
                    className="py-1"
                  />
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between text-[10px] uppercase font-bold text-zinc-500">
                    <span>Excursion Reach</span>
                    <span className="text-amber-500">{(filters.advanced.excursionRange?.[0] ?? 0).toFixed(2)}% - {(filters.advanced.excursionRange?.[1] ?? 4).toFixed(2)}%</span>
                  </div>
                  <Slider
                    max={4.0}
                    step={0.01}
                    value={[filters.advanced.excursionRange?.[0] ?? 0, filters.advanced.excursionRange?.[1] ?? 4]}
                    onValueChange={(v) => updateAdvanced('excursionRange', v)}
                    className="py-1"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-[10px] uppercase font-bold text-zinc-500">Judas Excursion Threshold %</label>
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    value={filters.advanced.judasExcursionThreshold ?? ''}
                    onChange={(e) => updateAdvanced('judasExcursionThreshold', e.target.value ? parseFloat(e.target.value) : null)}
                    placeholder="e.g., 5 or 15 (leave empty for no filter)"
                    className="w-full px-2 py-1 text-sm bg-zinc-900 border border-zinc-700 rounded text-zinc-300 placeholder:text-zinc-600 focus:outline-none focus:border-amber-500"
                  />
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between text-[10px] uppercase font-bold text-zinc-500">
                    <span>Macro Range Pct</span>
                    <span className="text-amber-500">{(filters.advanced.macroRangePercentile?.[0] ?? 0).toFixed(2)}% - {(filters.advanced.macroRangePercentile?.[1] ?? 4).toFixed(2)}%</span>
                  </div>
                  <Slider
                    max={4.0}
                    step={0.01}
                    value={[filters.advanced.macroRangePercentile?.[0] ?? 0, filters.advanced.macroRangePercentile?.[1] ?? 4]}
                    onValueChange={(v) => updateAdvanced('macroRangePercentile', v)}
                    className="py-1"
                  />
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between text-[10px] uppercase font-bold text-zinc-500">
                    <span>Streak Range</span>
                    <span className="text-amber-500">{filters.advanced.macroStreak?.[0] ?? 1} - {filters.advanced.macroStreak?.[1] ?? 10}</span>
                  </div>
                  <Slider
                    min={1}
                    max={10}
                    step={1}
                    value={[filters.advanced.macroStreak?.[0] ?? 1, filters.advanced.macroStreak?.[1] ?? 10]}
                    onValueChange={(v) => updateAdvanced('macroStreak', v)}
                    className="py-1"
                  />
                </div>
              </div>
            </>
          )}
        </div>
      </ScrollArea>

      <div className="p-4 bg-zinc-950/80 border-t border-zinc-900">
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between text-[10px] text-zinc-500 uppercase tracking-widest font-bold">
            <span>Query Engine</span>
            <span className="text-amber-500">DuckDB-WASM</span>
          </div>
          <p className="text-[9px] text-zinc-600 leading-tight">
            Filters are applied in real-time to the 6-year institutional dataset (2018-2024).
          </p>
        </div>
      </div>
    </Card>
  );
}
