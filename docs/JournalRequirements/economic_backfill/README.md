# Economic Backfill Drop Zone

Place additional historical economic calendar CSV files in this folder.

The sync job automatically ingests all `.csv` files here when running:
- `web/prisma/seed-economic-events.ts`

Required CSV header:
`date,indicator,category,importance,frequency,time,year,quarter,month,month_name,day_of_week,notes`

Notes:
- `date` format: `YYYY-MM-DD`
- `time` format: `HH:MM ET`
- `importance`: `High`, `Medium`, or `Low`
- Import is idempotent: duplicate `(name, datetime)` records are skipped.
