import { NextResponse } from 'next/server';
import * as fs from 'fs';
import path from 'path';

type IbTable = 'ib_facts' | 'ib_ext_detail' | 'ib_play_detail' | 'ib_level_touch_detail';

const TABLES: IbTable[] = ['ib_facts', 'ib_ext_detail', 'ib_play_detail', 'ib_level_touch_detail'];

function parseFilename(name: string): { table: IbTable; symbol: string } | null {
  const m = name.match(/^(ib_facts|ib_ext_detail|ib_play_detail|ib_level_touch_detail)_([A-Za-z0-9]+)\.parquet$/);
  if (!m) return null;
  return { table: m[1] as IbTable, symbol: m[2] };
}

export async function GET() {
  const dataDir = path.join(process.cwd(), '..', 'data', 'derived');

  if (!fs.existsSync(dataDir)) {
    return NextResponse.json({ symbols: [], tables: {}, files: [] });
  }

  const files = fs.readdirSync(dataDir).filter((f) => f.endsWith('.parquet'));
  const tableMap: Record<IbTable, string[]> = {
    ib_facts: [],
    ib_ext_detail: [],
    ib_play_detail: [],
    ib_level_touch_detail: [],
  };
  const symbolSet = new Set<string>();

  for (const name of files) {
    const parsed = parseFilename(name);
    if (!parsed) continue;
    tableMap[parsed.table].push(parsed.symbol);
    symbolSet.add(parsed.symbol);
  }

  for (const table of TABLES) {
    tableMap[table] = [...new Set(tableMap[table])].sort();
  }

  return NextResponse.json({
    symbols: [...symbolSet].sort(),
    tables: tableMap,
    files: files.sort(),
  });
}
