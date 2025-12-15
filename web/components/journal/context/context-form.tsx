"use client"

import { useState } from "react"
import { saveDailyContext } from "@/actions/context-actions"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { RotateCw, CheckCircle2, Globe } from "lucide-react"

interface ContextFormProps {
    initialNote?: any
}

export function ContextForm({ initialNote }: ContextFormProps) {
    const [bias, setBias] = useState<string>(initialNote?.mood || "")
    const [keyLevels, setKeyLevels] = useState<string>(
        initialNote?.tags ? JSON.parse(initialNote.tags).keyLevels || "" : ""
    )
    const [notes, setNotes] = useState<string>(initialNote?.content || "")
    const [saving, setSaving] = useState(false)
    const [lastSaved, setLastSaved] = useState<Date | null>(initialNote ? new Date(initialNote.updatedAt) : null)

    const handleSave = async () => {
        setSaving(true)
        const result = await saveDailyContext({
            bias: bias as any,
            content: notes,
            keyLevels: keyLevels
        })

        if (result.success) {
            setLastSaved(new Date())
        } else {
            alert("Failed to save context")
        }
        setSaving(false)
    }

    return (
        <Card className="h-full">
            <CardHeader>
                <CardTitle className="flex items-center gap-2">
                    <Globe className="h-5 w-5" />
                    Today's Context
                </CardTitle>
                <CardDescription>
                    Set your daily bias and plan
                    {lastSaved && <span className="ml-2 text-xs">Saved {lastSaved.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>}
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="space-y-2">
                    <Label htmlFor="bias">Daily Bias</Label>
                    <Select value={bias} onValueChange={setBias}>
                        <SelectTrigger id="bias" className={
                            bias === "BULLISH" ? "border-green-500 text-green-600 font-medium" :
                                bias === "BEARISH" ? "border-red-500 text-red-600 font-medium" : ""
                        }>
                            <SelectValue placeholder="Select Bias" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="BULLISH" className="text-green-600 font-medium">🚀 BULLISH</SelectItem>
                            <SelectItem value="BEARISH" className="text-red-600 font-medium">🐻 BEARISH</SelectItem>
                            <SelectItem value="NEUTRAL" className="text-yellow-600 font-medium">⚖️ NEUTRAL</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                <div className="space-y-2">
                    <Label htmlFor="key-levels">Key Levels / Liquidity</Label>
                    <Input
                        id="key-levels"
                        placeholder="e.g. 4800 resistance, 4750 gap fill"
                        value={keyLevels}
                        onChange={(e) => setKeyLevels(e.target.value)}
                    />
                </div>

                <div className="space-y-2">
                    <Label htmlFor="notes">Context Notes</Label>
                    <Textarea
                        id="notes"
                        placeholder="Overnight session highs broken? VIX expanding? News impact?"
                        className="min-h-[120px]"
                        value={notes}
                        onChange={(e) => setNotes(e.target.value)}
                    />
                </div>

                <Button className="w-full" onClick={handleSave} disabled={saving}>
                    {saving ? <RotateCw className="mr-2 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-2 h-4 w-4" />}
                    {saving ? "Saving..." : "Save Daily Context"}
                </Button>
            </CardContent>
        </Card>
    )
}
