"""
One-time migration: Update ResearchRun.equityCurvePath from .png to .json
for all legacy options strategy runs.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'web', 'prisma', 'dev.db')


def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT id, equityCurvePath FROM ResearchRun WHERE equityCurvePath LIKE '%.png'")
    runs = c.fetchall()
    print(f'Found {len(runs)} runs with PNG paths')

    updated = 0
    for run_id, png_path in runs:
        json_path = png_path.replace('.png', '.json')
        if os.path.exists(json_path):
            c.execute(
                'UPDATE ResearchRun SET equityCurvePath = ? WHERE id = ?',
                (json_path, run_id),
            )
            updated += 1

    conn.commit()
    print(f'Updated: {updated}')
    conn.close()


if __name__ == '__main__':
    main()