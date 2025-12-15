"use client"

import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group"
import { Checkbox } from "@/components/ui/checkbox"
import { updateTrade } from "@/actions/trade-actions"
import { CheckCircle } from "lucide-react"

interface TradeReviewProps {
    tradeId: string
    initialReview?: TradeReviewData | null
    onComplete?: () => void
}

export interface TradeReviewData {
    executionRating: number // 1-5
    followedPlan: boolean
    emotionalState: string
    whatWentWell: string
    whatWentWrong: string
    lessonsLearned: string
    wouldTakeAgain: boolean
    tags: string[]
}

const EMOTIONAL_STATES = [
    { value: "calm", label: "Calm & Focused" },
    { value: "confident", label: "Confident" },
    { value: "anxious", label: "Anxious" },
    { value: "frustrated", label: "Frustrated" },
    { value: "fomo", label: "FOMO" },
    { value: "revenge", label: "Revenge Trading" },
    { value: "overconfident", label: "Overconfident" },
]

const COMMON_MISTAKES = [
    "Moved stop loss",
    "Entered too early",
    "Entered too late",
    "Wrong position size",
    "Ignored setup rules",
    "Didn't wait for confirmation",
    "Chased the move",
    "Exited too early",
    "Held too long",
]

export function TradeReview({ tradeId, initialReview, onComplete }: TradeReviewProps) {
    const [saving, setSaving] = useState(false)
    const [saved, setSaved] = useState(false)

    const [executionRating, setExecutionRating] = useState(initialReview?.executionRating || 3)
    const [followedPlan, setFollowedPlan] = useState(initialReview?.followedPlan ?? true)
    const [emotionalState, setEmotionalState] = useState(initialReview?.emotionalState || "calm")
    const [whatWentWell, setWhatWentWell] = useState(initialReview?.whatWentWell || "")
    const [whatWentWrong, setWhatWentWrong] = useState(initialReview?.whatWentWrong || "")
    const [lessonsLearned, setLessonsLearned] = useState(initialReview?.lessonsLearned || "")
    const [wouldTakeAgain, setWouldTakeAgain] = useState(initialReview?.wouldTakeAgain ?? true)
    const [selectedMistakes, setSelectedMistakes] = useState<string[]>(initialReview?.tags || [])

    const toggleMistake = (mistake: string) => {
        setSelectedMistakes(prev =>
            prev.includes(mistake)
                ? prev.filter(m => m !== mistake)
                : [...prev, mistake]
        )
    }

    const handleSave = async () => {
        setSaving(true)

        const reviewData: TradeReviewData = {
            executionRating,
            followedPlan,
            emotionalState,
            whatWentWell,
            whatWentWrong,
            lessonsLearned,
            wouldTakeAgain,
            tags: selectedMistakes
        }

        // Store review as JSON in notes field (or a dedicated review field if schema updated)
        const reviewJson = JSON.stringify(reviewData)

        const result = await updateTrade(tradeId, {
            notes: `[REVIEW]\n${reviewJson}\n[/REVIEW]`
        })

        if (result.success) {
            setSaved(true)
            onComplete?.()
        }

        setSaving(false)
    }

    if (saved) {
        return (
            <Card>
                <CardContent className="py-8 text-center">
                    <CheckCircle className="h-12 w-12 text-green-500 mx-auto mb-4" />
                    <h3 className="text-lg font-semibold">Review Saved!</h3>
                    <p className="text-muted-foreground">Your trade review has been recorded.</p>
                </CardContent>
            </Card>
        )
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle>Trade Review</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
                {/* Execution Rating */}
                <div className="space-y-2">
                    <Label>Execution Quality (1-5)</Label>
                    <div className="flex gap-2">
                        {[1, 2, 3, 4, 5].map(rating => (
                            <Button
                                key={rating}
                                type="button"
                                variant={executionRating === rating ? "default" : "outline"}
                                size="sm"
                                onClick={() => setExecutionRating(rating)}
                                className="w-10 h-10"
                            >
                                {rating}
                            </Button>
                        ))}
                    </div>
                    <p className="text-xs text-muted-foreground">
                        1 = Poor, 5 = Perfect execution
                    </p>
                </div>

                {/* Followed Plan */}
                <div className="flex items-center gap-2">
                    <Checkbox
                        id="followedPlan"
                        checked={followedPlan}
                        onCheckedChange={(checked) => setFollowedPlan(checked as boolean)}
                    />
                    <Label htmlFor="followedPlan">Followed trading plan</Label>
                </div>

                {/* Emotional State */}
                <div className="space-y-2">
                    <Label>Emotional State</Label>
                    <RadioGroup value={emotionalState} onValueChange={setEmotionalState}>
                        <div className="grid grid-cols-2 gap-2">
                            {EMOTIONAL_STATES.map(state => (
                                <div key={state.value} className="flex items-center space-x-2">
                                    <RadioGroupItem value={state.value} id={state.value} />
                                    <Label htmlFor={state.value} className="text-sm font-normal">
                                        {state.label}
                                    </Label>
                                </div>
                            ))}
                        </div>
                    </RadioGroup>
                </div>

                {/* Mistakes */}
                <div className="space-y-2">
                    <Label>Mistakes Made (select all that apply)</Label>
                    <div className="grid grid-cols-2 gap-2">
                        {COMMON_MISTAKES.map(mistake => (
                            <div key={mistake} className="flex items-center space-x-2">
                                <Checkbox
                                    id={`mistake-${mistake}`}
                                    checked={selectedMistakes.includes(mistake)}
                                    onCheckedChange={() => toggleMistake(mistake)}
                                />
                                <Label htmlFor={`mistake-${mistake}`} className="text-sm font-normal">
                                    {mistake}
                                </Label>
                            </div>
                        ))}
                    </div>
                </div>

                {/* What went well */}
                <div className="space-y-2">
                    <Label htmlFor="whatWentWell">What went well?</Label>
                    <Textarea
                        id="whatWentWell"
                        value={whatWentWell}
                        onChange={(e) => setWhatWentWell(e.target.value)}
                        placeholder="Good entry timing, proper position sizing..."
                        className="min-h-[80px]"
                    />
                </div>

                {/* What went wrong */}
                <div className="space-y-2">
                    <Label htmlFor="whatWentWrong">What went wrong?</Label>
                    <Textarea
                        id="whatWentWrong"
                        value={whatWentWrong}
                        onChange={(e) => setWhatWentWrong(e.target.value)}
                        placeholder="Moved stop loss, didn't wait for confirmation..."
                        className="min-h-[80px]"
                    />
                </div>

                {/* Lessons Learned */}
                <div className="space-y-2">
                    <Label htmlFor="lessonsLearned">Lessons Learned</Label>
                    <Textarea
                        id="lessonsLearned"
                        value={lessonsLearned}
                        onChange={(e) => setLessonsLearned(e.target.value)}
                        placeholder="Key takeaways from this trade..."
                        className="min-h-[80px]"
                    />
                </div>

                {/* Would Take Again */}
                <div className="flex items-center gap-2">
                    <Checkbox
                        id="wouldTakeAgain"
                        checked={wouldTakeAgain}
                        onCheckedChange={(checked) => setWouldTakeAgain(checked as boolean)}
                    />
                    <Label htmlFor="wouldTakeAgain">Would take this trade again</Label>
                </div>

                {/* Save Button */}
                <Button onClick={handleSave} disabled={saving} className="w-full">
                    {saving ? "Saving..." : "Save Review"}
                </Button>
            </CardContent>
        </Card>
    )
}
