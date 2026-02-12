"use client"

import { useState } from "react"
import { Badge } from "@/components/ui/badge"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Plus, X } from "lucide-react"

export const DEFAULT_DEMONS = [
    "FOMO", "Chasing", "Wide Stop", "No Plan", "Revenge", "Boredom", "Gambling", "Overconfidence",
    "Hesitation", "Early Exit", "Overleveraging", "Counter-Trend", "News Trading", "Distracted",
    "Fat Finger", "System Failure", "Moved Stop", "Added Loser", "Hopium", "Revenge Trading"
]

export const DEFAULT_EMOTIONS = [
    "Fear", "Greed", "Anxious", "Calm", "Confident", "Frustrated", "Hopeful", "Excited",
    "Euphoric", "Angry", "Depressed", "Tilted", "Focused", "Patient", "Impatient", "Uncertain"
]

interface DemonFinderProps {
    discipline: number
    setDiscipline: (val: number) => void
    mistakes: string[]
    setMistakes: (val: string[]) => void
    emotions: string[]
    setEmotions: (val: string[]) => void
}

export function DemonFinder({ discipline, setDiscipline, mistakes, setMistakes, emotions, setEmotions }: DemonFinderProps) {
    const [newMistake, setNewMistake] = useState("")

    const toggleMistake = (tag: string) => {
        if (mistakes.includes(tag)) setMistakes(mistakes.filter(t => t !== tag))
        else setMistakes([...mistakes, tag])
    }

    const toggleEmotion = (tag: string) => {
        if (emotions.includes(tag)) setEmotions(emotions.filter(t => t !== tag))
        else setEmotions([...emotions, tag])
    }

    const addCustomMistake = () => {
        if (newMistake && !mistakes.includes(newMistake)) {
            setMistakes([...mistakes, newMistake])
            setNewMistake("")
        }
    }

    return (
        <div className="space-y-6 p-4 border rounded-lg bg-card/50">
            {/* Tiltmeter Slider */}
            <div className="space-y-2">
                <div className="flex justify-between">
                    <Label>Discipline Score (Tiltmeter)</Label>
                    <span className={`font-mono font-bold ${discipline >= 7 ? "text-green-500" : discipline <= 4 ? "text-red-500" : "text-yellow-500"}`}>
                        {discipline}/10
                    </span>
                </div>
                <Slider
                    value={[discipline]}
                    onValueChange={(v) => setDiscipline(v[0])}
                    max={10}
                    min={1}
                    step={1}
                    className="py-4"
                />
                <div className="flex justify-between text-xs text-muted-foreground w-full px-1">
                    <span>Tilt (1)</span>
                    <span>Neutral (5)</span>
                    <span>Robot (10)</span>
                </div>
            </div>

            {/* Demon Finder (Mistakes) */}
            <div className="space-y-2">
                <Label>Demons (Mistakes)</Label>
                <div className="flex flex-wrap gap-2">
                    {DEFAULT_DEMONS.map(demon => (
                        <Badge
                            key={demon}
                            variant={mistakes.includes(demon) ? "destructive" : "outline"}
                            className="cursor-pointer hover:bg-destructive/80 transition-colors"
                            onClick={() => toggleMistake(demon)}
                        >
                            {demon}
                        </Badge>
                    ))}
                    {mistakes.filter(m => !DEFAULT_DEMONS.includes(m)).map(m => (
                         <Badge
                            key={m}
                            variant="destructive"
                            className="cursor-pointer"
                            onClick={() => toggleMistake(m)}
                        >
                            {m} <X className="h-3 w-3 ml-1" />
                        </Badge>
                    ))}
                </div>
                <div className="flex gap-2 max-w-xs mt-2">
                    <Input 
                        value={newMistake} 
                        onChange={(e) => setNewMistake(e.target.value)} 
                        placeholder="Add custom demon..." 
                        className="h-8 text-xs"
                    />
                    <Button size="icon" variant="ghost" className="h-8 w-8" onClick={addCustomMistake}>
                        <Plus className="h-4 w-4" />
                    </Button>
                </div>
            </div>

            {/* Emotional State */}
            <div className="space-y-2">
                <Label>Emotional State</Label>
                <div className="flex flex-wrap gap-2">
                    {DEFAULT_EMOTIONS.map(emotion => (
                        <Badge
                            key={emotion}
                            variant={emotions.includes(emotion) ? "secondary" : "outline"}
                            className={`cursor-pointer transition-colors ${emotions.includes(emotion) ? "bg-blue-500/20 text-blue-500 hover:bg-blue-500/30" : ""}`}
                            onClick={() => toggleEmotion(emotion)}
                        >
                            {emotion}
                        </Badge>
                    ))}
                </div>
            </div>
        </div>
    )
}
