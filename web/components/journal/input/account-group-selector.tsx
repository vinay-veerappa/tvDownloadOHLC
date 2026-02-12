"use client"

import { useEffect, useState } from "react"
import { getAccountGroups, createAccountGroup } from "@/actions/account-group-actions"
import { getAccounts } from "@/actions/settings-actions"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue, SelectGroup, SelectLabel, SelectSeparator } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Plus } from "lucide-react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"

interface AccountGroupSelectorProps {
    // Old props for backward compat, but we'll try to move to new ones
    // value?: string 
    // onChange: (value: string) => void
    
    // New props pattern
    selectedType: 'all' | 'group' | 'account'
    selectedId?: string
    onScopeChange: (type: 'all' | 'group' | 'account', id?: string) => void
}

export function AccountGroupSelector({ selectedType, selectedId, onScopeChange }: AccountGroupSelectorProps) {
    const [groups, setGroups] = useState<any[]>([])
    const [accounts, setAccounts] = useState<any[]>([])
    const [open, setOpen] = useState(false)
    const [newGroupName, setNewGroupName] = useState("")

    useEffect(() => {
        loadData()
    }, [])

    async function loadData() {
        const [groupsRes, accountsRes] = await Promise.all([
            getAccountGroups(),
            getAccounts()
        ])
        
        if (groupsRes.success && groupsRes.data) {
            setGroups(groupsRes.data)
        }
        if (accountsRes.success && accountsRes.data) {
            setAccounts(accountsRes.data)
        }
    }

    async function handleCreateGroup() {
        if (!newGroupName.trim()) return
        const res = await createAccountGroup(newGroupName)
        if (res.success) {
            setNewGroupName("")
            setOpen(false)
            loadData()
        }
    }

    // Construct internal value string: "prefix:id"
    const internalValue = selectedType === 'all' ? 'all' : `${selectedType}:${selectedId}`

    const handleValueChange = (val: string) => {
        if (val === 'all') {
            onScopeChange('all')
        } else {
            const [type, id] = val.split(':')
            onScopeChange(type as 'group' | 'account', id)
        }
    }

    return (
        <div className="flex items-center gap-2">
            <Select value={internalValue} onValueChange={handleValueChange}>
                <SelectTrigger className="w-[200px]">
                    <SelectValue placeholder="Select Scope" />
                </SelectTrigger>
                <SelectContent>
                    <SelectItem value="all">All Accounts</SelectItem>
                    
                    <SelectSeparator />
                    
                    <SelectGroup>
                        <SelectLabel>Account Groups</SelectLabel>
                        {groups.map(g => (
                            <SelectItem key={g.id} value={`group:${g.id}`}>
                                📁 {g.name}
                            </SelectItem>
                        ))}
                    </SelectGroup>

                    <SelectSeparator />

                    <SelectGroup>
                        <SelectLabel>Single Accounts</SelectLabel>
                        {accounts.map(a => (
                            <SelectItem key={a.id} value={`account:${a.id}`}>
                                👤 {a.name}
                            </SelectItem>
                        ))}
                    </SelectGroup>
                </SelectContent>
            </Select>
            <Dialog open={open} onOpenChange={setOpen}>
                <DialogTrigger asChild>
                    <Button variant="outline" size="icon" title="New Group">
                        <Plus className="h-4 w-4" />
                    </Button>
                </DialogTrigger>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>Create Account Group</DialogTitle>
                    </DialogHeader>
                    <div className="space-y-4 py-4">
                        <div className="space-y-2">
                            <Label>Group Name</Label>
                            <Input 
                                placeholder="e.g. Topstep Futures" 
                                value={newGroupName}
                                onChange={(e) => setNewGroupName(e.target.value)}
                            />
                        </div>
                        <Button onClick={handleCreateGroup} className="w-full">Create Group</Button>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    )
}
