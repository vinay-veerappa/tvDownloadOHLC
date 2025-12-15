"use client"

import { useEffect, useState } from "react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"
import { Database, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { getDataStatus, DataFileStatus } from "@/actions/datamanager-actions"

export function DataStatusWidget() {
    const [files, setFiles] = useState<DataFileStatus[]>([])
    const [loading, setLoading] = useState(false)
    const [loaded, setLoaded] = useState(false)

    const fetchStatus = async () => {
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
        fetchStatus()
    }, [])

    return (
        <Card className="h-full">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                <div className="flex flex-col space-y-1.5">
                    <CardTitle className="flex items-center gap-2">
                        <Database className="h-5 w-5" />
                        Data Inventory
                    </CardTitle>
                    <CardDescription>Current status of intraday parquet files</CardDescription>
                </div>
                <Button variant="ghost" size="icon" onClick={fetchStatus} disabled={loading}>
                    <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                </Button>
            </CardHeader>
            <CardContent>
                <div className="rounded-md border">
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead>File Name</TableHead>
                                <TableHead>Last Updated</TableHead>
                                <TableHead>Size</TableHead>
                                <TableHead>Rows</TableHead>
                                <TableHead>Status</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {loading && !loaded && (
                                <TableRow>
                                    <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                                        Scanning data files...
                                    </TableCell>
                                </TableRow>
                            )}
                            {!loading && files.length === 0 && loaded && (
                                <TableRow>
                                    <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                                        No parquet files found in data directory.
                                    </TableCell>
                                </TableRow>
                            )}
                            {files.map((file) => (
                                <TableRow key={file.name}>
                                    <TableCell className="font-medium">{file.name}</TableCell>
                                    <TableCell>{file.updated}</TableCell>
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
                </div>
            </CardContent>
        </Card>
    )
}
