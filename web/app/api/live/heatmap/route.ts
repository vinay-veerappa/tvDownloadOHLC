import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const ticker = searchParams.get('ticker') || 'ES';
  
  const basePath = path.join(process.cwd(), '..', 'data', 'live');
  const heatmapPath = path.join(basePath, `heatmap_${ticker}.json`);
  const mhvnsPath = path.join(basePath, `mhvns_${ticker}.json`);

  try {
    let heatmapData = [];
    let mhvnsData = null;

    if (fs.existsSync(heatmapPath)) {
      heatmapData = JSON.parse(fs.readFileSync(heatmapPath, 'utf8'));
    }
    
    if (fs.existsSync(mhvnsPath)) {
      mhvnsData = JSON.parse(fs.readFileSync(mhvnsPath, 'utf8'));
    }

    return NextResponse.json({ heatmap: heatmapData, mhvns: mhvnsData });
  } catch (error) {
    return NextResponse.json({ error: 'Failed to read data' }, { status: 500 });
  }
}
