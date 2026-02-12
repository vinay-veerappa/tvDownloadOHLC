"use client"

import { useEffect, useState } from "react"
import { getPlaybooks, createPlaybook } from "@/actions/playbook-actions"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Plus } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

interface PlaybookSelectorProps {
    value?: string
    onChange: (value: string) => void
}

export function PlaybookSelector({ value, onChange }: PlaybookSelectorProps) {
    const [playbooks, setPlaybooks] = useState<any[]>([])
    const [open, setOpen] = useState(false)
    const [name, setName] = useState("")
    const [rules, setRules] = useState("")

    useEffect(() => {
        loadPlaybooks()
    }, [])

    async function loadPlaybooks() {
        const res = await getPlaybooks()
        if (res.success && res.data) {
            setPlaybooks(res.data)
        }
    }

    async function handleCreate() {
        if (!name.trim()) return
        const res = await createPlaybook(name, undefined, rules)
        if (res.success) {
            setName("")
            setRules("")
            setOpen(false)
            loadPlaybooks()
            if (res.data) onChange(res.data.id)
        }
    }

    return (
        <div className="flex items-center gap-2">
            <Select value={value} onValueChange={onChange}>
                <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select Playbook / Setup" />
                </SelectTrigger>
                <SelectContent>
                    {playbooks.map(p => (
                        <SelectItem key={p.id} value={p.id}>{p.name}</SelectItem>
                    ))}
                    {playbooks.length === 0 && <div className="p-2 text-xs text-muted-foreground text-center">No playbooks found</div>}
                </SelectContent>
            </Select>
            <Dialog open={open} onOpenChange={setOpen}>
                <DialogTrigger asChild>
                    <Button variant="outline" size="icon" type="button">
                        <Plus className="h-4 w-4" />
                    </Button>
                </DialogTrigger>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Create New Playbook</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label>Playbook Name</Label>
                            <Input 
                                placeholder="e.g. Opening Range Breakout" 
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                            />
                        </div>
                        <div className="space-y-2">
                            <Label>Rules (Optional)</Label>
                            <Textarea 
                                placeholder="- Wait for close above OR High..." 
                                value={rules}
                                onChange={(e) => setRules(e.target.value)}
                            />
                        </div>
                        <Button onClick={handleCreate} className="w-full">Create Playbook</Button>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    )
}
