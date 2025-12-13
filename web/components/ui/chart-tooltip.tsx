"use client"

import React from 'react';
import { cn } from "@/lib/utils";

interface ChartTooltipFrameProps {
    children: React.ReactNode;
    className?: string;
}

export function ChartTooltipFrame({ children, className }: ChartTooltipFrameProps) {
    return (
        <div className={cn(
            "bg-background border border-border shadow-xl rounded-md text-xs p-3 min-w-[140px] animate-in fade-in zoom-in-95 duration-200",
            className
        )}>
            {children}
        </div>
    );
}

interface ChartTooltipHeaderProps {
    children: React.ReactNode;
    color?: string;
    className?: string;
}

export function ChartTooltipHeader({ children, color, className }: ChartTooltipHeaderProps) {
    return (
        <div className={cn("font-bold text-base mb-2 flex items-center gap-2 text-foreground border-b border-border pb-2", className)}>
            {color && <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: color }} />}
            {children}
        </div>
    );
}

interface ChartTooltipRowProps {
    label: string;
    value: string | number;
    subValue?: string;
    indicatorColor?: string;
    className?: string;
}

export function ChartTooltipRow({ label, value, subValue, indicatorColor, className }: ChartTooltipRowProps) {
    return (
        <div className={cn("flex justify-between items-start gap-4 py-1", className)}>
            <div className="flex items-center gap-2">
                {indicatorColor && <div className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: indicatorColor }} />}
                <span className="text-muted-foreground">{label}</span>
            </div>
            <div className="text-right">
                <div className="font-mono font-medium text-foreground">{value}</div>
                {subValue && <div className="text-[10px] text-muted-foreground">{subValue}</div>}
            </div>
        </div>
    );
}
