"use client";

/**
 * FloatingToolbar - Context-aware toolbar that changes based on drawing type
 * 
 * Features:
 * - Tool-specific quick actions (color, size, style)
 * - Template dropdown for save/apply
 * - Common buttons (lock, delete, more)
 * - Overflow menu with additional options
 */

import {
    Settings, Copy, Lock, Unlock, Trash2, Eye, EyeOff,
    MoreHorizontal, Download, Target, GripVertical,
    Type, PaintBucket, Minus, Square, Pen, Layers
} from "lucide-react";
import React, { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "@/lib/utils";
import { getToolbarConfig, ToolbarButtonConfig } from "@/lib/toolbar-configs";
import { ColorPickerButton, SelectButton, TemplateDropdown } from "./toolbar-buttons";

interface FloatingToolbarProps {
    drawingId: string;
    drawingType: string;
    position: { x: number; y: number };
    options: Record<string, any>;  // Current drawing options
    isLocked?: boolean;
    isHidden?: boolean;
    onSettings: () => void;
    onClone: () => void;
    onLock: () => void;
    onDelete: () => void;
    onToggleVisibility: () => void;
    onOptionsChange: (updates: Record<string, any>) => void;
    onPositionChange?: (pos: { x: number; y: number }) => void;
    className?: string;
}

// Icon mapping
const ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
    Type, PaintBucket, Minus, Square, Pen, Layers, Target
};

export function FloatingToolbar({
    drawingId,
    drawingType,
    position,
    options,
    isLocked = false,
    isHidden = false,
    onSettings,
    onClone,
    onLock,
    onDelete,
    onToggleVisibility,
    onOptionsChange,
    onPositionChange,
    className,
}: FloatingToolbarProps) {
    const config = getToolbarConfig(drawingType);
    const [isDragging, setIsDragging] = React.useState(false);
    const dragStartRef = React.useRef<{ x: number; y: number } | null>(null);
    const startPosRef = React.useRef<{ x: number; y: number } | null>(null);

    React.useEffect(() => {
        const handleMouseMove = (e: MouseEvent) => {
            if (!isDragging || !dragStartRef.current || !startPosRef.current || !onPositionChange) return;

            const dx = e.clientX - dragStartRef.current.x;
            const dy = e.clientY - dragStartRef.current.y;

            onPositionChange({
                x: startPosRef.current.x + dx,
                y: startPosRef.current.y + dy
            });
        };

        const handleMouseUp = () => {
            setIsDragging(false);
            dragStartRef.current = null;
            startPosRef.current = null;
        };

        if (isDragging) {
            window.addEventListener('mousemove', handleMouseMove);
            window.addEventListener('mouseup', handleMouseUp);
        }

        return () => {
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        };
    }, [isDragging, onPositionChange]);

    const handleDragStart = (e: React.MouseEvent) => {
        e.preventDefault();
        setIsDragging(true);
        dragStartRef.current = { x: e.clientX, y: e.clientY };
        startPosRef.current = { x: position.x, y: position.y };
    };

    // Render a quick action button based on its config
    const renderQuickAction = (btn: ToolbarButtonConfig) => {
        const IconComponent = btn.icon ? ICONS[btn.icon] : null;

        if (btn.type === 'color' && btn.colorProp) {
            return (
                <ColorPickerButton
                    key={btn.id}
                    color={options[btn.colorProp] || '#FFFFFF'}
                    onChange={(color) => onOptionsChange({ [btn.colorProp!]: color })}
                    tooltip={btn.tooltip}
                    icon={IconComponent && <IconComponent className="h-3.5 w-3.5" />}
                    disabled={isLocked}
                />
            );
        }

        if (btn.type === 'select' && btn.selectProp && btn.options) {
            return (
                <SelectButton
                    key={btn.id}
                    value={options[btn.selectProp]}
                    options={btn.options}
                    onChange={(value) => onOptionsChange({ [btn.selectProp!]: value })}
                    tooltip={btn.tooltip}
                    icon={IconComponent && <IconComponent className="h-3.5 w-3.5" />}
                    disabled={isLocked}
                />
            );
        }

        if (btn.type === 'toggle' && btn.toggleProp) {
            const isOn = options[btn.toggleProp];
            return (
                <Tooltip key={btn.id}>
                    <TooltipTrigger asChild>
                        <Button
                            variant={isOn ? "secondary" : "ghost"}
                            size="icon"
                            className="h-7 w-7"
                            onClick={() => onOptionsChange({ [btn.toggleProp!]: !isOn })}
                        >
                            {IconComponent && <IconComponent className="h-3.5 w-3.5" />}
                        </Button>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="text-xs">{btn.tooltip}</TooltipContent>
                </Tooltip>
            );
        }

        return null;
    };

    return (
        <TooltipProvider delayDuration={300}>
            <div
                className={cn(
                    "absolute z-50 flex items-center gap-0.5 bg-background/95 backdrop-blur-sm border rounded-md shadow-lg p-0.5",
                    className
                )}
                style={{
                    left: position.x + 12,
                    top: position.y - 16,
                    transform: 'translateY(-50%)',
                }}
            >
                {/* Drag Handle */}
                <div
                    className="px-1 cursor-grab text-muted-foreground hover:text-foreground active:cursor-grabbing"
                    onMouseDown={handleDragStart}
                >
                    <GripVertical className="h-4 w-4" />
                </div>

                {/* Object Tree Button */}
                <Tooltip>
                    <TooltipTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-7 w-7">
                            <Layers className="h-3.5 w-3.5" />
                        </Button>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="text-xs">Object tree</TooltipContent>
                </Tooltip>

                {/* Tool-specific Quick Actions */}
                {config.quickActions.map(renderQuickAction)}

                {/* Separator */}
                <div className="w-px h-5 bg-border mx-0.5" />

                {/* Common Buttons */}
                {config.commonButtons.includes('target') && (
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-7 w-7">
                                <Target className="h-3.5 w-3.5" />
                            </Button>
                        </TooltipTrigger>
                        <TooltipContent side="top" className="text-xs">Target</TooltipContent>
                    </Tooltip>
                )}

                {config.commonButtons.includes('lock') && (
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <Button
                                variant="ghost"
                                size="icon"
                                className={cn("h-7 w-7", isLocked && "text-amber-500")}
                                onClick={onLock}
                            >
                                {isLocked ? <Lock className="h-3.5 w-3.5" /> : <Unlock className="h-3.5 w-3.5" />}
                            </Button>
                        </TooltipTrigger>
                        <TooltipContent side="top" className="text-xs">
                            {isLocked ? "Unlock" : "Lock"}
                        </TooltipContent>
                    </Tooltip>
                )}

                {config.commonButtons.includes('download') && (
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-7 w-7">
                                <Download className="h-3.5 w-3.5" />
                            </Button>
                        </TooltipTrigger>
                        <TooltipContent side="top" className="text-xs">Download</TooltipContent>
                    </Tooltip>
                )}

                {config.commonButtons.includes('delete') && (
                    <Tooltip>
                        <TooltipTrigger asChild>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7 text-destructive hover:text-destructive"
                                onClick={onDelete}
                            >
                                <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                        </TooltipTrigger>
                        <TooltipContent side="top" className="text-xs">Delete (Del)</TooltipContent>
                    </Tooltip>
                )}

                {/* More Options (Overflow Menu) */}
                <Popover>
                    <PopoverTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-7 w-7">
                            <MoreHorizontal className="h-3.5 w-3.5" />
                        </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-56 p-1" align="end">
                        <div className="flex flex-col">
                            {/* Template Section */}
                            <TemplateDropdown
                                toolType={drawingType}
                                currentOptions={options}
                                onApplyTemplate={(templateOptions) => onOptionsChange(templateOptions)}
                            />

                            <div className="my-1 border-t border-border" />

                            {/* Clone */}
                            <button
                                className="flex items-center justify-between px-2 py-1.5 text-sm rounded hover:bg-muted"
                                onClick={onClone}
                                disabled={isLocked}
                            >
                                <span className="flex items-center gap-2">
                                    <Copy className="h-4 w-4" />
                                    Clone
                                </span>
                                <span className="text-xs text-muted-foreground">Ctrl + Drag</span>
                            </button>

                            {/* Hide */}
                            <button
                                className="flex items-center gap-2 px-2 py-1.5 text-sm rounded hover:bg-muted"
                                onClick={onToggleVisibility}
                            >
                                {isHidden ? <Eye className="h-4 w-4" /> : <EyeOff className="h-4 w-4" />}
                                {isHidden ? "Show" : "Hide"}
                            </button>

                            {/* Settings */}
                            {config.commonButtons.includes('settings') && (
                                <button
                                    className="flex items-center gap-2 px-2 py-1.5 text-sm rounded hover:bg-muted"
                                    onClick={onSettings}
                                >
                                    <Settings className="h-4 w-4" />
                                    Settings
                                </button>
                            )}
                        </div>
                    </PopoverContent>
                </Popover>
            </div>
        </TooltipProvider>
    );
}
