import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

function getRepoRoot(): string {
  const cwd = process.cwd();
  if (fs.existsSync(path.join(cwd, 'reports')) || fs.existsSync(path.join(cwd, 'scripts', 'screener'))) {
    return cwd;
  }
  const parent = path.resolve(cwd, '..');
  if (fs.existsSync(path.join(parent, 'reports')) || fs.existsSync(path.join(parent, 'scripts', 'screener'))) {
    return parent;
  }
  return cwd;
}

function getPythonExecutable(repoRoot: string): string {
  const candidates = [
    path.join(repoRoot, '.venv', 'Scripts', 'python.exe'),
    path.join(repoRoot, 'venv', 'Scripts', 'python.exe'),
    path.join(repoRoot, '.venv', 'bin', 'python'),
    path.join(repoRoot, 'venv', 'bin', 'python'),
    'python3',
    'python'
  ];

  for (const candidate of candidates) {
    if (candidate.includes(path.sep) && fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return candidates[0];
}

export async function GET(
  request: Request,
  { params }: { params: Promise<{ ticker: string }> }
) {
  const { ticker } = await params;
  if (!ticker) {
    return NextResponse.json({ success: false, error: 'Ticker is required' }, { status: 400 });
  }

  const cleanTicker = ticker.toUpperCase().trim();
  const repoRoot = getRepoRoot();
  const pyPath = getPythonExecutable(repoRoot);

  const pyScript = `
import json, sys
import pandas as pd
from scripts.screener.core.provider import fetch_equity_daily_batch
from scripts.screener.core.data_policy import prepare_price_series
from scripts.screener.core.features import build_feature_matrix

try:
    dfs = fetch_equity_daily_batch(['${cleanTicker}'], provider='yfinance', fallback='schwab')
    df = dfs.get('${cleanTicker}')
    if df is None or df.empty:
        print(json.dumps({'success': False, 'error': 'No data found'}))
        sys.exit(0)

    split_df, tr_df = prepare_price_series(df)
    fm = build_feature_matrix(split_df, ticker='${cleanTicker}', tr_df=tr_df)
    if fm.empty:
        print(json.dumps({'success': False, 'error': 'Feature matrix empty'}))
        sys.exit(0)

    latest = fm.iloc[-1].to_dict()
    cleaned_metrics = {}
    for k, v in latest.items():
        if pd.isna(v):
            cleaned_metrics[k] = None
        elif isinstance(v, (int, float, str, bool)):
            cleaned_metrics[k] = v
        else:
            cleaned_metrics[k] = str(v)

    candles = []
    for idx, row in df.tail(250).iterrows():
        dt_val = row.get('datetime', row.get('date', idx))
        ts = int(pd.to_datetime(dt_val).timestamp()) if not pd.isna(dt_val) else 0
        candles.append({
            'time': ts,
            'open': float(row.get('open', 0)),
            'high': float(row.get('high', 0)),
            'low': float(row.get('low', 0)),
            'close': float(row.get('close', 0)),
            'volume': float(row.get('volume', 0)),
        })

    print(json.dumps({'success': True, 'ticker': '${cleanTicker}', 'metrics': cleaned_metrics, 'candles': candles}))
except Exception as e:
    print(json.dumps({'success': False, 'error': str(e)}))
`;

  try {
    const cmd = `"${pyPath}" -c "${pyScript.replace(/"/g, '\\"').replace(/\n/g, ' ')}"`;
    const { stdout } = await execAsync(cmd, { cwd: repoRoot, timeout: 15000 });
    const parsed = JSON.parse(stdout.trim());
    return NextResponse.json(parsed);
  } catch (err: any) {
    return NextResponse.json({ success: false, error: err?.message || 'Execution error' }, { status: 500 });
  }
}
