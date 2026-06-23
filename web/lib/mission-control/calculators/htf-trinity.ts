// HTFTrinityAnalysis interface is defined below
import path from 'path';
import fs from 'fs';

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
    let safeTicker = ticker;
    const roots = ["NQ", "ES", "YM", "RTY", "GC", "CL", "SI", "HG", "NG", "ZB", "ZN"];
    const clean = ticker.replace(/[^a-zA-Z]/g, "").toUpperCase();
    const root = clean.replace(/\d+$/, "");
    if (roots.includes(root)) {
        safeTicker = "/" + root;
    }

    try {
        const apiRes = await fetch(`http://127.0.0.1:8001/quote?symbol=${encodeURIComponent(safeTicker)}`, { cache: 'no-store' });
        if (apiRes.ok) {
            const apiData = await apiRes.json();
            if (apiData && typeof apiData.price === 'number') {
                return apiData.price;
            }
        }
    } catch (e) {
        console.error(`[HTFTrinity] getLivePrice failed to fetch from Spoke API:`, e);
    }
    return null;
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
