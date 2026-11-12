"""CSV parsing for scripts/import_live_stations.py (no database)."""
from decimal import Decimal

from scripts.import_live_stations import read_rows


def _csv(tmp_path, text):
    path = tmp_path / "stations.csv"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_reads_loose_headers_lists_and_flags(tmp_path):
    stations, problems = read_rows(_csv(tmp_path, (
        "Name,Region,Veg/Nonveg,Price Per Person,Min Guests,Equipment Needed,Active\n"
        "Dosa Station,south_indian,Veg,8.50,50,tawa; gas burner,yes\n"
        "\n"
        "Chaat Counter,north_indian,both,6,,,no\n"
    )))
    assert problems == []
    dosa, chaat = stations
    assert (dosa.vegNonveg, dosa.pricePerPerson, dosa.minGuests) == ("veg", Decimal("8.50"), 50)
    assert dosa.equipmentNeeded == ["tawa", "gas burner"]
    assert (chaat.minGuests, chaat.active, chaat.equipmentNeeded) == (1, False, [])


def test_reports_every_problem_and_keeps_nothing_bad(tmp_path):
    stations, problems = read_rows(_csv(tmp_path, (
        "name,region,veg_nonveg,price_per_person,colour\n"
        "Dosa,south_indian,vegetarian,-2,red\n"
        "Pasta,italian,veg,7,blue\n"
        "pasta,italian,veg,7,blue\n"
    )))
    assert [s.name for s in stations] == ["Pasta"]
    assert problems[0] == "unknown columns: colour"
    assert problems[1].startswith("line 2: vegNonveg")
    assert problems[2] == "line 4: 'pasta' appears twice in the file"
