"use client"

import { useState, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Badge } from "@/components/ui/badge"
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter
} from "@/components/ui/dialog"
import {
    Tabs, TabsContent, TabsList, TabsTrigger
} from "@/components/ui/tabs"
import { Download, Upload, FileText, TestTube, Check, AlertCircle } from "lucide-react"
import {
    exportTradesToCsv,
    importTradesFromCsv,
    getBacktestResults,
    importBacktestToJournal
} from "@/actions/csv-actions"

interface BacktestResult {
    id: string
    strategy: string
    ticker: string
    timeframe: string
    totalTrades: number
    winRate: number
    totalPnl: number
    createdAt: string
}

export function ImportExportDialog() {
    const [open, setOpen] = useState(false)
    const [activeTab, setActiveTab] = useState("export")

    // Export state
    const [exporting, setExporting] = useState(false)
    const [exportResult, setExportResult] = useState<string | null>(null)

    // Import state
    const [importing, setImporting] = useState(false)
    const [importResult, setImportResult] = useState<{ success: boolean; message: string } | null>(null)
    const [csvFile, setCsvFile] = useState<File | null>(null)
    const fileInputRef = useRef<HTMLInputElement>(null)

    // Backtest state
    const [backtests, setBacktests] = useState<BacktestResult[]>([])
    const [loadingBacktests, setLoadingBacktests] = useState(false)
    const [importingBacktest, setImportingBacktest] = useState<string | null>(null)

    const handleExport = async () => {
        setExporting(true)
        setExportResult(null)

        const result = await exportTradesToCsv()

        if (result.success && result.data) {
            // Trigger download
            const blob = new Blob([result.data], { type: "text/csv" })
            const url = URL.createObjectURL(blob)
            const a = document.createElement("a")
            a.href = url
            a.download = `trades_export_${new Date().toISOString().split('T')[0]}.csv`
            a.click()
            URL.revokeObjectURL(url)

            setExportResult(`Exported ${result.count} trades`)
        } else {
            setExportResult("Export failed")
        }

        setExporting(false)
    }

    const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0]
        if (file && file.name.endsWith('.csv')) {
            setCsvFile(file)
        }
    }

    const handleImport = async () => {
        if (!csvFile) return

        setImporting(true)
        setImportResult(null)

        const content = await csvFile.text()
        const result = await importTradesFromCsv(content, "default-sim-account")

        if (result.success) {
            setImportResult({
                success: true,
                message: `Imported ${result.imported} trades`
            })
            setCsvFile(null)
            if (fileInputRef.current) fileInputRef.current.value = ""
        } else {
            setImportResult({
                success: false,
                message: result.error || "Import failed"
            })
        }

        setImporting(false)
    }

    const handleLoadBacktests = async () => {
        setLoadingBacktests(true)
        const result = await getBacktestResults()
        if (result.success && result.data) {
            setBacktests(result.data)
        }
        setLoadingBacktests(false)
    }

    const handleImportBacktest = async (backtestId: string) => {
        setImportingBacktest(backtestId)

        const result = await importBacktestToJournal(backtestId)

        if (result.success) {
            setImportResult({
                success: true,
                message: `Backtest imported as: ${'accountName' in result ? result.accountName : 'new account'}`
            })
        } else {
            setImportResult({
                success: false,
                message: result.error || "Import failed"
            })
        }

        setImportingBacktest(null)
    }

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button variant="outline" size="sm">
                    <FileText className="h-4 w-4 mr-2" />
                    Import/Export
                </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
                <DialogHeader>
                    <DialogTitle>Import & Export Trades</DialogTitle>
                </DialogHeader>

                <Tabs value={activeTab} onValueChange={setActiveTab}>
                    <TabsList className="grid w-full grid-cols-3">
                        <TabsTrigger value="export">
                            <Download className="h-4 w-4 mr-2" />
                            Export CSV
                        </TabsTrigger>
                        <TabsTrigger value="import">
                            <Upload className="h-4 w-4 mr-2" />
                            Import CSV
                        </TabsTrigger>
                        <TabsTrigger value="backtest" onClick={handleLoadBacktests}>
                            <TestTube className="h-4 w-4 mr-2" />
                            Backtests
                        </TabsTrigger>
                    </TabsList>

                    {/* Export Tab */}
                    <TabsContent value="export" className="space-y-4">
                        <p className="text-sm text-muted-foreground">
                            Export all your trades to a CSV file for backup or analysis in other tools.
                        </p>
                        <Button onClick={handleExport} disabled={exporting}>
                            {exporting ? "Exporting..." : "Download CSV"}
                        </Button>
                        {exportResult && (
                            <p className="text-sm text-green-500">✓ {exportResult}</p>
                        )}
                    </TabsContent>

                    {/* Import Tab */}
                    <TabsContent value="import" className="space-y-4">
                        <p className="text-sm text-muted-foreground">
                            Import trades from a CSV file. Required columns: ticker, direction, entryDate, entryPrice
                        </p>
                        <div className="space-y-2">
                            <Label>Select CSV File</Label>
                            <Input
                                type="file"
                                accept=".csv"
                                ref={fileInputRef}
                                onChange={handleFileSelect}
                            />
                        </div>
                        {csvFile && (
                            <p className="text-sm text-muted-foreground">
                                Selected: {csvFile.name}
                            </p>
                        )}
                        <Button
                            onClick={handleImport}
                            disabled={!csvFile || importing}
                        >
                            {importing ? "Importing..." : "Import Trades"}
                        </Button>
                        {importResult && (
                            <p className={`text-sm ${importResult.success ? "text-green-500" : "text-red-500"}`}>
                                {importResult.success ? "✓" : "✗"} {importResult.message}
                            </p>
                        )}
                    </TabsContent>

                    {/* Backtest Tab */}
                    <TabsContent value="backtest" className="space-y-4">
                        <p className="text-sm text-muted-foreground">
                            Import trades from a saved backtest result.
                        </p>
                        {loadingBacktests ? (
                            <p className="text-sm text-muted-foreground">Loading backtests...</p>
                        ) : backtests.length === 0 ? (
                            <p className="text-sm text-muted-foreground">No backtest results found.</p>
                        ) : (
                            <div className="space-y-2 max-h-[300px] overflow-y-auto">
                                {backtests.map(bt => (
                                    <div
                                        key={bt.id}
                                        className="flex items-center justify-between p-3 border rounded-lg"
                                    >
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <span className="font-medium">{bt.strategy}</span>
                                                <Badge variant="secondary">{bt.ticker}</Badge>
                                                <Badge variant="outline">{bt.timeframe}</Badge>
                                            </div>
                                            <p className="text-xs text-muted-foreground">
                                                {bt.totalTrades} trades · {bt.winRate.toFixed(1)}% win ·
                                                ${bt.totalPnl.toFixed(0)} P&L
                                            </p>
                                        </div>
                                        <Button
                                            size="sm"
                                            variant="outline"
                                            onClick={() => handleImportBacktest(bt.id)}
                                            disabled={importingBacktest === bt.id}
                                        >
                                            {importingBacktest === bt.id ? "..." : "Import"}
                                        </Button>
                                    </div>
                                ))}
                            </div>
                        )}
                    </TabsContent>
                </Tabs>
            </DialogContent>
        </Dialog>
    )
}
