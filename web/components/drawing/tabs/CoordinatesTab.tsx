"use client";

/**
 * CoordinatesTab - Point editing for drawings
 * 
 * Allows precise editing of:
 * - Time/Date for each point
 * - Price for each point
 */

import { useState, useEffect } from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Time } from "lightweight-charts";

interface Point {
    time: Time;
    price: number;
}

interface CoordinatesTabProps {
    points: Point[];
    onChange: (points: Point[]) => void;
    labels?: string[]; // e.g., ["Point 1", "Point 2"]
}

export function CoordinatesTab({
    points,
    onChange,
    labels = ["Point 1", "Point 2"],
}: CoordinatesTabProps) {
    const [localPoints, setLocalPoints] = useState<Point[]>(points);

    useEffect(() => {
        setLocalPoints(points);
    }, [points]);

    const updatePoint = (index: number, updates: Partial<Point>) => {
        const newPoints = [...localPoints];
        newPoints[index] = { ...newPoints[index], ...updates };
        setLocalPoints(newPoints);
        onChange(newPoints);
    };

    const formatTime = (time: Time): string => {
        if (typeof time === 'number') {
            return new Date(time * 1000).toISOString().slice(0, 16);
        }
        return String(time);
    };

    const parseTime = (value: string): Time => {
        const date = new Date(value);
        return Math.floor(date.getTime() / 1000) as Time;
    };

    return (
        <div className="space-y-4 py-4">
            {localPoints.map((point, index) => (
                <div key={index} className="space-y-3">
                    <Label className="text-sm font-semibold">
                        {labels[index] || `Point ${index + 1}`}
                    </Label>

                    <div className="grid grid-cols-2 gap-3 pl-2">
                        <div className="space-y-1">
                            <Label className="text-xs text-muted-foreground">Time</Label>
                            <Input
                                type="datetime-local"
                                value={formatTime(point.time)}
                                onChange={(e) => updatePoint(index, { time: parseTime(e.target.value) })}
                                className="h-8 text-xs"
                            />
                        </div>

                        <div className="space-y-1">
                            <Label className="text-xs text-muted-foreground">Price</Label>
                            <Input
                                type="number"
                                value={point.price}
                                onChange={(e) => updatePoint(index, { price: parseFloat(e.target.value) || 0 })}
                                className="h-8 text-xs"
                                step="0.01"
                            />
                        </div>
                    </div>

                    {index < localPoints.length - 1 && <Separator />}
                </div>
            ))}
        </div>
    );
}

// ===== Single Price Variant (for Horizontal Line) =====

interface SinglePriceTabProps {
    price: number;
    onChange: (price: number) => void;
}

export function SinglePriceTab({ price, onChange }: SinglePriceTabProps) {
    return (
        <div className="space-y-4 py-4">
            <div className="space-y-2">
                <Label>Price Level</Label>
                <Input
                    type="number"
                    value={price}
                    onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
                    className="h-9"
                    step="0.01"
                />
            </div>
        </div>
    );
}
