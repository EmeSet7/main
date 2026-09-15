#!/usr/bin/env python3
"""
Generate tasks.ics from rules.json for a rolling window (default: today -> +13 days,
i.e. 2 weeks including today).

Usage:
    python generate_tasks.py [--rules rules.json] [--out tasks.ics] [--days 14]

Rule shapes (see task-rules.html for the editor):
{
  "timezone": "Europe/Lisbon",
  "rules": [
    {
      "id": "abc123",
      "title": "Take out the trash",
      "category": "chore",
      "recurrence": {"type": "weekly", "daysOfWeek": [1,3], "interval": 1},
      # daysOfWeek: 0=Sun..6=Sat. interval: every N weeks (1=every week, 2=biweekly...).
      # When interval > 1, "anchorDate" (below) fixes which week is "week 0".
      "time": "20:00" | null,
      "duration": 30,
      "notes": "Bins go out Tuesday night",
      "startDate": "2026-08-01" | null,
      "endDate": null,
      "anchorDate": "2026-08-01" | null,
      "active": true
    },
    {"recurrence": {"type": "daily", "interval": 1}, ...},

    # Monthly, by day-of-month:
    {"recurrence": {"type": "monthly", "mode": "dayOfMonth", "dayOfMonth": 1}, ...},  # or "last"

    # Monthly, by weekday pattern (e.g. "last Friday", "2nd Tuesday"):
    {"recurrence": {"type": "monthly", "mode": "weekday", "position": -1, "dayOfWeek": 5}, ...},
    # position: 1|2|3|4 for 1st..4th, or -1 for "last". dayOfWeek: 0=Sun..6=Sat.

    {"recurrence": {"type": "once", "date": "2026-09-15"}, ...}
  ]
}
"""
import argparse
import json
import sys
from calendar import monthrange
from datetime import date, datetime, timedelta

TZID = "Europe/Lisbon"

VTIMEZONE = """BEGIN:VTIMEZONE
TZID:Europe/Lisbon
BEGIN:STANDARD
DTSTART:19701025T020000
RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=10
TZNAME:WET
TZOFFSETFROM:+0100
TZOFFSETTO:+0000
END:STANDARD
BEGIN:DAYLIGHT
DTSTART:19700329T010000
RRULE:FREQ=YEARLY;BYDAY=-1SU;BYMONTH=3
TZNAME:WEST
TZOFFSETFROM:+0000
TZOFFSETTO:+0100
END:DAYLIGHT
END:VTIMEZONE"""

CATEGORY_EMOJI = {
    "chore": "\U0001F9F9",     # 🧹
    "work": "\U0001F4BC",      # 💼
    "health": "\U0001FAC0",    # 🫀
    "finance": "\U0001F4B0",   # 💰
    "personal": "\U0001F4CC",  # 📌
}


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d").date()


def in_range(d, rule):
    start = parse_date(rule["startDate"]) if rule.get("startDate") else None
    end = parse_date(rule["endDate"]) if rule.get("endDate") else None
    if start and d < start:
        return False
    if end and d > end:
        return False
    return True


def week_start(d):
    """Monday of the week containing d."""
    return d - timedelta(days=d.weekday())


def nth_weekday_of_month(year, month, weekday_schema, position):
    """weekday_schema: 0=Sun..6=Sat. position: 1-4, or -1 for 'last'. Returns a date or None."""
    last_day_num = monthrange(year, month)[1]

    if position == -1:
        last_day = date(year, month, last_day_num)
        offset = ((last_day.weekday() + 1) % 7 - weekday_schema) % 7
        return last_day - timedelta(days=offset)

    first_day = date(year, month, 1)
    offset = (weekday_schema - (first_day.weekday() + 1) % 7) % 7
    first_occurrence = first_day + timedelta(days=offset)
    candidate = first_occurrence + timedelta(weeks=position - 1)
    return candidate if candidate.month == month else None


def occurs_on(d, rule):
    rec = rule["recurrence"]
    rtype = rec["type"]

    if not in_range(d, rule):
        return False

    if rtype == "weekly":
        # Python: Monday=0..Sunday=6. Our schema: Sunday=0..Saturday=6.
        py_to_schema = (d.weekday() + 1) % 7
        if py_to_schema not in rec.get("daysOfWeek", []):
            return False
        interval = rec.get("interval", 1)
        if interval <= 1:
            return True
        anchor_str = rule.get("anchorDate") or rule.get("startDate")
        anchor = parse_date(anchor_str) if anchor_str else d
        weeks_between = (week_start(d) - week_start(anchor)).days // 7
        return weeks_between % interval == 0

    if rtype == "daily":
        interval = rec.get("interval", 1)
        anchor = parse_date(rule["startDate"]) if rule.get("startDate") else d
        return (d - anchor).days % interval == 0

    if rtype == "monthly":
        mode = rec.get("mode", "dayOfMonth")
        if mode == "weekday":
            target = nth_weekday_of_month(d.year, d.month, rec["dayOfWeek"], rec["position"])
            return target is not None and d == target
        dom = rec.get("dayOfMonth", 1)
        last_day = monthrange(d.year, d.month)[1]
        target_dom = last_day if dom == "last" else min(dom, last_day)
        return d.day == target_dom

    if rtype == "once":
        return d == parse_date(rec["date"])

    return False


def build_event(rule, d):
    cat = rule.get("category", "personal")
    emoji = CATEGORY_EMOJI.get(cat, "\U0001F4CC")
    uid = f"task-{rule['id']}-{d.isoformat()}@tiago"
    summary = f"{emoji} {rule['title']}"

    lines = ["BEGIN:VEVENT", f"UID:{uid}"]

    if rule.get("time"):
        hh, mm = rule["time"].split(":")
        start_dt = datetime(d.year, d.month, d.day, int(hh), int(mm))
        end_dt = start_dt + timedelta(minutes=rule.get("duration", 30))
        lines.append(f"DTSTART;TZID={TZID}:{start_dt.strftime('%Y%m%dT%H%M%S')}")
        lines.append(f"DTEND;TZID={TZID}:{end_dt.strftime('%Y%m%dT%H%M%S')}")
    else:
        next_day = d + timedelta(days=1)
        lines.append(f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}")
        lines.append(f"DTEND;VALUE=DATE:{next_day.strftime('%Y%m%d')}")

    lines.append(f"SUMMARY:{summary}")

    desc_parts = []
    if rule.get("notes"):
        desc_parts.append(rule["notes"].replace("\n", "\\n"))
    if desc_parts:
        lines.append(f"DESCRIPTION:{' '.join(desc_parts)}")

    lines.append("END:VEVENT")
    return "\n".join(lines)


def generate(rules_path, out_path, days):
    with open(rules_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    rules = data.get("rules", [])
    today = date.today()
    window = [today + timedelta(days=i) for i in range(days)]

    events = []
    for rule in rules:
        if not rule.get("active", True):
            continue
        for d in window:
            if occurs_on(d, rule):
                events.append(build_event(rule, d))

    body = "\n\n".join(events)
    ics = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Tiago Cardoso//Task Calendar//EN
CALNAME:Tasks
CALSCALE:GREGORIAN
METHOD:PUBLISH
X-WR-CALNAME:Tasks
X-WR-TIMEZONE:{TZID}

{VTIMEZONE}

{body}
END:VCALENDAR
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(ics)

    print(f"Generated {len(events)} events for {today.isoformat()} -> {window[-1].isoformat()} into {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", default="rules.json")
    parser.add_argument("--out", default="tasks.ics")
    parser.add_argument("--days", type=int, default=14)
    args = parser.parse_args()

    try:
        generate(args.rules, args.out, args.days)
    except FileNotFoundError:
        print(f"rules.json not found at {args.rules}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
