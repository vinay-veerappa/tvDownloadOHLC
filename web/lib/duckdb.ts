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
      mainModule: '/duckdb/duckdb-eh.wasm',
      mainWorker: '/duckdb/duckdb-browser-eh.worker.js',
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

export async function loadParquet(name: string, url: string) {
  const { db, conn } = await initDuckDB();
  
  console.log(`--- Loading Parquet: ${name} from ${url} ---`);
  
  // Register remote parquet file via HTTP
  await db.registerFileURL(name, url, duckdb.DuckDBDataProtocol.HTTP, false);
  
  // Create view for easy querying
  const tableName = name.replace('.parquet', '').replace(/-/g, '_');
  await conn.query(`CREATE VIEW IF NOT EXISTS ${tableName} AS SELECT * FROM '${name}'`);
  
  console.log(`--- Table Registered: ${tableName} ---`);
  return tableName;
}

export async function runQuery(sql: string) {
  const { conn } = await initDuckDB();
  const result = await conn.query(sql);
  return result.toArray().map((row: any) => row.toJSON());
}
