"use client"

import { useState } from "react"
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { RefreshCw, Upload, Terminal, CheckCircle, AlertTriangle } from "lucide-react"
import { runDataUpdate } from "@/actions/datamanager-actions"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"

export function DataActionsWidget() {
    const [updating, setUpdating] = useState(false)
    const [result, setResult] = useState<{ success: boolean; message: string } | null>(null)
    const [logs, setLogs] = useState<string>("")

    const handleUpdate = async () => {
        setUpdating(true)
        setResult(null)
        setLogs("Starting update process...\n")

        try {
            const res = await runDataUpdate()
            if (res.success) {
                setResult({ success: true, message: "Update completed successfully." })
                setLogs(prev => prev + (res.output || "No output") + "\nDone.")
            } else {
                setResult({ success: false, message: "Update failed." })
                setLogs(prev => prev + (res.error || "Unknown error") + "\nFailed.")
            }
        } catch (error) {
            setResult({ success: false, message: "Update error." })
        } finally {
            setUpdating(false)
        }
    }

    return (
        <Card className="flex flex-col h-full">
            <CardHeader>
                <CardTitle>Actions</CardTitle>
                <CardDescription>Common data operations</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 flex-1">
                <Button
                    className="w-full justify-start"
                    variant="outline"
                    onClick={handleUpdate}
                    disabled={updating}
                >
                    <RefreshCw className={`mr-2 h-4 w-4 ${updating ? 'animate-spin' : ''}`} />
                    {updating ? "Updating..." : "Update Intraday (Yahoo)"}
                </Button>

                <Button className="w-full justify-start" variant="outline" disabled>
                    <Upload className="mr-2 h-4 w-4" />
                    Import from Downloads (Coming Soon)
                </Button>

                {result && (
                    <Alert variant={result.success ? "default" : "destructive"} className="mt-4">
                        {result.success ? <CheckCircle className="h-4 w-4" /> : <AlertTriangle className="h-4 w-4" />}
                        <AlertTitle>{result.success ? "Success" : "Error"}</AlertTitle>
                        <AlertDescription>{result.message}</AlertDescription>
                    </Alert>
                )}

                {logs && (
                    <div className="mt-4">
                        <label className="text-xs text-muted-foreground font-semibold flex items-center mb-1">
                            <Terminal className="h-3 w-3 mr-1" /> Operation Logs
                        </label>
                        <div className="bg-slate-950 text-slate-50 p-2 rounded-md text-xs font-mono h-32 overflow-y-auto whitespace-pre-wrap">
                            {logs}
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    )
}
