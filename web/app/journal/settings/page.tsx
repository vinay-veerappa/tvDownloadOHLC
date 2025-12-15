"use client"

import { useState, useEffect } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import { Separator } from "@/components/ui/separator"
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
    AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import {
    Settings, Users, Target, Tag, Trash2, Download, Plus, Pencil, AlertTriangle,
    TrendingUp, Wallet, BarChart3, ChevronLeft, Calendar
} from "lucide-react"
import Link from "next/link"
import {
    getAccounts, createAccount, updateAccount, deleteAccount,
    getStrategies, createStrategy, updateStrategy, deleteStrategy,
    getTags, createTag, deleteTag, getTagGroups,
    getOverviewStats, deleteAllTrades, deleteTradesByDateRange, deleteTradesByAccount,
    exportAllData
} from "@/actions/settings-actions"

export default function SettingsPage() {
    const [activeTab, setActiveTab] = useState("overview")
    const [stats, setStats] = useState<any>(null)
    const [accounts, setAccounts] = useState<any[]>([])
    const [strategies, setStrategies] = useState<any[]>([])
    const [tags, setTags] = useState<any[]>([])
    const [tagGroups, setTagGroups] = useState<any[]>([])
    const [loading, setLoading] = useState(true)

    // Form states
    const [newAccountName, setNewAccountName] = useState("")
    const [newAccountBalance, setNewAccountBalance] = useState("")
    const [newStrategyName, setNewStrategyName] = useState("")
    const [newTagName, setNewTagName] = useState("")
    const [newTagGroupId, setNewTagGroupId] = useState("")

    // Delete states
    const [deleteStartDate, setDeleteStartDate] = useState("")
    const [deleteEndDate, setDeleteEndDate] = useState("")
    const [selectedAccountForDelete, setSelectedAccountForDelete] = useState("")

    const loadData = async () => {
        setLoading(true)
        try {
            const [statsRes, accountsRes, strategiesRes, tagsRes, groupsRes] = await Promise.all([
                getOverviewStats(),
                getAccounts(),
                getStrategies(),
                getTags(),
                getTagGroups()
            ])

            if (statsRes.success && statsRes.data) setStats(statsRes.data)
            if (accountsRes.success && accountsRes.data) setAccounts(accountsRes.data)
            if (strategiesRes.success && strategiesRes.data) setStrategies(strategiesRes.data)
            if (tagsRes.success && tagsRes.data) setTags(tagsRes.data)
            if (groupsRes.success && groupsRes.data) setTagGroups(groupsRes.data)
        } catch (error) {
            console.error("Failed to load settings data", error)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        loadData()
    }, [])

    // Account handlers
    const handleCreateAccount = async () => {
        if (!newAccountName.trim()) return
        await createAccount({
            name: newAccountName,
            initialBalance: parseFloat(newAccountBalance) || 0
        })
        setNewAccountName("")
        setNewAccountBalance("")
        loadData()
    }

    const handleDeleteAccount = async (id: string) => {
        const result = await deleteAccount(id)
        if (!result.success) {
            alert(result.error)
        }
        loadData()
    }

    // Strategy handlers
    const handleCreateStrategy = async () => {
        if (!newStrategyName.trim()) return
        await createStrategy({ name: newStrategyName })
        setNewStrategyName("")
        loadData()
    }

    const handleDeleteStrategy = async (id: string) => {
        const result = await deleteStrategy(id)
        if (!result.success) {
            alert(result.error)
        }
        loadData()
    }

    // Tag handlers
    const handleCreateTag = async () => {
        if (!newTagName.trim()) return
        await createTag({ name: newTagName, groupId: newTagGroupId })
        setNewTagName("")
        loadData()
    }

    const handleDeleteTag = async (id: string) => {
        await deleteTag(id)
        loadData()
    }

    // Data management handlers
    const handleDeleteAllTrades = async () => {
        const result = await deleteAllTrades()
        if (result.success) {
            alert(`Deleted ${result.deletedCount} trades`)
        }
        loadData()
    }

    const handleDeleteByDateRange = async () => {
        if (!deleteStartDate || !deleteEndDate) return
        const result = await deleteTradesByDateRange(
            new Date(deleteStartDate),
            new Date(deleteEndDate)
        )
        if (result.success) {
            alert(`Deleted ${result.deletedCount} trades`)
        }
        setDeleteStartDate("")
        setDeleteEndDate("")
        loadData()
    }

    const handleDeleteByAccount = async () => {
        if (!selectedAccountForDelete) return
        const result = await deleteTradesByAccount(selectedAccountForDelete)
        if (result.success) {
            alert(`Deleted ${result.deletedCount} trades`)
        }
        setSelectedAccountForDelete("")
        loadData()
    }

    const handleExportData = async () => {
        const result = await exportAllData()
        if (result.success && result.data) {
            const blob = new Blob([JSON.stringify(result.data, null, 2)], { type: 'application/json' })
            const url = URL.createObjectURL(blob)
            const a = document.createElement('a')
            a.href = url
            a.download = `journal-backup-${new Date().toISOString().split('T')[0]}.json`
            a.click()
            URL.revokeObjectURL(url)
        }
    }

    // Group tags by category
    const tagsByGroup = tags.reduce((acc: Record<string, any[]>, tag) => {
        const groupName = tag.group?.name || 'General'
        if (!acc[groupName]) acc[groupName] = []
        acc[groupName].push(tag)
        return acc
    }, {})

    if (loading) {
        return <div className="flex items-center justify-center h-screen">Loading settings...</div>
    }

    return (
        <div className="container max-w-5xl mx-auto py-6 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                    <Link href="/journal">
                        <Button variant="ghost" size="icon">
                            <ChevronLeft className="h-5 w-5" />
                        </Button>
                    </Link>
                    <div>
                        <h1 className="text-3xl font-bold flex items-center gap-2">
                            <Settings className="h-7 w-7" />
                            Journal Settings
                        </h1>
                        <p className="text-muted-foreground">Manage accounts, strategies, tags, and data</p>
                    </div>
                </div>
            </div>

            <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="grid w-full grid-cols-5">
                    <TabsTrigger value="overview" className="flex items-center gap-2">
                        <BarChart3 className="h-4 w-4" /> Overview
                    </TabsTrigger>
                    <TabsTrigger value="accounts" className="flex items-center gap-2">
                        <Wallet className="h-4 w-4" /> Accounts
                    </TabsTrigger>
                    <TabsTrigger value="strategies" className="flex items-center gap-2">
                        <Target className="h-4 w-4" /> Strategies
                    </TabsTrigger>
                    <TabsTrigger value="tags" className="flex items-center gap-2">
                        <Tag className="h-4 w-4" /> Tags
                    </TabsTrigger>
                    <TabsTrigger value="data" className="flex items-center gap-2">
                        <Trash2 className="h-4 w-4" /> Data
                    </TabsTrigger>
                </TabsList>

                {/* Overview Tab */}
                <TabsContent value="overview" className="space-y-6">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        <Card>
                            <CardHeader className="pb-2">
                                <CardDescription>Total Trades</CardDescription>
                                <CardTitle className="text-3xl">{stats?.tradeCount || 0}</CardTitle>
                            </CardHeader>
                        </Card>
                        <Card>
                            <CardHeader className="pb-2">
                                <CardDescription>Accounts</CardDescription>
                                <CardTitle className="text-3xl">{stats?.accountCount || 0}</CardTitle>
                            </CardHeader>
                        </Card>
                        <Card>
                            <CardHeader className="pb-2">
                                <CardDescription>Strategies</CardDescription>
                                <CardTitle className="text-3xl">{stats?.strategyCount || 0}</CardTitle>
                            </CardHeader>
                        </Card>
                        <Card>
                            <CardHeader className="pb-2">
                                <CardDescription>Tags</CardDescription>
                                <CardTitle className="text-3xl">{stats?.tagCount || 0}</CardTitle>
                            </CardHeader>
                        </Card>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                        <Card>
                            <CardHeader className="pb-2">
                                <CardDescription>Total P&L</CardDescription>
                                <CardTitle className={`text-2xl ${(stats?.totalPnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                    ${(stats?.totalPnl || 0).toFixed(2)}
                                </CardTitle>
                            </CardHeader>
                        </Card>
                        <Card>
                            <CardHeader className="pb-2">
                                <CardDescription>Win Rate</CardDescription>
                                <CardTitle className="text-2xl">{(stats?.winRate || 0).toFixed(1)}%</CardTitle>
                            </CardHeader>
                        </Card>
                        <Card>
                            <CardHeader className="pb-2">
                                <CardDescription>W/L Ratio</CardDescription>
                                <CardTitle className="text-2xl">
                                    {stats?.winningTrades || 0} / {stats?.losingTrades || 0}
                                </CardTitle>
                            </CardHeader>
                        </Card>
                    </div>
                </TabsContent>

                {/* Accounts Tab */}
                <TabsContent value="accounts" className="space-y-6">
                    <Card>
                        <CardHeader>
                            <CardTitle>Add Account</CardTitle>
                        </CardHeader>
                        <CardContent className="flex gap-4">
                            <Input
                                placeholder="Account name"
                                value={newAccountName}
                                onChange={(e) => setNewAccountName(e.target.value)}
                            />
                            <Input
                                type="number"
                                placeholder="Starting balance"
                                value={newAccountBalance}
                                onChange={(e) => setNewAccountBalance(e.target.value)}
                                className="w-40"
                            />
                            <Button onClick={handleCreateAccount}>
                                <Plus className="h-4 w-4 mr-2" /> Add
                            </Button>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Your Accounts</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-3">
                                {accounts.length === 0 ? (
                                    <p className="text-muted-foreground text-center py-4">No accounts yet</p>
                                ) : (
                                    accounts.map((account) => (
                                        <div key={account.id} className="flex items-center justify-between p-3 border rounded-lg">
                                            <div>
                                                <p className="font-medium">{account.name}</p>
                                                <p className="text-sm text-muted-foreground">
                                                    Balance: ${account.balance?.toFixed(2) || '0.00'} • {account._count?.trades || 0} trades
                                                </p>
                                            </div>
                                            <AlertDialog>
                                                <AlertDialogTrigger asChild>
                                                    <Button variant="ghost" size="icon">
                                                        <Trash2 className="h-4 w-4 text-destructive" />
                                                    </Button>
                                                </AlertDialogTrigger>
                                                <AlertDialogContent>
                                                    <AlertDialogHeader>
                                                        <AlertDialogTitle>Delete Account?</AlertDialogTitle>
                                                        <AlertDialogDescription>
                                                            This will delete the account "{account.name}". Accounts with trades cannot be deleted.
                                                        </AlertDialogDescription>
                                                    </AlertDialogHeader>
                                                    <AlertDialogFooter>
                                                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                                                        <AlertDialogAction onClick={() => handleDeleteAccount(account.id)}>
                                                            Delete
                                                        </AlertDialogAction>
                                                    </AlertDialogFooter>
                                                </AlertDialogContent>
                                            </AlertDialog>
                                        </div>
                                    ))
                                )}
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Strategies Tab */}
                <TabsContent value="strategies" className="space-y-6">
                    <Card>
                        <CardHeader>
                            <CardTitle>Add Strategy</CardTitle>
                        </CardHeader>
                        <CardContent className="flex gap-4">
                            <Input
                                placeholder="Strategy name"
                                value={newStrategyName}
                                onChange={(e) => setNewStrategyName(e.target.value)}
                                className="flex-1"
                            />
                            <Button onClick={handleCreateStrategy}>
                                <Plus className="h-4 w-4 mr-2" /> Add
                            </Button>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Your Strategies</CardTitle>
                        </CardHeader>
                        <CardContent>
                            <div className="space-y-3">
                                {strategies.length === 0 ? (
                                    <p className="text-muted-foreground text-center py-4">No strategies yet</p>
                                ) : (
                                    strategies.map((strategy) => (
                                        <div key={strategy.id} className="flex items-center justify-between p-3 border rounded-lg">
                                            <div>
                                                <p className="font-medium">{strategy.name}</p>
                                                {strategy.description && (
                                                    <p className="text-sm text-muted-foreground">{strategy.description}</p>
                                                )}
                                            </div>
                                            <AlertDialog>
                                                <AlertDialogTrigger asChild>
                                                    <Button variant="ghost" size="icon">
                                                        <Trash2 className="h-4 w-4 text-destructive" />
                                                    </Button>
                                                </AlertDialogTrigger>
                                                <AlertDialogContent>
                                                    <AlertDialogHeader>
                                                        <AlertDialogTitle>Delete Strategy?</AlertDialogTitle>
                                                        <AlertDialogDescription>
                                                            This will delete the strategy "{strategy.name}". Strategies with linked trades cannot be deleted.
                                                        </AlertDialogDescription>
                                                    </AlertDialogHeader>
                                                    <AlertDialogFooter>
                                                        <AlertDialogCancel>Cancel</AlertDialogCancel>
                                                        <AlertDialogAction onClick={() => handleDeleteStrategy(strategy.id)}>
                                                            Delete
                                                        </AlertDialogAction>
                                                    </AlertDialogFooter>
                                                </AlertDialogContent>
                                            </AlertDialog>
                                        </div>
                                    ))
                                )}
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Tags Tab */}
                <TabsContent value="tags" className="space-y-6">
                    <Card>
                        <CardHeader>
                            <CardTitle>Add Tag</CardTitle>
                        </CardHeader>
                        <CardContent className="flex gap-4">
                            <Input
                                placeholder="Tag name"
                                value={newTagName}
                                onChange={(e) => setNewTagName(e.target.value)}
                                className="flex-1"
                            />
                            <Select value={newTagGroupId} onValueChange={setNewTagGroupId}>
                                <SelectTrigger className="w-40">
                                    <SelectValue placeholder="Select Group" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="none">No Group</SelectItem>
                                    {tagGroups.map((group) => (
                                        <SelectItem key={group.id} value={group.id}>
                                            {group.name}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                            <Button onClick={handleCreateTag}>
                                <Plus className="h-4 w-4 mr-2" /> Add
                            </Button>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader>
                            <CardTitle>Your Tags</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {Object.keys(tagsByGroup).length === 0 ? (
                                <p className="text-muted-foreground text-center py-4">No tags yet</p>
                            ) : (
                                <div className="space-y-6">
                                    {Object.entries(tagsByGroup).map(([group, groupTags]) => (
                                        <div key={group}>
                                            <h4 className="text-sm font-medium mb-2 capitalize">{group}</h4>
                                            <div className="flex flex-wrap gap-2">
                                                {(groupTags as any[]).map((tag) => (
                                                    <Badge key={tag.id} variant="secondary" className="flex items-center gap-1">
                                                        {tag.name}
                                                        <button onClick={() => handleDeleteTag(tag.id)} className="ml-1 hover:text-destructive">
                                                            ×
                                                        </button>
                                                    </Badge>
                                                ))}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </TabsContent>

                {/* Data Tab */}
                <TabsContent value="data" className="space-y-6">
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Download className="h-5 w-5" /> Export Data
                            </CardTitle>
                            <CardDescription>Download a backup of all your journal data</CardDescription>
                        </CardHeader>
                        <CardContent>
                            <Button onClick={handleExportData}>
                                <Download className="h-4 w-4 mr-2" /> Export JSON Backup
                            </Button>
                        </CardContent>
                    </Card>

                    <Card className="border-destructive/50">
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2 text-destructive">
                                <AlertTriangle className="h-5 w-5" /> Danger Zone
                            </CardTitle>
                            <CardDescription>These actions cannot be undone</CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-6">
                            {/* Delete by Date Range */}
                            <div className="p-4 border rounded-lg space-y-3">
                                <h4 className="font-medium flex items-center gap-2">
                                    <Calendar className="h-4 w-4" /> Delete by Date Range
                                </h4>
                                <div className="flex gap-4">
                                    <div className="flex-1">
                                        <Label>Start Date</Label>
                                        <Input
                                            type="date"
                                            value={deleteStartDate}
                                            onChange={(e) => setDeleteStartDate(e.target.value)}
                                        />
                                    </div>
                                    <div className="flex-1">
                                        <Label>End Date</Label>
                                        <Input
                                            type="date"
                                            value={deleteEndDate}
                                            onChange={(e) => setDeleteEndDate(e.target.value)}
                                        />
                                    </div>
                                </div>
                                <AlertDialog>
                                    <AlertDialogTrigger asChild>
                                        <Button variant="destructive" disabled={!deleteStartDate || !deleteEndDate}>
                                            Delete Trades in Range
                                        </Button>
                                    </AlertDialogTrigger>
                                    <AlertDialogContent>
                                        <AlertDialogHeader>
                                            <AlertDialogTitle>Delete trades in date range?</AlertDialogTitle>
                                            <AlertDialogDescription>
                                                This will permanently delete all trades between {deleteStartDate} and {deleteEndDate}.
                                            </AlertDialogDescription>
                                        </AlertDialogHeader>
                                        <AlertDialogFooter>
                                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                                            <AlertDialogAction onClick={handleDeleteByDateRange}>Delete</AlertDialogAction>
                                        </AlertDialogFooter>
                                    </AlertDialogContent>
                                </AlertDialog>
                            </div>

                            {/* Delete by Account */}
                            <div className="p-4 border rounded-lg space-y-3">
                                <h4 className="font-medium flex items-center gap-2">
                                    <Wallet className="h-4 w-4" /> Delete by Account
                                </h4>
                                <Select value={selectedAccountForDelete} onValueChange={setSelectedAccountForDelete}>
                                    <SelectTrigger>
                                        <SelectValue placeholder="Select account" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {accounts.map((acc) => (
                                            <SelectItem key={acc.id} value={acc.id}>
                                                {acc.name} ({acc._count?.trades || 0} trades)
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                                <AlertDialog>
                                    <AlertDialogTrigger asChild>
                                        <Button variant="destructive" disabled={!selectedAccountForDelete}>
                                            Delete All Trades for Account
                                        </Button>
                                    </AlertDialogTrigger>
                                    <AlertDialogContent>
                                        <AlertDialogHeader>
                                            <AlertDialogTitle>Delete all trades for this account?</AlertDialogTitle>
                                            <AlertDialogDescription>
                                                This will permanently delete all trades associated with this account.
                                            </AlertDialogDescription>
                                        </AlertDialogHeader>
                                        <AlertDialogFooter>
                                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                                            <AlertDialogAction onClick={handleDeleteByAccount}>Delete</AlertDialogAction>
                                        </AlertDialogFooter>
                                    </AlertDialogContent>
                                </AlertDialog>
                            </div>

                            <Separator />

                            {/* Delete ALL */}
                            <div className="p-4 border border-destructive rounded-lg space-y-3">
                                <h4 className="font-medium text-destructive">Delete ALL Trades</h4>
                                <p className="text-sm text-muted-foreground">
                                    This will permanently delete all {stats?.tradeCount || 0} trades from your journal.
                                </p>
                                <AlertDialog>
                                    <AlertDialogTrigger asChild>
                                        <Button variant="destructive">
                                            <Trash2 className="h-4 w-4 mr-2" /> Delete All Trades
                                        </Button>
                                    </AlertDialogTrigger>
                                    <AlertDialogContent>
                                        <AlertDialogHeader>
                                            <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
                                            <AlertDialogDescription>
                                                This action cannot be undone. This will permanently delete all {stats?.tradeCount || 0} trades
                                                and their associated data.
                                            </AlertDialogDescription>
                                        </AlertDialogHeader>
                                        <AlertDialogFooter>
                                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                                            <AlertDialogAction onClick={handleDeleteAllTrades} className="bg-destructive">
                                                Yes, Delete All
                                            </AlertDialogAction>
                                        </AlertDialogFooter>
                                    </AlertDialogContent>
                                </AlertDialog>
                            </div>
                        </CardContent>
                    </Card>
                </TabsContent>
            </Tabs>
        </div>
    )
}
