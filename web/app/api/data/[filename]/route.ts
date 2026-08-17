import { NextRequest, NextResponse } from 'next/server';
import * as fs from 'fs';
import path from 'path';

/**
 * API Route to proxy parquet files from the root data/derived directory.
 * Ensures a single source of truth for the research dashboard.
 * Supports Range requests required by DuckDB-WASM over HTTP.
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ filename: string }> }
) {
  // Support both Nextjs 14 and 15 by handling Promise and object params
  const resolvedParams = await Promise.resolve(params);
  const { filename } = resolvedParams;

  // Validate filename to prevent path traversal
  if (!filename || !filename.endsWith('.parquet')) {
    return new NextResponse('Invalid file type', { status: 400 });
  }

  const filePath = path.join(process.cwd(), '..', 'data', 'derived', filename);

  if (!fs.existsSync(filePath)) {
    return new NextResponse(`File not found: ${filename}`, { status: 404 });
  }

  try {
    const stat = fs.statSync(filePath);
    const totalSize = stat.size;
    const lastModified = stat.mtime.toUTCString();
    const rangeHeader = request.headers.get('range');

    if (rangeHeader) {
      // Handle Range request for DuckDB
      const parts = rangeHeader.replace(/bytes=/, '').split('-');
      const start = parseInt(parts[0], 10);
      const end = parts[1] ? parseInt(parts[1], 10) : totalSize - 1;

      if (start >= totalSize || end >= totalSize) {
        return new NextResponse('', {
          status: 416,
          headers: {
            'Content-Range': `bytes */${totalSize}`
          }
        });
      }

      const chunksize = (end - start) + 1;
      
      // OPTIMIZED: Use file descriptor to read only the requested chunk
      const fd = fs.openSync(filePath, 'r');
      const buffer = Buffer.alloc(chunksize);
      fs.readSync(fd, buffer, 0, chunksize, start);
      fs.closeSync(fd);

      return new NextResponse(buffer, {
        status: 206,
        headers: {
          'Content-Type': 'application/octet-stream',
          'Content-Range': `bytes ${start}-${end}/${totalSize}`,
          'Accept-Ranges': 'bytes',
          'Content-Length': chunksize.toString(),
          'Last-Modified': lastModified,
          'Cache-Control': 'no-cache, no-store, must-revalidate',
        },
      });
    }

    // Return the whole file if no range (less common for DuckDB but supported)
    const fd = fs.openSync(filePath, 'r');
    const buffer = Buffer.alloc(totalSize);
    fs.readSync(fd, buffer, 0, totalSize, 0);
    fs.closeSync(fd);
    
    return new NextResponse(buffer, {
      status: 200,
      headers: {
        'Content-Type': 'application/octet-stream',
        'Content-Length': totalSize.toString(),
        'Accept-Ranges': 'bytes',
        'Last-Modified': lastModified,
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Content-Disposition': `attachment; filename="${filename}"`
      },
    });
  } catch (error) {
    console.error(`Error serving parquet file ${filename}:`, error);
    return new NextResponse('Internal Server Error', { status: 500 });
  }
}
