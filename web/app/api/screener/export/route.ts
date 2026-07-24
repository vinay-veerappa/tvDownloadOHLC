import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

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

const REPO_ROOT = getRepoRoot();
const REPORTS_DIR = path.join(REPO_ROOT, 'reports', 'screener');


export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const exportType = (searchParams.get('type') || 'matrix').toLowerCase();

  let fileName = 'strategy_comparison_matrix.csv';
  let downloadName = 'strategy_comparison_matrix.csv';

  if (exportType === 'tradingview' || exportType === 'tv') {
    fileName = 'tradingview_watchlist.csv';
    downloadName = 'tradingview_watchlist.csv';
  } else if (exportType === 'thinkorswim' || exportType === 'tos') {
    fileName = 'thinkorswim_watchlist.csv';
    downloadName = 'thinkorswim_watchlist.csv';
  }

  const filePath = path.join(REPORTS_DIR, fileName);

  if (!fs.existsSync(filePath)) {
    return new NextResponse('Report file not found. Please run the screener scan first.', { status: 404 });
  }

  const csvContent = fs.readFileSync(filePath, 'utf-8');

  return new NextResponse(csvContent, {
    status: 200,
    headers: {
      'Content-Type': 'text/csv; charset=utf-8',
      'Content-Disposition': `attachment; filename="${downloadName}"`,
      'Cache-Control': 'no-store',
    },
  });
}
