"use client"

import { useState, useEffect } from "react"
import { useTrading } from "@/context/trading-context"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Plus, Trash2, RefreshCw, Check } from "lucide-react"
import { toast } from "sonner"
import { createAccount, deleteAccount, resetAccount } from "@/actions/journal-actions"

interface AccountManagerProps {
    open: boolean
    onOpenChange: (open: boolean) => void
}

export function AccountManagerDialog({ open, onOpenChange }: AccountManagerProps) {
    const { accounts, activeAccount, refreshAccounts, setActiveAccount } = useTrading()
    const [isCreating, setIsCreating] = useState(false)
    const [newAccountName, setNewAccountName] = useState("")
    const [initialBalance, setInitialBalance] = useState("100000")

    const handleCreate = async () => {
        if (!newAccountName) return

        const res = await createAccount({
            name: newAccountName,
            initialBalance: parseFloat(initialBalance)
        })

        if (res.success) {
            toast.success("Account created")
            setNewAccountName("")
            setIsCreating(false)
            refreshAccounts()
        } else {
            toast.error(res.error || "Failed to create account")
        }
    }

    const handleDelete = async (id: string) => {
        if (confirm("Are you sure? This will delete all trades associated with this account.")) {
            const res = await deleteAccount(id)
            if (res.success) {
                toast.success("Account deleted")
                refreshAccounts()
            } else {
                toast.error("Failed to delete account")
            }
        }
    }

    const handleReset = async (id: string) => {
        if (confirm("Reset account balance and clear trades?")) {
            const res = await resetAccount(id)
            if (res.success) {
                toast.success("Account reset")
                refreshAccounts()
            } else {
                toast.error("Failed to reset account")
            }
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-[500px] bg-[#1e222d] border-[#2a2e39] text-[#d1d4dc]">
                <DialogHeader>
                    <DialogTitle>Trading Accounts</DialogTitle>
                    <DialogDescription>
                        Manage your simulated trading accounts.
                    </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-4">
                    {/* List Accounts */}
                    <div className="space-y-2 max-h-[300px] overflow-y-auto">
                        {accounts.map(acc => (
                            <div
                                key={acc.id}
                                className={`flex items-center justify-between p-3 rounded border ${activeAccount?.id === acc.id
                                        ? "border-[#2962FF] bg-[#2962FF]/10"
                                        : "border-[#2a2e39] hover:bg-[#2a2e39]/50"
                                    }`}
                            >
                                <div className="flex flex-col cursor-pointer flex-1" onClick={() => setActiveAccount(acc)}>
                                    <span className="font-medium text-white flex items-center gap-2">
                                        {acc.name}
                                        {activeAccount?.id === acc.id && <Check className="w-3 h-3 text-[#2962FF]" />}
                                    </span>
                                    <span className="text-xs text-[#787b86]">
                                        ${acc.currentBalance.toLocaleString()} / ${acc.initialBalance.toLocaleString()}
                                    </span>
                                </div>
                                <div className="flex gap-1" onClick={(e) => e.stopPropagation()}>
                                    <Button variant="ghost" size="icon" className="h-8 w-8 text-[#787b86] hover:text-white" onClick={() => handleReset(acc.id)}>
                                        <RefreshCw className="h-4 w-4" />
                                    </Button>
                                    <Button variant="ghost" size="icon" className="h-8 w-8 text-[#ef5350] hover:bg-[#ef5350]/10" onClick={() => handleDelete(acc.id)}>
                                        <Trash2 className="h-4 w-4" />
                                    </Button>
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Create New */}
                    {isCreating ? (
                        <div className="p-3 border border-[#2a2e39] rounded bg-[#2a2e39]/30 space-y-3">
                            <div className="space-y-1">
                                <Label>Account Name</Label>
                                <Input
                                    value={newAccountName}
                                    onChange={e => setNewAccountName(e.target.value)}
                                    className="bg-[#131722] border-[#2a2e39]"
                                    placeholder="e.g. $50k Challenge"
                                />
                            </div>
                            <div className="space-y-1">
                                <Label>Initial Balance</Label>
                                <Input
                                    type="number"
                                    value={initialBalance}
                                    onChange={e => setInitialBalance(e.target.value)}
                                    className="bg-[#131722] border-[#2a2e39]"
                                />
                            </div>
                            <div className="flex justify-end gap-2 pt-2">
                                <Button variant="ghost" onClick={() => setIsCreating(false)}>Cancel</Button>
                                <Button className="bg-[#2962FF] hover:bg-[#2962FF]/90" onClick={handleCreate}>Create</Button>
                            </div>
                        </div>
                    ) : (
                        <Button
                            variant="outline"
                            className="w-full border-dashed border-[#2a2e39] text-[#787b86] hover:text-white hover:border-[#2962FF]"
                            onClick={() => setIsCreating(true)}
                        >
                            <Plus className="w-4 h-4 mr-2" />
                            Add New Account
                        </Button>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    )
}
