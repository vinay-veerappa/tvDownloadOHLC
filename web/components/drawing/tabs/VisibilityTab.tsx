"use client";

/**
 * VisibilityTab - Timeframe visibility toggles
 * 
 * Controls which timeframes show the drawing
 */

import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";

const TIMEFRAMES = [
    { id: "1m", label: "1m" },
    { id: "5m", label: "5m" },
    { id: "15m", label: "15m" },
    { id: "30m", label: "30m" },
    { id: "1h", label: "1H" },
    { id: "4h", label: "4H" },
    { id: "1d", label: "1D" },
    { id: "1w", label: "1W" },
    { id: "1M", label: "1M" },
];

interface VisibilityTabProps {
    visibleTimeframes: string[]; // e.g., ["1m", "5m", "15m"]
    onChange: (timeframes: string[]) => void;
}

export function VisibilityTab({ visibleTimeframes, onChange }: VisibilityTabProps) {
    const toggleTimeframe = (tf: string) => {
        if (visibleTimeframes.includes(tf)) {
            onChange(visibleTimeframes.filter(t => t !== tf));
        } else {
            onChange([...visibleTimeframes, tf]);
        }
    };

    const selectAll = () => {
        onChange(TIMEFRAMES.map(tf => tf.id));
    };

    const selectNone = () => {
        onChange([]);
    };

    return (
        <div className="space-y-4 py-4">
            <div className="flex items-center justify-between">
                <Label className="text-sm font-semibold">Show on Timeframes</Label>
                <div className="flex gap-2">
                    <button
                        type="button"
                        className="text-xs text-primary hover:underline"
                        onClick={selectAll}
                    >
                        All
                    </button>
                    <span className="text-muted-foreground">|</span>
                    <button
                        type="button"
                        className="text-xs text-primary hover:underline"
                        onClick={selectNone}
                    >
                        None
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-3 gap-3">
                {TIMEFRAMES.map((tf) => (
                    <div key={tf.id} className="flex items-center space-x-2">
                        <Checkbox
                            id={`tf-${tf.id}`}
                            checked={visibleTimeframes.includes(tf.id)}
                            onCheckedChange={() => toggleTimeframe(tf.id)}
                        />
                        <Label
                            htmlFor={`tf-${tf.id}`}
                            className="text-sm cursor-pointer"
                        >
                            {tf.label}
                        </Label>
                    </div>
                ))}
            </div>
        </div>
    );
}
