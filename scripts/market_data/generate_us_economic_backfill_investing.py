import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta
import time
from zoneinfo import ZoneInfo

import requests


API_URL = "https://endpoints.investing.com/pd-instruments/v1/calendars/economic/events/occurrences"
CALENDAR_URL = "https://www.investing.com/economic-calendar/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/146.0.0.0 Safari/537.36"
)
DEFAULT_COUNTRY_IDS = "25,32,6,37,72,22,17,39,14,10,35,43,36,110,11,26,12,4,5,56"
US_COUNTRY_ID = 5


@dataclass
class EventMeta:
    event_id: int
    country_id: int
    name: str
    category: str
    importance: str


def normalize_name(meta: dict) -> str:
    name = (
        meta.get("event_translated")
        or meta.get("short_name")
        or meta.get("event_meta_title")
        or meta.get("long_name")
        or "Unknown Event"
    )
    name = str(name).strip()
    prefixes = ["U.S. ", "US ", "United States "]
    for p in prefixes:
        if name.startswith(p):
            return name[len(p) :].strip()
    return name


def normalize_category(raw: str) -> str:
    if not raw:
        return "Macro"
    return str(raw).replace("_", " ").title()


def normalize_importance(raw: str) -> str:
    v = (raw or "low").strip().lower()
    if v in {"high", "medium", "low"}:
        return v.title()
    return "Low"


def et_parts(iso_utc: str) -> tuple[str, str, datetime]:
    dt_utc = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
    dt_et = dt_utc.astimezone(ZoneInfo("America/New_York"))
    return dt_et.strftime("%Y-%m-%d"), dt_et.strftime("%H:%M ET"), dt_et


def fetch_all_occurrences(start_date: str, end_date: str, limit: int, window_days: int) -> tuple[list[dict], dict[int, EventMeta]]:
    session = requests.Session()
    session.get(CALENDAR_URL, headers={"User-Agent": USER_AGENT}, timeout=30)

    params = {
        "domain_id": 1,
        "limit": limit,
        "country_ids": DEFAULT_COUNTRY_IDS,
    }

    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Referer": CALENDAR_URL,
        "Origin": "https://www.investing.com",
    }

    all_occ: list[dict] = []
    event_map: dict[int, EventMeta] = {}
    seen_occurrence_ids: set[int] = set()

    start_dt = datetime.fromisoformat(start_date)
    end_dt = datetime.fromisoformat(end_date)
    if start_dt > end_dt:
        raise ValueError("start_date must be <= end_date")

    window_start = start_dt
    window_index = 0

    while window_start <= end_dt:
        window_end = min(window_start + timedelta(days=window_days), end_dt)
        window_index += 1

        query = dict(params)
        query["start_date"] = window_start.isoformat(timespec="milliseconds")
        query["end_date"] = window_end.isoformat(timespec="milliseconds")

        print(
            "Fetching window "
            f"{window_index}: {query['start_date']} -> {query['end_date']}"
        )

        payload = None
        for attempt in range(1, 6):
            try:
                resp = session.get(API_URL, params=query, headers=headers, timeout=30)
                resp.raise_for_status()
                payload = resp.json()
                break
            except Exception:
                if attempt == 5:
                    raise
                time.sleep(0.8 * attempt)

        if payload is None:
            raise RuntimeError("Failed to fetch Investing occurrences payload")

        for e in payload.get("events", []):
            eid = e.get("event_id")
            if not isinstance(eid, int):
                continue
            event_map[eid] = EventMeta(
                event_id=eid,
                country_id=int(e.get("country_id") or -1),
                name=normalize_name(e),
                category=normalize_category(str(e.get("category") or "")),
                importance=normalize_importance(str(e.get("importance") or "")),
            )

        window_occ = payload.get("occurrences", [])
        added = 0
        for occ in window_occ:
            oid = occ.get("occurrence_id")
            if not isinstance(oid, int):
                continue
            if oid in seen_occurrence_ids:
                continue
            seen_occurrence_ids.add(oid)
            all_occ.append(occ)
            added += 1

        print(f"  window occurrences: {len(window_occ)}; added unique: {added}; total unique: {len(all_occ)}")

        window_start = window_end + timedelta(milliseconds=1)

    return all_occ, event_map


def build_rows(occurrences: list[dict], event_map: dict[int, EventMeta]) -> list[list[str]]:
    rows: list[list[str]] = []
    seen: set[tuple[str, str, str]] = set()

    for occ in occurrences:
        eid = occ.get("event_id")
        if not isinstance(eid, int):
            continue

        meta = event_map.get(eid)
        if not meta or meta.country_id != US_COUNTRY_ID:
            continue

        occ_time = occ.get("occurrence_time")
        if not isinstance(occ_time, str):
            continue

        date_str, time_et, dt_et = et_parts(occ_time)

        key = (date_str, meta.name, time_et)
        if key in seen:
            continue
        seen.add(key)

        year = str(dt_et.year)
        month_num = dt_et.month
        quarter = str(((month_num - 1) // 3) + 1)
        month_name = dt_et.strftime("%B")
        day_name = dt_et.strftime("%A")

        rows.append(
            [
                date_str,
                meta.name,
                meta.category,
                meta.importance,
                "Unknown",
                time_et,
                year,
                quarter,
                str(month_num),
                month_name,
                day_name,
                "source=investing-occurrences-api",
            ]
        )

    rows.sort(key=lambda r: (r[0], r[5], r[1]))
    return rows


def write_csv(path: str, rows: list[list[str]]) -> None:
    header = [
        "date",
        "indicator",
        "category",
        "importance",
        "frequency",
        "time",
        "year",
        "quarter",
        "month",
        "month_name",
        "day_of_week",
        "notes",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate US economic calendar backfill CSV from Investing occurrences API")
    parser.add_argument(
        "--start-date",
        default="2026-01-01T00:00:00.000-07:00",
        help="API start_date format, e.g. 2026-01-01T00:00:00.000-07:00",
    )
    parser.add_argument(
        "--end-date",
        default="2026-04-05T23:59:59.999-07:00",
        help="API end_date format, e.g. 2026-04-05T23:59:59.999-07:00",
    )
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--window-days", type=int, default=6)
    parser.add_argument(
        "--out",
        default="docs/JournalRequirements/economic_backfill/us_economic_calendar_2026_q1.csv",
    )
    args = parser.parse_args()

    occ, event_map = fetch_all_occurrences(args.start_date, args.end_date, args.limit, args.window_days)
    rows = build_rows(occ, event_map)
    write_csv(args.out, rows)

    print(f"Fetched occurrences: {len(occ)}")
    print(f"US rows written: {len(rows)}")
    print(f"Output: {args.out}")
