import { NextRequest, NextResponse } from 'next/server';
import fs from 'fs';
import path from 'path';

export async function GET(request: NextRequest) {
    const searchParams = request.nextUrl.searchParams;
    const ticker = searchParams.get('ticker');

    if (!ticker) {
        return NextResponse.json({ error: 'Ticker required' }, { status: 400 });
    }

    // Sanitize: /NQ -> -NQ, etc.
    const cleanTicker = ticker.replace('/', '-');
    const filename = `latest_quote_${cleanTicker}.json`;

    // Look in project/data folder
    // Assuming process.cwd() is project root ("web" folder usually in Next.js? No, usually root of next app)
    // Wait, the python script writes to "tvDownloadOHLC/data".
    // Next.js app is in "tvDownloadOHLC/web".
    // So data dir is "../data" relative to web root?
    // Let's check where process.cwd() is usually. Usually where `package.json` is.
    // If we run `npm run dev` in `web`, then process.cwd() is `.../web`.
    // So data is `../data`.

    const dataDir = path.join(process.cwd(), '..', 'data');
    const filePath = path.join(dataDir, filename);

    try {
        if (fs.existsSync(filePath)) {
            const fileContent = fs.readFileSync(filePath, 'utf-8');
            const data = JSON.parse(fileContent);
            return NextResponse.json(data);
        } else {
            // Return 404 or just null price if file not created yet
            return NextResponse.json({ error: 'Quote not found' }, { status: 404 });
        }
    } catch (e) {
        return NextResponse.json({ error: 'Failed to read quote' }, { status: 500 });
    }
}
