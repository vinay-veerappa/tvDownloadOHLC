"use client"

import React, { createContext, useContext, useState, ReactNode } from 'react'
import { AccountGroupSelector } from "../input/account-group-selector"
import { AddTradeDialog } from "../add-trade-dialog"
import { ImportExportDialog } from "../import-export-dialog"
import { Button } from "@/components/ui/button"

interface DashboardContextType {
    filters: {
        dateRange: { from: Date; to: Date } | undefined
        accountId: string | undefined
        groupId: string | undefined
        strategyId: string | undefined
    }
    setFilters: (filters: any) => void
    refresh: () => void
    refreshKey: number
}

const DashboardContext = createContext<DashboardContextType | undefined>(undefined)

export function DashboardLayout({ children }: { children: ReactNode }) {
    const [filters, setFilters] = useState<{
        dateRange: { from: Date; to: Date } | undefined
        accountId: string | undefined
        groupId: string | undefined
        strategyId: string | undefined
    }>({
        dateRange: undefined,
        accountId: undefined,
        groupId: undefined,
        strategyId: undefined
    })
    const [refreshKey, setRefreshKey] = useState(0)

    const refresh = () => setRefreshKey(prev => prev + 1)

    return (
        <DashboardContext.Provider value={{ filters, setFilters, refresh, refreshKey }}>
            <div className="flex flex-col space-y-6 p-2 md:p-8 pt-6">
                <div className="flex justify-between items-center mb-4">
                    <h2 className="text-3xl font-bold tracking-tight">Trading Journal</h2>
                    <div className="flex items-center gap-2">
                        <AccountGroupSelector 
                            selectedType={filters.groupId ? 'group' : filters.accountId ? 'account' : 'all'}
                            selectedId={filters.groupId || filters.accountId}
                            onScopeChange={(type, id) => {
                                setFilters(prev => ({
                                    ...prev,
                                    groupId: type === 'group' ? id : undefined,
                                    accountId: type === 'account' ? id : undefined
                                }))
                            }}
                        />
                         {/* Date Range Picker placeholder */}
                        <Button variant="outline" onClick={refresh}>Refresh</Button>
                        <ImportExportDialog />
                        <AddTradeDialog />
                    </div>
                </div>
                {children}
            </div>
        </DashboardContext.Provider>
    )
}

export const useDashboard = () => {
    const context = useContext(DashboardContext)
    if (!context) throw new Error("useDashboard must be used within DashboardLayout")
    return context
}
