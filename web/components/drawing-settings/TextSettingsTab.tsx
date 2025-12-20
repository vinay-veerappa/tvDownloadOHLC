"use client";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Bold, Italic } from "lucide-react";

interface TextSettingsTabProps {
    options: {
        text?: string;
        textColor?: string;
        fontSize?: number;
        bold?: boolean;
        italic?: boolean;
        showLabel?: boolean; // For line tools toggle
        alignmentVertical?: 'top' | 'center' | 'bottom';
        alignmentHorizontal?: 'left' | 'center' | 'right';
        [key: string]: any;
    };
    onChange: (updates: any) => void;
    isLineTool?: boolean; // If true, shows "Show Text" toggle
}

const FONT_SIZES = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40, 48];

export function TextSettingsTab({ options, onChange, isLineTool }: TextSettingsTabProps) {
    return (
        <div className="space-y-4 pt-4">
            {/* Show Label Toggle for Line Tools */}
            {isLineTool && (
                <div className="flex items-center gap-2 mb-2">
                    <Checkbox
                        id="showLabel"
                        checked={options.showLabel}
                        onCheckedChange={(c) => onChange({ showLabel: !!c })}
                    />
                    <Label htmlFor="showLabel">Show Text</Label>
                </div>
            )}

            {/* Colors & Font Styles */}
            <div className="flex items-center gap-2">
                <Input
                    type="color"
                    value={options.textColor || '#FFFFFF'}
                    onChange={(e) => onChange({ textColor: e.target.value })}
                    className="w-10 h-10 p-1 cursor-pointer"
                    title="Text color"
                    disabled={isLineTool && !options.showLabel}
                />
                <Select
                    value={String(options.fontSize || 14)}
                    onValueChange={(v) => onChange({ fontSize: parseInt(v) })}
                    disabled={isLineTool && !options.showLabel}
                >
                    <SelectTrigger className="w-20">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        {FONT_SIZES.map(size => (
                            <SelectItem key={size} value={String(size)}>{size}</SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <div className="flex gap-1 bg-secondary/20 p-1 rounded-md">
                    <Button
                        variant={options.bold ? "secondary" : "ghost"}
                        size="icon"
                        onClick={() => onChange({ bold: !options.bold })}
                        className="h-8 w-8"
                        disabled={isLineTool && !options.showLabel}
                        title="Bold"
                    >
                        <Bold className="h-4 w-4" />
                    </Button>
                    <Button
                        variant={options.italic ? "secondary" : "ghost"}
                        size="icon"
                        onClick={() => onChange({ italic: !options.italic })}
                        className="h-8 w-8"
                        disabled={isLineTool && !options.showLabel}
                        title="Italic"
                    >
                        <Italic className="h-4 w-4" />
                    </Button>
                </div>
            </div>

            {/* Text Area */}
            <Textarea
                value={options.text || ''}
                onChange={(e) => onChange({ text: e.target.value })}
                placeholder="Add text"
                className="min-h-[100px] resize-none"
                disabled={isLineTool && !options.showLabel}
            />

            {/* Alignment Options */}
            <div className="flex items-center gap-4">
                <Label className="text-sm text-muted-foreground whitespace-nowrap">Text alignment</Label>
                <div className="flex gap-2 w-full">
                    {/* Vertical Alignment */}
                    <Select
                        value={options.alignmentVertical || 'center'}
                        onValueChange={(v) => onChange({ alignmentVertical: v })}
                        disabled={isLineTool && !options.showLabel}
                    >
                        <SelectTrigger className="w-full">
                            <SelectValue placeholder="Vertical" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="top">Top</SelectItem>
                            <SelectItem value="center">Middle</SelectItem>
                            <SelectItem value="bottom">Bottom</SelectItem>
                        </SelectContent>
                    </Select>

                    {/* Horizontal Alignment */}
                    <Select
                        value={options.alignmentHorizontal || 'center'}
                        onValueChange={(v) => onChange({ alignmentHorizontal: v })}
                        disabled={isLineTool && !options.showLabel}
                    >
                        <SelectTrigger className="w-full">
                            <SelectValue placeholder="Horizontal" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="left">Left</SelectItem>
                            <SelectItem value="center">Center</SelectItem>
                            <SelectItem value="right">Right</SelectItem>
                        </SelectContent>
                    </Select>
                </div>
            </div>
        </div>
    );
}
