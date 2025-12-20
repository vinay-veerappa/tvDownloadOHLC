"use client";

/**
 * useDrawingSettings - Hook for managing drawing settings dialogs
 * 
 * Provides:
 * - Open/close settings dialog for selected drawing
 * - Apply settings changes to drawings
 * - FloatingToolbar integration
 */

import { useState, useCallback } from "react";

interface DrawingWithOptions {
    id: () => string;
    options: () => Record<string, any>;
    applyOptions: (options: Record<string, any>) => void;
    isSelected?: () => boolean;
    setSelected?: (selected: boolean) => void;
    isLocked?: () => boolean;
    setLocked?: (locked: boolean) => void;
    isHidden?: () => boolean;
    setHidden?: (hidden: boolean) => void;
    _type?: string;
    _p1?: { time: any; price: number };
    _p2?: { time: any; price: number };
}

interface UseDrawingSettingsReturn {
    // State
    selectedDrawingId: string | null;
    settingsOpen: boolean;

    // Actions
    openSettings: (drawingId: string) => void;
    closeSettings: () => void;
    applySettings: (options: Record<string, any>) => void;

    // Floating toolbar actions
    handleClone: () => void;
    handleLock: () => void;
    handleDelete: () => void;
    handleToggleVisibility: () => void;

    // Getters for current drawing state
    isLocked: boolean;
    isHidden: boolean;
}

export function useDrawingSettings(
    drawingsRef: React.MutableRefObject<Map<string, DrawingWithOptions>>,
    onDelete?: (id: string) => void,
    onClone?: (drawing: DrawingWithOptions) => void,
): UseDrawingSettingsReturn {
    const [selectedDrawingId, setSelectedDrawingId] = useState<string | null>(null);
    const [settingsOpen, setSettingsOpen] = useState(false);

    // Get the selected drawing
    const getSelectedDrawing = useCallback((): DrawingWithOptions | undefined => {
        if (!selectedDrawingId) return undefined;
        return drawingsRef.current.get(selectedDrawingId);
    }, [selectedDrawingId, drawingsRef]);

    // Open settings dialog
    const openSettings = useCallback((drawingId: string) => {
        setSelectedDrawingId(drawingId);
        setSettingsOpen(true);
    }, []);

    // Close settings dialog
    const closeSettings = useCallback(() => {
        setSettingsOpen(false);
    }, []);

    // Apply settings to drawing
    const applySettings = useCallback((options: Record<string, any>) => {
        const drawing = getSelectedDrawing();
        if (drawing) {
            drawing.applyOptions(options);
        }
        closeSettings();
    }, [getSelectedDrawing, closeSettings]);

    // Clone the selected drawing
    const handleClone = useCallback(() => {
        const drawing = getSelectedDrawing();
        if (drawing && onClone) {
            onClone(drawing);
        }
    }, [getSelectedDrawing, onClone]);

    // Toggle lock state
    const handleLock = useCallback(() => {
        const drawing = getSelectedDrawing();
        if (drawing && drawing.setLocked && drawing.isLocked) {
            drawing.setLocked(!drawing.isLocked());
        }
    }, [getSelectedDrawing]);

    // Delete the selected drawing
    const handleDelete = useCallback(() => {
        if (selectedDrawingId && onDelete) {
            onDelete(selectedDrawingId);
            setSelectedDrawingId(null);
            setSettingsOpen(false);
        }
    }, [selectedDrawingId, onDelete]);

    // Toggle visibility
    const handleToggleVisibility = useCallback(() => {
        const drawing = getSelectedDrawing();
        if (drawing && drawing.setHidden && drawing.isHidden) {
            drawing.setHidden(!drawing.isHidden());
        }
    }, [getSelectedDrawing]);

    // Get current state
    const drawing = getSelectedDrawing();
    const isLocked = drawing?.isLocked?.() ?? false;
    const isHidden = drawing?.isHidden?.() ?? false;

    return {
        selectedDrawingId,
        settingsOpen,
        openSettings,
        closeSettings,
        applySettings,
        handleClone,
        handleLock,
        handleDelete,
        handleToggleVisibility,
        isLocked,
        isHidden,
    };
}
