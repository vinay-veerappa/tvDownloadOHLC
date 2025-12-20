"use client";

/**
 * FloatingToolbar - Appears after drawing is created/selected
 * 
 * TradingView-style toolbar with 6 buttons:
 * - Settings (opens settings dialog)
 * - Clone (duplicates drawing)
 * - Lock (prevents modification)
 * - Delete (removes drawing)
 * - Hide (toggles visibility)
 * - Favorite (adds tool to favorites)
 */

import { Settings, Copy, Lock, Unlock, Trash2, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger, TooltipProvider } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface FloatingToolbarProps {
    drawingId: string;
    drawingType: string;
    position: { x: number; y: number };
    isLocked?: boolean;
    isHidden?: boolean;
    onSettings: () => void;
    onClone: () => void;
    onLock: () => void;
    onDelete: () => void;
    onToggleVisibility: () => void;
    className?: string;
}

export function FloatingToolbar({
    drawingId,
    drawingType,
    position,
    isLocked = false,
    isHidden = false,
    onSettings,
    onClone,
    onLock,
    onDelete,
    onToggleVisibility,
    className,
}: FloatingToolbarProps) {
    // Toolbar is visible whenever rendered - parent controls visibility

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
                {/* Settings */}
                <Tooltip>
                    <TooltipTrigger asChild>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={onSettings}
                        >
                            <Settings className="h-3.5 w-3.5" />
                        </Button>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="text-xs">
                        Settings
                    </TooltipContent>
                </Tooltip>

                {/* Clone */}
                <Tooltip>
                    <TooltipTrigger asChild>
                        <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            onClick={onClone}
                            disabled={isLocked}
                        >
                            <Copy className="h-3.5 w-3.5" />
                        </Button>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="text-xs">
                        Clone (Ctrl+D)
                    </TooltipContent>
                </Tooltip>

                {/* Lock/Unlock */}
                <Tooltip>
                    <TooltipTrigger asChild>
                        <Button
                            variant="ghost"
                            size="icon"
                            className={cn("h-7 w-7", isLocked && "text-amber-500")}
                            onClick={onLock}
                        >
                            {isLocked ? (
                                <Lock className="h-3.5 w-3.5" />
                            ) : (
                                <Unlock className="h-3.5 w-3.5" />
                            )}
                        </Button>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="text-xs">
                        {isLocked ? "Unlock" : "Lock"}
                    </TooltipContent>
                </Tooltip>

                {/* Delete */}
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
                    <TooltipContent side="top" className="text-xs">
                        Delete (Del)
                    </TooltipContent>
                </Tooltip>

                {/* Hide/Show */}
                <Tooltip>
                    <TooltipTrigger asChild>
                        <Button
                            variant="ghost"
                            size="icon"
                            className={cn("h-7 w-7", isHidden && "text-muted-foreground")}
                            onClick={onToggleVisibility}
                        >
                            {isHidden ? (
                                <EyeOff className="h-3.5 w-3.5" />
                            ) : (
                                <Eye className="h-3.5 w-3.5" />
                            )}
                        </Button>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="text-xs">
                        {isHidden ? "Show" : "Hide"}
                    </TooltipContent>
                </Tooltip>
            </div>
        </TooltipProvider>
    );
}
