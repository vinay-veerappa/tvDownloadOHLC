/*
  Warnings:

  - You are about to drop the `Watchlist` table. If the table is not empty, all the data it contains will be lost.

*/
-- DropIndex
DROP INDEX "Watchlist_symbol_key";

-- AlterTable
ALTER TABLE "ExpectedMove" ADD COLUMN "basis" TEXT;
ALTER TABLE "ExpectedMove" ADD COLUMN "note" TEXT;

-- DropTable
PRAGMA foreign_keys=off;
DROP TABLE "Watchlist";
PRAGMA foreign_keys=on;

-- CreateTable
CREATE TABLE "AccountGroup" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "Playbook" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "rules" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "Rundown" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "date" DATETIME NOT NULL,
    "content" TEXT,
    "mood" TEXT,
    "score" INTEGER,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "ResearchStrategy" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "color" TEXT NOT NULL DEFAULT '#2962FF',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "ResearchRun" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "runId" TEXT NOT NULL,
    "ticker" TEXT NOT NULL,
    "environment" TEXT NOT NULL DEFAULT 'Backtest',
    "strategyId" TEXT NOT NULL,
    "metricsJson" TEXT,
    "configJson" TEXT,
    "equityCurveJson" TEXT,
    "grade" TEXT,
    "filePath" TEXT,
    "gitHash" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "ResearchRun_strategyId_fkey" FOREIGN KEY ("strategyId") REFERENCES "ResearchStrategy" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "WatchlistGroup" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "isDefault" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "WatchlistItem" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "symbol" TEXT NOT NULL,
    "name" TEXT,
    "groupId" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "WatchlistItem_groupId_fkey" FOREIGN KEY ("groupId") REFERENCES "WatchlistGroup" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "HistoricalVolatility" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "ticker" TEXT NOT NULL,
    "date" DATETIME NOT NULL,
    "iv" REAL NOT NULL,
    "hv" REAL,
    "closePrice" REAL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "ExpectedMoveHistory" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "ticker" TEXT NOT NULL,
    "date" DATETIME NOT NULL,
    "closePrice" REAL NOT NULL,
    "straddlePrice" REAL,
    "emStraddle" REAL,
    "iv365" REAL,
    "em365" REAL,
    "iv252" REAL,
    "em252" REAL,
    "source" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "RthExpectedMove" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "ticker" TEXT NOT NULL,
    "date" DATETIME NOT NULL,
    "openPrice" REAL,
    "vixValue" REAL,
    "straddlePrice" REAL,
    "emStraddle" REAL,
    "ivAtOpen" REAL,
    "emIv" REAL,
    "emVix" REAL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "Analysis" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "date" DATETIME NOT NULL,
    "sentiment" TEXT,
    "bias" TEXT,
    "notes" TEXT,
    "keyLevels" TEXT,
    "invalidationLevel" TEXT,
    "profilerSnapshot" TEXT,
    "candleScienceSnapshot" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "Wargame" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "analysisId" TEXT NOT NULL,
    "scenario" TEXT NOT NULL,
    "plan" TEXT NOT NULL,
    "probability" TEXT,
    "outcome" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Wargame_analysisId_fkey" FOREIGN KEY ("analysisId") REFERENCES "Analysis" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Routine" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "date" DATETIME NOT NULL,
    "checklist" TEXT,
    "rating" INTEGER,
    "notes" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "Chart" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "url" TEXT NOT NULL,
    "type" TEXT,
    "tags" TEXT,
    "tradeId" TEXT,
    "analysisId" TEXT,
    "wargameId" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Chart_tradeId_fkey" FOREIGN KEY ("tradeId") REFERENCES "Trade" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Chart_analysisId_fkey" FOREIGN KEY ("analysisId") REFERENCES "Analysis" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Chart_wargameId_fkey" FOREIGN KEY ("wargameId") REFERENCES "Wargame" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "GexSnapshot" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "ticker" TEXT NOT NULL,
    "timestamp" DATETIME NOT NULL,
    "tradingDate" DATETIME NOT NULL,
    "totalGex" REAL NOT NULL,
    "totalGexDeltaAdj" REAL,
    "callGammaTotal" REAL,
    "putGammaTotal" REAL,
    "gexRegime" TEXT NOT NULL,
    "regimeLabel" TEXT,
    "spotPrice" REAL NOT NULL,
    "gammaMagnet" REAL,
    "pinStrike" REAL,
    "callVolumeCentroid" REAL,
    "putVolumeCentroid" REAL,
    "netSpeedExposure" REAL,
    "netVannaExposure" REAL,
    "put25dIv" REAL,
    "call25dIv" REAL,
    "volatilitySkewPremium" REAL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "MacroSnapshot" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "ticker" TEXT NOT NULL,
    "timestamp" DATETIME NOT NULL,
    "tradingDate" DATETIME NOT NULL,
    "spotPrice" REAL NOT NULL,
    "macroCallWall" REAL,
    "macroPutWall" REAL,
    "zeroGamma" REAL,
    "put25dIv" REAL,
    "call25dIv" REAL,
    "volatilitySkewPremium" REAL,
    "anomalies" TEXT,
    "dominantNodes" TEXT
);

-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Account" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "currency" TEXT NOT NULL DEFAULT 'USD',
    "initialBalance" REAL NOT NULL,
    "currentBalance" REAL NOT NULL,
    "isDefault" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    "groupId" TEXT,
    CONSTRAINT "Account_groupId_fkey" FOREIGN KEY ("groupId") REFERENCES "AccountGroup" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_Account" ("createdAt", "currency", "currentBalance", "id", "initialBalance", "isDefault", "name", "updatedAt") SELECT "createdAt", "currency", "currentBalance", "id", "initialBalance", "isDefault", "name", "updatedAt" FROM "Account";
DROP TABLE "Account";
ALTER TABLE "new_Account" RENAME TO "Account";
CREATE TABLE "new_Trade" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "ticker" TEXT NOT NULL,
    "entryDate" DATETIME NOT NULL,
    "exitDate" DATETIME,
    "entryPrice" REAL,
    "exitPrice" REAL,
    "quantity" REAL NOT NULL,
    "direction" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "accountId" TEXT NOT NULL,
    "strategyId" TEXT,
    "orderType" TEXT NOT NULL DEFAULT 'MARKET',
    "limitPrice" REAL,
    "stopPrice" REAL,
    "stopLoss" REAL,
    "takeProfit" REAL,
    "pnl" REAL,
    "fees" REAL,
    "risk" REAL,
    "mae" REAL,
    "mfe" REAL,
    "duration" INTEGER,
    "chartSnapshot" TEXT,
    "notes" TEXT,
    "metadata" TEXT,
    "originalSource" TEXT,
    "playbookId" TEXT,
    "disciplineRating" INTEGER,
    "emotions" TEXT,
    "mistakes" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Trade_accountId_fkey" FOREIGN KEY ("accountId") REFERENCES "Account" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Trade_strategyId_fkey" FOREIGN KEY ("strategyId") REFERENCES "Strategy" ("id") ON DELETE SET NULL ON UPDATE CASCADE,
    CONSTRAINT "Trade_playbookId_fkey" FOREIGN KEY ("playbookId") REFERENCES "Playbook" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_Trade" ("accountId", "chartSnapshot", "createdAt", "direction", "duration", "entryDate", "entryPrice", "exitDate", "exitPrice", "fees", "id", "limitPrice", "mae", "metadata", "mfe", "notes", "orderType", "pnl", "quantity", "risk", "status", "stopLoss", "stopPrice", "strategyId", "takeProfit", "ticker", "updatedAt") SELECT "accountId", "chartSnapshot", "createdAt", "direction", "duration", "entryDate", "entryPrice", "exitDate", "exitPrice", "fees", "id", "limitPrice", "mae", "metadata", "mfe", "notes", "orderType", "pnl", "quantity", "risk", "status", "stopLoss", "stopPrice", "strategyId", "takeProfit", "ticker", "updatedAt" FROM "Trade";
DROP TABLE "Trade";
ALTER TABLE "new_Trade" RENAME TO "Trade";
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;

-- CreateIndex
CREATE UNIQUE INDEX "AccountGroup_name_key" ON "AccountGroup"("name");

-- CreateIndex
CREATE UNIQUE INDEX "Playbook_name_key" ON "Playbook"("name");

-- CreateIndex
CREATE UNIQUE INDEX "Rundown_date_key" ON "Rundown"("date");

-- CreateIndex
CREATE UNIQUE INDEX "ResearchStrategy_name_key" ON "ResearchStrategy"("name");

-- CreateIndex
CREATE UNIQUE INDEX "ResearchRun_runId_key" ON "ResearchRun"("runId");

-- CreateIndex
CREATE INDEX "ResearchRun_strategyId_idx" ON "ResearchRun"("strategyId");

-- CreateIndex
CREATE INDEX "ResearchRun_ticker_idx" ON "ResearchRun"("ticker");

-- CreateIndex
CREATE UNIQUE INDEX "WatchlistGroup_name_key" ON "WatchlistGroup"("name");

-- CreateIndex
CREATE UNIQUE INDEX "WatchlistItem_groupId_symbol_key" ON "WatchlistItem"("groupId", "symbol");

-- CreateIndex
CREATE INDEX "HistoricalVolatility_ticker_idx" ON "HistoricalVolatility"("ticker");

-- CreateIndex
CREATE UNIQUE INDEX "HistoricalVolatility_ticker_date_key" ON "HistoricalVolatility"("ticker", "date");

-- CreateIndex
CREATE INDEX "ExpectedMoveHistory_ticker_idx" ON "ExpectedMoveHistory"("ticker");

-- CreateIndex
CREATE UNIQUE INDEX "ExpectedMoveHistory_ticker_date_key" ON "ExpectedMoveHistory"("ticker", "date");

-- CreateIndex
CREATE INDEX "RthExpectedMove_ticker_idx" ON "RthExpectedMove"("ticker");

-- CreateIndex
CREATE UNIQUE INDEX "RthExpectedMove_ticker_date_key" ON "RthExpectedMove"("ticker", "date");

-- CreateIndex
CREATE UNIQUE INDEX "Analysis_date_key" ON "Analysis"("date");

-- CreateIndex
CREATE UNIQUE INDEX "Routine_date_key" ON "Routine"("date");

-- CreateIndex
CREATE INDEX "GexSnapshot_ticker_tradingDate_idx" ON "GexSnapshot"("ticker", "tradingDate");

-- CreateIndex
CREATE INDEX "GexSnapshot_ticker_timestamp_idx" ON "GexSnapshot"("ticker", "timestamp");

-- CreateIndex
CREATE INDEX "MacroSnapshot_ticker_idx" ON "MacroSnapshot"("ticker");

-- CreateIndex
CREATE UNIQUE INDEX "MacroSnapshot_ticker_tradingDate_key" ON "MacroSnapshot"("ticker", "tradingDate");
