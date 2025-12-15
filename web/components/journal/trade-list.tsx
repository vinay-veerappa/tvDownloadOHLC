"use client"

import { useEffect, useState, useMemo } from "react"
import { useRouter } from "next/navigation"
import { getTrades } from "@/actions/trade-actions"
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select"
import { format } from "date-fns"
import { ChevronUp, ChevronDown, ChevronLeft, ChevronRight, X } from "lucide-react"

interface Trade {
    id: string
    symbol: string
    direction: string
    entryDate: Date | string
    entryPrice: number | null
    exitPrice: number | null
    quantity: number
    status: string
    pnl: number | null
}

type SortKey = "entryDate" | "symbol" | "pnl" | "quantity"
type SortOrder = "asc" | "desc"

const ITEMS_PER_PAGE = 20

export function TradeList() {
    const router = useRouter()
    const [trades, setTrades] = useState<Trade[]>([])
    const [loading, setLoading] = useState(true)

    // Filters
    const [tickerFilter, setTickerFilter] = useState("")
    const [statusFilter, setStatusFilter] = useState<string>("all")
    const [directionFilter, setDirectionFilter] = useState<string>("all")
    const [startDate, setStartDate] = useState("")
    const [endDate, setEndDate] = useState("")

    // Sorting
    const [sortKey, setSortKey] = useState<SortKey>("entryDate")
    const [sortOrder, setSortOrder] = useState<SortOrder>("desc")

    // Pagination
    const [currentPage, setCurrentPage] = useState(1)

    useEffect(() => {
        async function loadTrades() {
            const result = await getTrades()
            if (result.success && result.data) {
                setTrades(result.data)
            }
            setLoading(false)
        }
        loadTrades()
    }, [])

    // Filter and sort trades
    const filteredTrades = useMemo(() => {
        let result = [...trades]

        // Apply filters
        if (tickerFilter) {
            result = result.filter(t =>
                t.symbol.toLowerCase().includes(tickerFilter.toLowerCase())
            )
        }
        if (statusFilter !== "all") {
            result = result.filter(t => t.status === statusFilter)
        }
        if (directionFilter !== "all") {
            result = result.filter(t => t.direction === directionFilter)
        }
        if (startDate) {
            result = result.filter(t =>
                new Date(t.entryDate) >= new Date(startDate)
            )
        }
        if (endDate) {
            result = result.filter(t =>
                new Date(t.entryDate) <= new Date(endDate + "T23:59:59")
            )
        }

        // Apply sorting
        result.sort((a, b) => {
            let comparison = 0
            switch (sortKey) {
                case "entryDate":
                    comparison = new Date(a.entryDate).getTime() - new Date(b.entryDate).getTime()
                    break
                case "symbol":
                    comparison = a.symbol.localeCompare(b.symbol)
                    break
                case "pnl":
                    comparison = (a.pnl || 0) - (b.pnl || 0)
                    break
                case "quantity":
                    comparison = a.quantity - b.quantity
                    break
            }
            return sortOrder === "asc" ? comparison : -comparison
        })

        return result
    }, [trades, tickerFilter, statusFilter, directionFilter, startDate, endDate, sortKey, sortOrder])

    // Paginate
    const totalPages = Math.ceil(filteredTrades.length / ITEMS_PER_PAGE)
    const paginatedTrades = filteredTrades.slice(
        (currentPage - 1) * ITEMS_PER_PAGE,
        currentPage * ITEMS_PER_PAGE
    )

    const handleSort = (key: SortKey) => {
        if (sortKey === key) {
            setSortOrder(sortOrder === "asc" ? "desc" : "asc")
        } else {
            setSortKey(key)
            setSortOrder("desc")
        }
    }

    const SortIcon = ({ column }: { column: SortKey }) => {
        if (sortKey !== column) return null
        return sortOrder === "asc" ?
            <ChevronUp className="h-3 w-3 ml-1 inline" /> :
            <ChevronDown className="h-3 w-3 ml-1 inline" />
    }

    const clearFilters = () => {
        setTickerFilter("")
        setStatusFilter("all")
        setDirectionFilter("all")
        setStartDate("")
        setEndDate("")
        setCurrentPage(1)
    }

    const hasActiveFilters = tickerFilter || statusFilter !== "all" ||
        directionFilter !== "all" || startDate || endDate

    if (loading) {
        return <div className="p-8 text-center text-muted-foreground">Loading trades...</div>
    }

    return (
        <div className="space-y-4">
            {/* Filters */}
            <div className="flex flex-wrap gap-3 items-end">
                <div className="flex-1 min-w-[120px] max-w-[200px]">
                    <Input
                        placeholder="Filter by ticker..."
                        value={tickerFilter}
                        onChange={(e) => { setTickerFilter(e.target.value); setCurrentPage(1) }}
                        className="h-9"
                    />
                </div>
                <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v); setCurrentPage(1) }}>
                    <SelectTrigger className="w-[130px] h-9">
                        <SelectValue placeholder="Status" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Status</SelectItem>
                        <SelectItem value="OPEN">Open</SelectItem>
                        <SelectItem value="CLOSED">Closed</SelectItem>
                        <SelectItem value="PENDING">Pending</SelectItem>
                    </SelectContent>
                </Select>
                <Select value={directionFilter} onValueChange={(v) => { setDirectionFilter(v); setCurrentPage(1) }}>
                    <SelectTrigger className="w-[130px] h-9">
                        <SelectValue placeholder="Direction" />
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="all">All Direction</SelectItem>
                        <SelectItem value="LONG">Long</SelectItem>
                        <SelectItem value="SHORT">Short</SelectItem>
                    </SelectContent>
                </Select>
                <Input
                    type="date"
                    value={startDate}
                    onChange={(e) => { setStartDate(e.target.value); setCurrentPage(1) }}
                    className="w-[140px] h-9"
                />
                <span className="text-muted-foreground">to</span>
                <Input
                    type="date"
                    value={endDate}
                    onChange={(e) => { setEndDate(e.target.value); setCurrentPage(1) }}
                    className="w-[140px] h-9"
                />
                {hasActiveFilters && (
                    <Button variant="ghost" size="sm" onClick={clearFilters} className="h-9">
                        <X className="h-4 w-4 mr-1" /> Clear
                    </Button>
                )}
            </div>

            {/* Results count */}
            <div className="text-sm text-muted-foreground">
                {filteredTrades.length} trade{filteredTrades.length !== 1 ? "s" : ""} found
            </div>

            {/* Table */}
            <div className="rounded-md border">
                <Table>
                    <TableHeader>
                        <TableRow>
                            <TableHead
                                className="cursor-pointer hover:bg-muted/50"
                                onClick={() => handleSort("entryDate")}
                            >
                                Date <SortIcon column="entryDate" />
                            </TableHead>
                            <TableHead
                                className="cursor-pointer hover:bg-muted/50"
                                onClick={() => handleSort("symbol")}
                            >
                                Symbol <SortIcon column="symbol" />
                            </TableHead>
                            <TableHead>Direction</TableHead>
                            <TableHead>Entry</TableHead>
                            <TableHead>Exit</TableHead>
                            <TableHead
                                className="cursor-pointer hover:bg-muted/50"
                                onClick={() => handleSort("quantity")}
                            >
                                Qty <SortIcon column="quantity" />
                            </TableHead>
                            <TableHead>Status</TableHead>
                            <TableHead
                                className="text-right cursor-pointer hover:bg-muted/50"
                                onClick={() => handleSort("pnl")}
                            >
                                PnL <SortIcon column="pnl" />
                            </TableHead>
                        </TableRow>
                    </TableHeader>
                    <TableBody>
                        {paginatedTrades.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={8} className="h-24 text-center">
                                    {trades.length === 0 ? "No trades recorded." : "No trades match filters."}
                                </TableCell>
                            </TableRow>
                        ) : (
                            paginatedTrades.map((trade) => (
                                <TableRow
                                    key={trade.id}
                                    className="cursor-pointer hover:bg-muted/50"
                                    onClick={() => router.push(`/journal/trade/${trade.id}`)}
                                >
                                    <TableCell>{format(new Date(trade.entryDate), "MMM d, yyyy")}</TableCell>
                                    <TableCell className="font-medium">{trade.symbol}</TableCell>
                                    <TableCell>
                                        <Badge variant={trade.direction === "LONG" ? "default" : "destructive"}>
                                            {trade.direction}
                                        </Badge>
                                    </TableCell>
                                    <TableCell>{trade.entryPrice?.toFixed(2) || "-"}</TableCell>
                                    <TableCell>{trade.exitPrice?.toFixed(2) || "-"}</TableCell>
                                    <TableCell>{trade.quantity}</TableCell>
                                    <TableCell>
                                        <Badge variant="outline">{trade.status}</Badge>
                                    </TableCell>
                                    <TableCell className={`text-right font-mono ${trade.pnl && trade.pnl > 0 ? "text-green-500" : trade.pnl && trade.pnl < 0 ? "text-red-500" : ""}`}>
                                        {trade.pnl ? `$${trade.pnl.toFixed(2)}` : "-"}
                                    </TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
                <div className="flex items-center justify-between">
                    <div className="text-sm text-muted-foreground">
                        Page {currentPage} of {totalPages}
                    </div>
                    <div className="flex gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                            disabled={currentPage === 1}
                        >
                            <ChevronLeft className="h-4 w-4" />
                        </Button>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                            disabled={currentPage === totalPages}
                        >
                            <ChevronRight className="h-4 w-4" />
                        </Button>
                    </div>
                </div>
            )}
        </div>
    )
}

