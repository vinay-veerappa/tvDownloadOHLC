import type {
  AsyncDuckDB,
  AsyncDuckDBConnection,
  DuckDBBundles,
} from '@duckdb/duckdb-wasm';

/**
 * DuckDB-WASM Manager
 * 
 * Handles singleton instance of DuckDB in the browser and provides
 * simplified API for loading parquet files and executing queries.
 */

type DuckDbBrowserModule = typeof import('@duckdb/duckdb-wasm/dist/duckdb-browser.mjs');

let duckdbModule: DuckDbBrowserModule | null = null;
let db: AsyncDuckDB | null = null;
let conn: AsyncDuckDBConnection | null = null;
let worker: Worker | null = null;
let initializationPromise: Promise<{ db: AsyncDuckDB; conn: AsyncDuckDBConnection }> | null = null;

export type DuckDbRow = Record<string, unknown>;

async function getDuckDbModule(): Promise<DuckDbBrowserModule> {
  if (duckdbModule) return duckdbModule;
  if (typeof window === 'undefined') {
    throw new Error('DuckDB-WASM is browser-only and cannot initialize during server render.');
  }
  duckdbModule = await import('@duckdb/duckdb-wasm/dist/duckdb-browser.mjs');
  return duckdbModule;
}

export async function initDuckDB() {
  if (initializationPromise) return initializationPromise;

  initializationPromise = (async () => {
    if (db && conn) return { db, conn };
    const duckdb = await getDuckDbModule();

    if (typeof Worker === 'undefined') {
      throw new Error('Web Worker API is unavailable in this environment.');
    }

    // Dynamically select the best bundle (MVP or EH) for the browser environment
    // to prevent errors like "_setThrew is not defined" on modern browsers.
    const BUNDLES: DuckDBBundles = {
      mvp: {
        mainModule: '/duckdb/duckdb-mvp.wasm',
        mainWorker: '/duckdb/duckdb-browser-mvp.worker.js',
      },
      eh: {
        mainModule: '/duckdb/duckdb-eh.wasm',
        mainWorker: '/duckdb/duckdb-browser-eh.worker.js',
      },
    };

    const bundle = await duckdb.selectBundle(BUNDLES);
    const logger = new duckdb.ConsoleLogger();
    worker = new Worker(bundle.mainWorker!);
    db = new duckdb.AsyncDuckDB(logger, worker);
    await db.instantiate(bundle.mainModule);
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
    const duckdb = await getDuckDbModule();
    
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

export async function resetDuckDB() {
  loadingPromises.clear();

  try {
    if (conn) {
      await conn.close();
    }
  } catch (error) {
    console.warn('Failed to close DuckDB connection cleanly:', error);
  }

  try {
    if (db) {
      await db.terminate();
    }
  } catch (error) {
    console.warn('Failed to terminate DuckDB cleanly:', error);
  }

  try {
    worker?.terminate();
  } catch (error) {
    console.warn('Failed to terminate DuckDB worker cleanly:', error);
  }

  db = null;
  conn = null;
  worker = null;
  duckdbModule = null;
  initializationPromise = null;
}

export async function runQuery<T extends object = DuckDbRow>(sql: string): Promise<T[]> {
  const { conn } = await initDuckDB();
  const result = await conn.query(sql);
  
  // Safely serialize Apache Arrow rows, handling BigInts and complex types
  const rows = result.toArray();
  return rows.map((row: any): T => {
    try {
      const obj = row.toJSON() as Record<string, unknown>;
      // Arrow toJSON doesn't stringify BigInt properly for React sometimes, manually walk it:
      const safeObj: DuckDbRow = {};
      for (const key in obj) {
        if (typeof obj[key] === 'bigint') {
          safeObj[key] = Number(obj[key]); // Or string if preferred
        } else {
          safeObj[key] = obj[key];
        }
      }
      return safeObj as T;
    } catch (e) {
      console.warn('Failed to serialize row:', e);
      throw new Error(`DuckDB row serialization failed: ${e instanceof Error ? e.message : String(e)}`);
    }
  });
}
