"use client"

import { useEffect, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { format } from "date-fns"
import { ArrowLeft, Edit, Trash2, Save, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { getTrade, updateTrade, deleteTrade } from "@/actions/trade-actions"

interface Trade {
    id: string
    ticker: string
    direction: string
    entryDate: Date | string
    exitDate?: Date | string | null
    entryPrice: number | null
    exitPrice: number | null
    quantity: number
    status: string
    pnl: number | null
    stopLoss: number | null
    takeProfit: number | null
    notes: string | null
    mae: number | null
    mfe: number | null
    duration: number | null
    strategy?: { id: string; name: string; color: string } | null
    account?: { id: string; name: string } | null
}

export default function TradeDetailPage() {
    const params = useParams()
    const router = useRouter()
    const tradeId = params.id as string

    const [trade, setTrade] = useState<Trade | null>(null)
    const [loading, setLoading] = useState(true)
    const [isEditing, setIsEditing] = useState(false)
    const [editedNotes, setEditedNotes] = useState("")

    useEffect(() => {
        async function loadTrade() {
            const result = await getTrade(tradeId)
            if (result.success && result.data) {
                setTrade(result.data)
                setEditedNotes(result.data.notes || "")
            }
            setLoading(false)
        }
        loadTrade()
    }, [tradeId])

    const handleSaveNotes = async () => {
        if (!trade) return
        const result = await updateTrade(trade.id, { notes: editedNotes })
        if (result.success) {
            setTrade({ ...trade, notes: editedNotes })
            setIsEditing(false)
        }
    }

    const handleDelete = async () => {
        if (!trade) return
        if (confirm("Are you sure you want to delete this trade?")) {
            const result = await deleteTrade(trade.id)
            if (result.success) {
                router.push("/journal")
            }
        }
    }

    if (loading) {
        return <div className="p-6">Loading trade...</div>
    }

    if (!trade) {
        return <div className="p-6">Trade not found</div>
    }

    const isProfitable = trade.pnl && trade.pnl > 0
    const durationMinutes = trade.duration ? Math.floor(trade.duration / 60) : null

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Button variant="ghost" size="icon" onClick={() => router.push("/journal")}>
                        <ArrowLeft className="h-4 w-4" />
                    </Button>
                    <div>
                        <h2 className="text-2xl font-bold">
                            {trade.ticker} {trade.direction}
                        </h2>
                        <p className="text-sm text-muted-foreground">
                            {format(new Date(trade.entryDate), "MMMM d, yyyy 'at' h:mm a")}
                        </p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={handleDelete}>
                        <Trash2 className="h-4 w-4 mr-1" />
                        Delete
                    </Button>
                </div>
            </div>

            {/* Main Content */}
            <div className="grid gap-6 md:grid-cols-2">
                {/* Trade Summary Card */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-lg">Trade Summary</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="flex justify-between items-center">
                            <span className="text-muted-foreground">Direction</span>
                            <Badge variant={trade.direction === "LONG" ? "default" : "destructive"}>
                                {trade.direction}
                            </Badge>
                        </div>
                        <div className="flex justify-between items-center">
                            <span className="text-muted-foreground">Status</span>
                            <Badge variant="outline">{trade.status}</Badge>
                        </div>
                        <div className="flex justify-between items-center">
                            <span className="text-muted-foreground">Entry Price</span>
                            <span className="font-mono">{trade.entryPrice?.toFixed(2) || "-"}</span>
                        </div>
                        <div className="flex justify-between items-center">
                            <span className="text-muted-foreground">Exit Price</span>
                            <span className="font-mono">{trade.exitPrice?.toFixed(2) || "-"}</span>
                        </div>
                        <div className="flex justify-between items-center">
                            <span className="text-muted-foreground">Quantity</span>
                            <span>{trade.quantity}</span>
                        </div>
                        <div className="flex justify-between items-center">
                            <span className="text-muted-foreground">P&L</span>
                            <span className={`font-bold ${isProfitable ? "text-green-500" : "text-red-500"}`}>
                                {trade.pnl ? `$${trade.pnl.toFixed(2)}` : "-"}
                            </span>
                        </div>
                    </CardContent>
                </Card>

                {/* Risk & Metrics Card */}
                <Card>
                    <CardHeader>
                        <CardTitle className="text-lg">Risk & Metrics</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="flex justify-between items-center">
                            <span className="text-muted-foreground">Stop Loss</span>
                            <span className="font-mono">{trade.stopLoss?.toFixed(2) || "-"}</span>
                        </div>
                        <div className="flex justify-between items-center">
                            <span className="text-muted-foreground">Take Profit</span>
                            <span className="font-mono">{trade.takeProfit?.toFixed(2) || "-"}</span>
                        </div>
                        <div className="flex justify-between items-center">
                            <span className="text-muted-foreground">MAE</span>
                            <span className="font-mono text-red-400">{trade.mae?.toFixed(2) || "-"}</span>
                        </div>
                        <div className="flex justify-between items-center">
                            <span className="text-muted-foreground">MFE</span>
                            <span className="font-mono text-green-400">{trade.mfe?.toFixed(2) || "-"}</span>
                        </div>
                        <div className="flex justify-between items-center">
                            <span className="text-muted-foreground">Duration</span>
                            <span>{durationMinutes ? `${durationMinutes} min` : "-"}</span>
                        </div>
                        <div className="flex justify-between items-center">
                            <span className="text-muted-foreground">Strategy</span>
                            <span>{trade.strategy?.name || "None"}</span>
                        </div>
                    </CardContent>
                </Card>
            </div>

            {/* Notes Section */}
            <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                    <CardTitle className="text-lg">Notes</CardTitle>
                    {!isEditing ? (
                        <Button variant="ghost" size="sm" onClick={() => setIsEditing(true)}>
                            <Edit className="h-4 w-4 mr-1" />
                            Edit
                        </Button>
                    ) : (
                        <div className="flex gap-2">
                            <Button variant="ghost" size="sm" onClick={() => setIsEditing(false)}>
                                <X className="h-4 w-4 mr-1" />
                                Cancel
                            </Button>
                            <Button size="sm" onClick={handleSaveNotes}>
                                <Save className="h-4 w-4 mr-1" />
                                Save
                            </Button>
                        </div>
                    )}
                </CardHeader>
                <CardContent>
                    {isEditing ? (
                        <Textarea
                            value={editedNotes}
                            onChange={(e) => setEditedNotes(e.target.value)}
                            placeholder="Add notes about this trade..."
                            className="min-h-[150px]"
                        />
                    ) : (
                        <p className="text-muted-foreground whitespace-pre-wrap">
                            {trade.notes || "No notes for this trade."}
                        </p>
                    )}
                </CardContent>
            </Card>
        </div>
    )
}
