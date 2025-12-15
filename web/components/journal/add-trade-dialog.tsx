"use client"

import { useState, useEffect } from "react"
import { createTrade, getStrategies } from "@/actions/trade-actions"
import { Button } from "@/components/ui/button"
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { useTradeContext } from "@/components/journal/trade-context"
import { format } from "date-fns"

interface Strategy {
    id: string
    name: string
    color: string
}

export function AddTradeDialog() {
    const { isOpen, setIsOpen, initialData } = useTradeContext()
    const [loading, setLoading] = useState(false)
    const [strategies, setStrategies] = useState<Strategy[]>([])

    // Form state
    const [selectedStrategy, setSelectedStrategy] = useState<string>("none")

    useEffect(() => {
        async function loadStrategies() {
            const result = await getStrategies()
            if (result.success && result.data) {
                setStrategies(result.data)
            }
        }
        loadStrategies()
    }, [])

    // Form default values
    const defaultSymbol = initialData?.symbol || "ES"
    const defaultPrice = initialData?.price?.toString() || ""
    const defaultDate = initialData?.date
        ? format(initialData.date, "yyyy-MM-dd'T'HH:mm")
        : format(new Date(), "yyyy-MM-dd'T'HH:mm")
    const defaultDirection = initialData?.direction || "LONG"

    async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault()
        setLoading(true)

        const formData = new FormData(event.currentTarget)

        const stopLossValue = formData.get("stopLoss") as string
        const takeProfitValue = formData.get("takeProfit") as string

        const data = {
            ticker: formData.get("symbol") as string,
            direction: formData.get("direction") as "LONG" | "SHORT",
            entryDate: new Date(formData.get("entryDate") as string),
            entryPrice: parseFloat(formData.get("entryPrice") as string),
            quantity: parseFloat(formData.get("quantity") as string),
            status: "OPEN" as const,
            orderType: "MARKET" as const,
            accountId: "default-sim-account",
            strategyId: selectedStrategy !== "none" ? selectedStrategy : undefined,
            stopLoss: stopLossValue ? parseFloat(stopLossValue) : undefined,
            takeProfit: takeProfitValue ? parseFloat(takeProfitValue) : undefined,
            risk: 0
        }

        const result = await createTrade(data)

        if (result.success) {
            setIsOpen(false)
            window.location.reload()
        } else {
            alert("Failed to create trade")
        }
        setLoading(false)
    }

    return (
        <Dialog open={isOpen} onOpenChange={setIsOpen}>
            <DialogTrigger asChild>
                <Button onClick={() => setIsOpen(true)}>Add Trade</Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[500px]">
                <form onSubmit={onSubmit}>
                    <DialogHeader>
                        <DialogTitle>Add New Trade</DialogTitle>
                        <DialogDescription>
                            Enter the details of your trade execution.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                        {/* Row 1: Symbol & Direction */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="symbol">Symbol</Label>
                                <Input
                                    id="symbol"
                                    name="symbol"
                                    defaultValue={defaultSymbol}
                                    required
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="direction">Direction</Label>
                                <Select name="direction" defaultValue={defaultDirection} required>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select direction" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="LONG">Long</SelectItem>
                                        <SelectItem value="SHORT">Short</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        {/* Row 2: Date & Quantity */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="entryDate">Entry Date</Label>
                                <Input
                                    id="entryDate"
                                    name="entryDate"
                                    type="datetime-local"
                                    defaultValue={defaultDate}
                                    required
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="quantity">Quantity</Label>
                                <Input
                                    id="quantity"
                                    name="quantity"
                                    type="number"
                                    step="1"
                                    defaultValue="1"
                                    required
                                />
                            </div>
                        </div>

                        {/* Row 3: Entry Price & Strategy */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="entryPrice">Entry Price</Label>
                                <Input
                                    id="entryPrice"
                                    name="entryPrice"
                                    type="number"
                                    step="0.01"
                                    defaultValue={defaultPrice}
                                    required
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="strategy">Strategy</Label>
                                <Select value={selectedStrategy} onValueChange={setSelectedStrategy}>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select strategy" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="none">None</SelectItem>
                                        {strategies.map(s => (
                                            <SelectItem key={s.id} value={s.id}>
                                                <span className="flex items-center gap-2">
                                                    <span
                                                        className="w-2 h-2 rounded-full"
                                                        style={{ backgroundColor: s.color }}
                                                    />
                                                    {s.name}
                                                </span>
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        {/* Row 4: Stop Loss & Take Profit */}
                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="stopLoss">Stop Loss (optional)</Label>
                                <Input
                                    id="stopLoss"
                                    name="stopLoss"
                                    type="number"
                                    step="0.01"
                                    placeholder="Price"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="takeProfit">Take Profit (optional)</Label>
                                <Input
                                    id="takeProfit"
                                    name="takeProfit"
                                    type="number"
                                    step="0.01"
                                    placeholder="Price"
                                />
                            </div>
                        </div>

                        {/* Row 5: Notes */}
                        <div className="space-y-2">
                            <Label htmlFor="notes">Notes (optional)</Label>
                            <Textarea
                                id="notes"
                                name="notes"
                                placeholder="Add any notes about this trade..."
                                className="min-h-[80px]"
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button type="button" variant="outline" onClick={() => setIsOpen(false)}>
                            Cancel
                        </Button>
                        <Button type="submit" disabled={loading}>
                            {loading ? "Saving..." : "Save Trade"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    )
}

