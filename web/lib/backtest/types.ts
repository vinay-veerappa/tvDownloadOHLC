
export interface BacktestConfig {
    ticker: string
    timeframe: string
    strategy: string
    params: Record<string, any>
}

export interface Trade {
    entryDate: number
    exitDate: number
    entryPrice: number
    exitPrice: number
    direction: 'LONG' | 'SHORT'
    pnl: number
    result: 'WIN' | 'LOSS'
    metadata?: Record<string, any>
    exitReason?: string


    // Visualization Fields
    tpPrice?: number
    slPrice?: number
    mae?: number // Max Adverse Excursion (Max Loss potential during trade)
    mfe?: number // Max Favorable Excursion (Max Profit potential during trade)
}

export interface BacktestResult {
    totalTrades: number
    winRate: number
    profitFactor: number
    totalPnl: number
    startDate: number
    endDate: number
    trades: Trade[]
}

export interface OHLCData {
    time: number
    open: number
    high: number
    low: number
    close: number
    volume?: number
}

// Interface for a Strategy Implementation
export interface Strategy {
    name: string
    run(data: OHLCData[], params: Record<string, any>): Promise<Trade[]>
}
