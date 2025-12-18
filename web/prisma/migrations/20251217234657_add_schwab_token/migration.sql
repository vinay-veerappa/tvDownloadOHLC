-- CreateTable
CREATE TABLE "SchwabToken" (
    "id" TEXT NOT NULL PRIMARY KEY DEFAULT 'schwab-primary',
    "accessToken" TEXT NOT NULL,
    "refreshToken" TEXT NOT NULL,
    "expiresAt" INTEGER NOT NULL,
    "idToken" TEXT,
    "tokenType" TEXT NOT NULL,
    "scope" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" DATETIME NOT NULL
);
