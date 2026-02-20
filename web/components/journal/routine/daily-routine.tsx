"use client"

import { useState, useEffect } from "react"
import { format } from "date-fns"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Calendar } from "@/components/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { CalendarIcon, Save, Plus, Trash2, Camera, RefreshCw } from "lucide-react"
import { cn } from "@/lib/utils"
import { toast } from "sonner"
import { getDailyContext, upsertAnalysis, upsertRoutine, createWargame, updateWargameOutcome, deleteWargame } from "@/actions/routine-actions"
import { ProfilerView } from "@/components/profiler/profiler-view"
// import { CandleSciencePanel } from "../mission-control/panels/CandleSciencePanel" // Placeholder until fully integrated
import { Badge } from "@/components/ui/badge"

// Types
type Wargame = {
    id: string
    scenario: string
    plan: string
    probability?: string | null
    outcome?: string | null
}

export function DailyRoutine() {
    const [date, setDate] = useState<Date>(new Date())
    const [loading, setLoading] = useState(true)
    
    // Analysis State
    const [sentiment, setSentiment] = useState<string>("NEUTRAL")
    const [bias, setBias] = useState<string>("NONE")
    const [notes, setNotes] = useState("")
    const [keyLevels, setKeyLevels] = useState("")
    const [invalidation, setInvalidation] = useState("")
    
    // Wargame State
    const [wargames, setWargames] = useState<Wargame[]>([])
    const [newScenario, setNewScenario] = useState("")
    const [newPlan, setNewPlan] = useState("")
    const [newProb, setNewProb] = useState("Medium")

    // Routine State
    const [checklist, setChecklist] = useState<Record<string, boolean>>({
        meditate: false,
        review_htf: false,
        check_news: false,
        plan_trades: false,
        journal_end: false
    })
    const [rating, setRating] = useState(5)

    // Snapshots
    const [hasSnapshot, setHasSnapshot] = useState(false)

    useEffect(() => {
        loadData(date)
    }, [date])

    async function loadData(d: Date) {
        setLoading(true)
        try {
            const { analysis, routine } = await getDailyContext(d)
            
            if (analysis) {
                setSentiment(analysis.sentiment || "NEUTRAL")
                setBias(analysis.bias || "NONE")
                setNotes(analysis.notes || "")
                setKeyLevels(analysis.keyLevels || "")
                setInvalidation(analysis.invalidationLevel || "")
                setWargames(analysis.wargames || [])
                setHasSnapshot(!!analysis.profilerSnapshot)
            } else {
                // Reset defaults
                setSentiment("NEUTRAL")
                setBias("NONE")
                setNotes("")
                setKeyLevels("")
                setInvalidation("")
                setWargames([])
                setHasSnapshot(false)
            }

            if (routine) {
                if (routine.checklist) {
                    try {
                        setChecklist(JSON.parse(routine.checklist))
                    } catch (e) { console.error("Failed to parse checklist", e)}
                }
                setRating(routine.rating || 5)
            } else {
                setChecklist({
                    meditate: false,
                    review_htf: false,
                    check_news: false,
                    plan_trades: false,
                    journal_end: false
                })
                setRating(5)
            }

        } catch (error) {
            console.error("Failed to load daily context:", error)
            toast.error("Failed to load data")
        } finally {
            setLoading(false)
        }
    }

    async function handleSaveAnalysis() {
        try {
            await upsertAnalysis({
                date,
                sentiment: sentiment as any,
                bias: bias as any,
                notes,
                keyLevels,
                invalidationLevel: invalidation
            })
            toast.success("Analysis saved")
        } catch (error) {
            toast.error("Failed to save analysis")
        }
    }

    async function handleAddWargame() {
        if (!newScenario || !newPlan) return
        
        // Ensure analysis exists first
        await upsertAnalysis({ date })
        const { analysis } = await getDailyContext(date)
        
        if (analysis) {
            await createWargame(analysis.id, {
                scenario: newScenario,
                plan: newPlan,
                probability: newProb
            })
            setNewScenario("")
            setNewPlan("")
            loadData(date) // Reload to get ID
            toast.success("Scenario added")
        }
    }

    async function handleDeleteWargame(id: string) {
        await deleteWargame(id)
        setWargames(prev => prev.filter(w => w.id !== id))
    }

    async function handleSaveRoutine() {
        try {
            await upsertRoutine({
                date,
                checklist,
                rating,
            })
            toast.success("Routine updated")
        } catch (error) {
            toast.error("Failed to update routine")
        }
    }
    
    async function handleCaptureSnapshot() {
        // In a real implementation, we'd fetch the current state from a global store or ref
        // For now, we'll simulate capturing a timestamp
        const snapshot = {
            timestamp: new Date().toISOString(),
            // Mock data representing Profiler state
            profiler: { bias: "LONG_TRUE", probability: 0.65 }
        }
        
         await upsertAnalysis({
                date,
                profilerSnapshot: JSON.stringify(snapshot)
            })
        setHasSnapshot(true)
        toast.success("Profiler Snapshot Captured")
    }

    return (
        <div className="flex flex-col h-full space-y-4 p-4">
            <div className="flex justify-between items-center">
                <div className="flex items-center gap-2">
                    <h2 className="text-2xl font-bold">Daily Routine</h2>
                    <Popover>
                        <PopoverTrigger asChild>
                            <Button variant="outline" className={cn("w-[240px] justify-start text-left font-normal")}>
                                <CalendarIcon className="mr-2 h-4 w-4" />
                                {format(date, "PPP")}
                            </Button>
                        </PopoverTrigger>
                        <PopoverContent className="w-auto p-0" align="start">
                            <Calendar
                                mode="single"
                                selected={date}
                                onSelect={(d) => d && setDate(d)}
                                initialFocus
                            />
                        </PopoverContent>
                    </Popover>
                </div>
                <div className="flex items-center gap-2">
                     <Button onClick={handleSaveAnalysis}><Save className="mr-2 h-4 w-4"/> Save All</Button>
                </div>
            </div>

            <Tabs defaultValue="context" className="h-full">
                <TabsList>
                    <TabsTrigger value="context">1. Market Context</TabsTrigger>
                    <TabsTrigger value="wargame">2. Wargaming</TabsTrigger>
                    <TabsTrigger value="review">3. Post-Analysis</TabsTrigger>
                    <TabsTrigger value="routine">Discipline</TabsTrigger>
                </TabsList>

                {/* --- CONTEXT TAB --- */}
                <TabsContent value="context" className="space-y-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 h-full">
                        <Card className="h-full">
                            <CardHeader>
                                <CardTitle>Daily Context</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="grid grid-cols-2 gap-4">
                                    <div className="space-y-2">
                                        <Label>Sentiment</Label>
                                        <Select value={sentiment} onValueChange={setSentiment}>
                                            <SelectTrigger>
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="BULLISH">Bullish</SelectItem>
                                                <SelectItem value="BEARISH">Bearish</SelectItem>
                                                <SelectItem value="NEUTRAL">Neutral</SelectItem>
                                                <SelectItem value="MIXED">Mixed</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                    <div className="space-y-2">
                                        <Label>Bias</Label>
                                        <Select value={bias} onValueChange={setBias}>
                                            <SelectTrigger>
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                <SelectItem value="LONG">Long</SelectItem>
                                                <SelectItem value="SHORT">Short</SelectItem>
                                                <SelectItem value="BOTH">Both</SelectItem>
                                                <SelectItem value="NONE">None</SelectItem>
                                            </SelectContent>
                                        </Select>
                                    </div>
                                </div>
                                <div className="space-y-2">
                                    <Label>Key Levels</Label>
                                    <Textarea 
                                        placeholder="e.g. 18200 Pivot, 18150 Support..." 
                                        value={keyLevels}
                                        onChange={e => setKeyLevels(e.target.value)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>Invalidation Level</Label>
                                    <Input 
                                        placeholder="Price where thesis is wrong..." 
                                        value={invalidation}
                                        onChange={e => setInvalidation(e.target.value)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>Notes / Narrative</Label>
                                    <Textarea 
                                        className="min-h-[200px]" 
                                        placeholder="What is the story of the market today?"
                                        value={notes}
                                        onChange={e => setNotes(e.target.value)}
                                    />
                                </div>
                            </CardContent>
                        </Card>

                        {/* Profiler Integration Side-Panel */}
                        <Card className="h-full flex flex-col">
                            <CardHeader className="flex flex-row items-center justify-between">
                                <CardTitle>Profiler Snapshot</CardTitle>
                                <Button size="sm" variant="outline" onClick={handleCaptureSnapshot}>
                                    <Camera className="mr-2 h-4 w-4" />
                                    {hasSnapshot ? "Update Snapshot" : "Capture State"}
                                </Button>
                            </CardHeader>
                            <CardContent className="flex-1 overflow-auto">
                                <div className="opacity-75 pointer-events-none scale-90 origin-top-left">
                                    {/* Embed simple version or just link */}
                                    <ProfilerView />
                                </div>
                            </CardContent>
                        </Card>
                    </div>
                </TabsContent>

                {/* --- WARGAME TAB --- */}
                <TabsContent value="wargame" className="space-y-4">
                     <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <Card>
                            <CardHeader>
                                <CardTitle>Scenario Builder</CardTitle>
                                <CardDescription>If / Then planning for today's session.</CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="space-y-2">
                                    <Label>IF (Scenario)</Label>
                                    <Textarea 
                                        placeholder="Market accepts above 18250..." 
                                        value={newScenario}
                                        onChange={e => setNewScenario(e.target.value)}
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>THEN (Plan)</Label>
                                    <Textarea 
                                        placeholder="Look for longs targeting 18300..." 
                                        value={newPlan}
                                        onChange={e => setNewPlan(e.target.value)}
                                    />
                                </div>
                                <div className="flex items-center gap-2">
                                     <Select value={newProb} onValueChange={setNewProb}>
                                        <SelectTrigger className="w-[140px]">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="High">High Prob</SelectItem>
                                            <SelectItem value="Medium">Medium Prob</SelectItem>
                                            <SelectItem value="Low">Low Prob</SelectItem>
                                        </SelectContent>
                                    </Select>
                                    <Button onClick={handleAddWargame} className="flex-1">
                                        <Plus className="mr-2 h-4 w-4" /> Add Scenario
                                    </Button>
                                </div>

                                <div className="mt-6 space-y-4">
                                    <h3 className="text-sm font-medium">Active Scenarios</h3>
                                    {wargames.map(wg => (
                                        <div key={wg.id} className="p-3 border rounded-lg bg-card/50 flex justify-between items-start gap-2">
                                            <div className="space-y-1">
                                                <div className="font-semibold text-sm flex items-center gap-2">
                                                    <Badge variant="outline">{wg.probability}</Badge>
                                                    If: {wg.scenario}
                                                </div>
                                                <div className="text-sm text-muted-foreground">
                                                    Then: {wg.plan}
                                                </div>
                                            </div>
                                            <Button size="icon" variant="ghost" className="h-6 w-6 text-red-500" onClick={() => handleDeleteWargame(wg.id)}>
                                                <Trash2 className="h-4 w-4" />
                                            </Button>
                                        </div>
                                    ))}
                                    {wargames.length === 0 && <p className="text-sm text-muted-foreground italic">No scenarios planned yet.</p>}
                                </div>
                            </CardContent>
                        </Card>
                         
                         {/* Candle Science Integration */}
                        <Card>
                            <CardHeader>
                                <CardTitle>Probabilities (Candle Science)</CardTitle>
                            </CardHeader>
                            <CardContent className="flex items-center justify-center h-[300px] border-dashed border-2 rounded">
                                <p className="text-muted-foreground">Candle Science Panel Integration (Coming Soon)</p>
                                {/* <CandleSciencePanel /> */}
                            </CardContent>
                        </Card>
                     </div>
                </TabsContent>

                {/* --- POST ANALYSIS TAB --- */}
                <TabsContent value="review" className="space-y-4">
                     <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <Card>
                            <CardHeader>
                                <CardTitle>Outcomes</CardTitle>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                {wargames.map(wg => (
                                    <div key={wg.id} className="p-4 border rounded space-y-2">
                                        <div className="flex justify-between">
                                            <span className="font-medium">{wg.scenario}</span>
                                            <Badge>{wg.outcome || "Pending"}</Badge>
                                        </div>
                                        <div className="flex gap-2 mt-2">
                                            <Button size="sm" variant="outline" onClick={() => updateWargameOutcome(wg.id, "Played Out")}>Played Out</Button>
                                            <Button size="sm" variant="outline" onClick={() => updateWargameOutcome(wg.id, "Invalidated")}>Invalidated</Button>
                                            <Button size="sm" variant="outline" onClick={() => updateWargameOutcome(wg.id, "Did Not Trigger")}>Did Not Trigger</Button>
                                        </div>
                                    </div>
                                ))}
                            </CardContent>
                        </Card>
                        <Card>
                            <CardHeader><CardTitle>End of Day Review</CardTitle></CardHeader>
                             <CardContent>
                                <Textarea 
                                        className="min-h-[300px]" 
                                        placeholder="What happened? Did you follow the plan? What did you learn?"
                                    />
                             </CardContent>
                        </Card>
                     </div>
                </TabsContent>

                {/* --- ROUTINE TAB --- */}
                <TabsContent value="routine">
                    <Card>
                        <CardHeader>
                            <CardTitle>Daily Checklist</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-4">
                             {Object.entries(checklist).map(([key, val]) => (
                                 <div key={key} className="flex items-center space-x-2">
                                     <Input 
                                        type="checkbox" 
                                        className="h-4 w-4" 
                                        checked={val} 
                                        onChange={e => setChecklist({...checklist, [key]: e.target.checked})} 
                                     />
                                     <Label className="capitalize">{key.replace('_', ' ')}</Label>
                                 </div>
                             ))}
                             
                             <div className="pt-4 border-t">
                                <Label>Discipline Rating (1-10)</Label>
                                <Input 
                                    type="number" 
                                    min={1} 
                                    max={10} 
                                    value={rating} 
                                    onChange={e => setRating(parseInt(e.target.value))} 
                                    className="w-[100px] mt-2"
                                />
                             </div>
                             
                             <Button onClick={handleSaveRoutine} className="w-full mt-4">Log Routine</Button>
                        </CardContent>
                    </Card>
                </TabsContent>

            </Tabs>
        </div>
    )
}
