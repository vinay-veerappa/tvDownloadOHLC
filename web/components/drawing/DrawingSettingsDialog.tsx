"use client";

/**
 * DrawingSettingsDialog - 4-tab settings dialog for drawings
 * 
 * TradingView-style dialog with tabs:
 * - Style: Color, width, opacity, style, tool-specific options
 * - Coordinates: Point editing (time/price)
 * - Visibility: Timeframe toggles
 * - Text: Text annotation options
 * 
 * Plus: Template dropdown for save/load presets
 * Dialog is draggable by the header
 */

import { useState, useRef, useCallback, useEffect } from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectSeparator,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { templateStorage, DrawingTemplate } from "@/lib/template-storage";
import { GripHorizontal } from "lucide-react";

interface DrawingSettingsDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    title: string;
    toolType: string;

    // Tab content (provided by caller)
    styleTab: React.ReactNode;
    coordinatesTab?: React.ReactNode;
    visibilityTab?: React.ReactNode;
    textTab?: React.ReactNode;

    // Callbacks
    onApply: () => void;
    onCancel: () => void;

    // For template support
    currentOptions?: Record<string, any>;
    onApplyTemplate?: (options: Record<string, any>) => void;
}

export function DrawingSettingsDialog({
    open,
    onOpenChange,
    title,
    toolType,
    styleTab,
    coordinatesTab,
    visibilityTab,
    textTab,
    onApply,
    onCancel,
    currentOptions,
    onApplyTemplate,
}: DrawingSettingsDialogProps) {
    const [showSaveDialog, setShowSaveDialog] = useState(false);
    const [newTemplateName, setNewTemplateName] = useState("");

    // Drag state - use refs for smooth DOM manipulation during drag
    const dialogRef = useRef<HTMLDivElement>(null);
    const positionRef = useRef({ x: 0, y: 0 });
    const dragStartRef = useRef({ x: 0, y: 0, posX: 0, posY: 0 });
    const isDraggingRef = useRef(false);

    // Reset position when dialog opens
    useEffect(() => {
        if (open && dialogRef.current) {
            positionRef.current = { x: 0, y: 0 };
            dialogRef.current.style.transform = 'translate3d(0px, 0px, 0px)';
            dialogRef.current.style.willChange = 'transform';
        }
    }, [open]);

    // Drag handlers - direct DOM + GPU acceleration for maximum speed
    // TODO: Dialog drag is functional but not instant. Consider:
    //   - CSS containment (contain: layout style)
    //   - Reducing dialog complexity during drag
    //   - Native drag API if needed
    const handleDragStart = useCallback((e: React.MouseEvent) => {
        e.preventDefault();
        const dialog = dialogRef.current;
        if (!dialog) return;

        const startX = e.clientX;
        const startY = e.clientY;
        const startPosX = positionRef.current.x;
        const startPosY = positionRef.current.y;

        // Enable GPU layer promotion and visual feedback
        dialog.style.willChange = 'transform';
        document.body.style.cursor = 'grabbing';
        document.body.style.userSelect = 'none';

        const handleMouseMove = (e: MouseEvent) => {
            const newX = startPosX + (e.clientX - startX);
            const newY = startPosY + (e.clientY - startY);
            positionRef.current = { x: newX, y: newY };
            // translate3d promotes to GPU layer for faster rendering
            dialog.style.transform = `translate3d(${newX}px, ${newY}px, 0)`;
        };

        const handleMouseUp = () => {
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        };

        window.addEventListener('mousemove', handleMouseMove);
        window.addEventListener('mouseup', handleMouseUp);
    }, []);

    // Get templates for this tool type
    const templates = templateStorage.getByToolType(toolType);
    const defaultTemplate = templateStorage.getDefault(toolType);

    const handleTemplateChange = (value: string) => {
        if (value === "__save__") {
            setShowSaveDialog(true);
            return;
        }

        if (value === "__default__") {
            // Apply default options (handled by caller)
            return;
        }

        const template = templateStorage.get(value);
        if (template && onApplyTemplate) {
            onApplyTemplate(template.options);
        }
    };

    const handleSaveTemplate = () => {
        if (!newTemplateName.trim() || !currentOptions) return;

        templateStorage.save({
            name: newTemplateName.trim(),
            toolType,
            options: currentOptions,
        });

        setNewTemplateName("");
        setShowSaveDialog(false);
    };

    const handleApply = () => {
        onApply();
        onOpenChange(false);
    };

    const handleCancel = () => {
        onCancel();
        onOpenChange(false);
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent
                ref={dialogRef}
                className="max-w-md"
            >
                <DialogHeader
                    className="cursor-move select-none flex flex-row items-center gap-2"
                    onMouseDown={handleDragStart}
                >
                    <GripHorizontal className="h-4 w-4 text-muted-foreground" />
                    <DialogTitle>{title}</DialogTitle>
                </DialogHeader>

                <Tabs defaultValue="style" className="w-full">
                    <TabsList className="grid w-full grid-cols-4">
                        <TabsTrigger value="style">Style</TabsTrigger>
                        <TabsTrigger value="coords" disabled={!coordinatesTab}>
                            Coordinates
                        </TabsTrigger>
                        <TabsTrigger value="visibility" disabled={!visibilityTab}>
                            Visibility
                        </TabsTrigger>
                        <TabsTrigger value="text" disabled={!textTab}>
                            Text
                        </TabsTrigger>
                    </TabsList>

                    <TabsContent value="style" className="max-h-[400px] overflow-y-auto pr-2">
                        {styleTab}
                    </TabsContent>

                    {coordinatesTab && (
                        <TabsContent value="coords" className="max-h-[400px] overflow-y-auto pr-2">
                            {coordinatesTab}
                        </TabsContent>
                    )}

                    {visibilityTab && (
                        <TabsContent value="visibility" className="max-h-[400px] overflow-y-auto pr-2">
                            {visibilityTab}
                        </TabsContent>
                    )}

                    {textTab && (
                        <TabsContent value="text" className="max-h-[400px] overflow-y-auto pr-2">
                            {textTab}
                        </TabsContent>
                    )}
                </Tabs>

                <DialogFooter className="flex items-center justify-between sm:justify-between">
                    {/* Template Dropdown */}
                    <div className="flex items-center gap-2">
                        <Select onValueChange={handleTemplateChange}>
                            <SelectTrigger className="w-[160px] h-9">
                                <SelectValue placeholder="Template" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="__default__">Default</SelectItem>
                                {templates.length > 0 && (
                                    <>
                                        <SelectSeparator />
                                        {templates.map((t) => (
                                            <SelectItem key={t.id} value={t.id}>
                                                {t.name}
                                                {defaultTemplate?.id === t.id && " ✓"}
                                            </SelectItem>
                                        ))}
                                    </>
                                )}
                                <SelectSeparator />
                                <SelectItem value="__save__">✚ Save as...</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex gap-2">
                        <Button variant="outline" onClick={handleCancel}>
                            Cancel
                        </Button>
                        <Button onClick={handleApply}>OK</Button>
                    </div>
                </DialogFooter>

                {/* Save Template Dialog */}
                {showSaveDialog && (
                    <div className="absolute inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center rounded-lg">
                        <div className="bg-background border rounded-lg p-4 shadow-lg space-y-4 w-64">
                            <Label>Template Name</Label>
                            <Input
                                value={newTemplateName}
                                onChange={(e) => setNewTemplateName(e.target.value)}
                                placeholder="My Template"
                                autoFocus
                            />
                            <div className="flex justify-end gap-2">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setShowSaveDialog(false)}
                                >
                                    Cancel
                                </Button>
                                <Button
                                    size="sm"
                                    onClick={handleSaveTemplate}
                                    disabled={!newTemplateName.trim()}
                                >
                                    Save
                                </Button>
                            </div>
                        </div>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}
