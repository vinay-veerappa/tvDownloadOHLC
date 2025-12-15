"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Badge } from "@/components/ui/badge"
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter
} from "@/components/ui/dialog"
import { BookOpen, Plus, ChevronRight, Image } from "lucide-react"

export interface PlaybookSetup {
    id: string
    name: string
    description: string
    entryRules: string[]
    exitRules: string[]
    riskRules: string[]
    timeframes: string[]
    screenshotUrl?: string
    tags: string[]
    winRate?: number
    tradeCount?: number
}

interface PlaybookProps {
    setups: PlaybookSetup[]
    onAddSetup?: (setup: Omit<PlaybookSetup, 'id' | 'winRate' | 'tradeCount'>) => void
    onSelectSetup?: (setup: PlaybookSetup) => void
}

export function Playbook({ setups, onAddSetup, onSelectSetup }: PlaybookProps) {
    const [isDialogOpen, setIsDialogOpen] = useState(false)
    const [newSetup, setNewSetup] = useState({
        name: "",
        description: "",
        entryRules: "",
        exitRules: "",
        riskRules: "",
        timeframes: "",
        tags: ""
    })

    const handleAdd = () => {
        if (!newSetup.name.trim()) return

        onAddSetup?.({
            name: newSetup.name.trim(),
            description: newSetup.description.trim(),
            entryRules: newSetup.entryRules.split('\n').filter(r => r.trim()),
            exitRules: newSetup.exitRules.split('\n').filter(r => r.trim()),
            riskRules: newSetup.riskRules.split('\n').filter(r => r.trim()),
            timeframes: newSetup.timeframes.split(',').map(t => t.trim()).filter(Boolean),
            tags: newSetup.tags.split(',').map(t => t.trim()).filter(Boolean)
        })

        setNewSetup({
            name: "", description: "", entryRules: "", exitRules: "", riskRules: "", timeframes: "", tags: ""
        })
        setIsDialogOpen(false)
    }

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                    <BookOpen className="h-5 w-5" />
                    Trading Playbook
                </CardTitle>
                <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
                    <DialogTrigger asChild>
                        <Button size="sm">
                            <Plus className="h-4 w-4 mr-1" /> Add Setup
                        </Button>
                    </DialogTrigger>
                    <DialogContent className="max-w-2xl">
                        <DialogHeader>
                            <DialogTitle>Add New Setup</DialogTitle>
                        </DialogHeader>
                        <div className="grid gap-4 py-4">
                            <div className="grid grid-cols-2 gap-4">
                                <div className="space-y-2">
                                    <Label>Setup Name</Label>
                                    <Input
                                        value={newSetup.name}
                                        onChange={(e) => setNewSetup({ ...newSetup, name: e.target.value })}
                                        placeholder="Opening Range Breakout"
                                    />
                                </div>
                                <div className="space-y-2">
                                    <Label>Timeframes (comma-separated)</Label>
                                    <Input
                                        value={newSetup.timeframes}
                                        onChange={(e) => setNewSetup({ ...newSetup, timeframes: e.target.value })}
                                        placeholder="5m, 15m, 1h"
                                    />
                                </div>
                            </div>
                            <div className="space-y-2">
                                <Label>Description</Label>
                                <Textarea
                                    value={newSetup.description}
                                    onChange={(e) => setNewSetup({ ...newSetup, description: e.target.value })}
                                    placeholder="Brief description of this setup..."
                                    className="min-h-[60px]"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Entry Rules (one per line)</Label>
                                <Textarea
                                    value={newSetup.entryRules}
                                    onChange={(e) => setNewSetup({ ...newSetup, entryRules: e.target.value })}
                                    placeholder="Price breaks above opening range high&#10;Volume above average&#10;VIX under 20"
                                    className="min-h-[80px]"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Exit Rules (one per line)</Label>
                                <Textarea
                                    value={newSetup.exitRules}
                                    onChange={(e) => setNewSetup({ ...newSetup, exitRules: e.target.value })}
                                    placeholder="Target 1R or 2R&#10;Trail stop after 1R&#10;Exit before 3pm"
                                    className="min-h-[80px]"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Risk Rules (one per line)</Label>
                                <Textarea
                                    value={newSetup.riskRules}
                                    onChange={(e) => setNewSetup({ ...newSetup, riskRules: e.target.value })}
                                    placeholder="1% max risk per trade&#10;Stop below opening range low&#10;Max 2 attempts per day"
                                    className="min-h-[80px]"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Tags (comma-separated)</Label>
                                <Input
                                    value={newSetup.tags}
                                    onChange={(e) => setNewSetup({ ...newSetup, tags: e.target.value })}
                                    placeholder="momentum, breakout, morning"
                                />
                            </div>
                        </div>
                        <DialogFooter>
                            <Button variant="outline" onClick={() => setIsDialogOpen(false)}>Cancel</Button>
                            <Button onClick={handleAdd}>Add Setup</Button>
                        </DialogFooter>
                    </DialogContent>
                </Dialog>
            </CardHeader>
            <CardContent>
                {setups.length === 0 ? (
                    <div className="text-center py-8 text-muted-foreground">
                        <BookOpen className="h-12 w-12 mx-auto mb-4 opacity-50" />
                        <p>No setups in your playbook yet.</p>
                        <p className="text-sm">Add your first trading setup to get started.</p>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {setups.map((setup) => (
                            <div
                                key={setup.id}
                                className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 cursor-pointer transition-colors"
                                onClick={() => onSelectSetup?.(setup)}
                            >
                                <div className="flex-1">
                                    <div className="flex items-center gap-2">
                                        <h4 className="font-medium">{setup.name}</h4>
                                        {setup.timeframes.map(tf => (
                                            <Badge key={tf} variant="secondary" className="text-xs">
                                                {tf}
                                            </Badge>
                                        ))}
                                    </div>
                                    <p className="text-sm text-muted-foreground line-clamp-1">
                                        {setup.description}
                                    </p>
                                    {setup.winRate !== undefined && (
                                        <p className="text-xs text-muted-foreground mt-1">
                                            {setup.tradeCount} trades · {setup.winRate.toFixed(1)}% win rate
                                        </p>
                                    )}
                                </div>
                                <ChevronRight className="h-4 w-4 text-muted-foreground" />
                            </div>
                        ))}
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
