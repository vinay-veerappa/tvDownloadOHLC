import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
import json
import argparse
from datetime import datetime, timedelta

# Add project root to path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(ROOT_DIR)

# --- CONFIG ---
DATA_DIR = os.path.join(ROOT_DIR, "data")
DERIVED_DIR = os.path.join(DATA_DIR, "derived")
DOCS_DIR = os.path.join(ROOT_DIR, "docs", "DailyClassification")

def load_matrices(ticker):
    """Load probability matrices from docs."""
    overnight_path = os.path.join(DOCS_DIR, f"{ticker}_overnight_probability_matrix.csv")
    sequential_path = os.path.join(DOCS_DIR, f"{ticker}_sequential_probabilities.csv")
    
    overnight_df = pd.read_csv(overnight_path, index_col=0) if os.path.exists(overnight_path) else None
    sequential_df = pd.read_csv(sequential_path, index_col=0) if os.path.exists(sequential_path) else None
    
    return overnight_df, sequential_df

def get_prior_classification(ticker, target_date):
    """Get classification for the day before target_date."""
    class_path = os.path.join(DERIVED_DIR, f"{ticker}_daily_classification.parquet")
    if not os.path.exists(class_path):
        return None
    
    df = pd.read_parquet(class_path)
    df['date'] = pd.to_datetime(df['date']).dt.date
    
    # Filter for dates before target_date
    prior_days = df[df['date'] < target_date].sort_values('date', ascending=False)
    if prior_days.empty:
        return None
        
    return prior_days.iloc[0]['type']


import sys
from pathlib import Path

# Add project root to sys.path dynamically
_current_dir = Path(__file__).resolve().parent
while _current_dir.name and _current_dir.name != "scripts":
    _current_dir = _current_dir.parent
if _current_dir.name == "scripts":
    _root_dir = str(_current_dir.parent)
    if _root_dir not in sys.path:
        sys.path.insert(0, _root_dir)

from scripts.utils.fused_data_loader import load_fused_data
from scripts.analysis.analyze_daily_nqstats import get_session_data

def get_current_overnight_scenario(ticker, target_date):
    """Analyze current live data to determine Asia/London statuses."""
    df = load_fused_data(ticker, timeframe="1m", require_historical=False)
    if df.empty:
        return None
        
    # Get Session Data
    asia = get_session_data(df, 'Asia', target_date)
    london = get_session_data(df, 'London', target_date)
    
    if asia.empty or london.empty:
        return None
        
    ah, al = asia['high'].max(), asia['low'].min()
    am = (ah + al) / 2
    
    lh, ll = london['high'].max(), london['low'].min()
    lm = (lh + ll) / 2
    
    # 1. Determine Statuses (V14/V24 style)
    # Status is based on Close vs Mid (simplified for bias report)
    # Long True = Close > High, Short True = Close < Low
    # Long False = Broke High but Closed below Mid
    # Short False = Broke Low but Closed above Mid
    
    def get_status(sess_df, sess_open, prev_close):
        if sess_df.empty: return "None"
        sh, sl = sess_df['high'].max(), sess_df['low'].min()
        sm = (sh + sl) / 2
        sc = sess_df['close'].iloc[-1]
        
        # Simplified logic for matching overnight matrix keys
        if sc > sm:
            return "long true" if sc > sh else "short false"
        else:
            return "short true" if sc < sl else "long false"

    # Need opens and prior closes
    # For a quick bias report, we can use the simplified 'status' logic
    # that matches the CSV keys: 'long true', 'short true', 'long false', 'short false'
    
    asia_status = get_status(asia, asia['open'].iloc[0], asia['open'].iloc[0])
    london_status = get_status(london, london['open'].iloc[0], asia['close'].iloc[-1])
    
    # 2. Check if Asia Broken in London
    # Check if any price in London touched Asia Mid
    broke_mask = (london['low'] <= am) & (london['high'] >= am)
    is_broken = broke_mask.any()
    
    key = f"{asia_status} | {london_status} | LdnBreak:{is_broken}"
    return key

def main():
    parser = argparse.ArgumentParser(description="Daily Classification Bias Report")
    parser.add_argument("--ticker", default="NQ1", help="Ticker (NQ1, ES1, etc.)")
    parser.add_argument("--date", help="Target date (YYYY-MM-DD), default Today")
    parser.add_argument("--discord", action="store_true", help="Send to Discord")
    parser.add_argument("--channel", default="test_channel", help="Discord channel")
    args = parser.parse_args()
    
    target_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else datetime.now().date()
    
    print(f"==========================================")
    print(f"🏷️  DAILY CLASSIFICATION BIAS: {args.ticker}")
    print(f"==========================================\n")
    
    # 1. Get Prior Day Info
    prior_type = get_prior_classification(args.ticker, target_date)
    print(f"Prev Day Type: {prior_type if prior_type else 'Unknown'}")
    
    # 2. Get Overnight Info
    overnight_key = get_current_overnight_scenario(args.ticker, target_date)
    print(f"Overnight Key: {overnight_key if overnight_key else 'Unknown'}")
    
    # 3. Load Probabilities
    over_probs_df, seq_probs_df = load_matrices(args.ticker)
    
    report_lines = []
    report_lines.append(f"### 🏷️ CLASSIFICATION BIAS: {args.ticker}")
    report_lines.append(f"---")
    
    # A. Sequential Probability
    if seq_probs_df is not None and prior_type in seq_probs_df.index:
        row = seq_probs_df.loc[prior_type]
        report_lines.append(f"**Sequential Probability** (After `{prior_type}`):")
        # Handle columns with or without % (Sequential CSV has no %, Overnight Matrix does)
        p_items = []
        for c in ['R1', 'R2', 'DWP', 'DNP']:
            val = None
            if f'{c}%' in row: val = row[f'{c}%']
            elif c in row: val = row[c]
            
            val_str = f"`{val}%`" if val is not None else "`N/A`"
            p_items.append(f"{c}: {val_str}")
        
        report_lines.append(f"> {' | '.join(p_items)}")
        seq_dict = {c: float(str(seq_probs_df.loc[prior_type].get(c, seq_probs_df.loc[prior_type].get(f'{c}%', 0)))) for c in ['R1', 'R2', 'DWP', 'DNP']}
    else:
        report_lines.append(f"**Sequential Probability**: Data missing for `{prior_type}`")

    # B. Overnight Probability
    if over_probs_df is not None and overnight_key in over_probs_df.index:
        row = over_probs_df.loc[overnight_key]
        report_lines.append(f"\n**Overnight Probability** (Key: `{overnight_key}`):")
        p_items = []
        for c in ['R1', 'R2', 'DWP', 'DNP']:
            val = row.get(f'{c}%') if f'{c}%' in row else row.get(c, 0.0)
            p_items.append(f"{c}: `{val}%`")
            
        report_lines.append(f"> {' | '.join(p_items)}")
        
        most_likely = row['most_likely']
        count = int(row['n'])
        report_lines.append(f"\n**Most Likely Outcome**: `{most_likely}` (n={count})")
        over_dict = {c: float(str(over_probs_df.loc[overnight_key].get(c, over_probs_df.loc[overnight_key].get(f'{c}%', 0)))) for c in ['R1', 'R2', 'DWP', 'DNP']}
    else:
        report_lines.append(f"\n**Overnight Probability**: No match found for `{overnight_key}`")

    report_text = "\n".join(report_lines)
    print("\n" + report_text)
    print("\n" + "="*42)
    
    if args.discord:
        from scripts.utils.discord_notify import get_webhook_url, send_message
        url = get_webhook_url(args.channel)
        if url:
            send_message(url, report_text)
        else:
            print("❌ Discord Error: Webhook not found.")
            
    # 6. Prepare Result Data
    result_data = {
        'prior_type': prior_type,
        'overnight_key': overnight_key,
        'sequential_probs': seq_dict if 'seq_dict' in locals() else {},
        'overnight_probs': over_dict if 'over_dict' in locals() else {},
        'most_likely': most_likely if 'most_likely' in locals() else 'Unknown'
    }
            
    return report_text, result_data

if __name__ == "__main__":
    report, data = main()
