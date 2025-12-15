-- CreateTable
CREATE TABLE "MarketNews" (
    "id" TEXT NOT NULL PRIMARY KEY,
    "uuid" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "publisher" TEXT NOT NULL,
    "link" TEXT NOT NULL,
    "providerPublishTime" DATETIME NOT NULL,
    "type" TEXT,
    "relatedTickers" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- CreateIndex
CREATE UNIQUE INDEX "MarketNews_uuid_key" ON "MarketNews"("uuid");
