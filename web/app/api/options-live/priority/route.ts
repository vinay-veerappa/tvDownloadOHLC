import { NextRequest, NextResponse } from "next/server";
import fs from "fs/promises";
import path from "path";

const REPO_ROOT = path.resolve(process.cwd(), "..");
const PRIORITY_FILE = path.join(REPO_ROOT, "priority_tickers.json");
const TRIGGER_FILE = path.join(REPO_ROOT, "manual_trigger.json");

/**
 * GET: Return current priority tickers
 */
export async function GET() {
  try {
    const data = await fs.readFile(PRIORITY_FILE, "utf-8");
    return NextResponse.json(JSON.parse(data));
  } catch (e) {
    // If file doesn't exist, return empty array
    return NextResponse.json([]);
  }
}

/**
 * POST: Update priority tickers or trigger a refresh
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { action, ticker, priorityList } = body;

    if (action === "update_priority") {
      if (!Array.isArray(priorityList)) {
        return NextResponse.json({ error: "priorityList must be an array" }, { status: 400 });
      }
      await fs.writeFile(PRIORITY_FILE, JSON.stringify(priorityList, null, 2));
      return NextResponse.json({ success: true, priorityList });
    }

    if (action === "refresh_ticker") {
      if (!ticker) {
        return NextResponse.json({ error: "ticker is required" }, { status: 400 });
      }
      
      // Append to manual_trigger.json if it exists, otherwise create it
      let currentTrigger: string[] = [];
      try {
          const data = await fs.readFile(TRIGGER_FILE, "utf-8");
          currentTrigger = JSON.parse(data);
      } catch (e) {}
      
      if (!currentTrigger.includes(ticker)) {
          currentTrigger.push(ticker);
          await fs.writeFile(TRIGGER_FILE, JSON.stringify(currentTrigger, null, 2));
      }
      
      return NextResponse.json({ success: true, message: `Refresh triggered for ${ticker}` });
    }

    return NextResponse.json({ error: "Invalid action" }, { status: 400 });
  } catch (err: any) {
    console.error("[Priority API POST]", err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
