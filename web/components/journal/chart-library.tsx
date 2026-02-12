"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import { ScrollArea } from "@/components/ui/scroll-area"
import { getCharts, saveChart } from "@/actions/routine-actions"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Image as ImageIcon, Grid, List as ListIcon, Maximize2, Trash2 } from "lucide-react"
import { toast } from "sonner"

export function ChartLibrary() {
    const [charts, setCharts] = useState<any[]>([])
    const [loading, setLoading] = useState(true)
    const [viewMode, setViewMode] = useState<"grid" | "scroll">("grid")
    const [filterTag, setFilterTag] = useState("")
    
    // Upload State
    const [pasteUrl, setPasteUrl] = useState("")
    const [pasteTags, setPasteTags] = useState("")

    useEffect(() => {
        loadCharts()
    }, [filterTag])

    async function loadCharts() {
        setLoading(true)
        try {
            const data = await getCharts({ tag: filterTag || undefined })
            setCharts(data)
        } catch (error) {
            console.error(error)
        } finally {
            setLoading(false)
        }
    }

    async function handleSaveChart() {
        if (!pasteUrl) return
        try {
            await saveChart({
                url: pasteUrl,
                type: "MANUAL",
                tags: pasteTags.split(",").map(t => t.trim()).filter(Boolean)
            })
            setPasteUrl("")
            setPasteTags("")
            loadCharts()
            toast.success("Chart saved")
        } catch (error) {
            toast.error("Failed to save chart")
        }
    }

    return (
        <div className="flex flex-col h-full space-y-4">
            <div className="flex justify-between items-center bg-card p-4 rounded-lg border">
                <div className="flex items-center gap-4">
                    <h2 className="text-lg font-semibold flex items-center gap-2">
                        <ImageIcon className="h-5 w-5" /> Chart Library
                    </h2>
                    <div className="flex bg-muted rounded-md p-1">
                        <Button 
                            variant={viewMode === "grid" ? "secondary" : "ghost"} 
                            size="sm" 
                            onClick={() => setViewMode("grid")}
                        >
                            <Grid className="h-4 w-4" />
                        </Button>
                        <Button 
                            variant={viewMode === "scroll" ? "secondary" : "ghost"} 
                            size="sm" 
                            onClick={() => setViewMode("scroll")}
                        >
                            <ListIcon className="h-4 w-4" />
                        </Button>
                    </div>
                    <Input 
                        placeholder="Filter by tag..." 
                        className="w-[200px] h-8"
                        value={filterTag}
                        onChange={e => setFilterTag(e.target.value)}
                    />
                </div>
                
                <Dialog>
                    <DialogTrigger asChild>
                        <Button size="sm">Add Chart</Button>
                    </DialogTrigger>
                    <DialogContent>
                        <DialogHeader>
                            <DialogTitle>Add Chart</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4 py-4">
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Image URL / Link</label>
                                <Input 
                                    placeholder="https://tradingview.com/x/..." 
                                    value={pasteUrl}
                                    onChange={e => setPasteUrl(e.target.value)}
                                />
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-medium">Tags (comma separated)</label>
                                <Input 
                                    placeholder="ES, Long, Setup A..." 
                                    value={pasteTags}
                                    onChange={e => setPasteTags(e.target.value)}
                                />
                            </div>
                            <Button onClick={handleSaveChart} className="w-full">Save to Library</Button>
                        </div>
                    </DialogContent>
                </Dialog>
            </div>

            <ScrollArea className="flex-1 h-[600px] rounded-md border p-4">
                {viewMode === "grid" ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {charts.map(chart => (
                            <Card key={chart.id} className="overflow-hidden group relative">
                                <div className="aspect-video bg-muted relative">
                                    {/* Handle real images vs plain links */}
                                    <img 
                                        src={chart.url} 
                                        alt="Chart" 
                                        className="object-cover w-full h-full text-xs text-muted-foreground flex items-center justify-center"
                                        onError={(e) => {
                                            (e.target as HTMLImageElement).style.display = 'none';
                                            (e.target as HTMLImageElement).nextElementSibling?.classList.remove('hidden');
                                        }}
                                    />
                                    <div className="hidden absolute inset-0 flex items-center justify-center p-4 text-center">
                                        <a href={chart.url} target="_blank" rel="noopener noreferrer" className="text-blue-500 underline break-all text-sm">
                                            {chart.url}
                                        </a>
                                    </div>
                                    <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <Button size="icon" variant="secondary" className="h-8 w-8" onClick={() => window.open(chart.url, '_blank')}>
                                            <Maximize2 className="h-4 w-4" />
                                        </Button>
                                    </div>
                                </div>
                                <div className="p-3">
                                    <div className="flex flex-wrap gap-1 mt-1">
                                        {chart.tags?.split(",").map((tag: string) => (
                                            <Badge key={tag} variant="secondary" className="text-xs px-1">{tag}</Badge>
                                        ))}
                                    </div>
                                    <div className="text-xs text-muted-foreground mt-2">
                                        {new Date(chart.createdAt).toLocaleDateString()}
                                    </div>
                                </div>
                            </Card>
                        ))}
                    </div>
                ) : (
                    <div className="space-y-8 max-w-3xl mx-auto">
                        {/* Scroll / Photo Frame Mode */}
                        {charts.map(chart => (
                            <div key={chart.id} className="space-y-2">
                                <div className="flex justify-between items-center text-sm text-muted-foreground px-1">
                                    <span>{new Date(chart.createdAt).toLocaleDateString()}</span>
                                    <div className="flex gap-2">
                                         {chart.tags?.split(",").map((tag: string) => (
                                            <span key={tag}>#{tag}</span>
                                        ))}
                                    </div>
                                </div>
                                <div className="border rounded-lg overflow-hidden bg-card shadow-sm">
                                     <img 
                                        src={chart.url} 
                                        className="w-full h-auto"
                                        loading="lazy"
                                     />
                                </div>
                            </div>
                        ))}
                    </div>
                )}
                
                {!loading && charts.length === 0 && (
                    <div className="h-full flex items-center justify-center text-muted-foreground">
                        No charts found. Add one or adjust filters.
                    </div>
                )}
            </ScrollArea>
        </div>
    )
}
