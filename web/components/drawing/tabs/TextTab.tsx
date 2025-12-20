"use client";

/**
 * TextTab - Text annotation options
 * 
 * Controls:
 * - Text content
 * - Font size
 * - Bold/Italic
 * - Color
 * - Position (left/center/right)
 */

import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Bold, Italic, AlignLeft, AlignCenter, AlignRight } from "lucide-react";

interface TextOptions {
    text: string;
    fontSize?: number;
    bold?: boolean;
    italic?: boolean;
    color?: string;
    alignment?: 'left' | 'center' | 'right';
}

interface TextTabProps {
    options: TextOptions;
    onChange: (updates: Partial<TextOptions>) => void;
}

export function TextTab({ options, onChange }: TextTabProps) {
    const {
        text = '',
        fontSize = 12,
        bold = false,
        italic = false,
        color = '#000000',
        alignment = 'center',
    } = options;

    return (
        <div className="space-y-4 py-4">
            {/* Text Content */}
            <div className="space-y-2">
                <Label>Text</Label>
                <Textarea
                    value={text}
                    onChange={(e) => onChange({ text: e.target.value })}
                    placeholder="Enter text..."
                    className="min-h-[80px] resize-none"
                />
            </div>

            {/* Font Size */}
            <div className="flex items-center justify-between">
                <Label>Font Size</Label>
                <Select
                    value={fontSize.toString()}
                    onValueChange={(v) => onChange({ fontSize: parseInt(v) })}
                >
                    <SelectTrigger className="w-[80px] h-8">
                        <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                        {[8, 10, 12, 14, 16, 18, 20, 24, 28, 32].map((size) => (
                            <SelectItem key={size} value={size.toString()}>
                                {size}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {/* Style (Bold/Italic) */}
            <div className="flex items-center justify-between">
                <Label>Style</Label>
                <div className="flex gap-1">
                    <ToggleGroup
                        type="multiple"
                        value={[
                            ...(bold ? ['bold'] : []),
                            ...(italic ? ['italic'] : []),
                        ]}
                        onValueChange={(values) => {
                            onChange({
                                bold: values.includes('bold'),
                                italic: values.includes('italic'),
                            });
                        }}
                    >
                        <ToggleGroupItem value="bold" className="h-8 w-8">
                            <Bold className="h-4 w-4" />
                        </ToggleGroupItem>
                        <ToggleGroupItem value="italic" className="h-8 w-8">
                            <Italic className="h-4 w-4" />
                        </ToggleGroupItem>
                    </ToggleGroup>
                </div>
            </div>

            {/* Color */}
            <div className="flex items-center justify-between">
                <Label>Color</Label>
                <div className="flex items-center gap-2">
                    <Input
                        type="color"
                        value={color}
                        onChange={(e) => onChange({ color: e.target.value })}
                        className="w-10 h-8 p-0.5 cursor-pointer border-2"
                    />
                    <span className="text-xs text-muted-foreground font-mono w-16">
                        {color.toUpperCase()}
                    </span>
                </div>
            </div>

            {/* Alignment */}
            <div className="flex items-center justify-between">
                <Label>Alignment</Label>
                <ToggleGroup
                    type="single"
                    value={alignment}
                    onValueChange={(v) => v && onChange({ alignment: v as 'left' | 'center' | 'right' })}
                >
                    <ToggleGroupItem value="left" className="h-8 w-8">
                        <AlignLeft className="h-4 w-4" />
                    </ToggleGroupItem>
                    <ToggleGroupItem value="center" className="h-8 w-8">
                        <AlignCenter className="h-4 w-4" />
                    </ToggleGroupItem>
                    <ToggleGroupItem value="right" className="h-8 w-8">
                        <AlignRight className="h-4 w-4" />
                    </ToggleGroupItem>
                </ToggleGroup>
            </div>
        </div>
    );
}
