"use client";

/**
 * TextSettings - 2-tab settings dialog for text drawings
 * 
 * Matches TradingView screenshot:
 * - Tab 1: Text (color, size, B/I, textarea, background, border, wrap)
 * - Tab 2: Visibility (timeframe toggles)
 */

import { useState, useEffect, useCallback } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Bold, Italic } from "lucide-react";
import { VisibilityTab } from "@/components/drawing/tabs/VisibilityTab";
import { templateStorage } from "@/lib/template-storage";
import { TextSettingsTab } from "@/components/drawing-settings/TextSettingsTab";

interface TextSettingsProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    options: {
        text?: string;
        color?: string;
        textColor?: string;
        fontSize?: number;
        fontFamily?: string;
        bold?: boolean;
        italic?: boolean;
        backgroundColor?: string;
        backgroundVisible?: boolean;
        borderColor?: string;
        borderVisible?: boolean;
        wordWrap?: boolean;
        wordWrapWidth?: number;
        alignmentVertical?: 'top' | 'center' | 'bottom';
        alignmentHorizontal?: 'left' | 'center' | 'right';
        visibleTimeframes?: string[];
    };
    onSave: (options: any) => void;
    onCancel: () => void;
}

const FONT_SIZES = [8, 10, 12, 14, 16, 18, 20, 24, 28, 32, 36, 40, 48];

export function TextSettings({
    open,
    onOpenChange,
    options: initialOptions,
    onSave,
    onCancel,
}: TextSettingsProps) {
    const [options, setOptions] = useState(initialOptions);

    // Only reset options when the dialog opens, not on every render
    useEffect(() => {
        if (open) {
            setOptions(initialOptions);
        }
    }, [open]);

    const handleChange = useCallback((updates: Partial<typeof options>) => {
        setOptions(prev => ({ ...prev, ...updates }));
    }, []);

    const handleSave = () => {
        onSave(options);
        onOpenChange(false);
    };

    const templates = templateStorage.getByToolType('text');

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-md">
                <DialogHeader className="flex flex-row items-center gap-2">
                    <DialogTitle>Text</DialogTitle>
                </DialogHeader>

                <Tabs defaultValue="text" className="w-full">
                    <TabsList className="grid w-full grid-cols-2">
                        <TabsTrigger value="text">Text</TabsTrigger>
                        <TabsTrigger value="visibility">Visibility</TabsTrigger>
                    </TabsList>

                    {/* Text Tab */}
                    <TabsContent value="text">
                        <TextSettingsTab
                            options={options}
                            onChange={handleChange}
                            isLineTool={false}
                        />
                    </TabsContent>

                    {/* Visibility Tab */}
                    <TabsContent value="visibility" className="pt-4">
                        <VisibilityTab
                            visibleTimeframes={options.visibleTimeframes || []}
                            onChange={(timeframes) => handleChange({ visibleTimeframes: timeframes })}
                        />
                    </TabsContent>
                </Tabs>

                <DialogFooter className="flex items-center justify-between sm:justify-between">
                    <Select defaultValue="default">
                        <SelectTrigger className="w-[130px]">
                            <SelectValue placeholder="Template" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="default">Template</SelectItem>
                            {templates.map(t => (
                                <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>

                    <div className="flex gap-2">
                        <Button variant="outline" onClick={onCancel}>Cancel</Button>
                        <Button onClick={handleSave}>Ok</Button>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
