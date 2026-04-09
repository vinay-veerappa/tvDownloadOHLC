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

interface MultiSelectProps {
  label: string;
  options: string[];
  selected: string[];
  onChange: (values: string[]) => void;
  className?: string;
}

const MultiSelect = ({ label, options, selected, onChange, className }: MultiSelectProps) => {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button 
          variant="outline" 
          size="sm" 
          className={cn(
            "h-8 w-full justify-between text-xs font-normal border-zinc-800 bg-zinc-900/50 hover:bg-zinc-800 hover:text-zinc-100",
            selected.length > 0 && "border-amber-500/50 text-amber-500 bg-amber-500/5",
            className
          )}
        >
          <div className="flex items-center gap-2 truncate">
            <span className="text-zinc-500">{label}:</span>
            <span className="truncate">
              {selected.length === 0 ? 'All' : 
               selected.length === 1 ? selected[0] : 
               `${selected.length} selected`}
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
                  const newSelected = selected.includes(option)
                    ? selected.filter((s) => s !== option)
                    : [...selected, option];
                  onChange(newSelected);
                }}
              >
                <Checkbox
                  checked={selected.includes(option)}
                  className="border-zinc-700 data-[state=checked]:bg-amber-500 data-[state=checked]:border-amber-500"
                />
                <span className="text-xs font-medium text-zinc-300 pointer-events-none lowercase">
                  {option}
                </span>
              </div>
            ))}
          </div>
        </ScrollArea>
        {selected.length > 0 && (
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

interface FilterPanelProps {
  filters: MacroFilterState;
  updateFilter: (key: keyof Omit<MacroFilterState, 'dateRange' | 'advanced'>, values: string[]) => void;
  updateAdvanced: (key: keyof MacroFilterState['advanced'], value: any) => void;
  resetFilters: () => void;
}

export function FilterPanel({ filters, updateFilter, updateAdvanced, resetFilters }: FilterPanelProps) {
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
              label="Judas" 
              options={['bullish_judas', 'bearish_judas', 'trend_up', 'trend_down', 'neutral']} 
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
              label="VIX" 
              options={['low', 'medium', 'high', 'extreme']} 
              selected={filters.vixRegimes}
              onChange={(v) => updateFilter('vixRegimes', v)}
            />
            <MultiSelect 
              label="Day" 
              options={['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']} 
              selected={filters.daysOfWeek}
              onChange={(v) => updateFilter('daysOfWeek', v)}
            />
          </div>

          <Separator className="bg-zinc-900" />

          {/* Section: Advanced Institutional */}
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
              label="vs RTH Open" 
              options={['above', 'below', 'inside']} 
              selected={filters.advanced.openVsRthBar}
              onChange={(v) => updateAdvanced('openVsRthBar', v)}
            />
          </div>

          <Separator className="bg-zinc-900" />

          {/* Section: Logic Toggles */}
          <div className="space-y-3">
            <h3 className="text-[10px] font-bold text-zinc-600 uppercase tracking-tighter">Trade Logic</h3>
            
            <div className="flex items-center justify-between py-1 px-1">
              <span className="text-xs text-zinc-400">Has FVG</span>
              <Checkbox 
                checked={filters.advanced.hasFVG === true}
                onCheckedChange={(checked) => updateAdvanced('hasFVG', checked === 'indeterminate' ? null : checked)}
                className="border-zinc-800"
              />
            </div>
            
            <div className="flex items-center justify-between py-1 px-1">
              <span className="text-xs text-zinc-400">Judas First</span>
              <Checkbox 
                checked={filters.advanced.judasFirst === true}
                onCheckedChange={(checked) => updateAdvanced('judasFirst', checked === 'indeterminate' ? null : checked)}
                className="border-zinc-800"
              />
            </div>

            <div className="flex items-center justify-between py-1 px-1">
              <span className="text-xs text-zinc-400">News (+/-60m)</span>
              <Checkbox 
                checked={filters.advanced.newsWithin60m === true}
                onCheckedChange={(checked) => updateAdvanced('newsWithin60m', checked === 'indeterminate' ? null : checked)}
                className="border-zinc-800"
              />
            </div>
          </div>
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
