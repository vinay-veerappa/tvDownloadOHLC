"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Progress } from "@/components/ui/progress"
import { Badge } from "@/components/ui/badge"
import { Target, TrendingUp, TrendingDown, Edit, Save, X } from "lucide-react"

interface GoalData {
    dailyTarget: number
    weeklyTarget: number
    monthlyTarget: number
    maxLossPerDay: number
    maxTradesPerDay: number
}

interface GoalProgressData {
    todayPnl: number
    weekPnl: number
    monthPnl: number
    todayTrades: number
}

interface GoalTrackerProps {
    goals?: GoalData
    progress: GoalProgressData
    onSaveGoals?: (goals: GoalData) => void
}

const DEFAULT_GOALS: GoalData = {
    dailyTarget: 500,
    weeklyTarget: 2000,
    monthlyTarget: 8000,
    maxLossPerDay: 500,
    maxTradesPerDay: 5
}

export function GoalTracker({ goals = DEFAULT_GOALS, progress, onSaveGoals }: GoalTrackerProps) {
    const [isEditing, setIsEditing] = useState(false)
    const [editedGoals, setEditedGoals] = useState<GoalData>(goals)

    const handleSave = () => {
        onSaveGoals?.(editedGoals)
        setIsEditing(false)
    }

    const handleCancel = () => {
        setEditedGoals(goals)
        setIsEditing(false)
    }

    const calculateProgress = (current: number, target: number) => {
        if (target === 0) return 0
        const pct = (current / target) * 100
        return Math.min(Math.max(pct, 0), 100)
    }

    const getStatusColor = (current: number, target: number, isLoss = false) => {
        if (isLoss) {
            return current >= target ? "text-red-500" : "text-green-500"
        }
        if (current >= target) return "text-green-500"
        if (current >= target * 0.5) return "text-yellow-500"
        return "text-muted-foreground"
    }

    return (
        <Card>
            <CardHeader className="flex flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                    <Target className="h-5 w-5" />
                    Trading Goals
                </CardTitle>
                {!isEditing ? (
                    <Button variant="ghost" size="sm" onClick={() => setIsEditing(true)}>
                        <Edit className="h-4 w-4 mr-1" /> Edit
                    </Button>
                ) : (
                    <div className="flex gap-2">
                        <Button variant="ghost" size="sm" onClick={handleCancel}>
                            <X className="h-4 w-4" />
                        </Button>
                        <Button size="sm" onClick={handleSave}>
                            <Save className="h-4 w-4 mr-1" /> Save
                        </Button>
                    </div>
                )}
            </CardHeader>
            <CardContent className="space-y-6">
                {isEditing ? (
                    <div className="grid gap-4">
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Daily Target ($)</Label>
                                <Input
                                    type="number"
                                    value={editedGoals.dailyTarget}
                                    onChange={(e) => setEditedGoals({ ...editedGoals, dailyTarget: Number(e.target.value) })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Max Loss/Day ($)</Label>
                                <Input
                                    type="number"
                                    value={editedGoals.maxLossPerDay}
                                    onChange={(e) => setEditedGoals({ ...editedGoals, maxLossPerDay: Number(e.target.value) })}
                                />
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label>Weekly Target ($)</Label>
                                <Input
                                    type="number"
                                    value={editedGoals.weeklyTarget}
                                    onChange={(e) => setEditedGoals({ ...editedGoals, weeklyTarget: Number(e.target.value) })}
                                />
                            </div>
                            <div className="space-y-2">
                                <Label>Max Trades/Day</Label>
                                <Input
                                    type="number"
                                    value={editedGoals.maxTradesPerDay}
                                    onChange={(e) => setEditedGoals({ ...editedGoals, maxTradesPerDay: Number(e.target.value) })}
                                />
                            </div>
                        </div>
                        <div className="space-y-2">
                            <Label>Monthly Target ($)</Label>
                            <Input
                                type="number"
                                value={editedGoals.monthlyTarget}
                                onChange={(e) => setEditedGoals({ ...editedGoals, monthlyTarget: Number(e.target.value) })}
                            />
                        </div>
                    </div>
                ) : (
                    <>
                        {/* Daily Progress */}
                        <div className="space-y-2">
                            <div className="flex justify-between items-center">
                                <span className="text-sm font-medium">Today</span>
                                <span className={`font-mono text-sm ${getStatusColor(progress.todayPnl, goals.dailyTarget)}`}>
                                    ${progress.todayPnl.toFixed(2)} / ${goals.dailyTarget}
                                </span>
                            </div>
                            <Progress
                                value={calculateProgress(progress.todayPnl, goals.dailyTarget)}
                                className="h-2"
                            />
                            <div className="flex justify-between text-xs text-muted-foreground">
                                <span>{progress.todayTrades} trades today</span>
                                <span>Max: {goals.maxTradesPerDay}</span>
                            </div>
                        </div>

                        {/* Weekly Progress */}
                        <div className="space-y-2">
                            <div className="flex justify-between items-center">
                                <span className="text-sm font-medium">This Week</span>
                                <span className={`font-mono text-sm ${getStatusColor(progress.weekPnl, goals.weeklyTarget)}`}>
                                    ${progress.weekPnl.toFixed(2)} / ${goals.weeklyTarget}
                                </span>
                            </div>
                            <Progress
                                value={calculateProgress(progress.weekPnl, goals.weeklyTarget)}
                                className="h-2"
                            />
                        </div>

                        {/* Monthly Progress */}
                        <div className="space-y-2">
                            <div className="flex justify-between items-center">
                                <span className="text-sm font-medium">This Month</span>
                                <span className={`font-mono text-sm ${getStatusColor(progress.monthPnl, goals.monthlyTarget)}`}>
                                    ${progress.monthPnl.toFixed(2)} / ${goals.monthlyTarget}
                                </span>
                            </div>
                            <Progress
                                value={calculateProgress(progress.monthPnl, goals.monthlyTarget)}
                                className="h-2"
                            />
                        </div>

                        {/* Risk Alert */}
                        {progress.todayPnl < 0 && Math.abs(progress.todayPnl) >= goals.maxLossPerDay * 0.8 && (
                            <div className="bg-red-500/10 border border-red-500/50 rounded-lg p-3">
                                <div className="flex items-center gap-2 text-red-500">
                                    <TrendingDown className="h-4 w-4" />
                                    <span className="text-sm font-medium">
                                        Daily loss limit {Math.abs(progress.todayPnl) >= goals.maxLossPerDay ? 'exceeded' : 'approaching'}!
                                    </span>
                                </div>
                            </div>
                        )}

                        {/* Success Alert */}
                        {progress.todayPnl >= goals.dailyTarget && (
                            <div className="bg-green-500/10 border border-green-500/50 rounded-lg p-3">
                                <div className="flex items-center gap-2 text-green-500">
                                    <TrendingUp className="h-4 w-4" />
                                    <span className="text-sm font-medium">
                                        Daily target reached! 🎉
                                    </span>
                                </div>
                            </div>
                        )}
                    </>
                )}
            </CardContent>
        </Card>
    )
}
