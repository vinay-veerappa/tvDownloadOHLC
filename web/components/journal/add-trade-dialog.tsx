"use client"

import { useState } from "react"
import { createTrade } from "@/actions/trade-actions"
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
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"

export function AddTradeDialog() {
    const [open, setOpen] = useState(false)
    const [loading, setLoading] = useState(false)

    async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
        event.preventDefault()
        setLoading(true)

        const formData = new FormData(event.currentTarget)

        const data = {
            symbol: formData.get("symbol") as string,
            direction: formData.get("direction") as "LONG" | "SHORT",
            entryDate: new Date(formData.get("entryDate") as string),
            entryPrice: parseFloat(formData.get("entryPrice") as string),
            quantity: parseFloat(formData.get("quantity") as string),
            status: "OPEN" as const,
        }

        const result = await createTrade(data)

        if (result.success) {
            setOpen(false)
            // Ideally trigger a refresh of the list here, 
            // but Server Actions revalidatePath handles it for server components.
            // For client components, we might need a context or router refresh.
            window.location.reload() // Simple brute force refresh for now
        } else {
            alert("Failed to create trade")
        }
        setLoading(false)
    }

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button>Add Trade</Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[425px]">
                <form onSubmit={onSubmit}>
                    <DialogHeader>
                        <DialogTitle>Add New Trade</DialogTitle>
                        <DialogDescription>
                            Enter the details of your trade execution.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="grid gap-4 py-4">
                        <div className="grid grid-cols-4 items-center gap-4">
                            <Label htmlFor="symbol" className="text-right">
                                Symbol
                            </Label>
                            <Input
                                id="symbol"
                                name="symbol"
                                defaultValue="ES"
                                className="col-span-3"
                                required
                            />
                        </div>
                        <div className="grid grid-cols-4 items-center gap-4">
                            <Label htmlFor="direction" className="text-right">
                                Direction
                            </Label>
                            <Select name="direction" defaultValue="LONG" required>
                                <SelectTrigger className="col-span-3">
                                    <SelectValue placeholder="Select direction" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="LONG">Long</SelectItem>
                                    <SelectItem value="SHORT">Short</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div className="grid grid-cols-4 items-center gap-4">
                            <Label htmlFor="entryDate" className="text-right">
                                Date
                            </Label>
                            <Input
                                id="entryDate"
                                name="entryDate"
                                type="datetime-local"
                                className="col-span-3"
                                required
                            />
                        </div>
                        <div className="grid grid-cols-4 items-center gap-4">
                            <Label htmlFor="entryPrice" className="text-right">
                                Price
                            </Label>
                            <Input
                                id="entryPrice"
                                name="entryPrice"
                                type="number"
                                step="0.01"
                                className="col-span-3"
                                required
                            />
                        </div>
                        <div className="grid grid-cols-4 items-center gap-4">
                            <Label htmlFor="quantity" className="text-right">
                                Quantity
                            </Label>
                            <Input
                                id="quantity"
                                name="quantity"
                                type="number"
                                step="0.1"
                                defaultValue="1"
                                className="col-span-3"
                                required
                            />
                        </div>
                    </div>
                    <DialogFooter>
                        <Button type="submit" disabled={loading}>
                            {loading ? "Saving..." : "Save Trade"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    )
}
