import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { OpeningRangeOptions, RangeDefinition } from "@/lib/charts/indicators/opening-range"
import { Badge } from "@/components/ui/badge"
import { Trash2, Plus } from "lucide-react"

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
        <div className="space-y-6">
            {/* Global History Settings */}
            <Card>
                <CardHeader className="py-3">
                    <CardTitle className="text-sm font-medium">History Settings</CardTitle>
                </CardHeader>
                <CardContent className="grid grid-cols-2 gap-4 py-3">
                    <div className="space-y-1">
                        <Label>History Scope</Label>
                        <Select
                            value={options.showHistory || 'all'}
                            onValueChange={(val) => updateGlobal('showHistory', val)}
                        >
                            <SelectTrigger>
                                <SelectValue placeholder="Select history scope" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all">Show All</SelectItem>
                                <SelectItem value="last-n">Last N Boxes</SelectItem>
                                <SelectItem value="since-date">Since Date</SelectItem>
                            </SelectContent>
                        </Select>
                    </div>
                    {options.showHistory === 'last-n' && (
                        <div className="space-y-1">
                            <Label>Count</Label>
                            <Input
                                type="number"
                                value={options.historyCount || 5}
                                onChange={(e) => updateGlobal('historyCount', parseInt(e.target.value))}
                                min="1"
                            />
                        </div>
                    )}
                    {options.showHistory === 'since-date' && (
                        <div className="space-y-1">
                            <Label>Start Date</Label>
                            <Input
                                type="date"
                                value={options.historyStartDate || ""}
                                onChange={(e) => updateGlobal('historyStartDate', e.target.value)}
                            />
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Definitions List */}
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <Label className="text-base font-semibold">Ranges ({definitions.length}/4)</Label>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleAddDefinition}
                        disabled={definitions.length >= 4}
                    >
                        <Plus className="w-4 h-4 mr-1" /> Add Range
                    </Button>
                </div>

                {definitions.map((def, idx) => (
                    <Card key={def.id || idx} className="relative overflow-hidden">
                        <div className="absolute left-0 top-0 bottom-0 w-1" style={{ backgroundColor: def.lineColor }} />
                        <CardContent className="pt-4 space-y-4">
                            <div className="flex justify-between items-start">
                                <div className="grid grid-cols-2 gap-4 w-full pr-8">
                                    <div className="space-y-1">
                                        <Label>Start Time</Label>
                                        <Input
                                            type="time"
                                            value={def.startTime}
                                            onChange={(e) => handleUpdateDefinition(idx, 'startTime', e.target.value)}
                                        />
                                    </div>
                                    <div className="space-y-1">
                                        <Label>Duration (Min)</Label>
                                        <Input
                                            type="number"
                                            min="1"
                                            value={def.durationMinutes}
                                            onChange={(e) => handleUpdateDefinition(idx, 'durationMinutes', parseInt(e.target.value))}
                                        />
                                    </div>
                                </div>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="absolute right-2 top-2 text-muted-foreground hover:text-destructive"
                                    onClick={() => handleRemoveDefinition(idx)}
                                >
                                    <Trash2 className="w-4 h-4" />
                                </Button>
                            </div>

                            <div className="grid grid-cols-3 gap-4 border-t pt-3">
                                <div className="flex items-center gap-2">
                                    <Switch
                                        checked={def.extend}
                                        onCheckedChange={(v) => handleUpdateDefinition(idx, 'extend', v)}
                                    />
                                    <Label className="text-xs">Extend</Label>
                                </div>
                                {def.extend && (
                                    <div className="col-span-2 flex items-center gap-2">
                                        <Label className="text-xs whitespace-nowrap">Until</Label>
                                        <Input
                                            type="time"
                                            className="h-8"
                                            value={def.extendUntil || "16:00"}
                                            onChange={(e) => handleUpdateDefinition(idx, 'extendUntil', e.target.value)}
                                        />
                                    </div>
                                )}
                            </div>

                            <div className="flex flex-col gap-2 border-t mt-3 pt-3">
                                <div className="flex items-center gap-2">
                                    <Label className="text-xs w-20">Moves</Label>
                                    <Select
                                        value={def.measuredMoveType || 'deviation'}
                                        onValueChange={(v) => handleUpdateDefinition(idx, 'measuredMoveType', v)}
                                    >
                                        <SelectTrigger className="h-8 text-xs">
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
                                <div className="flex items-center gap-2 pl-[5.5rem]">
                                    <div className="flex flex-col gap-1">
                                        <Label className="text-[10px] text-muted-foreground">Count</Label>
                                        <Input
                                            type="number"
                                            className="h-8 w-16 text-xs"
                                            placeholder="Count"
                                            min="0"
                                            value={def.measuredMoveCount ?? 0}
                                            onChange={(e) => handleUpdateDefinition(idx, 'measuredMoveCount', parseInt(e.target.value) || 0)}
                                        />
                                    </div>

                                    {def.measuredMoveType === 'fixed' && (
                                        <div className="flex flex-col gap-1">
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

                                    <div className="flex flex-col gap-1">
                                        <Label className="text-[10px] text-muted-foreground">Color</Label>
                                        <Input
                                            type="color"
                                            className="w-8 h-8 p-0 border-0"
                                            value={def.measuredMoveColor || "#FF9800"}
                                            onChange={(e) => handleUpdateDefinition(idx, 'measuredMoveColor', e.target.value)}
                                        />
                                    </div>
                                </div>
                            </div>

                            <div className="flex items-center gap-4 border-t pt-3">
                                <div className="flex items-center gap-2 flex-1">
                                    <Input
                                        type="color"
                                        className="w-8 h-8 p-0 border-0"
                                        value={def.lineColor}
                                        onChange={(e) => handleUpdateDefinition(idx, 'lineColor', e.target.value)}
                                    />
                                    <div className="flex flex-col">
                                        <Label className="text-xs">Line</Label>
                                        <Input
                                            type="number"
                                            className="h-6 w-12 text-xs p-1"
                                            value={def.lineWidth}
                                            onChange={(e) => handleUpdateDefinition(idx, 'lineWidth', parseInt(e.target.value))}
                                        />
                                    </div>
                                </div>
                                <div className="flex items-center gap-2 flex-1">
                                    <Input
                                        type="color"
                                        className="w-8 h-8 p-0 border-0"
                                        value={def.fillColor}
                                        onChange={(e) => handleUpdateDefinition(idx, 'fillColor', e.target.value)}
                                    />
                                    <div className="flex flex-col">
                                        <Label className="text-xs">Opacity</Label>
                                        <Input
                                            type="number"
                                            step="0.1"
                                            max="1"
                                            className="h-6 w-12 text-xs p-1"
                                            value={def.fillOpacity}
                                            onChange={(e) => handleUpdateDefinition(idx, 'fillOpacity', parseFloat(e.target.value))}
                                        />
                                    </div>
                                </div>
                            </div>
                        </CardContent>
                    </Card>
                ))}

                {definitions.length === 0 && (
                    <div className="text-center py-8 text-muted-foreground border-2 border-dashed rounded-md">
                        No ranges defined. Add one to start.
                    </div>
                )}
            </div>
        </div >
    );
}
