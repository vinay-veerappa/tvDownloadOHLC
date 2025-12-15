"use client"

import { useEffect, useState } from "react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Database, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { getDataStatus, DataFileStatus } from "@/actions/datamanager-actions"

export function DataStatusWidget() {
    const [files, setFiles] = useState<DataFileStatus[]>([])
    const [loading, setLoading] = useState(false)
    const [loaded, setLoaded] = useState(false)

    const loadStatus = async () => {
        setLoading(true)
        try {
            const res = await getDataStatus()
            if (res.success && res.data) {
                setFiles(res.data)
            }
        } catch (error) {
            console.error("Failed to fetch status", error)
        } finally {
            setLoading(false)
            setLoaded(true)
        }
    }

    useEffect(() => {
        loadStatus()
    }, [])

    const marketFiles = files.filter(f => f.category === 'Market Data').sort((a, b) => a.name.localeCompare(b.name));
    const derivedFiles = files.filter(f => f.category === 'Derived Assets').sort((a, b) => a.name.localeCompare(b.name));
    const otherFiles = files.filter(f => f.category !== 'Market Data' && f.category !== 'Derived Assets');

    // Group Market Files by Ticker
    const groupedMarketData = marketFiles.reduce((acc, file) => {
        const ticker = file.name.split('_')[0];
        if (!acc[ticker]) acc[ticker] = [];
        acc[ticker].push(file);
        return acc;
    }, {} as Record<string, DataFileStatus[]>);

    // Helper to render table
    const FileTable = ({ data }: { data: DataFileStatus[] }) => (
        <Table>
            <TableHeader>
                <TableRow>
                    <TableHead>File Name</TableHead>
                    <TableHead>Last Updated</TableHead>
                    <TableHead>Start Date</TableHead>
                    <TableHead>End Date</TableHead>
                    <TableHead>Size</TableHead>
                    <TableHead>Rows</TableHead>
                    <TableHead>Status</TableHead>
                </TableRow>
            </TableHeader>
            <TableBody>
                {loading && !loaded && (
                    <TableRow>
                        <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                            Scanning data files...
                        </TableCell>
                    </TableRow>
                )}
                {!loading && data.length === 0 && loaded && (
                    <TableRow>
                        <TableCell colSpan={7} className="text-center py-8 text-muted-foreground">
                            No files found in this category.
                        </TableCell>
                    </TableRow>
                )}
                {data.map((file) => (
                    <TableRow key={file.name}>
                        <TableCell className="font-medium">{file.name}</TableCell>
                        <TableCell>{file.updated}</TableCell>
                        <TableCell className="text-muted-foreground">{file.startDate || '-'}</TableCell>
                        <TableCell className="text-muted-foreground">{file.endDate || '-'}</TableCell>
                        <TableCell>{file.size}</TableCell>
                        <TableCell className="text-muted-foreground">{file.rows}</TableCell>
                        <TableCell>
                            <Badge variant="outline" className={file.status === 'OK' ? "bg-green-50 text-green-700 border-green-200" : "bg-yellow-50 text-yellow-700 border-yellow-200"}>
                                {file.status}
                            </Badge>
                        </TableCell>
                    </TableRow>
                ))}
            </TableBody>
        </Table>
    );

    return (
        <Card className="h-full">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
                <div>
                    <CardTitle className="text-xl">Data Inventory</CardTitle>
                    <CardDescription>Status of local data files</CardDescription>
                </div>
                <Button variant="outline" size="sm" onClick={loadStatus} disabled={loading}>
                    <RefreshCw className={`h-4 w-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
                    Refresh
                </Button>
            </CardHeader>
            <CardContent>
                <Tabs defaultValue="market" className="w-full">
                    <TabsList className="mb-4">
                        <TabsTrigger value="market">Market Data ({marketFiles.length})</TabsTrigger>
                        <TabsTrigger value="derived">Derived Assets ({derivedFiles.length})</TabsTrigger>
                        {otherFiles.length > 0 && <TabsTrigger value="other">Other ({otherFiles.length})</TabsTrigger>}
                    </TabsList>

                    <TabsContent value="market">
                        {/* Render Groups */}
                        {Object.keys(groupedMarketData).sort().map(ticker => (
                            <details open key={ticker} className="group mb-4 rounded-lg border bg-card text-card-foreground shadow-sm">
                                <summary className="cursor-pointer p-4 font-semibold hover:bg-muted/50 flex items-center justify-between select-none">
                                    <span>{ticker}</span>
                                    <Badge variant="secondary">{groupedMarketData[ticker].length} files</Badge>
                                </summary>
                                <div className="p-0 border-t">
                                    <FileTable data={groupedMarketData[ticker]} />
                                </div>
                            </details>
                        ))}
                        {marketFiles.length === 0 && <FileTable data={[]} />}
                    </TabsContent>

                    <TabsContent value="derived">
                        <FileTable data={derivedFiles} />
                    </TabsContent>

                    {otherFiles.length > 0 && (
                        <TabsContent value="other">
                            <FileTable data={otherFiles} />
                        </TabsContent>
                    )}
                </Tabs>
            </CardContent>
        </Card>
    )
}
