"use server";

import prisma from "@/lib/prisma";
import { revalidatePath } from "next/cache";

export interface CsvTradeRow {
  ticker: string;
  direction: "LONG" | "SHORT";
  entryDate: string; // ISO date string
  exitDate?: string;
  entryPrice: number;
  exitPrice?: number;
  quantity: number;
  pnl?: number;
  stopLoss?: number;
  takeProfit?: number;
  notes?: string;
  strategy?: string;
}

// Export trades to CSV format
export async function exportTradesToCsv(filters?: {
  accountId?: string;
  strategyId?: string;
  startDate?: Date;
  endDate?: Date;
}) {
  try {
    const where: any = {};

    if (filters?.accountId) where.accountId = filters.accountId;
    if (filters?.strategyId) where.strategyId = filters.strategyId;
    if (filters?.startDate || filters?.endDate) {
      where.entryDate = {};
      if (filters.startDate) where.entryDate.gte = filters.startDate;
      if (filters.endDate) where.entryDate.lte = filters.endDate;
    }

    const trades = await prisma.trade.findMany({
      where,
      include: { strategy: true, account: true },
      orderBy: { entryDate: "asc" },
    });

    const csvHeader = [
      "id",
      "ticker",
      "direction",
      "entryDate",
      "exitDate",
      "entryPrice",
      "exitPrice",
      "quantity",
      "pnl",
      "stopLoss",
      "takeProfit",
      "status",
      "strategy",
      "account",
      "notes",
    ].join(",");

    const csvRows = trades.map((t) =>
      [
        t.id,
        t.ticker,
        t.direction,
        t.entryDate.toISOString(),
        t.exitDate?.toISOString() || "",
        t.entryPrice,
        t.exitPrice || "",
        t.quantity,
        t.pnl || "",
        t.stopLoss || "",
        t.takeProfit || "",
        t.status,
        t.strategy?.name || "",
        t.account?.name || "",
        `"${(t.notes || "").replace(/"/g, '""')}"`,
      ].join(","),
    );

    const csv = [csvHeader, ...csvRows].join("\n");

    return { success: true, data: csv, count: trades.length };
  } catch (error) {
    console.error("Export failed:", error);
    return { success: false, error: "Failed to export trades" };
  }
}

// ------------------------------------------------------------------
// Import Logic
// ------------------------------------------------------------------

type BrokerFormat = "TRADINGVIEW" | "TRADOVATE" | "TOPSTEPX" | "NINJATRADER" | "GENERIC";

function detectBrokerFormat(headers: string[]): BrokerFormat {
    const h = headers.join(",").toLowerCase();
    
    // TopstepX: Id,ContractName,EnteredAt,ExitedAt...
    if (h.includes("contractname") && h.includes("enteredat") && h.includes("exitedat")) {
        return "TOPSTEPX";
    }
    
    // NinjaTrader: Instrument,Account,Strategy,Market pos.,Qty...
    // Also Header might be "Trade number" first
    if ((h.includes("instrument") && h.includes("market pos.") && h.includes("strategy")) || 
        (h.includes("trade number") && h.includes("entry price") && h.includes("exit price"))) {
        return "NINJATRADER";
    }

    // TradingView Strategy Tester: Trade #,Type,Date and time...
    if (h.includes("trade #") && h.includes("date and time") && h.includes("signal")) {
        return "TRADINGVIEW";
    }

    // TradingView Trade History (Manual): Symbol,Side,Qty,Fill Price,Closing Time...
    if ((h.includes("fill price") && (h.includes("closing time") || h.includes("close time"))) || 
        (h.includes("order id") && h.includes("commission") && h.includes("symbol"))) {
        return "TRADINGVIEW"; // Broaden detection for manual exports too
    }
    
    // Tradovate: Account, Contract, B/S, Price...
    if (h.includes("account") && (h.includes("b/s") || h.includes("side")) && h.includes("avg price")) {
        return "TRADOVATE";
    }
    
    return "GENERIC";
}

// Helper to parse CSV line with quote handling
function parseCsvLine(line: string): string[] {
  const result: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === "," && !inQuotes) {
      result.push(current.trim());
      current = "";
    } else {
      current += char;
    }
  }
  result.push(current.trim());
  return result;
}

// Helper for currency string parsing: ($100.00) -> -100.00
function parseCurrency(val: string): number {
    if (!val) return 0;
    const clean = val.replace(/[$,]/g, "").trim();
    if (clean.startsWith("(") && clean.endsWith(")")) {
        return -parseFloat(clean.slice(1, -1));
    }
    return parseFloat(clean);
}

async function parseNinjaTraderCsv(lines: string[], accountId: string, strategyId?: string) {
    const trades: any[] = [];
    const errors: string[] = [];
    
    // Headers: Instrument,Account,Strategy,Market pos.,Qty,Entry price,Exit price,Entry time,Exit time,Entry name,Exit name,Profit,Cum. net profit...
    // Note: The header might contain "Market pos." with a dot.
    const headersRaw = parseCsvLine(lines[0]); 
    // Normalize headers for lookup but keep original index structure
    const headers = headersRaw.map(h => h.trim().toLowerCase());

    const rows = lines.slice(1);

    for (let i = 0; i < rows.length; i++) {
        const row = parseCsvLine(rows[i]);
        if (row.length < 5) continue;

        const getCol = (namePart: string) => {
            // Find index where header contains the namePart
            const idx = headers.findIndex(h => h.includes(namePart.toLowerCase()));
            return idx !== -1 ? row[idx] : undefined;
        };

        try {
            const ticker = getCol("Instrument");
            const directionStr = getCol("Market pos") || getCol("Market pos.");
            const qtyStr = getCol("Qty");
            const entryPriceStr = getCol("Entry price");
            const exitPriceStr = getCol("Exit price");
            const entryTimeStr = getCol("Entry time");
            const exitTimeStr = getCol("Exit time");
            const pnlStr = getCol("Profit");
            
            // Advanced NinjaTrader fields
            const maeStr = getCol("MAE");
            const mfeStr = getCol("MFE");
            const etdStr = getCol("ETD"); // Exit Trade Drawdown (profit giveback)

            // Skip empty rows or summary rows
            if (!ticker || !entryTimeStr) continue;

            const entryDate = new Date(entryTimeStr);
            const exitDate = exitTimeStr ? new Date(exitTimeStr) : undefined;
            const entryPrice = parseFloat(entryPriceStr || "0");
            const exitPrice = parseFloat(exitPriceStr || "0");
            const quantity = parseFloat(qtyStr || "0");
            const pnl = parseCurrency(pnlStr || "0");
            const mae = parseCurrency(maeStr || "0"); // Usually positive in NT CSV export but represents adverse
            const mfe = parseCurrency(mfeStr || "0"); // Usually positive
            
            // Fix MAE sign if NT exports it as positive absolute value
            // MAE (Max Adverse) is typically a drawdown, so maybe store as negative?
            // Edgewonk often stores MAE/MFE as absolute distances or prices. 
            // Our schema uses Float. Let's store the price or the value?
            // Re-reading schema: `mae Float? // Max Adverse Excursion price`
            // If the CSV gives DOLLAR value of MAE (like $66.00), we might need to convert to price if we want PRICE.
            // But usually MAE/MFE in generic journals are stored as PnL impact ($).
            // Let's check a sample row:
            // "1,MNQ 03-26... Long,1,22720.00... MAE $66.00"
            // MAE $66 with 1 contract ($2 per tick) -> 33 ticks.
            // If we store the dollar value, that's fine for PnL analysis.
            // Let's store the Dollar Value for now as that's what is in the CSV.
            // We can rename schema later if we strictly want price.
            // Actually, for "Analysis" derived fields, storing the $ impact is often more useful for "Risk Multiple" calcs.
            
            const direction = directionStr?.toLowerCase().includes("long") ? "LONG" : "SHORT";
            const status = "CLOSED"; 

            trades.push({
                accountId,
                strategyId, // Pass through if user selected, otherwise null
                ticker,
                direction,
                entryDate,
                exitDate,
                entryPrice,
                exitPrice,
                quantity,
                pnl,
                mae, // Store raw dollar value from NT
                mfe, // Store raw dollar value from NT
                metadata: JSON.stringify({ etd: parseCurrency(etdStr || "0") }), // Store ETD in metadata for now
                status,
                orderType: "MARKET",
                originalSource: "NINJATRADER_CSV"
            });

        } catch (e) {
            errors.push(`Row ${i + 2}: ${String(e)}`);
        }
    }
    return { trades, errors };
}

async function parseTopstepXCsv(lines: string[], accountId: string, strategyId?: string) {
    const trades: any[] = [];
    const errors: string[] = [];
    
    // Headers: Id,ContractName,EnteredAt,ExitedAt,EntryPrice,ExitPrice,Fees,PnL,Size,Type,TradeDay,TradeDuration,Commissions
    const headers = parseCsvLine(lines[0].toLowerCase());
    const rows = lines.slice(1);

    for (let i = 0; i < rows.length; i++) {
        const row = parseCsvLine(rows[i]);
        if (row.length < 5) continue;

        const getCol = (name: string) => {
            const idx = headers.findIndex(h => h === name.toLowerCase());
            return idx !== -1 ? row[idx] : undefined;
        };

        try {
            const ticker = getCol("ContractName");
            const enteredAtRaw = getCol("EnteredAt");
            const exitedAtRaw = getCol("ExitedAt"); // Can be empty if open? Topstep usually closed.
            const entryPriceStr = getCol("EntryPrice");
            const exitPriceStr = getCol("ExitPrice");
            const sizeStr = getCol("Size");
            const typeRaw = getCol("Type"); // "Long" or "Short"
            const pnlStr = getCol("PnL");

            if (!ticker || !enteredAtRaw) continue;

            const entryDate = new Date(enteredAtRaw);
            const exitDate = exitedAtRaw ? new Date(exitedAtRaw) : undefined;
            const entryPrice = parseFloat(entryPriceStr || "0");
            const exitPrice = parseFloat(exitPriceStr || "0");
            const quantity = parseFloat(sizeStr || "0");
            const pnl = parseFloat(pnlStr || "0");
            
            const direction = typeRaw?.toUpperCase() === "LONG" ? "LONG" : "SHORT";
            const status = "CLOSED"; // TopstepX export is typically closed trades

            trades.push({
                accountId,
                strategyId,
                ticker,
                direction,
                entryDate,
                exitDate,
                entryPrice,
                exitPrice,
                quantity,
                pnl,
                status,
                orderType: "MARKET",
                originalSource: "TOPSTEPX_CSV"
            });

        } catch (e) {
            errors.push(`Row ${i + 2}: ${String(e)}`);
        }
    }
    return { trades, errors };
}

async function parseTradingViewCsv(lines: string[], accountId: string, strategyId?: string) {
    const trades: any[] = [];
    const errors: string[] = [];
    
    const headers = parseCsvLine(lines[0].toLowerCase());
    
    // Check if Strategy Tester Format
    if (headers.includes("trade #") && headers.includes("date and time") && headers.includes("signal")) {
        // Strategy Tester Parsing (Grouped Rows)
        const rows = lines.slice(1).map(l => parseCsvLine(l));
        const tradeGroups = new Map<string, any[]>(); // Trade # -> Rows[]

        const colIdx = {
            tradeNum: headers.indexOf("trade #"),
            type: headers.indexOf("type"),
            dateTime: headers.indexOf("date and time"),
            signal: headers.indexOf("signal"),
            price: headers.indexOf("price usd"), // "Price USD" often
            qty: headers.indexOf("position size (qty)"),
            pnl: headers.indexOf("net p&l usd"), // "Net P&L USD"
        };
        
        // Use generic "price" search if specific not found
        if (colIdx.price === -1) colIdx.price = headers.findIndex(h => h.includes("price"));
        if (colIdx.pnl === -1) colIdx.pnl = headers.findIndex(h => h.includes("net p&l") || h.includes("profit"));
        if (colIdx.qty === -1) colIdx.qty = headers.findIndex(h => h.includes("qty") || h.includes("contracts"));

        // Group rows
        for (const row of rows) {
            if (row.length < 2) continue;
            const tradeId = row[colIdx.tradeNum];
            if (!tradeId) continue;
            
            if (!tradeGroups.has(tradeId)) tradeGroups.set(tradeId, []);
            tradeGroups.get(tradeId)?.push(row);
        }

        // Process Groups
        for (const [id, group] of tradeGroups.entries()) {
            try {
                const entryRow = group.find(r => r[colIdx.type].toLowerCase().includes("entry"));
                const exitRow = group.find(r => r[colIdx.type].toLowerCase().includes("exit"));
                
                if (!entryRow) {
                    errors.push(`Trade #${id}: Missing entry row`);
                    continue;
                }

                // Assume Entry row has the correct Direction
                const typeStr = entryRow[colIdx.type].toLowerCase();
                const direction = typeStr.includes("long") ? "LONG" : "SHORT";
                
                const entryDateStr = entryRow[colIdx.dateTime];
                const entryDate = new Date(entryDateStr);
                const entryPrice = parseFloat(entryRow[colIdx.price] || "0");
                const quantity = parseFloat(entryRow[colIdx.qty] || "1"); // Default 1
                
                // Exit details
                const exitDate = exitRow ? new Date(exitRow[colIdx.dateTime]) : undefined;
                const exitPrice = exitRow ? parseFloat(exitRow[colIdx.price] || "0") : undefined;
                
                // PnL usually on both or just exit? In sample, it's on both.
                // We prefer the value from the Exit row if available as it's final.
                const pnlRaw = exitRow ? exitRow[colIdx.pnl] : (entryRow[colIdx.pnl] || "0");
                const pnl = parseFloat(pnlRaw || "0");

                // Get Ticker from filename or context? TV Strategy export doesn't have Ticker column usually!
                // It's usually "Symbol" in the first row meta-data or undefined.
                // We will default to a placeholder if not found, or use the "Signal" if it looks like a symbol
                // In the sample `ORBv5_CME_MINI_NQ1!...`, the filename has it. 
                // But inside CSV, no ticker column. 
                // We'll use "NQ1!" or user-supplied context. 
                // For now, let's look for known symbols in "Signal" or fallback.
                const ticker = "UNK_TV_STRAT"; // Placeholder, user can edit.

                trades.push({
                    accountId,
                    strategyId,
                    ticker, 
                    direction,
                    entryDate,
                    exitDate,
                    entryPrice,
                    exitPrice,
                    quantity,
                    pnl,
                    status: exitDate ? "CLOSED" : "OPEN",
                    notes: `TV Signal: ${entryRow[colIdx.signal]}`,
                    originalSource: "TV_STRATEGY_TESTER"
                });

            } catch (e) {
                errors.push(`Trade #${id}: Parse error`);
            }
        }

    } else {
        // Fallback or other TV formats (Manual Trade History)
        // ... (existing logic or error)
        errors.push("Detected TradingView but format not Strategy Tester. Manual history implementation pending.");
    }
    
    return { trades, errors };
}

async function parseTradovateCsv(lines: string[], accountId: string, strategyId?: string) {
    const trades: any[] = [];
    const errors: string[] = [];
    errors.push("Tradovate import not fully implemented pending sample data verification.");
    return { trades, errors };
}

function parseGenericCsv(lines: string[], header: string[], accountId: string, strategyId?: string) {
  const trades: any[] = [];
  const errors: string[] = [];
  const dataLines = lines.slice(1);

  // Map column indices
  const colIdx = {
    ticker: header.findIndex(h => h.includes("ticker") || h.includes("symbol") || h.includes("contract")),
    direction: header.findIndex(h => h.includes("direction") || h.includes("side") || h.includes("type")),
    entryDate: header.findIndex(h => h.includes("entrydate") || h.includes("entry_date") || h.includes("time") || h.includes("date")),
    exitDate: header.findIndex(h => h.includes("exitdate") || h.includes("exit_date")), // Optional
    entryPrice: header.findIndex(h => h.includes("entryprice") || h.includes("entry_price") || h.includes("price")),
    exitPrice: header.findIndex(h => h.includes("exitprice") || h.includes("exit_price")), // Optional
    quantity: header.findIndex(h => h.includes("quantity") || h.includes("qty") || h.includes("size")),
    pnl: header.findIndex(h => h.includes("pnl") || h.includes("profit")),
    notes: header.findIndex(h => h.includes("note")),
  };

  if (colIdx.ticker < 0 || colIdx.entryDate < 0 || colIdx.entryPrice < 0) {
    errors.push("Generic CSV missing required columns: Symbol/Ticker, Date/Time, Price");
    return { trades, errors };
  }

  for (let i = 0; i < dataLines.length; i++) {
    const line = dataLines[i];
    const cols = parseCsvLine(line);
    if (cols.length < 2) continue;

    try {
      const ticker = cols[colIdx.ticker]?.trim();
      const rawDirection = colIdx.direction >= 0 ? cols[colIdx.direction]?.trim().toUpperCase() : "LONG"; // Default
      const entryDateStr = cols[colIdx.entryDate]?.trim();
      const entryPriceVal = parseFloat(cols[colIdx.entryPrice]?.replace(/[^0-9.-]/g, "") || "0");

      if (!ticker || !entryDateStr) continue;

      const entryDate = new Date(entryDateStr);
      let exitDate: Date | undefined;
      let exitPrice: number | undefined;
      let pnl: number | undefined;
      
      if (colIdx.exitDate >= 0 && cols[colIdx.exitDate]) exitDate = new Date(cols[colIdx.exitDate]);
      if (colIdx.exitPrice >= 0 && cols[colIdx.exitPrice]) exitPrice = parseFloat(cols[colIdx.exitPrice]);
      if (colIdx.pnl >= 0 && cols[colIdx.pnl]) pnl = parseFloat(cols[colIdx.pnl].replace(/[^0-9.-]/g, ""));

      const direction = (rawDirection.includes("SHORT") || rawDirection.includes("SELL")) ? "SHORT" : "LONG";
      
      trades.push({
        accountId,
        strategyId,
        ticker,
        direction,
        entryDate,
        exitDate,
        entryPrice: entryPriceVal,
        exitPrice,
        quantity: colIdx.quantity >= 0 ? parseFloat(cols[colIdx.quantity]) || 1 : 1,
        pnl,
        status: exitDate ? "CLOSED" : "OPEN",
        notes: colIdx.notes >= 0 ? cols[colIdx.notes] : undefined,
        originalSource: "GENERIC_CSV",
      });
    } catch (err) {
      errors.push(`Row ${i + 2}: Parse error`);
    }
  }
  return { trades, errors };
}

export async function importTradesFromCsv(formData: FormData) {
    const file = formData.get("file") as File;
    const accountId = formData.get("accountId") as string;
    // Default Strategy handling if we add it to the UI later
    // const defaultStrategy = formData.get("strategy") as string; 

    if (!file || !accountId) {
        return { success: false, error: "Missing file or account ID" };
    }

    try {
        const text = await file.text();
        const lines = text.split(/\r?\n/).filter(line => line.trim());
        
        if (lines.length < 2) {
            return { success: false, error: "CSV file is empty or missing header" };
        }

        const headerLine = lines[0];
        const headers = parseCsvLine(headerLine.toLowerCase()); // Normalize
        const format = detectBrokerFormat(headers);
        
        console.log(`Detected CSV Format: ${format}`); // For debugging

        let result;
        if (format === "TOPSTEPX") {
            result = await parseTopstepXCsv(lines, accountId);
        } else if (format === "NINJATRADER") {
            result = await parseNinjaTraderCsv(lines, accountId);
        } else if (format === "TRADINGVIEW") {
            result = await parseTradingViewCsv(lines, accountId);
        } else if (format === "TRADOVATE") {
            result = await parseTradovateCsv(lines, accountId);
        } else {
            // For Generic fallbacks, use strict headers if ambiguous, or loosen generic logic
            result = parseGenericCsv(lines, headers, accountId);
        }

        const { trades, errors } = result;

        if (trades.length === 0) {
            return { 
                success: false, 
                error: "No valid trades found to import.", 
                details: errors.slice(0, 10).join("\n") 
            };
        }

        // Bulk insert
        const CHUNK_SIZE = 50;
        let importedCount = 0;
        
        for (let i = 0; i < trades.length; i += CHUNK_SIZE) {
            const chunk = trades.slice(i, i + CHUNK_SIZE);
            await prisma.trade.createMany({ data: chunk });
            importedCount += chunk.length;
        }

        revalidatePath("/journal");
        return { success: true, count: importedCount, failed: errors.length };

    } catch (e) {
        console.error("Import error:", e);
        return { success: false, error: "Failed to process CSV: " + String(e) };
    }
}
