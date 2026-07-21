import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET(
  request: Request,
  { params }: { params: { type: string } }
) {
  try {
    const { type } = params;
    const validTypes = ['sp500', 'nasdaq100', 'themes', 'etfs'];
    
    if (!validTypes.includes(type)) {
      return NextResponse.json({ error: 'Invalid heatmap type' }, { status: 400 });
    }

    const filePath = path.join(process.cwd(), 'public/data/heatmaps', `${type}.json`);
    
    if (!fs.existsSync(filePath)) {
      return NextResponse.json({ error: 'Heatmap data file not found' }, { status: 440 });
    }

    const fileContent = fs.readFileSync(filePath, 'utf-8');
    const data = JSON.parse(fileContent);

    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
