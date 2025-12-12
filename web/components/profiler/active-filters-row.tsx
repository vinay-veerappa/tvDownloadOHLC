"use client"

import { Badge } from '@/components/ui/badge';
import { X } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ActiveFiltersRowProps {
    filters: Record<string, string>;
    brokenFilters: Record<string, string>;
    intraSessionState: string;
    onClearAll: () => void;
}

export function ActiveFiltersRow({ filters, brokenFilters, intraSessionState, onClearAll }: ActiveFiltersRowProps) {
    const activeItems = [];

    // Context Sessions
    Object.entries(filters).forEach(([sess, val]) => {
        if (val && val !== 'Any') {
            activeItems.push({
                label: `${sess}: ${val}`,
                type: 'status',
                key: `${sess}-status`
            });
        }
    });

    Object.entries(brokenFilters).forEach(([sess, val]) => {
        if (val && val !== 'Any') {
            const isBroken = val === 'Yes' ? 'Broken' : 'Held';
            activeItems.push({
                label: `${sess}: ${isBroken}`,
                type: 'broken',
                key: `${sess}-broken`
            });
        }
    });

    // Intra-Session
    if (intraSessionState && intraSessionState !== 'Any') {
        activeItems.push({
            label: `Target State: ${intraSessionState}`,
            type: 'intra',
            key: 'intra'
        });
    }

    if (activeItems.length === 0) return null;

    return (
        <div className="flex items-center flex-wrap gap-2 py-2">
            <span className="text-sm text-muted-foreground mr-2">Active Filters:</span>
            {activeItems.map(item => (
                <Badge
                    key={item.key}
                    variant="outline"
                    className={`
                        px-2 py-1 flex items-center gap-1
                        ${item.type === 'status' ? 'bg-blue-50/50 border-blue-200 text-blue-800' : ''}
                        ${item.type === 'broken' ? 'bg-red-50/50 border-red-200 text-red-800' : ''}
                        ${item.type === 'intra' ? 'bg-green-50/50 border-green-200 text-green-800' : ''}
                    `}
                >
                    {item.label}
                </Badge>
            ))}

            <Button
                variant="ghost"
                size="sm"
                className="h-6 w-6 p-0 rounded-full ml-2 hover:bg-slate-100"
                onClick={onClearAll}
                title="Clear All Filters"
            >
                <X className="h-3 w-3 text-muted-foreground" />
            </Button>
        </div>
    );
}
