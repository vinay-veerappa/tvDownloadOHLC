"use client"

import React, { createContext, useContext, useState } from "react"

interface TradeInitialData {
    symbol?: string
    price?: number
    date?: Date
    direction?: "LONG" | "SHORT"
}

interface TradeContextType {
    isOpen: boolean
    setIsOpen: (open: boolean) => void
    initialData: TradeInitialData | null
    openTradeDialog: (data?: TradeInitialData) => void
}

const TradeContext = createContext<TradeContextType | undefined>(undefined)

export function TradeProvider({ children }: { children: React.ReactNode }) {
    const [isOpen, setIsOpen] = useState(false)
    const [initialData, setInitialData] = useState<TradeInitialData | null>(null)

    const openTradeDialog = (data?: TradeInitialData) => {
        if (data) setInitialData(data)
        setIsOpen(true)
    }

    return (
        <TradeContext.Provider value={{ isOpen, setIsOpen, initialData, openTradeDialog }}>
            {children}
        </TradeContext.Provider>
    )
}

export function useTradeContext() {
    const context = useContext(TradeContext)
    if (context === undefined) {
        throw new Error("useTradeContext must be used within a TradeProvider")
    }
    return context
}
