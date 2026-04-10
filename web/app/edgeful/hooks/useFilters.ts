import { useState, useCallback, useEffect, useRef } from 'react';
import { useRouter, usePathname, useSearchParams } from 'next/navigation';
import { MacroFilterState } from '../types';

type MultiSelectFilterKey =
  | 'instruments'
  | 'macroWindows'
  | 'ictAliases'
  | 'judasClass'
  | 'indicatorClass'
  | 'vixRegimes'
  | 'daysOfWeek'
  | 'gapDirections';

const TRI_STATE_ADVANCED_KEYS = [
  'hasFVG',
  'isComplete',
  'newsWithin60m',
  'isOpExWeek',
  'sameDirectionAsPrior',
  'judasFirst',
  'midRetested',
  'midRetestWin',
  'isEventDay',
] as const satisfies ReadonlyArray<keyof MacroFilterState['advanced']>;

const INITIAL_STATE: MacroFilterState = {
  instruments: [],
  macroWindows: [],
  ictAliases: [],
  judasClass: [],
  indicatorClass: [],
  vixRegimes: [],
  daysOfWeek: [],
  gapDirections: [],
  lookbackDays: null,
  dateRange: {
    start: null,
    end: null,
  },
  advanced: {
    realDirection: [],
    hasFVG: null,
    isComplete: null,
    newsWithin60m: null,
    isOpExWeek: null,
    openVsMidnight: [],
    openVsDailyOpen: [],
    openVsRthBar: [],
    priorMacroDirection: [],
    sameDirectionAsPrior: null,
    macroStreak: null,
    macroRangePercentile: null,
    judasFirst: null,
    magnitudeRange: null,
    excursionRange: null,
    judasExcursionThreshold: null,
    midRetested: null,
    midRetestWin: null,
    isEventDay: null,
  },
};

function normalizeFilters(rawState: unknown): MacroFilterState {
  const candidate = (rawState && typeof rawState === 'object' ? rawState : {}) as Partial<MacroFilterState>;
  const advancedCandidate = (candidate.advanced && typeof candidate.advanced === 'object'
    ? candidate.advanced
    : {}) as Partial<MacroFilterState['advanced']>;

  const normalized: MacroFilterState = {
    ...INITIAL_STATE,
    ...candidate,
    advanced: {
      ...INITIAL_STATE.advanced,
      ...advancedCandidate,
    },
  };

  for (const key of TRI_STATE_ADVANCED_KEYS) {
    const value = normalized.advanced[key];
    if (value !== true && value !== false) {
      normalized.advanced[key] = null;
    }
  }

  return normalized;
}

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
        // searchParams.get() already URL-decodes, don't decode again
        const urlState = JSON.parse(stateParam);
        return normalizeFilters(urlState);
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
    const newParamStr = filterString !== JSON.stringify(INITIAL_STATE) ? filterString : null;
    const currentParam = searchParams.get('state');

    // Prevent deep loop by checking if state actually needs to be updated
    if (newParamStr !== null) {
      params.set('state', newParamStr);
    } else {
      params.delete('state');
    }

    if (currentParam === newParamStr || (!currentParam && !newParamStr)) {
      return; // Already synced
    }

    const newUrl = `${pathname}${params.toString() ? `?${params.toString()}` : ''}`;
    // Using replace to avoid filling history stack
    router.replace(newUrl, { scroll: false });
  }, [filters, pathname, router, searchParams]);

  const updateFilter = useCallback((key: MultiSelectFilterKey, values: string[]) => {
    setFilters(prev => ({ ...prev, [key]: values }));
  }, []);

  const updateDateRange = useCallback((start: string | null, end: string | null) => {
    setFilters(prev => ({ ...prev, dateRange: { start, end } }));
  }, []);

  const updateLookback = useCallback((days: number | null) => {
    setFilters(prev => ({ ...prev, lookbackDays: days }));
  }, []);

  const updateAdvanced = useCallback((key: keyof MacroFilterState['advanced'], value: any) => {
    setFilters(prev => ({
      ...prev,
      advanced: {
        ...prev.advanced,
        [key]: TRI_STATE_ADVANCED_KEYS.includes(key)
          ? (value === true || value === false ? value : null)
          : value,
      }
    }));
  }, []);

  const resetFilters = useCallback(() => {
    setFilters(INITIAL_STATE);
  }, []);

  return {
    filters,
    updateFilter,
    updateDateRange,
    updateLookback,
    updateAdvanced,
    resetFilters,
  };
}
