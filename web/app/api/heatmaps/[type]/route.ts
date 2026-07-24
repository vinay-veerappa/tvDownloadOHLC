import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET(
  request: Request,
  { params }: { params: Promise<{ type: string }> }
) {
  try {
    const { type } = await params;
    const validTypes = ['sp500', 'nasdaq100', 'themes', 'etfs'];
    
    if (!validTypes.includes(type)) {
      return NextResponse.json({ error: 'Invalid heatmap type' }, { status: 400 });
    }

    const candidates = [
      path.join(process.cwd(), 'public/data/heatmaps', `${type}.json`),
      path.join(process.cwd(), 'web/public/data/heatmaps', `${type}.json`),
      path.join(process.cwd(), '../web/public/data/heatmaps', `${type}.json`),
    ];

    let filePath = candidates.find((p) => fs.existsSync(p));

    if (!filePath) {
      return NextResponse.json({ error: `Heatmap data file '${type}.json' not found` }, { status: 404 });
    }

    const fileContent = fs.readFileSync(filePath, 'utf-8');

    const data = JSON.parse(fileContent);

    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
