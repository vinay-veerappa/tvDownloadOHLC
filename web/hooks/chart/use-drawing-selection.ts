import { useEffect, useState, useRef } from "react"

interface UseDrawingSelectionProps {
    v2Sandbox: any | null
    onSelectionChange?: (selection: any) => void
    onToolSelect?: (tool: any) => void
    selectionProp?: any
    DRAWING_TYPES: string[]
}

export function useDrawingSelection({
    v2Sandbox, onSelectionChange, onToolSelect, selectionProp, DRAWING_TYPES
}: UseDrawingSelectionProps) {
    // Selection state
    const [selectedDrawing, setSelectedDrawing] = useState<any | null>(null)
    const [selectedDrawingId, setSelectedDrawingId] = useState<string | null>(null)
    const selectedDrawingRef = useRef<any | null>(null)
    const [selectedDrawingType, setSelectedDrawingType] = useState<string>('')
    const [selectedDrawingOptions, setSelectedDrawingOptions] = useState<any>({})
    const [selectedDrawingPoints, setSelectedDrawingPoints] = useState<any[]>([])
    
    // UI state
    const [toolbarPosition, setToolbarPosition] = useState<{ x: number; y: number } | null>(null)
    const [showProperties, setShowProperties] = useState(false)
    const [isDrawingLocked, setIsDrawingLocked] = useState(false)
    const [isDrawingHidden, setIsDrawingHidden] = useState(false)
    const [textSettingsOpen, setTextSettingsOpen] = useState(false)
    const [inlineTextEditing, setInlineTextEditing] = useState<string | null>(null)
    
    // Tool Specific Dialogs
    const [trendLineSettingsOpen, setTrendLineSettingsOpen] = useState(false)
    const [horizontalLineSettingsOpen, setHorizontalLineSettingsOpen] = useState(false)
    const [rectangleSettingsOpen, setRectangleSettingsOpen] = useState(false)
    const [verticalLineSettingsOpen, setVerticalLineSettingsOpen] = useState(false)
    const [raySettingsOpen, setRaySettingsOpen] = useState(false)

    const lastClickRef = useRef<number>(0)
    const lastClickIdRef = useRef<string | null>(null)

    useEffect(() => {
        if (!v2Sandbox) return

        const handleSelectionChange = ({ drawing, position }: { drawing: any; position: { x: number; y: number } | null }) => {
            setSelectedDrawing(drawing)
            setSelectedDrawingId(drawing ? drawing.id : null)
            selectedDrawingRef.current = drawing
            setToolbarPosition(position)

            if (drawing) {
                // Adapt type for V1 UI
                const toolType = typeof drawing.toolType === 'function' ? drawing.toolType() : drawing.toolType
                const adaptedType = toolType.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase()
                setSelectedDrawingType(adaptedType)
                
                const options = typeof drawing.options === 'function' ? drawing.options() : drawing.options
                setSelectedDrawingOptions(options)
                
                const points = typeof drawing.points === 'function' ? drawing.points() : drawing.points
                setSelectedDrawingPoints(points || [])
                
                setIsDrawingLocked(options.locked?.value || false)
                setIsDrawingHidden(options.hidden?.value || false)

                onSelectionChange?.({ type: adaptedType, id: drawing.id })
            } else {
                onSelectionChange?.(null)
            }
        }

        v2Sandbox.subscribeSelectionChange(handleSelectionChange)

        return () => {
            v2Sandbox.unsubscribeSelectionChange(handleSelectionChange)
        }
    }, [v2Sandbox, onSelectionChange])

    // Sync external selection  
    useEffect(() => {
        if (!selectionProp) {
            deselectDrawing();
            return;
        }
        
        // Check if it's a drawing type
        const isDrawingType = DRAWING_TYPES.includes(selectionProp.type);

        if (isDrawingType && v2Sandbox) {
            if (selectionProp.id !== selectedDrawingId) {
                const tool = v2Sandbox.plugin.getLineTool(selectionProp.id);
                if (tool) {
                    setSelectedDrawingId(selectionProp.id);
                    selectedDrawingRef.current = tool;
                    
                    let options = {};
                    if (typeof tool.options === 'function') {
                        try {
                            options = tool.options();
                        } catch (e) {
                            console.warn('[useDrawingSelection] Failed to call tool.options() in effect:', e);
                        }
                    } else if (tool.options) {
                        options = tool.options;
                    }

                    let tType = typeof tool.toolType === 'function' ? tool.toolType() : (tool.toolType || 'drawing');
                    tType = tType.replace(/([a-z0-9])([A-Z])/g, '$1-$2').toLowerCase();
                    
                    // We need V2OptionAdapter.toV1FlatOptions here or handle it in the hook
                    // For now let's assume raw options are fine or handle the normalization
                    setSelectedDrawingOptions(options); 
                    setSelectedDrawingType(tType);
                }
            }
        } else if (!isDrawingType) {
            deselectDrawing();
        }
    }, [selectionProp, selectedDrawingId, v2Sandbox, DRAWING_TYPES]);

    const handleUpdateDrawing = (updates: any) => {
        if (selectedDrawingId && v2Sandbox) {
            v2Sandbox.updateDrawing(selectedDrawingId, updates)
            // Local state update
            setSelectedDrawingOptions((prev: any) => ({ ...prev, ...updates }))
            if (updates.locked !== undefined) setIsDrawingLocked(updates.locked.value)
            if (updates.hidden !== undefined) setIsDrawingHidden(updates.hidden.value)
        }
    }

    const handleDeleteDrawing = () => {
        if (selectedDrawingId && v2Sandbox) {
            v2Sandbox.deleteDrawing(selectedDrawingId)
            deselectDrawing()
        }
    }

    const deselectDrawing = () => {
        setSelectedDrawing(null)
        setSelectedDrawingId(null)
        selectedDrawingRef.current = null
        setToolbarPosition(null)
        setShowProperties(false)
        onSelectionChange?.(null)
    }

    const deleteSelectedDrawing = () => {
        handleDeleteDrawing()
    }

    return {
        selectedDrawing,
        selectedDrawingId,
        setSelectedDrawingId,
        selectedDrawingRef,
        selectedDrawingType,
        setSelectedDrawingType,
        selectedDrawingOptions,
        setSelectedDrawingOptions,
        selectedDrawingPoints,
        setSelectedDrawingPoints,
        toolbarPosition,
        setToolbarPosition,
        showProperties,
        setShowProperties,
        isDrawingLocked,
        setIsDrawingLocked,
        isDrawingHidden,
        setIsDrawingHidden,
        textSettingsOpen,
        setTextSettingsOpen,
        inlineTextEditing,
        setInlineTextEditing,
        trendLineSettingsOpen,
        setTrendLineSettingsOpen,
        horizontalLineSettingsOpen,
        setHorizontalLineSettingsOpen,
        rectangleSettingsOpen,
        setRectangleSettingsOpen,
        verticalLineSettingsOpen,
        setVerticalLineSettingsOpen,
        raySettingsOpen,
        setRaySettingsOpen,
        lastClickRef,
        lastClickIdRef,
        handleUpdateDrawing,
        handleDeleteDrawing,
        deselectDrawing,
        deleteSelectedDrawing
    }
}
