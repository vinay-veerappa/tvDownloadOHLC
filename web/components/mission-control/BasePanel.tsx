/**
 * Base Panel Component
 * 
 * Wrapper for all Mission Control panels.
 * Handles:
 * - Container styling (Bento grid look)
 * - Header (Title, Description, Actions)
 * - Collapsible state
 * - Snapshot mode behavior
 */

'use client';

import { useState } from 'react';
import { ChevronDown, ChevronUp, Maximize2, Minimize2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';

export interface BasePanelProps {
    title: string;
    description?: string;
    children: React.ReactNode;
    colSpan?: string;
    isSnapshotMode?: boolean;
    defaultExpanded?: boolean;
    headerAction?: React.ReactNode;
}

export function BasePanel({
    title,
    description,
    children,
    colSpan = 'col-span-1',
    isSnapshotMode = false,
    defaultExpanded = true,
    headerAction,
}: BasePanelProps) {
    // In snapshot mode, always expanded
    const [isExpanded, setIsExpanded] = useState(defaultExpanded);
    const showContent = isSnapshotMode || isExpanded;

    return (
        <div
            className={cn(
                'group relative flex flex-col overflow-hidden rounded-xl border bg-card text-card-foreground shadow-sm transition-all duration-200',
                colSpan,
                !showContent && 'h-fit' // Shrink when collapsed
            )}
        >
            {/* Header */}
            <div className="flex items-center justify-between border-b bg-muted/30 px-4 py-3">
                <div className="flex flex-col gap-0.5">
                    <h3 className="font-semibold leading-none tracking-tight">{title}</h3>
                    {description && (
                        <p className="text-xs text-muted-foreground">{description}</p>
                    )}
                </div>

                <div className="flex items-center gap-2 opacity-0 transition-opacity group-hover:opacity-100 sm:opacity-100">
                    {/* Optional Header Actions (e.g. chart toggle) */}
                    {headerAction}

                    {/* Collapse Toggle (Hidden in Snapshot Mode) */}
                    {!isSnapshotMode && (
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-6 w-6"
                            onClick={() => setIsExpanded(!isExpanded)}
                        >
                            {showContent ? (
                                <ChevronUp className="h-4 w-4" />
                            ) : (
                                <ChevronDown className="h-4 w-4" />
                            )}
                            <span className="sr-only">Toggle</span>
                        </Button>
                    )}
                </div>
            </div>

            {/* Content */}
            {showContent && <div className="flex-1 p-4 animate-in fade-in zoom-in-95 duration-200">{children}</div>}
        </div>
    );
}
