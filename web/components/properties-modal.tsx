import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { useState, useEffect } from "react"
import { Bold, Italic, AlignLeft, AlignCenter, AlignRight, AlignVerticalJustifyCenter, ArrowUpToLine, ArrowDownToLine, Save, Star, Trash2 } from "lucide-react"
import { TemplateManager } from "@/lib/template-manager"
import { toast } from "sonner"
import { FibonacciSettingsView } from "./drawing-settings/fibonacci-settings-view"
import { FibonacciOptions } from "@/lib/charts/plugins/fibonacci"

interface PropertiesModalProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    drawingType: string;
    initialOptions: any;
    onSave: (options: any) => void;
}

// Helper to convert Hex + Alpha (0-1) to RGBA string
const hexToRgba = (hex: string, alpha: number) => {
    let c: any;
    if (/^#([A-Fa-f0-9]{3}){1,2}$/.test(hex)) {
        c = hex.substring(1).split('');
        if (c.length === 3) {
            c = [c[0], c[0], c[1], c[1], c[2], c[2]];
        }
        c = '0x' + c.join('');
        return 'rgba(' + [(c >> 16) & 255, (c >> 8) & 255, c & 255].join(',') + ',' + alpha + ')';
    }
    return hex;
}

// Helper to parse RGBA/Hex to Hex + Alpha
const parseColor = (color: string) => {
    if (!color) return { hex: '#000000', alpha: 1 };
    if (color.startsWith('#')) return { hex: color, alpha: 1 };
    if (color.startsWith('rgba')) {
        const parts = color.match(/[\d.]+/g);
        if (parts && parts.length >= 4) {
            const r = parseInt(parts[0]).toString(16).padStart(2, '0');
            const g = parseInt(parts[1]).toString(16).padStart(2, '0');
            const b = parseInt(parts[2]).toString(16).padStart(2, '0');
            return { hex: `#${r}${g}${b}`, alpha: parseFloat(parts[3]) };
        }
    }
    return { hex: '#000000', alpha: 1 };
}

export function PropertiesModal({ open, onOpenChange, drawingType, initialOptions, onSave }: PropertiesModalProps) {
    const [options, setOptions] = useState(initialOptions || {});
    // Local state for color inputs to handle hex/alpha split
    const [lineColorState, setLineColorState] = useState({ hex: '#000000', alpha: 1 });
    const [fillColorState, setFillColorState] = useState({ hex: '#000000', alpha: 1 });
    const [textColorState, setTextColorState] = useState({ hex: '#000000', alpha: 1 });

    // Specific state for Fib options if type is 'fibonacci'
    const [fibOptions, setFibOptions] = useState<FibonacciOptions | null>(null);

    useEffect(() => {
        const opts = initialOptions || {};
        setOptions(opts);
        if (drawingType === 'fibonacci') {
            setFibOptions(opts as FibonacciOptions);
        }

        if (opts.lineColor) setLineColorState(parseColor(opts.lineColor));
        else if (opts.color) setLineColorState(parseColor(opts.color));

        if (opts.fillColor) setFillColorState(parseColor(opts.fillColor));

        if (opts.textColor) setTextColorState(parseColor(opts.textColor));
        // Fallback for TextLabel which might use 'color' if it's just a label tool, but usually it's 'textColor' in complex shapes
    }, [initialOptions, open, drawingType]);

    const handleSave = () => {
        let finalOptions;

        if (drawingType === 'fibonacci' && fibOptions) {
            finalOptions = fibOptions;
        } else {
            // Construct final options with RGBA colors for generic tools
            finalOptions = {
                ...options,
                lineColor: hexToRgba(lineColorState.hex, lineColorState.alpha),
                color: hexToRgba(lineColorState.hex, lineColorState.alpha), // Sync both for compatibility
                fillColor: options.fillColor ? hexToRgba(fillColorState.hex, fillColorState.alpha) : undefined,
                textColor: hexToRgba(textColorState.hex, textColorState.alpha)
            };
        }

        onSave(finalOptions);
        onOpenChange(false);
    };

    const handleChange = (key: string, value: any) => {
        setOptions((prev: any) => ({ ...prev, [key]: value }));
    };

    // Template management state
    const [templates, setTemplates] = useState<any[]>([]);
    const [selectedTemplate, setSelectedTemplate] = useState<string>("");
    const [newTemplateName, setNewTemplateName] = useState("");
    const [showSaveDialog, setShowSaveDialog] = useState(false);

    // Load templates on mount
    useEffect(() => {
        const loadedTemplates = TemplateManager.getTemplates(drawingType);
        setTemplates(loadedTemplates);
    }, [drawingType, open]);

    const handleLoadTemplate = (templateName: string) => {
        const template = TemplateManager.getTemplate(drawingType, templateName);
        if (template) {
            const tOps = template.options;
            setOptions(tOps);
            if (drawingType === 'fibonacci') {
                setFibOptions(tOps as FibonacciOptions);
            }
            if (tOps.lineColor) setLineColorState(parseColor(tOps.lineColor));
            if (tOps.fillColor) setFillColorState(parseColor(tOps.fillColor));
            if (tOps.textColor) setTextColorState(parseColor(tOps.textColor));
            setSelectedTemplate(templateName);
            toast.success(`Template "${templateName}" loaded`);
        }
    };

    const handleSaveTemplate = () => {
        if (!newTemplateName.trim()) {
            toast.error("Please enter a template name");
            return;
        }
        let currentOptions;
        if (drawingType === 'fibonacci' && fibOptions) {
            currentOptions = fibOptions;
        } else {
            currentOptions = {
                ...options,
                lineColor: hexToRgba(lineColorState.hex, lineColorState.alpha),
                fillColor: options.fillColor ? hexToRgba(fillColorState.hex, fillColorState.alpha) : undefined,
                textColor: hexToRgba(textColorState.hex, textColorState.alpha)
            };
        }
        TemplateManager.saveTemplate(newTemplateName, drawingType, currentOptions);
        toast.success(`Template "${newTemplateName}" saved`);
        setTemplates(TemplateManager.getTemplates(drawingType));
        setNewTemplateName("");
        setShowSaveDialog(false);
    };

    const handleSetDefault = () => {
        let currentOptions;
        if (drawingType === 'fibonacci' && fibOptions) {
            currentOptions = fibOptions;
        } else {
            currentOptions = {
                ...options,
                lineColor: hexToRgba(lineColorState.hex, lineColorState.alpha),
                fillColor: options.fillColor ? hexToRgba(fillColorState.hex, fillColorState.alpha) : undefined,
                textColor: hexToRgba(textColorState.hex, textColorState.alpha)
            };
        }
        TemplateManager.saveDefault(drawingType, currentOptions);
        toast.success("Saved as default");
    };

    const handleDeleteTemplate = (templateName: string) => {
        TemplateManager.deleteTemplate(drawingType, templateName);
        toast.success(`Template "${templateName}" deleted`);
        setTemplates(TemplateManager.getTemplates(drawingType));
        if (selectedTemplate === templateName) setSelectedTemplate("");
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[500px]">
                <DialogHeader>
                    <DialogTitle>{drawingType === 'fibonacci' ? 'Fib Retracement' : `${drawingType} Properties`}</DialogTitle>
                    <DialogDescription>
                        Modify the properties of the selected {drawingType.toLowerCase()}.
                    </DialogDescription>
                </DialogHeader>

                {drawingType === 'fibonacci' && fibOptions ? (
                    <FibonacciSettingsView options={fibOptions} onChange={setFibOptions} />
                ) : (
                    <Tabs defaultValue="style" className="w-full">
                        <TabsList className="grid w-full grid-cols-3">
                            <TabsTrigger value="style">Style</TabsTrigger>
                            <TabsTrigger value="text">Text</TabsTrigger>
                            <TabsTrigger value="coords">Coordinates</TabsTrigger>
                        </TabsList>

                        {/* STYLE TAB */}
                        <TabsContent value="style" className="space-y-6 py-4">
                            <div className="space-y-4">
                                <Label>Line Style</Label>
                                <div className="grid grid-cols-4 items-center gap-4">
                                    <Label className="text-right text-xs">Style</Label>
                                    <Select
                                        value={options.lineStyle?.toString() || "0"}
                                        onValueChange={(val) => handleChange('lineStyle', parseInt(val))}
                                    >
                                        <SelectTrigger className="col-span-3 h-8" aria-label="Line Style">
                                            <SelectValue placeholder="Select style" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="0">Solid</SelectItem>
                                            <SelectItem value="1">Dotted</SelectItem>
                                            <SelectItem value="2">Dashed</SelectItem>
                                            <SelectItem value="3">Large Dashed</SelectItem>
                                            <SelectItem value="4">Sparse Dotted</SelectItem>
                                        </SelectContent>
                                    </Select>

                                    <Label htmlFor="lineColor" className="text-right text-xs">Color</Label>
                                    <div className="col-span-3 flex items-center gap-2">
                                        <Input
                                            id="lineColor"
                                            type="color"
                                            value={lineColorState.hex}
                                            onChange={(e) => setLineColorState(p => ({ ...p, hex: e.target.value }))}
                                            className="w-12 h-8 p-1"
                                        />
                                        <div className="flex-1 flex items-center gap-2">
                                            <span className="text-xs text-muted-foreground">Opacity</span>
                                            <input
                                                type="range"
                                                min="0"
                                                max="1"
                                                step="0.1"
                                                value={lineColorState.alpha}
                                                onChange={(e) => setLineColorState(p => ({ ...p, alpha: parseFloat(e.target.value) }))}
                                                title="Opacity"
                                                aria-label="Line Opacity"
                                                className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer"
                                            />
                                            <span className="text-xs w-8 text-right">{Math.round(lineColorState.alpha * 100)}%</span>
                                        </div>
                                    </div>
                                </div>

                                <div className="grid grid-cols-4 items-center gap-4">
                                    <Label htmlFor="lineWidth" className="text-right text-xs">Width</Label>
                                    <Input
                                        id="lineWidth"
                                        type="number"
                                        min="1"
                                        max="10"
                                        value={options.lineWidth || options.width || 1}
                                        onChange={(e) => {
                                            const val = parseInt(e.target.value);
                                            handleChange('lineWidth', val);
                                            handleChange('width', val);
                                        }}
                                        className="col-span-3"
                                    />
                                </div>
                            </div>

                            {(options.fillColor !== undefined) && (
                                <div className="space-y-4 pt-4 border-t">
                                    <Label>Fill & Border</Label>
                                    <div className="grid grid-cols-4 items-center gap-4">
                                        <Label htmlFor="fillColor" className="text-right text-xs">Fill</Label>
                                        <div className="col-span-3 flex items-center gap-2">
                                            <Input
                                                id="fillColor"
                                                type="color"
                                                value={fillColorState.hex}
                                                onChange={(e) => setFillColorState(p => ({ ...p, hex: e.target.value }))}
                                                className="w-12 h-8 p-1"
                                            />
                                            <div className="flex-1 flex items-center gap-2">
                                                <span className="text-xs text-muted-foreground">Opacity</span>
                                                <input
                                                    type="range"
                                                    min="0"
                                                    max="1"
                                                    step="0.1"
                                                    value={fillColorState.alpha}
                                                    onChange={(e) => setFillColorState(p => ({ ...p, alpha: parseFloat(e.target.value) }))}
                                                    title="Fill Opacity"
                                                    aria-label="Fill Opacity"
                                                    className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer"
                                                />
                                                <span className="text-xs w-8 text-right">{Math.round(fillColorState.alpha * 100)}%</span>
                                            </div>
                                        </div>
                                    </div>
                                    {drawingType === 'rectangle' && (
                                        <>
                                            <div className="grid grid-cols-4 items-center gap-4">
                                                <Label htmlFor="borderColor" className="text-right text-xs">Border</Label>
                                                <div className="col-span-3 flex items-center gap-2">
                                                    <Input
                                                        id="borderColor"
                                                        type="color"
                                                        value={options.borderColor || '#2962FF'}
                                                        onChange={(e) => handleChange('borderColor', e.target.value)}
                                                        className="w-12 h-8 p-1"
                                                    />
                                                    <Input
                                                        type="number"
                                                        min="0"
                                                        max="10"
                                                        value={options.borderWidth || 0}
                                                        onChange={(e) => handleChange('borderWidth', parseInt(e.target.value))}
                                                        className="w-20"
                                                        placeholder="Width"
                                                        title="Border Width"
                                                        aria-label="Border Width"
                                                    />
                                                </div>
                                            </div>

                                            <div className="grid grid-cols-4 gap-4">
                                                <Label className="text-right text-xs pt-2">Extend</Label>
                                                <div className="col-span-3 flex gap-4">
                                                    <div className="flex items-center space-x-2">
                                                        <input type="checkbox" id="extLeft" checked={options.extendLeft} onChange={(e) => handleChange('extendLeft', e.target.checked)} />
                                                        <Label htmlFor="extLeft" className="text-xs">Left</Label>
                                                    </div>
                                                    <div className="flex items-center space-x-2">
                                                        <input type="checkbox" id="extRight" checked={options.extendRight} onChange={(e) => handleChange('extendRight', e.target.checked)} />
                                                        <Label htmlFor="extRight" className="text-xs">Right</Label>
                                                    </div>
                                                </div>
                                            </div>

                                            <div className="grid grid-cols-4 gap-4 pt-2 border-t">
                                                <Label className="text-right text-xs pt-2">Internal</Label>
                                                <div className="col-span-3 space-y-2">
                                                    <div className="flex items-center gap-2">
                                                        <input
                                                            type="checkbox"
                                                            checked={options.midline?.visible}
                                                            onChange={(e) => handleChange('midline', { ...options.midline, visible: e.target.checked })}
                                                            title="Midline Visibility"
                                                            aria-label="Midline Visibility"
                                                        />
                                                        <span className="text-xs w-16">Midline</span>
                                                        <Input type="color" title="Midline Color" aria-label="Midline Color" value={options.midline?.color || '#2962FF'} onChange={(e) => handleChange('midline', { ...options.midline, color: e.target.value })} className="w-8 h-6 p-0" />
                                                        <select
                                                            className="h-6 text-xs border rounded"
                                                            value={options.midline?.width || 1}
                                                            onChange={(e) => handleChange('midline', { ...options.midline, width: parseInt(e.target.value) })}
                                                            title="Midline Width"
                                                            aria-label="Midline Width"
                                                        >
                                                            {[1, 2, 3, 4].map(w => <option key={w} value={w}>{w}px</option>)}
                                                        </select>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <input
                                                            type="checkbox"
                                                            checked={options.quarterLines?.visible}
                                                            onChange={(e) => handleChange('quarterLines', { ...options.quarterLines, visible: e.target.checked })}
                                                            title="Quarters Visibility"
                                                            aria-label="Quarters Visibility"
                                                        />
                                                        <span className="text-xs w-16">Quarters</span>
                                                        <Input type="color" title="Quarters Color" aria-label="Quarters Color" value={options.quarterLines?.color || '#2962FF'} onChange={(e) => handleChange('quarterLines', { ...options.quarterLines, color: e.target.value })} className="w-8 h-6 p-0" />
                                                    </div>
                                                </div>
                                            </div>
                                        </>
                                    )}
                                </div>
                            )}
                        </TabsContent>

                        {/* TEXT TAB */}
                        <TabsContent value="text" className="space-y-6 py-4">
                            <div className="flex items-center space-x-2">
                                <input
                                    type="checkbox"
                                    id="showText"
                                    checked={(options.showLabels !== undefined ? options.showLabels : options.showLabel) !== false && options.visible !== false}
                                    onChange={(e) => {
                                        handleChange('showLabels', e.target.checked);
                                        handleChange('showLabel', e.target.checked);
                                        handleChange('visible', e.target.checked);
                                    }}
                                    className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                                />
                                <Label htmlFor="showText">Show Text</Label>
                            </div>

                            <div className="space-y-4 pt-4 border-t">
                                <div className="flex items-center space-x-2">
                                    <input
                                        type="checkbox"
                                        id="showBorder"
                                        checked={options.borderVisible === true}
                                        onChange={(e) => handleChange('borderVisible', e.target.checked)}
                                        className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                                    />
                                    <Label htmlFor="showBorder">Show Border</Label>
                                </div>

                                {options.borderVisible && (
                                    <div className="grid grid-cols-2 gap-4 pl-6">
                                        <div className="space-y-2">
                                            <Label className="text-xs">Border Color</Label>
                                            <div className="flex items-center gap-2">
                                                <Input
                                                    type="color"
                                                    value={options.borderColor || '#FFFFFF'}
                                                    onChange={(e) => handleChange('borderColor', e.target.value)}
                                                    className="w-full h-8 p-1"
                                                />
                                            </div>
                                        </div>
                                        <div className="space-y-2">
                                            <Label className="text-xs">Border Width</Label>
                                            <Input
                                                type="number"
                                                min="1"
                                                max="10"
                                                value={options.borderWidth || 1}
                                                onChange={(e) => handleChange('borderWidth', parseInt(e.target.value))}
                                                className="h-8"
                                            />
                                        </div>
                                    </div>
                                )}
                            </div>

                            <div className="space-y-2">
                                <textarea
                                    value={options.text || ''}
                                    onChange={(e) => handleChange('text', e.target.value)}
                                    placeholder="Enter text..."
                                    className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                                />
                            </div>

                            <div className="grid grid-cols-2 gap-4">
                                {/* Color & Opacity */}
                                <div className="space-y-2">
                                    <Label className="text-xs">Color</Label>
                                    <div className="flex items-center gap-2">
                                        <Input
                                            type="color"
                                            value={textColorState.hex}
                                            onChange={(e) => setTextColorState(p => ({ ...p, hex: e.target.value }))}
                                            className="w-10 h-8 p-1"
                                        />
                                        <input
                                            type="range"
                                            min="0"
                                            max="1"
                                            step="0.1"
                                            value={textColorState.alpha}
                                            onChange={(e) => setTextColorState(p => ({ ...p, alpha: parseFloat(e.target.value) }))}
                                            title="Text Opacity"
                                            aria-label="Text Opacity"
                                            className="flex-1 h-2 bg-secondary rounded-lg appearance-none cursor-pointer"
                                        />
                                    </div>
                                </div>

                                {/* Font Size */}
                                <div className="space-y-2">
                                    <Label className="text-xs">Size</Label>
                                    <Select
                                        value={(options.fontSize || 12).toString()}
                                        onValueChange={(val) => handleChange('fontSize', parseInt(val))}
                                    >
                                        <SelectTrigger className="h-8">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            {[10, 12, 14, 16, 20, 24, 28, 32, 40].map(s => (
                                                <SelectItem key={s} value={s.toString()}>{s}px</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>

                            <div className="flex justify-between items-center bg-secondary/20 p-2 rounded-md">
                                {/* Formatting */}
                                <div className="flex gap-1">
                                    <Button
                                        variant={options.bold ? "secondary" : "ghost"}
                                        size="icon"
                                        className="h-8 w-8"
                                        onClick={() => handleChange('bold', !options.bold)}
                                    >
                                        <Bold className="h-4 w-4" />
                                    </Button>
                                    <Button
                                        variant={options.italic ? "secondary" : "ghost"}
                                        size="icon"
                                        className="h-8 w-8"
                                        onClick={() => handleChange('italic', !options.italic)}
                                    >
                                        <Italic className="h-4 w-4" />
                                    </Button>
                                </div>

                                {/* Orientation (for lines) */}
                                {(drawingType === 'trend-line' || drawingType === 'vertical-line') && (
                                    <div className="flex gap-1 border-l pl-2 ml-2">
                                        <Button
                                            variant={options.orientation !== 'along-line' ? "secondary" : "ghost"}
                                            size="sm"
                                            className="h-8 text-xs"
                                            onClick={() => handleChange('orientation', 'horizontal')}
                                            title="Horizontal Text"
                                        >
                                            Horiz
                                        </Button>
                                        <Button
                                            variant={options.orientation === 'along-line' ? "secondary" : "ghost"}
                                            size="sm"
                                            className="h-8 text-xs"
                                            onClick={() => handleChange('orientation', 'along-line')}
                                            title="Along Line"
                                        >
                                            Along
                                        </Button>
                                    </div>
                                )}

                                {/* Alignment */}
                                <div className="flex gap-1 border-l pl-2 ml-2">
                                    {/* Vertical */}
                                    <Button variant={options.alignment?.vertical === 'top' ? "secondary" : "ghost"} size="icon" className="h-8 w-8" onClick={() => handleChange('alignment', { ...options.alignment, vertical: 'top' })} title="Top">
                                        <ArrowUpToLine className="h-4 w-4" />
                                    </Button>
                                    <Button variant={options.alignment?.vertical === 'middle' ? "secondary" : "ghost"} size="icon" className="h-8 w-8" onClick={() => handleChange('alignment', { ...options.alignment, vertical: 'middle' })} title="Middle">
                                        <AlignVerticalJustifyCenter className="h-4 w-4" />
                                    </Button>
                                    <Button variant={options.alignment?.vertical === 'bottom' ? "secondary" : "ghost"} size="icon" className="h-8 w-8" onClick={() => handleChange('alignment', { ...options.alignment, vertical: 'bottom' })} title="Bottom">
                                        <ArrowDownToLine className="h-4 w-4" />
                                    </Button>
                                </div>
                                <div className="flex gap-1 border-l pl-2 ml-2">
                                    {/* Horizontal */}
                                    <Button variant={options.alignment?.horizontal === 'left' ? "secondary" : "ghost"} size="icon" className="h-8 w-8" onClick={() => handleChange('alignment', { ...options.alignment, horizontal: 'left' })} title="Left">
                                        <AlignLeft className="h-4 w-4" />
                                    </Button>
                                    <Button variant={options.alignment?.horizontal === 'center' ? "secondary" : "ghost"} size="icon" className="h-8 w-8" onClick={() => handleChange('alignment', { ...options.alignment, horizontal: 'center' })} title="Center">
                                        <AlignCenter className="h-4 w-4" />
                                    </Button>
                                    <Button variant={options.alignment?.horizontal === 'right' ? "secondary" : "ghost"} size="icon" className="h-8 w-8" onClick={() => handleChange('alignment', { ...options.alignment, horizontal: 'right' })} title="Right">
                                        <AlignRight className="h-4 w-4" />
                                    </Button>
                                </div>
                            </div>
                        </TabsContent>

                        <TabsContent value="coords">
                            <div className="py-4 text-center text-sm text-muted-foreground">
                                Coordinates editing coming soon.
                            </div>
                        </TabsContent>
                    </Tabs>
                )}

                {drawingType === 'anchored-text' && (
                    <div className="border-t pt-4 mt-4">
                        <Label className="mb-2 block">Position Offsets</Label>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-1">
                                <Label className="text-xs">Top</Label>
                                <Input type="number" value={options.topOffset || 0} onChange={(e) => handleChange('topOffset', parseInt(e.target.value))} />
                            </div>
                            <div className="space-y-1">
                                <Label className="text-xs">Bottom</Label>
                                <Input type="number" value={options.bottomOffset || 0} onChange={(e) => handleChange('bottomOffset', parseInt(e.target.value))} />
                            </div>
                            <div className="space-y-1">
                                <Label className="text-xs">Left</Label>
                                <Input type="number" value={options.leftOffset || 0} onChange={(e) => handleChange('leftOffset', parseInt(e.target.value))} />
                            </div>
                            <div className="space-y-1">
                                <Label className="text-xs">Right</Label>
                                <Input type="number" value={options.rightOffset || 0} onChange={(e) => handleChange('rightOffset', parseInt(e.target.value))} />
                            </div>
                        </div>
                    </div>
                )}

                {/* TEMPLATE CONTROLS */}
                <div className="border-t pt-4 space-y-3">
                    <Label className="text-sm font-semibold">Templates</Label>
                    <div className="flex gap-2">
                        <Select value={selectedTemplate} onValueChange={handleLoadTemplate}>
                            <SelectTrigger className="flex-1">
                                <SelectValue placeholder="Load template..." />
                            </SelectTrigger>
                            <SelectContent>
                                {templates.length === 0 ? (
                                    <SelectItem value="_none" disabled>No templates saved</SelectItem>
                                ) : (
                                    templates.map(t => (
                                        <SelectItem key={t.name} value={t.name}>{t.name}</SelectItem>
                                    ))
                                )}
                            </SelectContent>
                        </Select>
                        {selectedTemplate && (
                            <Button
                                variant="ghost"
                                size="icon"
                                onClick={() => handleDeleteTemplate(selectedTemplate)}
                                title="Delete template"
                            >
                                <Trash2 className="h-4 w-4" />
                            </Button>
                        )}
                    </div>

                    {showSaveDialog ? (
                        <div className="flex gap-2">
                            <Input
                                placeholder="Template name..."
                                value={newTemplateName}
                                onChange={(e) => setNewTemplateName(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleSaveTemplate()}
                            />
                            <Button onClick={handleSaveTemplate} size="sm">
                                <Save className="h-4 w-4 mr-1" />
                                Save
                            </Button>
                            <Button variant="ghost" size="sm" onClick={() => setShowSaveDialog(false)}>
                                Cancel
                            </Button>
                        </div>
                    ) : (
                        <div className="flex gap-2">
                            <Button variant="outline" size="sm" onClick={() => setShowSaveDialog(true)} className="flex-1">
                                <Save className="h-4 w-4 mr-1" />
                                Save as Template
                            </Button>
                            <Button variant="outline" size="sm" onClick={handleSetDefault}>
                                <Star className="h-4 w-4 mr-1" />
                                Set as Default
                            </Button>
                        </div>
                    )}
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
                    <Button onClick={handleSave}>Save</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

