"""Curate high-signal YouTube videos from top Level-1 (OHLCV / Volume / Greeks) creators.

Strict Level 1 constraint:
No Level 2 / DOM / Depth of Market required.
All strategies operate on:
- OHLCV candlestick geometry (VCP, NR7, IBS, TheStrat, H2/L2, High Tight Flags)
- Level 1 Volume (Volume Profile from bars, RVOL, Volume dry-up)
- Public / End-of-Day Options Open Interest & Greeks (GEX, Expected Move, 0DTE Credit)
- Mathematical Indicators (RSI, ATR, Supertrend, Moving Averages, Kaufman ER)
"""
import json
from pathlib import Path
import scrapetube

MANIFEST_PATH = Path("data/strategies/raw_mined/level1_creator_manifest.json")

CREATOR_TARGETS = [
    {
        "creator": "Kristjan Qullamaggie",
        "handle": "Qullamaggie",
        "domain": "Stock Scanners, Episodic Pivots & High Tight Flags",
        "target_notebook": "80b7afae-c643-4af5-89ce-fdf309ab3034",  # stock_scanners_screeners
        "queries": [
            "Qullamaggie Episodic Pivot rules",
            "Qullamaggie High Tight Flag setup",
            "Qullamaggie breakout trading strategy rules",
        ]
    },
    {
        "creator": "Quantified Strategies",
        "handle": "QuantifiedStrategies",
        "domain": "Pure Quantitative Backtests & Statistical Edge",
        "target_notebook": "c9856fd5-3394-49db-ac05-9594db94dd00",  # mean_reversion or quant
        "queries": [
            "Quantified Strategies Internal Bar Strength IBS rules",
            "Quantified Strategies turn of the month trading strategy",
            "Quantified Strategies 200 day moving average RSI backtest",
        ]
    },
    {
        "creator": "The Art of Trading",
        "handle": "TheArtofTrading",
        "domain": "Systematic Algorithmic & Pine Script Systems",
        "target_notebook": "c9e73ff9-b36b-4d74-af98-7a35c70c3d3d",  # indicator_oscillators
        "queries": [
            "The Art of Trading ATR trailing stop strategy backtest",
            "The Art of Trading trend following breakout strategy rules",
            "The Art of Trading multi timeframe moving average strategy",
        ]
    },
    {
        "creator": "SpotGamma",
        "handle": "SpotGamma",
        "domain": "GEX, Absolute Gamma & Market Maker Volatility Triggers",
        "target_notebook": "dbbc0d63-d9df-4378-a958-d8f15ac60f3b",  # gamma_exposure_gex
        "queries": [
            "SpotGamma Zero Gamma level explained trading rules",
            "SpotGamma Call Wall Put Wall market maker hedging",
            "SpotGamma HIRO options flow indicator explained",
        ]
    },
    {
        "creator": "Al Brooks Price Action",
        "handle": "BrooksPriceAction",
        "domain": "Bar-by-Bar Price Action & High 2 / Low 2 Second Entries",
        "target_notebook": "4f569cc3-220e-408d-afaf-47add3fb67f1",  # price action / the strat
        "queries": [
            "Al Brooks second entry H2 L2 trading rules",
            "Al Brooks 20 EMA gap bar price action strategy",
            "Al Brooks opening range reversal rules",
        ]
    },
    {
        "creator": "Jim Dalton Market Profile",
        "handle": "JimDaltonTrading",
        "domain": "Market Profile 80% Rule & Auction Balance",
        "target_notebook": "b52fb636-8a91-40f3-9035-def8b94cb090",  # range_chop_congestion
        "queries": [
            "Jim Dalton 80% rule market profile trading strategy",
            "Jim Dalton auction market theory value area acceptance",
        ]
    },
    {
        "creator": "Bob Volman Price Action",
        "handle": "BobVolman",
        "domain": "5m OHLC Price Action Scalping & Block Breaks",
        "target_notebook": "b52fb636-8a91-40f3-9035-def8b94cb090",  # range_chop_congestion
        "queries": [
            "Bob Volman price action scalping block break strategy",
            "Bob Volman 20 EMA pullback range break setup",
        ]
    },
    {
        "creator": "Rob Carver Systematic Trading",
        "handle": "RobertCarverQuant",
        "domain": "Systematic Trend Following & Position Sizing",
        "target_notebook": "c9856fd5-3394-49db-ac05-9594db94dd00",  # quant
        "queries": [
            "Rob Carver systematic trading trend following rules",
            "Rob Carver position sizing volatility targeting",
        ]
    }
]

def harvest_creator_videos():
    results = {}
    total_videos = 0
    
    for target in CREATOR_TARGETS:
        c_name = target["creator"]
        print(f"\nSearching for {c_name} ({target['domain']})...")
        videos_found = []
        seen_ids = set()
        
        for q in target["queries"]:
            try:
                search_res = scrapetube.get_search(q, limit=5)
                for item in search_res:
                    vid_id = item.get("videoId")
                    if not vid_id or vid_id in seen_ids:
                        continue
                    
                    # Extract title
                    title = "Unknown"
                    if "title" in item and "runs" in item["title"] and item["title"]["runs"]:
                        title = item["title"]["runs"][0].get("text", "Unknown")
                    elif "title" in item and "accessibility" in item["title"]:
                        title = item["title"]["accessibility"]["accessibilityData"].get("label", "Unknown")
                        
                    # Filter out obvious shorts or clickbait
                    title_lower = title.lower()
                    if "#shorts" in title_lower or "100% win" in title_lower:
                        continue
                        
                    seen_ids.add(vid_id)
                    videos_found.append({
                        "video_id": vid_id,
                        "title": title,
                        "url": f"https://www.youtube.com/watch?v={vid_id}",
                        "query": q,
                        "requires_level2": False
                    })
                    
                    if len(videos_found) >= 3:
                        break
            except Exception as e:
                print(f"  Error querying '{q}': {e}")
            if len(videos_found) >= 3:
                break
                
        results[c_name] = {
            "domain": target["domain"],
            "target_notebook": target["target_notebook"],
            "video_count": len(videos_found),
            "videos": videos_found,
            "urls": [v["url"] for v in videos_found]
        }
        total_videos += len(videos_found)
        print(f"  Found {len(videos_found)} high-signal Level 1 videos for {c_name}.")
        
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
        
    print(f"\nTotal curated Level 1 videos: {total_videos}")
    print(f"Manifest written to {MANIFEST_PATH}")

if __name__ == "__main__":
    harvest_creator_videos()
