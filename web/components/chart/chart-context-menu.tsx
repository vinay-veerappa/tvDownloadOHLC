"use client"

import { useEffect, useState } from "react"

interface ChartContextMenuProps {
    containerRef: React.RefObject<HTMLDivElement | null>
    selectedDrawing: any
    onDelete: () => void
    onSettings: () => void
}

export function ChartContextMenu({ containerRef, selectedDrawing, onDelete, onSettings }: ChartContextMenuProps) {
    const [contextMenu, setContextMenu] = useState<{ x: number; y: number; visible: boolean }>({ x: 0, y: 0, visible: false })

    useEffect(() => {
        if (!containerRef.current) return;
        const container = containerRef.current;

        const handleContextMenu = (e: MouseEvent) => {
            if (!selectedDrawing) return;

            const rect = container.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            const hit = selectedDrawing.hitTest?.(x, y);
            if (hit) {
                e.preventDefault();
                setContextMenu({ x: e.clientX - rect.left, y: e.clientY - rect.top, visible: true });
            }
        };

        const handleClickOutside = () => {
            setContextMenu(prev => ({ ...prev, visible: false }));
        };

        container.addEventListener('contextmenu', handleContextMenu);
        window.addEventListener('click', handleClickOutside);

        return () => {
            container.removeEventListener('contextmenu', handleContextMenu);
            window.removeEventListener('click', handleClickOutside);
        };
    }, [containerRef, selectedDrawing]);

    if (!contextMenu.visible) return null;

    return (
        <div
            className="absolute bg-popover text-popover-foreground border rounded-md shadow-md p-1 min-w-[150px] z-50 flex flex-col gap-1"
            // eslint-disable-next-line
            style={{ left: contextMenu.x, top: contextMenu.y }}
        >
            <button
                className="w-full text-left px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground rounded-sm"
                onClick={() => {
                    onSettings()
                    setContextMenu(prev => ({ ...prev, visible: false }))
                }}
            >
                Settings
            </button>
            <button
                className="w-full text-left px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground rounded-sm text-destructive"
                onClick={() => {
                    onDelete()
                    setContextMenu(prev => ({ ...prev, visible: false }))
                }}
            >
                Delete
            </button>
        </div>
    )
}
