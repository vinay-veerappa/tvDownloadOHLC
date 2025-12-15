-- CreateTable
CREATE TABLE "MarketCondition" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "tradeId" TEXT NOT NULL,
    "vix" REAL,
    "vvix" REAL,
    "atr" REAL,
    "trend" TEXT,
    "session" TEXT,
    "volume" TEXT,
    CONSTRAINT "MarketCondition_tradeId_fkey" FOREIGN KEY ("tradeId") REFERENCES "Trade" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "EconomicEvent" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "datetime" DATETIME NOT NULL,
    "name" TEXT NOT NULL,
    "impact" TEXT NOT NULL,
    "actual" REAL,
    "forecast" REAL,
    "previous" REAL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateTable
CREATE TABLE "TradeEvent" (
    "tradeId" TEXT NOT NULL,
    "eventId" TEXT NOT NULL,

    PRIMARY KEY ("tradeId", "eventId"),
    CONSTRAINT "TradeEvent_tradeId_fkey" FOREIGN KEY ("tradeId") REFERENCES "Trade" ("id") ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT "TradeEvent_eventId_fkey" FOREIGN KEY ("eventId") REFERENCES "EconomicEvent" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "Note" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "tradeId" TEXT,
    "date" DATETIME,
    "type" TEXT NOT NULL DEFAULT 'trade',
    "content" TEXT NOT NULL,
    "aiGenerated" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Note_tradeId_fkey" FOREIGN KEY ("tradeId") REFERENCES "Trade" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "TradePlan" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "date" DATETIME NOT NULL,
    "instrument" TEXT NOT NULL,
    "setup" TEXT,
    "entryPlan" TEXT,
    "exitPlan" TEXT,
    "riskPlan" TEXT,
    "linkedTradeId" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "TradePlan_linkedTradeId_fkey" FOREIGN KEY ("linkedTradeId") REFERENCES "Trade" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);

-- CreateTable
CREATE TABLE "TagGroup" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "color" TEXT NOT NULL DEFAULT '#6b7280'
);

-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Tag" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "groupId" TEXT,
    CONSTRAINT "Tag_groupId_fkey" FOREIGN KEY ("groupId") REFERENCES "TagGroup" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_Tag" ("id", "name") SELECT "id", "name" FROM "Tag";
DROP TABLE "Tag";
ALTER TABLE "new_Tag" RENAME TO "Tag";
CREATE UNIQUE INDEX "Tag_name_key" ON "Tag"("name");
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;

-- CreateIndex
CREATE UNIQUE INDEX "MarketCondition_tradeId_key" ON "MarketCondition"("tradeId");

-- CreateIndex
CREATE UNIQUE INDEX "TradePlan_linkedTradeId_key" ON "TradePlan"("linkedTradeId");

-- CreateIndex
CREATE UNIQUE INDEX "TagGroup_name_key" ON "TagGroup"("name");
