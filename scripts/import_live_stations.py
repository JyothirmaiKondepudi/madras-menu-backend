"""Loads one caterer's live stations from a CSV file into live_stations.

Safe to run again: a station whose name already exists for that organization
(ignoring case) is updated, not duplicated. Stations missing from the file are
left alone. Every row is checked first; if any row is invalid, nothing is
written and the problems are listed.

    DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5433/madras_menu_local \\
        env/bin/python scripts/import_live_stations.py --org-id <uuid> --csv live_stations.csv [--dry-run]

CSV columns (header row required; names are matched ignoring case and spaces):
    name               required
    region             required, cuisine tag such as north_indian
    veg_nonveg         required: veg, nonveg or both
    price_per_person   optional, e.g. 8.50; leave empty if not priced yet
    meals              optional: breakfast, lunch, dinner, separated by ; or |
    min_guests         optional, default 1
    description        optional
    equipment_needed   optional, separated by ; or |
    active             optional: yes/no, true/false (default yes)
"""
import argparse
import csv
import os
import re
import sys
from uuid import UUID

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic import ValidationError  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from database import SessionLocal  # noqa: E402
from models import LiveStation, Organization  # noqa: E402
from schemas.pricing import LiveStationCreate  # noqa: E402

_FIELDS = {
    "name": "name", "region": "region", "vegnonveg": "vegNonveg",
    "priceperperson": "pricePerPerson", "meals": "mealPeriods", "mealperiods": "mealPeriods",
    "minguests": "minGuests", "description": "description",
    "equipmentneeded": "equipmentNeeded", "active": "active",
}


def _key(header: str) -> str:
    return re.sub(r"[^a-z]", "", header.lower())


def read_rows(path: str) -> tuple[list[LiveStationCreate], list[str]]:
    stations, problems, seen = [], [], set()
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = {header: _FIELDS.get(_key(header)) for header in reader.fieldnames or []}
        unknown = [header for header, field in columns.items() if field is None]
        if unknown:
            problems.append(f"unknown columns: {', '.join(unknown)}")
        for line, row in enumerate(reader, start=2):
            values = {columns[h]: (v or "").strip() for h, v in row.items() if columns.get(h) and (v or "").strip()}
            if not values:
                continue  # blank line
            for field in ("equipmentNeeded", "mealPeriods"):
                if field in values:
                    values[field] = [p.strip() for p in re.split(r"[;|]", values[field]) if p.strip()]
            if "mealPeriods" in values:
                values["mealPeriods"] = [p.lower() for p in values["mealPeriods"]]
            if "active" in values:
                values["active"] = values["active"].lower() in {"yes", "y", "true", "1"}
            if "vegNonveg" in values:
                values["vegNonveg"] = values["vegNonveg"].lower().replace("-", "").replace(" ", "")
            try:
                station = LiveStationCreate(**values)
            except ValidationError as error:
                details = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors())
                problems.append(f"line {line}: {details}")
                continue
            name_key = station.name.lower()
            if name_key in seen:
                problems.append(f"line {line}: {station.name!r} appears twice in the file")
                continue
            seen.add(name_key)
            stations.append(station)
    return stations, problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--org-id", required=True, type=UUID)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--dry-run", action="store_true", help="check the file and report, write nothing")
    args = parser.parse_args()

    stations, problems = read_rows(args.csv)
    if problems:
        sys.exit("Nothing imported. Fix these first:\n  " + "\n  ".join(problems))

    db = SessionLocal()
    try:
        if db.get(Organization, args.org_id) is None:
            sys.exit(f"No organization with id {args.org_id}.")
        added = updated = 0
        for station in stations:
            existing = db.execute(
                select(LiveStation).where(
                    LiveStation.orgId == args.org_id, func.lower(LiveStation.name) == station.name.lower()
                )
            ).scalars().first()
            if existing is None:
                db.add(LiveStation(orgId=args.org_id, **station.model_dump()))
                added += 1
            else:
                for field, value in station.model_dump().items():
                    setattr(existing, field, value)
                updated += 1
        unpriced = sum(station.pricePerPerson is None for station in stations)
        note = f" {unpriced} have no price yet." if unpriced else ""
        if args.dry_run:
            db.rollback()
            print(f"Dry run: would add {added} and update {updated} live stations.{note}")
        else:
            db.commit()
            print(f"Added {added} and updated {updated} live stations.{note}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
