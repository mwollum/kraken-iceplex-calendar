#!/usr/bin/env python3
"""
Kraken Community Iceplex → ICS calendar generator

Fetches the public drop-in calendar and writes .ics files you can subscribe to
in Google Calendar, Apple Calendar, Outlook, or any iCalendar-compatible app.

Usage:
    python3 kraken_calendar.py                    # generate all three variants
    python3 kraken_calendar.py --sport hockey     # hockey only
    python3 kraken_calendar.py --sport skate      # public skate only
    python3 kraken_calendar.py --sport all        # every event on the calendar
    python3 kraken_calendar.py --days 60          # next 60 days (default: 90)
"""

import argparse
import hashlib
import sys
import urllib.request
import urllib.parse
import json
from datetime import datetime, timedelta, timezone


ENDPOINT = "https://www.krakencommunityiceplex.com/Umbraco/api/DaySmartCalendarApi/GetEventsAsync"
LOCATION = "Kraken Community Iceplex, 925 Westlake Ave N, Seattle, WA 98109"

SPORT_HOCKEY = 20
SPORT_PUBLIC_SKATE = 30


def fetch_events(start: datetime, end: datetime) -> list[dict]:
    params = urllib.parse.urlencode({
        "start": start.strftime("%Y-%m-%d"),
        "end": end.strftime("%Y-%m-%d"),
        "variant": "2",
    })
    url = f"{ENDPOINT}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def to_ics_dt(iso: str) -> str:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.strftime("%Y%m%dT%H%M%SZ")


def ics_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def make_uid(event: dict) -> str:
    key = f"{event['start']}-{event['title']}-kraken"
    return hashlib.md5(key.encode()).hexdigest() + "@krakencommunityiceplex.com"


def build_ics(events: list[dict], calendar_name: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Kraken Community Iceplex//Calendar//EN",
        f"X-WR-CALNAME:{ics_escape(calendar_name)}",
        "X-WR-TIMEZONE:America/Los_Angeles",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"LAST-MODIFIED:{now}",
    ]
    for e in events:
        reg_url = e.get("url", "")
        desc = f"Register at: {reg_url}" if reg_url else "Kraken Community Iceplex"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{make_uid(e)}",
            f"SUMMARY:{ics_escape(e['title'])}",
            f"DTSTART:{to_ics_dt(e['start'])}",
            f"DTEND:{to_ics_dt(e['end'])}",
            f"LOCATION:{ics_escape(LOCATION)}",
            f"DESCRIPTION:{ics_escape(desc)}",
            f"URL:{reg_url}",
            f"DTSTAMP:{now}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


VARIANTS = [
    ("hockey",          "kraken_hockey.ics",            "Kraken Iceplex — Hockey Drop-In"),
    ("stickpuck",       "kraken_stick_puck.ics",        "Kraken Iceplex — Stick & Puck"),
    ("stickpuck_open",  "kraken_stick_puck_open.ics",   "Kraken Iceplex — Stick & Puck (Open)"),
    ("skate",           "kraken_public_skate.ics",      "Kraken Iceplex — Public Skate"),
    ("all",             "kraken_all.ics",               "Kraken Iceplex — All Events"),
]


def filter_events(events: list[dict], sport: str) -> list[dict]:
    if sport == "hockey":
        return [e for e in events if e.get("sportId") == SPORT_HOCKEY]
    if sport == "stickpuck":
        return [e for e in events if "stick & puck" in e.get("title", "").lower()]
    if sport == "stickpuck_open":
        return [e for e in events
                if "stick & puck" in e.get("title", "").lower()
                and "female" not in e.get("title", "").lower()
                and "14 and under" not in e.get("title", "").lower()]
    if sport == "skate":
        return [e for e in events if e.get("sportId") == SPORT_PUBLIC_SKATE]
    return events


def main():
    parser = argparse.ArgumentParser(description="Generate Kraken Iceplex ICS calendars")
    parser.add_argument("--sport", choices=["hockey", "skate", "all", "all-variants"],
                        default="all-variants",
                        help="Which calendar to generate (default: all three variants)")
    parser.add_argument("--days", type=int, default=90,
                        help="Days ahead to fetch (default: 90)")
    parser.add_argument("--out", default=None,
                        help="Output filename (only used with --sport hockey/skate/all)")
    args = parser.parse_args()

    start = datetime.now(timezone.utc)
    end = start + timedelta(days=args.days)

    print(f"Fetching {args.days} days of events...", file=sys.stderr)
    try:
        all_events = fetch_events(start, end)
    except Exception as e:
        print(f"Error fetching events: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Fetched {len(all_events)} total events.", file=sys.stderr)

    if args.sport == "all-variants":
        for sport, filename, cal_name in VARIANTS:
            events = filter_events(all_events, sport)
            ics = build_ics(events, cal_name)
            with open(filename, "w", encoding="utf-8") as f:
                f.write(ics)
            print(f"  {filename}: {len(events)} events", file=sys.stderr)
    else:
        filename = args.out or next(fn for s, fn, _ in VARIANTS if s == args.sport)
        cal_name = next(cn for s, _, cn in VARIANTS if s == args.sport)
        events = filter_events(all_events, args.sport)
        ics = build_ics(events, cal_name)
        with open(filename, "w", encoding="utf-8") as f:
            f.write(ics)
        print(f"  {filename}: {len(events)} events", file=sys.stderr)

    print("Done.", file=sys.stderr)


if __name__ == "__main__":
    main()
