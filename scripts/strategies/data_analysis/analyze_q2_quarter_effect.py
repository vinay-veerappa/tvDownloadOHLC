import pandas as pd
import numpy as np
from datetime import time

DATA_DIR = 'data'
TICKERS = ['NQ1', 'ES1']
START_YEAR = 2020
END_YEAR = 2025

RANGE_START = time(8, 0)
RANGE_END = time(12, 0)
NOON = time(12, 0)
SESSION_END = time(16, 0)


def load_data(ticker: str) -> pd.DataFrame:
    path = f"{DATA_DIR}/{ticker}_1m.parquet"
    df = pd.read_parquet(path)
    if 'time' in df.columns:
        df['datetime'] = pd.to_datetime(df['time'], unit='s', utc=True)
        df = df.set_index('datetime')
    df = df.tz_convert('America/New_York')
    df = df[(df.index.year >= START_YEAR) & (df.index.year <= END_YEAR)]
    return df


def classify_day(day_data: pd.DataFrame) -> dict | None:
    range_data = day_data.between_time(RANGE_START, RANGE_END, inclusive='left')
    pm_data = day_data.between_time(NOON, SESSION_END, inclusive='left')

    if len(range_data) < 60 or len(pm_data) < 60:
        return None

    # Dynamic quarter windows for the 8-12 range (4h -> 60m quarters)
    range_minutes = 240
    quarter_minutes = range_minutes // 4

    q1_start = time(8, 0)
    q1_end = time(9, 0)
    q2_start = time(9, 0)
    q2_end = time(10, 0)

    q1_data = day_data.between_time(q1_start, q1_end, inclusive='left')
    q2_data = day_data.between_time(q2_start, q2_end, inclusive='left')
    if len(q1_data) == 0 or len(q2_data) == 0:
        return None

    q1_high = q1_data['high'].max()
    q1_low = q1_data['low'].min()
    q2_broke_q1_high = (q2_data['high'] > q1_high).any()
    q2_broke_q1_low = (q2_data['low'] < q1_low).any()

    # Expected direction from last AM extreme (same as deep analysis script)
    am_high_idx = range_data['high'].idxmax()
    am_low_idx = range_data['low'].idxmin()
    if am_high_idx > am_low_idx:
        expected_dir = 'BULL'
    elif am_low_idx > am_high_idx:
        expected_dir = 'BEAR'
    else:
        return None

    am_high = range_data['high'].max()
    am_low = range_data['low'].min()
    pm_high = pm_data['high'].max()
    pm_low = pm_data['low'].min()

    new_pm_high = pm_high > am_high
    new_pm_low = pm_low < am_low

    if new_pm_high and not new_pm_low:
        actual_pm_dir = 'BULL'
    elif new_pm_low and not new_pm_high:
        actual_pm_dir = 'BEAR'
    elif new_pm_high and new_pm_low:
        pm_high_time = pm_data['high'].idxmax()
        pm_low_time = pm_data['low'].idxmin()
        actual_pm_dir = 'BULL' if pm_high_time < pm_low_time else 'BEAR'
    else:
        actual_pm_dir = 'NONE'

    pred_correct = expected_dir == actual_pm_dir

    # Q2 gate pass logic mirrors Pine gate behavior
    gate_pass = (expected_dir == 'BULL' and q2_broke_q1_high) or (expected_dir == 'BEAR' and q2_broke_q1_low)

    return {
        'Date': str(range_data.index[0].date()),
        'Expected_Dir': expected_dir,
        'Actual_PM_Dir': actual_pm_dir,
        'Prediction_Correct': pred_correct,
        'Q2_Broke_Q1_High': bool(q2_broke_q1_high),
        'Q2_Broke_Q1_Low': bool(q2_broke_q1_low),
        'Q2_Gate_Pass': bool(gate_pass),
    }


def summarize(df: pd.DataFrame, label: str) -> dict:
    n = len(df)
    if n == 0:
        return {'label': label, 'n': 0, 'acc': np.nan}
    acc = df['Prediction_Correct'].mean() * 100
    return {'label': label, 'n': n, 'acc': acc}


def run_ticker(ticker: str):
    df = load_data(ticker)
    rows = []
    for _, day_data in df.groupby(df.index.date):
        r = classify_day(day_data)
        if r is not None:
            rows.append(r)

    out = pd.DataFrame(rows)
    if out.empty:
        print(f"{ticker}: no usable rows")
        return

    all_days = summarize(out, 'All Days (No Q2 Gate)')
    gate_on = summarize(out[out['Q2_Gate_Pass']], 'Q2 Gate ON (only pass days)')
    gate_off = summarize(out[~out['Q2_Gate_Pass']], 'Q2 Gate FAIL days')

    print('\n' + '=' * 80)
    print(f"Q2 Quarter-Gate Effect: {ticker} ({START_YEAR}-{END_YEAR})")
    print('=' * 80)
    print(f"{all_days['label']:<30} n={all_days['n']:4d} | acc={all_days['acc']:.2f}%")
    print(f"{gate_on['label']:<30} n={gate_on['n']:4d} | acc={gate_on['acc']:.2f}%")
    print(f"{gate_off['label']:<30} n={gate_off['n']:4d} | acc={gate_off['acc']:.2f}%")

    retained = (gate_on['n'] / all_days['n'] * 100) if all_days['n'] > 0 else 0
    uplift = gate_on['acc'] - all_days['acc']
    print(f"Retained sample with gate ON: {retained:.1f}%")
    print(f"Accuracy uplift with gate ON: {uplift:+.2f} pts")

    out_path = f"DataAnalysisExpert/q2_quarter_effect_{ticker}_{START_YEAR}_{END_YEAR}.csv"
    out.to_csv(out_path, index=False)
    print(f"Saved rows: {out_path}")


def main():
    for ticker in TICKERS:
        run_ticker(ticker)


if __name__ == '__main__':
    main()
