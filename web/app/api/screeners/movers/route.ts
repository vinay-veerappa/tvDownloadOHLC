import { NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET() {
  try {
    const filePath = path.join(process.cwd(), 'public/data/screeners/top_movers.json');
    if (!fs.existsSync(filePath)) {
      return NextResponse.json({ topGainers: [], topLosers: [], volumeLeaders: [] });
    }
    const fileContent = fs.readFileSync(filePath, 'utf-8');
    const data = JSON.parse(fileContent);
    return NextResponse.json(data);
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
