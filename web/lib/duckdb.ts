import * as duckdb from '@duckdb/duckdb-wasm';

/**
 * DuckDB-WASM Manager
 * 
 * Handles singleton instance of DuckDB in the browser and provides
 * simplified API for loading parquet files and executing queries.
 */

let db: duckdb.AsyncDuckDB | null = null;
let conn: duckdb.AsyncDuckDBConnection | null = null;
let initializationPromise: Promise<{ db: duckdb.AsyncDuckDB; conn: duckdb.AsyncDuckDBConnection }> | null = null;

export async function initDuckDB() {
  if (initializationPromise) return initializationPromise;

  initializationPromise = (async () => {
    if (db && conn) return { db, conn };

    // Use local assets from /public/duckdb to avoid cross-origin Worker security restrictions
    const MANIFEST = {
      mainModule: '/duckdb/duckdb-mvp.wasm',
      mainWorker: '/duckdb/duckdb-browser-mvp.worker.js',
    } as duckdb.DuckDBBundle;

    const logger = new duckdb.ConsoleLogger();
    db = new duckdb.AsyncDuckDB(logger, new Worker(MANIFEST.mainWorker!));
    await db.instantiate(MANIFEST.mainModule);
    conn = await db.connect();

    console.log('--- DuckDB-WASM Initialized ---');
    return { db, conn };
  })();

  return initializationPromise;
}

const loadingPromises = new Map<string, Promise<string>>();

export async function loadParquet(name: string, url: string) {
  if (loadingPromises.has(name)) return loadingPromises.get(name)!;

  const p = (async () => {
    const { db, conn } = await initDuckDB();
    
    // Convert relative URL to absolute URL to ensure DuckDB worker finds the file
    const absoluteUrl = new URL(url, window.location.origin).href;
    
    console.log(`--- Loading Parquet: ${name} from ${absoluteUrl} ---`);
    
    // Register remote parquet file via HTTP
    await db.registerFileURL(name, absoluteUrl, duckdb.DuckDBDataProtocol.HTTP, false);
    
    // Create view for easy querying
    const tableName = name.replace('.parquet', '').replace(/-/g, '_');
    await conn.query(`CREATE VIEW IF NOT EXISTS ${tableName} AS SELECT * FROM '${name}'`);
    
    console.log(`--- Table Registered: ${tableName} ---`);
    return tableName;
  })();

  loadingPromises.set(name, p);
  return p;
}

export async function runQuery(sql: string) {
  const { conn } = await initDuckDB();
  const result = await conn.query(sql);
  
  // Safely serialize Apache Arrow rows, handling BigInts and complex types
  const rows = result.toArray();
  return rows.map((row: any) => {
    try {
      const obj = row.toJSON();
      // Arrow toJSON doesn't stringify BigInt properly for React sometimes, manually walk it:
      const safeObj: any = {};
      for (const key in obj) {
        if (typeof obj[key] === 'bigint') {
          safeObj[key] = Number(obj[key]); // Or string if preferred
        } else {
          safeObj[key] = obj[key];
        }
      }
      return safeObj;
    } catch (e) {
      console.warn('Failed to serialize row:', e);
      return {};
    }
  });
}
