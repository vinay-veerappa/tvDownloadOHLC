// HTFTrinityAnalysis interface is defined below
import path from 'path';
import fs from 'fs';
import { ParquetReader } from 'parquetjs-lite';

export interface HTFProfile {
    timeframe: 'WEEKLY' | 'MONTHLY';
    high: number;
    low: number;
    mid: number;
    zone: 'PREMIUM' | 'DISCOUNT' | 'EQUILIBRIUM';
    position_pct: number;
}

export interface HTFTrinityAnalysis {
    price: number;
    trinity_bias: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
    daily_ema: {
        value: number;
        position: 'ABOVE' | 'BELOW';
    };
    weekly: HTFProfile;
    monthly: HTFProfile;
}

// Helper to load derived context
async function loadHTFContext(ticker: string) {
    const validTicker = ticker === 'NQ1' ? '-NQ' : ticker;
    const ctxPath = path.join(process.cwd(), '..', 'data', 'derived', `htf_context_${validTicker}.json`);

    if (fs.existsSync(ctxPath)) {
        try {
            const raw = fs.readFileSync(ctxPath, 'utf-8');
            return JSON.parse(raw);
        } catch (e) { console.error("Error reading HTF context:", e); }
    }
    return null;
}

// Helper to get live price (from Hybrid source)
async function getLivePrice(ticker: string): Promise<number | null> {
    const validTicker = ticker === 'NQ1' ? '-NQ' : ticker;
    // 1. Try Fast JSON (Live Chart)
    const jsonPath = path.join(process.cwd(), '..', 'data', 'live', `live_chart_${validTicker}.json`);
    if (fs.existsSync(jsonPath)) {
        try {
            const jData = JSON.parse(fs.readFileSync(jsonPath, 'utf-8'));
            // Use live_price if valid
            if (typeof jData.live_price === 'number') return jData.live_price;
            // Fallback to last candle close
            if (jData.candles && jData.candles.length > 0) return jData.candles[jData.candles.length - 1].close;
        } catch (e) { }
    }

    // 2. Fallback to Parquet Scan (Slower but reliable)
    const livePath = path.join(process.cwd(), '..', 'data', 'live', `live_storage_${validTicker}.parquet`);
    if (!fs.existsSync(livePath)) return null;

    try {
        const reader = await ParquetReader.openFile(livePath);
        const cursor = reader.getCursor();
        let lastRecord = null;
        let record = null;
        while (record = await cursor.next()) {
            lastRecord = record;
        }
        await reader.close();
        return lastRecord ? lastRecord.close : null;
    } catch (e) { return null; }
}

function analyzeProfile(profile: any, currentPrice: number, timeframe: 'WEEKLY' | 'MONTHLY'): HTFProfile {
    // profile from JSON has { high, low, mid, close }
    const { high, low, mid } = profile;
    const range = high - low;
    const position_pct = range === 0 ? 50 : ((currentPrice - low) / range) * 100;

    let zone: 'PREMIUM' | 'DISCOUNT' | 'EQUILIBRIUM' = 'EQUILIBRIUM';
    if (position_pct > 55) zone = 'PREMIUM';
    else if (position_pct < 45) zone = 'DISCOUNT';

    return {
        timeframe,
        high,
        low,
        mid,
        zone,
        position_pct
    };
}

export async function calculateHTFTrinity(
    ticker: string,
    lookbackDays: number = 30
): Promise<HTFTrinityAnalysis | null> {

    // 1. Load Context
    const context = await loadHTFContext(ticker);
    if (!context) return null;

    // 2. Load Live Price
    const currentPrice = await getLivePrice(ticker) || context.prev_day_close;

    // 3. Analyze Profiles
    const weekly = analyzeProfile(context.weekly_profile, currentPrice, 'WEEKLY');
    const monthly = analyzeProfile(context.monthly_profile, currentPrice, 'MONTHLY');

    // 4. Daily EMA Status
    const emaVal = context.prev_day_ema5;
    const emaPos = currentPrice > emaVal ? 'ABOVE' : 'BELOW';

    // 5. Total Bias
    let bullishScore = 0;
    if (emaPos === 'ABOVE') bullishScore++;
    if (weekly.position_pct > 50) bullishScore++;
    if (monthly.position_pct > 50) bullishScore++;

    const trinity_bias = bullishScore >= 2 ? 'BULLISH' : bullishScore <= 1 ? 'BEARISH' : 'NEUTRAL';

    return {
        price: currentPrice,
        trinity_bias,
        daily_ema: {
            value: emaVal,
            position: emaPos
        },
        weekly,
        monthly
    };
}
