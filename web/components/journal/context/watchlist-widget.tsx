"use client"

import { useState, useEffect } from "react"
import { YahooQuote } from "@/lib/yahoo-finance"
import {
    addToWatchlist,
    removeFromWatchlist,
    searchTicker,
    seedDefaultWatchlist,
    getWatchlistGroups,
    getWatchlistItems,
    createWatchlistGroup,
    deleteWatchlistGroup
} from "@/actions/watchlist-actions"
import { getLatestQuotes } from "@/actions/context-actions"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
    Plus, Trash2, TrendingUp, TrendingDown,
    List, RefreshCw, FolderPlus, FolderX, Folder
} from "lucide-react"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "@/components/ui/dialog"

interface WatchlistWidgetProps {
    initialGroups?: any[]
    initialItems?: any[]
    initialQuotes?: YahooQuote[]
}

export function WatchlistWidget({ }: WatchlistWidgetProps) {
    // State
    const [groups, setGroups] = useState<any[]>([])
    const [selectedGroupId, setSelectedGroupId] = useState<string>("")
    const [items, setItems] = useState<any[]>([])
    const [quotes, setQuotes] = useState<YahooQuote[]>([])

    // UI State
    const [loading, setLoading] = useState(false)
    const [searchQuery, setSearchQuery] = useState("")
    const [searchResults, setSearchResults] = useState<any[]>([])
    const [showResults, setShowResults] = useState(false)

    // Dialogs
    const [newGroupName, setNewGroupName] = useState("")
    const [isCreateOpen, setIsCreateOpen] = useState(false)

    // 1. Load Groups on Mount
    useEffect(() => {
        loadGroups()
    }, [])

    const loadGroups = async () => {
        setLoading(true)
        const res = await getWatchlistGroups()
        if (res.success && res.data && res.data.length > 0) {
            setGroups(res.data)
            // Select Default or First
            const defaultGroup = res.data.find((g: any) => g.isDefault) || res.data[0]
            setSelectedGroupId(defaultGroup.id)
        } else {
            // If absolutely no groups, seed default?
            // UI will show empty state
            setGroups([])
        }
        setLoading(false)
    }

    // 2. Load Items when Group Changes
    useEffect(() => {
        if (!selectedGroupId) {
            setItems([])
            return
        }
        loadItems(selectedGroupId)
    }, [selectedGroupId])

    const loadItems = async (groupId: string) => {
        setLoading(true)
        const res = await getWatchlistItems(groupId)
        if (res.success && res.data) {
            setItems(res.data)
            await fetchQuotes(res.data)
        }
        setLoading(false)
    }

    const fetchQuotes = async (currentItems: any[]) => {
        if (currentItems.length === 0) {
            setQuotes([])
            return
        }
        try {
            const symbols = currentItems.map(w => w.symbol)
            const res = await getLatestQuotes(symbols)
            if (res.success && res.data) {
                setQuotes(res.data)
            }
        } catch (error) {
            console.error("Failed to refresh quotes", error)
        }
    }

    // --- Actions ---

    const handleCreateGroup = async () => {
        if (!newGroupName.trim()) return
        const res = await createWatchlistGroup(newGroupName)
        if (res.success && res.data) {
            setGroups([...groups, res.data])
            setSelectedGroupId(res.data.id)
            setIsCreateOpen(false)
            setNewGroupName("")
        }
    }

    const handleDeleteGroup = async () => {
        if (!selectedGroupId) return
        if (!confirm("Delete this entire watchlist?")) return

        await deleteWatchlistGroup(selectedGroupId)
        // Refresh groups
        loadGroups() // Re-fetch to be safe
    }

    const handleSelectTicker = async (symbol: string) => {
        setSearchQuery("")
        setShowResults(false)
        if (!selectedGroupId) return // Should not happen if UI handles it

        await addToWatchlist(symbol, selectedGroupId)
        loadItems(selectedGroupId)
    }

    const handleRemoveItem = async (id: string) => {
        await removeFromWatchlist(id)
        loadItems(selectedGroupId)
    }

    const handleSeed = async () => {
        setLoading(true)
        await seedDefaultWatchlist()
        await loadGroups() // Should find Default now
    }

    // Search Logic
    useEffect(() => {
        const timer = setTimeout(async () => {
            if (searchQuery.length >= 2) {
                const res = await searchTicker(searchQuery)
                if (res.success && res.data) {
                    setSearchResults(res.data)
                    setShowResults(true)
                }
            } else {
                setSearchResults([])
                setShowResults(false)
            }
        }, 500)
        return () => clearTimeout(timer)
    }, [searchQuery])

    // Merge for Display
    const displayItems = items.map(item => {
        const quote = quotes.find(q => q.symbol === item.symbol)
        return { ...item, quote }
    })

    const selectedGroup = groups.find(g => g.id === selectedGroupId)

    return (
        <Card className="h-full flex flex-col">
            <CardHeader className="pb-2 space-y-2">
                <div className="flex flex-row items-center justify-between">
                    <CardTitle className="flex items-center gap-2 text-md">
                        <Folder className="h-5 w-5" />
                        Watchlists
                    </CardTitle>
                    <div className="flex gap-1">
                        <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
                            <DialogTrigger asChild>
                                <Button variant="ghost" size="icon" className="h-7 w-7"><FolderPlus className="h-4 w-4" /></Button>
                            </DialogTrigger>
                            <DialogContent>
                                <DialogHeader><DialogTitle>New Watchlist</DialogTitle></DialogHeader>
                                <Input
                                    placeholder="List Name (e.g. High Beta)"
                                    value={newGroupName}
                                    onChange={e => setNewGroupName(e.target.value)}
                                />
                                <DialogFooter>
                                    <Button onClick={handleCreateGroup}>Create</Button>
                                </DialogFooter>
                            </DialogContent>
                        </Dialog>

                        {selectedGroup && !selectedGroup.isDefault && (
                            <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive" onClick={handleDeleteGroup}>
                                <FolderX className="h-4 w-4" />
                            </Button>
                        )}

                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => loadItems(selectedGroupId)}>
                            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                        </Button>
                    </div>
                </div>

                {/* Group Selector */}
                {groups.length > 0 && (
                    <Select value={selectedGroupId} onValueChange={setSelectedGroupId}>
                        <SelectTrigger className="h-8">
                            <SelectValue placeholder="Select List" />
                        </SelectTrigger>
                        <SelectContent>
                            {groups.map((g: any) => (
                                <SelectItem key={g.id} value={g.id}>
                                    {g.name} {g.isDefault && "(Default)"}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                )}
            </CardHeader>

            <CardContent className="space-y-4 flex-1 overflow-hidden flex flex-col pt-0">
                {/* Search Bar */}
                <div className="relative mt-2">
                    <Input
                        placeholder={selectedGroupId ? "Add Symbol..." : "Select a list first"}
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="uppercase h-8"
                        disabled={!selectedGroupId}
                    />
                    {showResults && searchResults.length > 0 && (
                        <div className="absolute top-full left-0 right-0 z-10 bg-background border rounded-md shadow-lg mt-1 max-h-60 overflow-y-auto">
                            {searchResults.map((res: any) => (
                                <button
                                    key={res.symbol}
                                    className="w-full text-left px-3 py-2 hover:bg-muted text-sm flex justify-between items-center"
                                    onClick={() => handleSelectTicker(res.symbol)}
                                >
                                    <span className="font-bold">{res.symbol}</span>
                                    <span className="text-muted-foreground truncate max-w-[150px]">{res.shortname}</span>
                                </button>
                            ))}
                        </div>
                    )}
                </div>

                {/* List Items */}
                <div className="space-y-1 overflow-y-auto flex-1 pr-1">
                    {groups.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-6 gap-2">
                            <p className="text-sm text-muted-foreground">No watchlists found.</p>
                            <Button variant="outline" size="sm" onClick={handleSeed}>
                                <Plus className="h-3 w-3 mr-1" /> Import Defaults
                            </Button>
                        </div>
                    ) : displayItems.length === 0 ? (
                        <p className="text-sm text-muted-foreground text-center py-4">
                            List is empty.
                        </p>
                    ) : (
                        displayItems.map((item) => (
                            <div key={item.id} className="flex items-center justify-between p-2 hover:bg-muted/50 rounded group gap-2 text-sm">
                                <div className="flex flex-col min-w-0 flex-1">
                                    <span className="font-bold">{item.symbol}</span>
                                    <span className="text-[10px] text-muted-foreground line-clamp-1 truncate">{item.name}</span>
                                </div>

                                {item.quote && typeof item.quote.price === 'number' ? (
                                    <div className="text-right shrink-0">
                                        <div className="font-mono">{item.quote.price.toFixed(2)}</div>
                                        <div className={`text-[10px] flex items-center justify-end ${item.quote.change >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                            {item.quote.change >= 0 ? <TrendingUp className="h-3 w-3 mr-1" /> : <TrendingDown className="h-3 w-3 mr-1" />}
                                            {item.quote.changePercent?.toFixed(2)}%
                                        </div>
                                    </div>
                                ) : (
                                    <span className="text-xs text-muted-foreground shrink-0 w-16 text-right">
                                        {item.quote ? "N/A" : "..."}
                                    </span>
                                )}

                                <Button
                                    variant="ghost"
                                    size="icon"
                                    className="h-6 w-6 text-muted-foreground hover:text-destructive shrink-0 opacity-0 group-hover:opacity-100"
                                    onClick={() => handleRemoveItem(item.id)}
                                >
                                    <Trash2 className="h-3 w-3" />
                                </Button>
                            </div>
                        ))
                    )}
                </div>
            </CardContent>
        </Card>
    )
}
