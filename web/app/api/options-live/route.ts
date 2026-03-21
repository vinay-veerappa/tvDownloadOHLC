import { NextResponse } from "next/server";
import fs from "fs/promises";
import path from "path";

// Define where the Python script is writing the files
const DATA_DIR = path.join(process.cwd(), "..", "data"); // Point to /data folder in root

export async function GET() {
  try {
    const dailyLevelsPath = path.join(DATA_DIR, "daily_levels.json");
    const pipelineStatePath = path.join(DATA_DIR, "pipeline_state.json");
    const gexProfilesPath = path.join(DATA_DIR, "gex_profiles.json");
    const liveTrendPath = path.join(DATA_DIR, "live_trend.json");

    let dailyLevels = [];
    let pipelineState = {};
    let gexProfiles = {};
    let liveTrend = {};

    try {
      const dailyLevelsContent = await fs.readFile(dailyLevelsPath, "utf-8");
      dailyLevels = JSON.parse(dailyLevelsContent);
    } catch (e) {
      console.warn("Could not read daily_levels.json", e);
    }

    try {
      const pipelineStateContent = await fs.readFile(pipelineStatePath, "utf-8");
      pipelineState = JSON.parse(pipelineStateContent);
    } catch (e) {
      console.warn("Could not read pipeline_state.json", e);
    }

    try {
      const gexProfilesContent = await fs.readFile(gexProfilesPath, "utf-8");
      gexProfiles = JSON.parse(gexProfilesContent);
    } catch (e) {
      console.warn("Could not read gex_profiles.json", e);
    }

    try {
      const liveTrendContent = await fs.readFile(liveTrendPath, "utf-8");
      liveTrend = JSON.parse(liveTrendContent);
    } catch (e) {
      console.warn("Could not read live_trend.json", e);
    }

    return NextResponse.json({
      success: true,
      lastUpdated: new Date().toISOString(),
      data: {
        dailyLevels,
        pipelineState,
        gexProfiles,
        liveTrend,
      },
    });
  } catch (error) {
    console.error("Error fetching options live data:", error);
    return NextResponse.json(
      { success: false, error: "Failed to load live options data" },
      { status: 500 }
    );
  }
}
