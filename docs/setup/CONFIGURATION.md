# Configuration Service

## Schwab API Setup
To enable Expected Move calculations and Futures data fetching, you must configure the Schwab API credentials.

### 1. `secrets.json`
Create a file at the project root `c:\Users\vinay\tvDownloadOHLC\secrets.json` with the following structure:
```json
{
  "app_key": "YOUR_APP_KEY",
  "app_secret": "YOUR_APP_SECRET"
}
```

### 2. `token.json`
This file is generated automatically after the first Oauth flow. It stores the refresh/access tokens.
- **Location**: `c:\Users\vinay\tvDownloadOHLC\token.json`
- **Maintenance**: Schwab refresh tokens expire every 7 days. You may need to re-authenticate if scripts fail.

## Scheduled Jobs (Cron)
For automated data persistence, use `update-em-db.ts`.

### Expected Move Updates
Run this script to fetch the latest Straddle prices and Expected Moves from Schwab and save them to the local SQLite database.

**Command:**
```bash
cd web
npx tsx scripts/cron/update-em-db.ts
```

**Recommended Schedule (Windows Task Scheduler):**
1.  **Morning Update**: 09:30 AM EST (Capture Open Price)
2.  **Evening Update**: 04:15 PM EST (Capture Closing/Settlement Price)

## Environment Variables
The web application uses `.env` for configuration.

```env
DATABASE_URL="file:./dev.db"
# Optional: Overrides
PORT=3000
```
