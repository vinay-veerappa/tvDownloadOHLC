"use client";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
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
        backgroundColor?: string;
        backgroundVisible?: boolean;
        backgroundOpacity?: number;
        borderColor?: string;
        borderVisible?: boolean;
        borderWidth?: number;
        [key: string]: any;
    };
    onChange: (updates: any) => void;
    isLineTool?: boolean; // If true, shows "Show Text" toggle
}

const FONT_SIZES = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40, 48];

export function TextSettingsTab({ options, onChange, isLineTool }: TextSettingsTabProps) {
    return (
        <div className="space-y-4 pt-4">
            {/* Show Text toggle hidden per user request */}

            {/* Colors & Font Styles */}
            <div className="flex items-center gap-2">
                <Input
                    type="color"
                    value={options.textColor || '#FFFFFF'}
                    onChange={(e) => onChange({ textColor: e.target.value })}
                    className="w-10 h-10 p-1 cursor-pointer"
                    title="Text color"
                />
                <Select
                    value={String(options.fontSize || 14)}
                    onValueChange={(v) => onChange({ fontSize: parseInt(v) })}
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
                        title="Bold"
                    >
                        <Bold className="h-4 w-4" />
                    </Button>
                    <Button
                        variant={options.italic ? "secondary" : "ghost"}
                        size="icon"
                        onClick={() => onChange({ italic: !options.italic })}
                        className="h-8 w-8"
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
            />

            {/* Alignment Options */}
            <div className="flex items-center gap-4">
                <Label className="text-sm text-muted-foreground whitespace-nowrap">Text alignment</Label>
                <div className="flex gap-2 w-full">
                    {/* Vertical Alignment */}
                    <Select
                        value={options.alignmentVertical || 'center'}
                        onValueChange={(v) => onChange({ alignmentVertical: v })}
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
            {/* Background & Border */}
            <div className="space-y-3 pt-2">
                {/* Background */}
                <div className="flex items-center gap-2">
                    <Checkbox
                        id="bg-visible"
                        checked={options.backgroundVisible || false}
                        onCheckedChange={(c) => onChange({ backgroundVisible: c === true })}
                    />
                    <Label htmlFor="bg-visible" className="text-sm cursor-pointer w-24">Background</Label>
                    <Input
                        type="color"
                        value={options.backgroundColor || '#2962FF'}
                        onChange={(e) => onChange({ backgroundColor: e.target.value })}
                        disabled={!options.backgroundVisible}
                        className="w-8 h-8 p-0 border-0 rounded-full cursor-pointer disabled:opacity-50"
                    />
                    {/* Opacity slider could go here in future */}
                </div>

                {/* Border */}
                <div className="flex items-center gap-2">
                    <Checkbox
                        id="border-visible"
                        checked={options.borderVisible || false}
                        onCheckedChange={(c) => onChange({ borderVisible: c === true })}
                    />
                    <Label htmlFor="border-visible" className="text-sm cursor-pointer w-24">Border</Label>
                    <Input
                        type="color"
                        value={options.borderColor || '#FFFFFF'}
                        onChange={(e) => onChange({ borderColor: e.target.value })}
                        disabled={!options.borderVisible}
                        className="w-8 h-8 p-0 border-0 rounded-full cursor-pointer disabled:opacity-50"
                    />
                    <Select
                        value={String(options.borderWidth || 1)}
                        onValueChange={(v) => onChange({ borderWidth: parseInt(v) })}
                        disabled={!options.borderVisible}
                    >
                        <SelectTrigger className="w-16 h-8">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            {[1, 2, 3, 4].map(w => (
                                <SelectItem key={w} value={String(w)}>{w}px</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            </div>
        </div>
    );
}
