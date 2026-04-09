import * as React from 'react';
import { Clock, Database } from 'lucide-react';

interface QueryStatusProps {
  dbStatus: 'loading' | 'ready' | 'error';
  queryTimeMs?: number;
  totalRecords?: number;
  lastDataUpdate?: string | null;
}

export function QueryStatus({ dbStatus, queryTimeMs, totalRecords, lastDataUpdate }: QueryStatusProps) {
  const lastUpdateLabel = lastDataUpdate ? new Date(lastDataUpdate).toLocaleString() : 'Unknown';

  return (
    <>
      <div className="flex items-center gap-4 text-[10px] font-bold uppercase tracking-widest text-zinc-500">
        <div className="flex items-center gap-1.5">
          <Clock className="h-3 w-3" />
          <span>{queryTimeMs != null ? `${queryTimeMs.toFixed(0)}ms` : '--'}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <Database className="h-3 w-3" />
          <span>{totalRecords != null ? `${Number(totalRecords).toLocaleString()} Records` : 'Loading...'}</span>
        </div>
        <div className="hidden xl:block">
          <span>Last Update: {lastUpdateLabel}</span>
        </div>
        <div className="hidden xl:block">
          <span>Status: {dbStatus.toUpperCase()}</span>
        </div>
      </div>
    </>
  );
}
