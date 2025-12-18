import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { OpeningRangeOptions, RangeDefinition } from "@/lib/charts/indicators/opening-range"
import { Trash2, Plus } from "lucide-react"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"

interface OpeningRangeSettingsViewProps {
    initialOptions: OpeningRangeOptions;
    onChange: (options: Partial<OpeningRangeOptions>) => void;
    ticker?: string;
}

export function OpeningRangeSettingsView({ initialOptions, onChange, ticker = '' }: OpeningRangeSettingsViewProps) {
    if (!initialOptions) return null;

    const options = initialOptions;
    const definitions = options.definitions || [];

    const getDefaultFixedPoints = (t: string) => {
        const cleanTicker = t.toUpperCase();
        if (cleanTicker.includes('NQ')) return 65;
        if (cleanTicker.includes('ES')) return 15;
        if (cleanTicker.includes('GC')) return 45;
        if (cleanTicker.includes('CL')) return 0.60;
        return 10;
    };

    const handleUpdateDefinition = (index: number, key: keyof RangeDefinition, value: any) => {
        const newDefs = [...definitions];
        // Auto-populate logic if switching to fixed
        if (key === 'measuredMoveType' && value === 'fixed' && !newDefs[index].fixedMoveValue) {
            newDefs[index] = {
                ...newDefs[index],
                [key]: value,
                fixedMoveValue: getDefaultFixedPoints(ticker)
            };
        } else {
            newDefs[index] = { ...newDefs[index], [key]: value };
        }
        onChange({ definitions: newDefs });
    };

    const handleAddDefinition = () => {
        if (definitions.length >= 4) return;
        const newDef: RangeDefinition = {
            id: `range-${Date.now()}`,
            startTime: "10:00",
            durationMinutes: 30,
            extend: true,
            extendUntil: "16:00",
            lineColor: "#FF6D00",
            lineWidth: 2,
            fillColor: "#FF6D00",
            fillOpacity: 0.3
        };
        onChange({ definitions: [...definitions, newDef] });
    };

    const handleRemoveDefinition = (index: number) => {
        const newDefs = definitions.filter((_, i) => i !== index);
        onChange({ definitions: newDefs });
    };

    // Helper for global option updates
    const updateGlobal = (key: keyof OpeningRangeOptions, value: any) => {
        onChange({ [key]: value });
    };

    return (
        <div className="flex flex-col h-full min-h-0">
            {/* Scrollable Content Area */}
            <div className="flex-1 overflow-y-auto scrollbar-minimal px-6 py-4 space-y-6">

                {/* SECTION: History Scope */}
                <section className="space-y-3">
                    <h3 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">History Settings</h3>
                    <div className="grid grid-cols-2 gap-4 items-start bg-muted/30 p-3 rounded-md border">
                        <div className="space-y-1.5">
                            <Label className="text-xs">History Scope</Label>
                            <Select
                                value={options.showHistory || 'all'}
                                onValueChange={(val) => updateGlobal('showHistory', val)}
                            >
                                <SelectTrigger className="h-8 text-xs">
                                    <SelectValue placeholder="Scope" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="all">Show All</SelectItem>
                                    <SelectItem value="last-n">Last N Boxes</SelectItem>
                                    <SelectItem value="since-date">Since Date</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        {options.showHistory === 'last-n' && (
                            <div className="space-y-1.5">
                                <Label className="text-xs">Count</Label>
                                <Input
                                    type="number"
                                    className="h-8 text-xs"
                                    value={options.historyCount || 5}
                                    onChange={(e) => updateGlobal('historyCount', parseInt(e.target.value))}
                                    min="1"
                                />
                            </div>
                        )}
                        {options.showHistory === 'since-date' && (
                            <div className="space-y-1.5">
                                <Label className="text-xs">Start Date</Label>
                                <Input
                                    type="date"
                                    className="h-8 text-xs"
                                    value={options.historyStartDate || ""}
                                    onChange={(e) => updateGlobal('historyStartDate', e.target.value)}
                                />
                            </div>
                        )}
                    </div>
                </section>

                <Separator />

                {/* SECTION: Definitions */}
                <section className="space-y-3">
                    <div className="flex items-center justify-between">
                        <h3 className="text-xs font-semibold uppercase text-muted-foreground tracking-wider">
                            Ranges ({definitions.length}/4)
                        </h3>
                        <Button
                            variant="secondary"
                            size="sm"
                            className="h-7 text-xs px-2"
                            onClick={handleAddDefinition}
                            disabled={definitions.length >= 4}
                        >
                            <Plus className="w-3.5 h-3.5 mr-1" /> Add Range
                        </Button>
                    </div>

                    <div className="space-y-4">
                        {definitions.map((def, idx) => (
                            <div key={def.id || idx} className="border rounded-md bg-card shadow-sm overflow-hidden flex">
                                {/* Color Stripe */}
                                <div className="w-1.5 shrink-0" style={{ backgroundColor: def.lineColor }} />

                                <div className="flex-1 p-3 space-y-3">
                                    {/* Row 1: Time & Duration header */}
                                    <div className="flex items-start justify-between gap-4">
                                        <div className="flex gap-4">
                                            <div className="space-y-1">
                                                <Label className="text-[10px] text-muted-foreground uppercase">Start</Label>
                                                <Input
                                                    type="time"
                                                    className="h-8 w-28 text-xs font-mono"
                                                    value={def.startTime}
                                                    onChange={(e) => handleUpdateDefinition(idx, 'startTime', e.target.value)}
                                                />
                                            </div>
                                            <div className="space-y-1">
                                                <Label className="text-[10px] text-muted-foreground uppercase">Duration (m)</Label>
                                                <Input
                                                    type="number"
                                                    min="1"
                                                    className="h-8 w-20 text-xs"
                                                    value={def.durationMinutes}
                                                    onChange={(e) => handleUpdateDefinition(idx, 'durationMinutes', parseInt(e.target.value))}
                                                />
                                            </div>
                                        </div>
                                        <Button
                                            variant="ghost"
                                            size="icon"
                                            className="h-6 w-6 text-muted-foreground hover:text-destructive shrink-0"
                                            onClick={() => handleRemoveDefinition(idx)}
                                            title="Remove Range"
                                        >
                                            <Trash2 className="w-3.5 h-3.5" />
                                        </Button>
                                    </div>

                                    {/* Row 2: Logic (Context) */}
                                    <div className="flex items-center gap-6 bg-muted/20 p-2 rounded border border-dashed border-border/50">
                                        <div className="flex items-center gap-2">
                                            <Switch
                                                className="scale-75 origin-left"
                                                checked={def.extend}
                                                onCheckedChange={(v) => handleUpdateDefinition(idx, 'extend', v)}
                                            />
                                            <Label className="text-xs">Extend</Label>
                                        </div>
                                        {def.extend && (
                                            <div className="flex items-center gap-2">
                                                <Label className="text-xs text-muted-foreground">Until</Label>
                                                <Input
                                                    type="time"
                                                    className="h-7 w-24 text-xs font-mono bg-background"
                                                    value={def.extendUntil || "16:00"}
                                                    onChange={(e) => handleUpdateDefinition(idx, 'extendUntil', e.target.value)}
                                                />
                                            </div>
                                        )}
                                    </div>

                                    {/* Row 3: Moves Config */}
                                    <div className="grid grid-cols-[auto_1fr] gap-4">
                                        <div className="space-y-1">
                                            <Label className="text-[10px] text-muted-foreground uppercase">Moves</Label>
                                            <div className="flex items-center gap-2">
                                                <Select
                                                    value={def.measuredMoveType || 'deviation'}
                                                    onValueChange={(v) => handleUpdateDefinition(idx, 'measuredMoveType', v)}
                                                >
                                                    <SelectTrigger className="h-8 w-24 text-xs">
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        <SelectItem value="deviation">Std Dev</SelectItem>
                                                        <SelectItem value="fixed">Fixed</SelectItem>
                                                    </SelectContent>
                                                </Select>

                                                <Select
                                                    value={def.measuredMoveStyle || 'dashed'}
                                                    onValueChange={(v) => handleUpdateDefinition(idx, 'measuredMoveStyle', v)}
                                                >
                                                    <SelectTrigger className="h-8 w-24 text-xs">
                                                        <SelectValue />
                                                    </SelectTrigger>
                                                    <SelectContent>
                                                        <SelectItem value="solid">Solid</SelectItem>
                                                        <SelectItem value="dashed">Dashed</SelectItem>
                                                        <SelectItem value="dotted">Dotted</SelectItem>
                                                    </SelectContent>
                                                </Select>
                                            </div>
                                        </div>

                                        <div className="flex gap-2 items-end">
                                            <div className="space-y-1">
                                                <Label className="text-[10px] text-muted-foreground">Count</Label>
                                                <Input
                                                    type="number"
                                                    className="h-8 w-14 text-xs"
                                                    placeholder="#"
                                                    min="0"
                                                    value={def.measuredMoveCount ?? 0}
                                                    onChange={(e) => handleUpdateDefinition(idx, 'measuredMoveCount', parseInt(e.target.value) || 0)}
                                                />
                                            </div>

                                            {def.measuredMoveType === 'fixed' && (
                                                <div className="space-y-1">
                                                    <Label className="text-[10px] text-muted-foreground">Pts</Label>
                                                    <Input
                                                        type="number"
                                                        className="h-8 w-16 text-xs"
                                                        placeholder="Pts"
                                                        step={def.fixedMoveValue && def.fixedMoveValue < 1 ? "0.01" : "1"}
                                                        value={def.fixedMoveValue ?? 10}
                                                        onChange={(e) => handleUpdateDefinition(idx, 'fixedMoveValue', parseFloat(e.target.value) || 0)}
                                                    />
                                                </div>
                                            )}

                                            <div className="space-y-1">
                                                <Label className="text-[10px] text-muted-foreground">Color</Label>
                                                <div className="h-8 w-8 rounded overflow-hidden border">
                                                    <Input
                                                        type="color"
                                                        className="w-[150%] h-[150%] -top-1/4 -left-1/4 absolute p-0 border-0 cursor-pointer relative"
                                                        value={def.measuredMoveColor || "#FF9800"}
                                                        onChange={(e) => handleUpdateDefinition(idx, 'measuredMoveColor', e.target.value)}
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Vis Props Bottom Bar */}
                                    <div className="flex items-center gap-6 pt-2 border-t text-xs">
                                        <div className="flex items-center gap-2">
                                            <span className="text-muted-foreground">Main Line:</span>
                                            <input type="color" className="w-4 h-4 rounded border-0 p-0" value={def.lineColor} onChange={e => handleUpdateDefinition(idx, 'lineColor', e.target.value)} title="Main Line Color" aria-label="Main Line Color" />
                                            <Input
                                                type="number"
                                                className="h-6 w-12 text-xs px-1"
                                                value={def.lineWidth}
                                                onChange={e => handleUpdateDefinition(idx, 'lineWidth', parseInt(e.target.value))}
                                            />
                                            <span className="text-muted-foreground text-[10px]">px</span>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="text-muted-foreground">Fill:</span>
                                            <input type="color" className="w-4 h-4 rounded border-0 p-0" value={def.fillColor} onChange={e => handleUpdateDefinition(idx, 'fillColor', e.target.value)} title="Fill Color" aria-label="Fill Color" />
                                            <Input
                                                type="number"
                                                className="h-6 w-12 text-xs px-1"
                                                step="0.1"
                                                max="1"
                                                value={def.fillOpacity}
                                                onChange={e => handleUpdateDefinition(idx, 'fillOpacity', parseFloat(e.target.value))}
                                            />
                                            <span className="text-muted-foreground text-[10px]">opacity</span>
                                        </div>
                                    </div>

                                </div>
                            </div>
                        ))}

                        {definitions.length === 0 && (
                            <div className="text-center py-12 text-muted-foreground border-2 border-dashed rounded-md bg-muted/10">
                                <p>No ranges defined.</p>
                                <Button variant="link" onClick={handleAddDefinition} size="sm" className="mt-2">
                                    + Add your first range
                                </Button>
                            </div>
                        )}
                    </div>
                </section>
            </div>
        </div >
    );
}

