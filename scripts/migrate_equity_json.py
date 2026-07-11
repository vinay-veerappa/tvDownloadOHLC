"""
One-time migration: Generate JSON equity data files for existing ResearchRun
records that currently have PNG equityCurvePath values.

The equity API endpoint expects JSON files ({timestamps: [], values: []}),
but legacy options strategies stored PNG paths. This script reads trade data
from the DB and generates the missing JSON files alongside the PNGs.
"""
import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'web', 'prisma', 'dev.db')


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    c.execute("SELECT id, runId, strategyId, equityCurvePath, metricsJson FROM ResearchRun WHERE equityCurvePath LIKE '%.png'")
    runs = c.fetchall()
    print(f'Found {len(runs)} runs with PNG paths')

    generated = 0
    skipped = 0
    for run in runs:
        png_path = run['equityCurvePath']
        json_path = png_path.replace('.png', '.json')

        if os.path.exists(json_path):
            skipped += 1
            continue

        # Get initial balance from metricsJson
        initial = 10000.0
        try:
            initial = json.loads(run['metricsJson']).get('initial_balance', 10000.0)
        except Exception:
            pass

        # Get trades for this run via strategyId (Trade has no runId column)
        c.execute(
            'SELECT entryDate, exitDate, pnl FROM Trade WHERE strategyId = ? ORDER BY exitDate',
            (run['strategyId'],),
        )
        trades = c.fetchall()

        if not trades:
            data = {'timestamps': ['1970-01-01T00:00:00'], 'values': [initial]}
        else:
            timestamps = []
            values = []
            current = initial
            timestamps.append(trades[0]['entryDate'] or '1970-01-01T00:00:00')
            values.append(current)
            for t in trades:
                current += t['pnl'] or 0.0
                timestamps.append(t['exitDate'] or t['entryDate'] or '1970-01-01T00:00:00')
                values.append(current)
            data = {'timestamps': timestamps, 'values': values}

        with open(json_path, 'w') as f:
            json.dump(data, f)
        generated += 1

    print(f'Generated: {generated}, Already existed: {skipped}')
    conn.close()


if __name__ == '__main__':
    main()