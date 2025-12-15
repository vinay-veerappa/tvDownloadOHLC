import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Database, Upload, RefreshCw, AlertTriangle } from "lucide-react"
import { DataStatusWidget } from "@/components/datamanager/data-status-widget"
import { DataActionsWidget } from "@/components/datamanager/data-actions-widget"

export default function DataManagerPage() {
    return (
        <div className="space-y-6">
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-2xl font-bold tracking-tight">Data Manager</h2>
                    <p className="text-muted-foreground">
                        Centralized hub for data integrity, updates, and imports.
                    </p>
                </div>
            </div>

            <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                {/* Status Card */}
                <div className="col-span-2">
                    <DataStatusWidget />
                </div>

                {/* Actions Card */}
                <div>
                    <DataActionsWidget />
                </div>
            </div>
        </div>
    )
}
