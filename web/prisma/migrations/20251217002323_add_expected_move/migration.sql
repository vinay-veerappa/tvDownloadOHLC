-- CreateTable
CREATE TABLE "ExpectedMove" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "ticker" TEXT NOT NULL,
    "calculationDate" DATETIME NOT NULL,
    "expiryDate" DATETIME NOT NULL,
    "price" REAL NOT NULL,
    "straddle" REAL NOT NULL,
    "em365" REAL NOT NULL,
    "em252" REAL NOT NULL,
    "adjEm" REAL NOT NULL,
    "manualEm" REAL,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);

-- CreateIndex
CREATE UNIQUE INDEX "ExpectedMove_ticker_calculationDate_expiryDate_key" ON "ExpectedMove"("ticker", "calculationDate", "expiryDate");
