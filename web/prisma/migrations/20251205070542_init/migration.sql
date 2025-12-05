/*
  Warnings:

  - You are about to drop the column `color` on the `Tag` table. All the data in the column will be lost.
  - You are about to drop the column `symbol` on the `Trade` table. All the data in the column will be lost.
  - Added the required column `ticker` to the `Trade` table without a default value. This is not possible if the table is not empty.

*/
-- CreateTable
CREATE TABLE "BacktestResult" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "strategy" TEXT NOT NULL,
    "ticker" TEXT NOT NULL,
    "timeframe" TEXT NOT NULL,
    "startDate" DATETIME NOT NULL,
    "endDate" DATETIME NOT NULL,
    "totalTrades" INTEGER NOT NULL,
    "winRate" REAL NOT NULL,
    "profitFactor" REAL NOT NULL,
    "totalPnl" REAL NOT NULL,
    "config" TEXT NOT NULL,
    "trades" TEXT NOT NULL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Tag" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL
);
INSERT INTO "new_Tag" ("id", "name") SELECT "id", "name" FROM "Tag";
DROP TABLE "Tag";
ALTER TABLE "new_Tag" RENAME TO "Tag";
CREATE UNIQUE INDEX "Tag_name_key" ON "Tag"("name");
CREATE TABLE "new_Trade" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "ticker" TEXT NOT NULL,
    "entryDate" DATETIME NOT NULL,
    "exitDate" DATETIME,
    "entryPrice" REAL NOT NULL,
    "exitPrice" REAL,
    "quantity" REAL NOT NULL,
    "direction" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "pnl" REAL,
    "notes" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);
INSERT INTO "new_Trade" ("createdAt", "direction", "entryDate", "entryPrice", "exitDate", "exitPrice", "id", "notes", "pnl", "quantity", "status", "updatedAt") SELECT "createdAt", "direction", "entryDate", "entryPrice", "exitDate", "exitPrice", "id", "notes", "pnl", "quantity", "status", "updatedAt" FROM "Trade";
DROP TABLE "Trade";
ALTER TABLE "new_Trade" RENAME TO "Trade";
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
