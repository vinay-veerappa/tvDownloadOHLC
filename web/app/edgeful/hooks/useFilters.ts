import { useState, useCallback, useEffect, useRef } from 'react';
import { useRouter, usePathname, useSearchParams } from 'next/navigation';
import { MacroFilterState } from '../types';

const INITIAL_STATE: MacroFilterState = {
  instruments: [],
  macroWindows: [],
  judasClass: [],
  indicatorClass: [],
  vixRegimes: [],
  daysOfWeek: [],
  dateRange: {
    start: null,
    end: null,
  },
  advanced: {
    realDirection: [],
    hasFVG: null,
    isComplete: null,
    newsWithin60m: null,
    openVsMidnight: [],
    openVsDailyOpen: [],
    openVsRthBar: [],
    judasFirst: null,
  },
};

export function useFilters() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const isInitializing = useRef(true);

  // Initialize from URL or INITIAL_STATE
  const [filters, setFilters] = useState<MacroFilterState>(() => {
    try {
      const stateParam = searchParams.get('state');
      if (stateParam) {
        return JSON.parse(decodeURIComponent(stateParam)) as MacroFilterState;
      }
    } catch (e) {
      console.error('Failed to parse filters from URL:', e);
    }
    return INITIAL_STATE;
  });

  // Sync back to URL when filters change
  useEffect(() => {
    if (isInitializing.current) {
      isInitializing.current = false;
      return;
    }
    
    const params = new URLSearchParams(searchParams.toString());
    const filterString = JSON.stringify(filters);
    
    // Only update if it's not the initial state to keep URL clean
    if (filterString !== JSON.stringify(INITIAL_STATE)) {
      params.set('state', encodeURIComponent(filterString));
    } else {
      params.delete('state');
    }
    
    const newUrl = `${pathname}${params.toString() ? `?${params.toString()}` : ''}`;
    // Using replace to avoid filling history stack
    router.replace(newUrl, { scroll: false });
  }, [filters, pathname, router, searchParams]);

  const updateFilter = useCallback((key: keyof Omit<MacroFilterState, 'dateRange' | 'advanced'>, values: string[]) => {
    setFilters(prev => ({ ...prev, [key]: values }));
  }, []);

  const updateDateRange = useCallback((start: string | null, end: string | null) => {
    setFilters(prev => ({ ...prev, dateRange: { start, end } }));
  }, []);

  const updateAdvanced = useCallback((key: keyof MacroFilterState['advanced'], value: any) => {
    setFilters(prev => ({
      ...prev,
      advanced: { ...prev.advanced, [key]: value }
    }));
  }, []);

  const resetFilters = useCallback(() => {
    setFilters(INITIAL_STATE);
  }, []);

  return {
    filters,
    updateFilter,
    updateDateRange,
    updateAdvanced,
    resetFilters,
  };
}
