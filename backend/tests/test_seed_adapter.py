from __future__ import annotations

from pathlib import Path

from race_watcher.adapters.seed import SeedFileAdapter


def test_loads_meeting_with_races_and_runners(tiny_seed: Path) -> None:
    meeting = SeedFileAdapter(path=tiny_seed).load_meeting()
    assert meeting.track == "Flemington"
    assert len(meeting.races) == 1
    race = meeting.races[0]
    assert race.number == 1
    assert race.distance_m == 1200
    assert len(race.runners) == 3
    alpha = next(r for r in race.runners if r.number == 1)
    assert alpha.name == "Alpha"
    assert alpha.seed_price == 2.50  # type: ignore[comparison-overlap]
    assert alpha.seed_prediction_rating == "top"
    assert any("wet" in (fl.note or "").lower() for fl in alpha.form_lines)


def test_loads_real_seed_smoke() -> None:
    path = Path(__file__).parents[1] / "seed" / "flemington.json"
    meeting = SeedFileAdapter(path=path).load_meeting()
    assert meeting.track == "Flemington"
    assert len(meeting.races) == 9
    # Every race in the seed has at least one runner with a name.
    for race in meeting.races:
        assert race.runners
        for runner in race.runners:
            assert runner.name
