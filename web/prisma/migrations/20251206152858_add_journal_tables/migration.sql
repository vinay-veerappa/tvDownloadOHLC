/*
  Warnings:

  - Added the required column `accountId` to the `Trade` table without a default value. This is not possible if the table is not empty.

*/
-- CreateTable
CREATE TABLE "Account" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "currency" TEXT NOT NULL DEFAULT 'USD',
    "initialBalance" REAL NOT NULL,
    "currentBalance" REAL NOT NULL,
    "isDefault" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateTable
CREATE TABLE "Strategy" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "name" TEXT NOT NULL,
    "description" TEXT,
    "color" TEXT NOT NULL DEFAULT '#2962FF',
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
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
    "notes" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL,
    CONSTRAINT "Trade_accountId_fkey" FOREIGN KEY ("accountId") REFERENCES "Account" ("id") ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT "Trade_strategyId_fkey" FOREIGN KEY ("strategyId") REFERENCES "Strategy" ("id") ON DELETE SET NULL ON UPDATE CASCADE
);
INSERT INTO "new_Trade" ("createdAt", "direction", "entryDate", "entryPrice", "exitDate", "exitPrice", "id", "notes", "pnl", "quantity", "status", "ticker", "updatedAt") SELECT "createdAt", "direction", "entryDate", "entryPrice", "exitDate", "exitPrice", "id", "notes", "pnl", "quantity", "status", "ticker", "updatedAt" FROM "Trade";
DROP TABLE "Trade";
ALTER TABLE "new_Trade" RENAME TO "Trade";
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
