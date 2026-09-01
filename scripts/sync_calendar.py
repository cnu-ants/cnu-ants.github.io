#!/usr/bin/env python3
"""Upsert upcoming conference deadlines onto the ANTS Google Calendar."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import yaml
except ImportError:
    sys.stderr.write("PyYAML is required. Install with: pip install pyyaml\n")
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "_data" / "conferences.yml"
DEFAULT_CALENDAR_ID = (
    "04e8b4748a864cc0420d48d1c278162e6860e05e3d08fac783d0b7470b4b8093"
    "@group.calendar.google.com"
)
MANAGED_FLAG = "cnu-ants-deadlines"
EVENT_PREFIX = "antsd"

TZ_OFFSETS = {
    "AoE": dt.timedelta(hours=-12),
    "UTC": dt.timedelta(0),
    "UTC+0": dt.timedelta(0),
    "UTC-0": dt.timedelta(0),
    "UTC-12": dt.timedelta(hours=-12),
    "UTC-11": dt.timedelta(hours=-11),
    "UTC-10": dt.timedelta(hours=-10),
    "UTC-9": dt.timedelta(hours=-9),
    "UTC-8": dt.timedelta(hours=-8),
    "UTC-7": dt.timedelta(hours=-7),
    "UTC-6": dt.timedelta(hours=-6),
    "UTC-5": dt.timedelta(hours=-5),
    "UTC-4": dt.timedelta(hours=-4),
    "UTC-3": dt.timedelta(hours=-3),
    "UTC-2": dt.timedelta(hours=-2),
    "UTC-1": dt.timedelta(hours=-1),
    "UTC+1": dt.timedelta(hours=1),
    "UTC+2": dt.timedelta(hours=2),
    "UTC+3": dt.timedelta(hours=3),
    "UTC+4": dt.timedelta(hours=4),
    "UTC+5": dt.timedelta(hours=5),
    "UTC+6": dt.timedelta(hours=6),
    "UTC+7": dt.timedelta(hours=7),
    "UTC+8": dt.timedelta(hours=8),
    "UTC+9": dt.timedelta(hours=9),
    "UTC+10": dt.timedelta(hours=10),
    "UTC+11": dt.timedelta(hours=11),
    "UTC+12": dt.timedelta(hours=12),
}


def parse_deadline(value, timezone_name):
    if not value or value == "TBD":
        return None
    naive = dt.datetime.strptime(value.strip(), "%Y-%m-%d %H:%M:%S")
    if timezone_name == "PT":
        return naive.replace(tzinfo=ZoneInfo("America/Los_Angeles")).astimezone(
            dt.timezone.utc
        )
    offset = TZ_OFFSETS.get(timezone_name, TZ_OFFSETS["AoE"])
    return naive.replace(tzinfo=dt.timezone(offset)).astimezone(dt.timezone.utc)


def event_id(key: str) -> str:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return (EVENT_PREFIX + digest)[:1024]


def to_rfc3339(moment: dt.datetime) -> str:
    return moment.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_description(edition, item) -> str:
    lines = []
    if edition.get("description"):
        lines.append(str(edition["description"]))
        lines.append("")
    if edition.get("link"):
        lines.append(str(edition["link"]))
        lines.append("")
    when_where = " / ".join(
        part for part in [edition.get("date"), edition.get("place")] if part
    )
    if when_where:
        lines.append(when_where)
    tz = edition.get("timezone") or "AoE"
    lines.append("Deadline: %s %s" % (item["deadline"], tz))
    if item.get("abstract_deadline"):
        lines.append("Abstract deadline: %s %s" % (item["abstract_deadline"], tz))
    if item.get("comment"):
        lines.append(str(item["comment"]))
    return "\n".join(lines).strip()


def desired_events(editions, now: dt.datetime):
    events = []
    for edition in editions or []:
        cycles = edition.get("deadlines") or []
        for index, item in enumerate(cycles):
            parsed = parse_deadline(item.get("deadline"), edition.get("timezone") or "AoE")
            if parsed is None or parsed < now:
                continue
            title = edition.get("title") or "Conference"
            year = edition.get("year")
            name = "%s %s Deadline" % (title, year) if year else "%s Deadline" % title
            if len(cycles) > 1:
                name = "%s (%s/%s)" % (name, index + 1, len(cycles))
            body = {
                "id": event_id("%s|%s" % (edition.get("id") or title, index)),
                "summary": name,
                "description": build_description(edition, item),
                "start": {"dateTime": to_rfc3339(parsed), "timeZone": "UTC"},
                "end": {
                    "dateTime": to_rfc3339(parsed + dt.timedelta(minutes=15)),
                    "timeZone": "UTC",
                },
                "extendedProperties": {"private": {"antsSource": MANAGED_FLAG}},
                "reminders": {
                    "useDefault": False,
                    "overrides": [
                        {"method": "popup", "minutes": 7 * 24 * 60},
                        {"method": "popup", "minutes": 24 * 60},
                    ],
                },
            }
            if edition.get("place"):
                body["location"] = str(edition["place"])
            events.append(body)
    events.sort(key=lambda row: row["start"]["dateTime"])
    return events


def load_credentials():
    raw = os.environ.get("GOOGLE_CALENDAR_CREDENTIALS", "").strip()
    if not raw:
        local = ROOT / "scripts" / "google-calendar-credentials.json"
        if local.exists():
            raw = local.read_text(encoding="utf-8")
    if not raw:
        return None
    info = json.loads(raw)
    from google.oauth2 import service_account

    return service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/calendar"]
    )


def calendar_service(credentials):
    from googleapiclient.discovery import build

    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def list_managed_events(service, calendar_id):
    items = []
    page_token = None
    while True:
        response = (
            service.events()
            .list(
                calendarId=calendar_id,
                privateExtendedProperty="antsSource=%s" % MANAGED_FLAG,
                maxResults=2500,
                singleEvents=True,
                pageToken=page_token,
            )
            .execute()
        )
        items.extend(response.get("items") or [])
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return items


def event_start_utc(event) -> dt.datetime | None:
    start = (event.get("start") or {}).get("dateTime")
    if not start:
        return None
    return dt.datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(
        dt.timezone.utc
    )


def sync(service, calendar_id, desired, now, dry_run=False):
    existing = list_managed_events(service, calendar_id)
    existing_by_id = {item["id"]: item for item in existing if item.get("id")}
    desired_ids = {item["id"] for item in desired}
    inserted = updated = deleted = 0

    for body in desired:
        event_id = body["id"]
        if dry_run:
            action = "update" if event_id in existing_by_id else "insert"
            print("%s\t%s\t%s" % (action, body["start"]["dateTime"], body["summary"]))
            continue
        if event_id in existing_by_id:
            service.events().update(
                calendarId=calendar_id, eventId=event_id, body=body
            ).execute()
            updated += 1
        else:
            service.events().insert(calendarId=calendar_id, body=body).execute()
            inserted += 1

    for item in existing:
        event_id = item.get("id")
        if not event_id or event_id in desired_ids:
            continue
        start = event_start_utc(item)
        if start is None or start < now:
            continue
        if dry_run:
            print("delete\t%s\t%s" % (item.get("start"), item.get("summary")))
            continue
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        deleted += 1

    return {
        "desired": len(desired),
        "inserted": inserted,
        "updated": updated,
        "deleted": deleted,
        "dry_run": dry_run,
    }


def main():
    calendar_id = os.environ.get("GOOGLE_CALENDAR_ID", DEFAULT_CALENDAR_ID)
    dry_run = "--dry-run" in sys.argv or os.environ.get("DRY_RUN") == "1"
    data = yaml.safe_load(DATA_PATH.read_text(encoding="utf-8")) or {}
    now = dt.datetime.now(dt.timezone.utc)
    desired = desired_events(data.get("editions"), now)
    print(
        json.dumps(
            {"upcoming_deadlines": len(desired), "calendar_id": calendar_id},
            ensure_ascii=False,
        )
    )

    credentials = load_credentials()
    if credentials is None:
        if dry_run:
            for body in desired:
                print("insert\t%s\t%s" % (body["start"]["dateTime"], body["summary"]))
            return
        sys.stderr.write(
            "GOOGLE_CALENDAR_CREDENTIALS is not set. "
            "Share the ANTS calendar with a Google service account "
            "(Make changes to events), then add the JSON key as that secret.\n"
        )
        sys.exit(2)

    service = calendar_service(credentials)
    try:
        meta = service.calendars().get(calendarId=calendar_id).execute()
    except Exception as exc:
        sys.stderr.write(
            "Cannot write to %s (%s). "
            "Confirm the calendar is shared with the service account "
            "as 'Make changes to events'.\n" % (calendar_id, exc)
        )
        sys.exit(2)

    print(json.dumps({"calendar_summary": meta.get("summary")}, ensure_ascii=False))
    result = sync(service, calendar_id, desired, now, dry_run=dry_run)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
