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
  return candidates[0]; // fallback
}

const REPO_ROOT = getRepoRoot();
const MATRIX_CSV_PATH = path.join(REPO_ROOT, 'reports', 'screener', 'strategy_comparison_matrix.csv');

const STRATEGIES = [
  'kell_ema_bounce',
  'minervini_trend',
  'oneil_breakout',
  'parabolic_short',
  'qullamaggie_hft',
  'rs_vs_spy',
  'stockbee_ep',
  'stockbee_momentum',
  'stockbee_sss20',
  'weinstein_stage2',
  'wheel_income',
  'zanger_volume_surge',
];

function parseCSVLine(line: string): string[] {
  const result: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === ',' && !inQuotes) {
      result.push(current.trim());
      current = '';
    } else {
      current += char;
    }
  }
  result.push(current.trim());
  return result;
}

function loadMatrixCSV() {
  if (!fs.existsSync(MATRIX_CSV_PATH)) {
    return { candidates: [], last_modified: null };
  }

  const fileContent = fs.readFileSync(MATRIX_CSV_PATH, 'utf-8');
  const lines = fileContent.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length <= 1) {
    return { candidates: [], last_modified: null };
  }

  const headers = parseCSVLine(lines[0]);
  const candidates = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i]);
    if (values.length < headers.length) continue;

    const row: Record<string, any> = {};
    headers.forEach((h, idx) => {
      row[h] = values[idx];
    });

    const strategyMatches: Record<string, boolean> = {};
    STRATEGIES.forEach((s) => {
      strategyMatches[s] = row[s] === '1' || row[s] === 'true';
    });

    candidates.push({
      ticker: row['ticker'] || '',
      company: row['company'] || '',
      sector: row['sector'] || '',
      industry: row['industry'] || '',
      close: parseFloat(row['close'] || '0'),
      matched_strategies_count: parseInt(row['matched_strategies_count'] || '0', 10),
      matched_strategies_list: row['matched_strategies_list'] || '',
      strategy_matches: strategyMatches,
    });
  }

  const stats = fs.statSync(MATRIX_CSV_PATH);
  return { candidates, last_modified: stats.mtime.toISOString() };
}

async function getDynamicMarketRegime() {
  try {
    const pyPath = getPythonExecutable(REPO_ROOT);
    const cmd = `"${pyPath}" -c "import json; from scripts.screener.core.regime import get_market_regime; r=get_market_regime(); print(json.dumps({'status': r.status, 'spy_close': r.spy_close, 'is_macro_high_risk': r.is_macro_high_risk, 'evaluated_at': r.evaluated_at}))"`;
    const { stdout } = await execAsync(cmd, { cwd: REPO_ROOT, timeout: 5000 });
    const parsed = JSON.parse(stdout.trim());
    return parsed;
  } catch (err) {
    console.warn('Fallback to default market regime due to evaluation timeout/error:', err);
    return {
      status: 'BULL_EXPLOSIVE',
      spy_close: 500.0,
      is_macro_high_risk: false,
      evaluated_at: new Date().toISOString(),
    };
  }
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const shouldRun = searchParams.get('run') === 'true';
  const limit = searchParams.get('limit') || '100';

  if (shouldRun) {
    try {
      const pyPath = getPythonExecutable(REPO_ROOT);
      const cmd = `"${pyPath}" -m scripts.screener.generate_reports --limit ${limit}`;
      await execAsync(cmd, { cwd: REPO_ROOT, timeout: 120000 });
    } catch (err: any) {
      console.error('Failed to run screener reports via CLI:', err?.message || err);
    }
  }

  const { candidates, last_modified } = loadMatrixCSV();
  const market_regime = await getDynamicMarketRegime();

  return NextResponse.json({
    success: true,
    market_regime,
    strategies: STRATEGIES,
    candidates,
    updated_at: last_modified || new Date().toISOString(),
  });
}

