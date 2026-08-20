"""Tests for the raw hand store and the two scrape strategies.

The bug these guard against: hands are served newest-first, so page N holds
different hands every time somebody plays. Any caching or writing keyed on
page *index* loses hands — the real corpus ended up with a 7-day hole between
page 1 and page 2 because of exactly that.
"""

import asyncio
import json

import pytest

import scraper
from scraper import (
    load_existing_hand_ids,
    load_raw_hands_by_id,
    merge_raw_hands,
)

DAY = 24 * 60 * 60 * 1000
# 2026-08-10T00:00:00Z
AUG_10 = 1786320000000


def _hand(hand_id, ts):
    return {"id": hand_id, "timestamp": ts}


class TestMergeRawHands:
    def test_partitions_by_utc_date(self, tmp_path):
        merge_raw_hands(str(tmp_path), [_hand("a", AUG_10), _hand("b", AUG_10 + DAY)])
        names = sorted(p.name for p in tmp_path.iterdir())
        assert names == ["hands_2026-08-10.json", "hands_2026-08-11.json"]

    def test_is_additive_across_calls(self, tmp_path):
        assert merge_raw_hands(str(tmp_path), [_hand("a", AUG_10)]) == 1
        assert merge_raw_hands(str(tmp_path), [_hand("b", AUG_10)]) == 1
        assert set(load_raw_hands_by_id(str(tmp_path))) == {"a", "b"}

    def test_reports_only_newly_added(self, tmp_path):
        merge_raw_hands(str(tmp_path), [_hand("a", AUG_10)])
        assert merge_raw_hands(str(tmp_path), [_hand("a", AUG_10), _hand("b", AUG_10)]) == 1

    def test_never_drops_an_existing_hand(self, tmp_path):
        """A later run covering the same date must not evict earlier hands."""
        merge_raw_hands(str(tmp_path), [_hand(str(i), AUG_10) for i in range(50)])
        merge_raw_hands(str(tmp_path), [_hand("new", AUG_10)])
        stored = load_raw_hands_by_id(str(tmp_path))
        assert len(stored) == 51
        assert all(str(i) in stored for i in range(50))

    def test_stored_hands_are_sorted_by_timestamp(self, tmp_path):
        merge_raw_hands(str(tmp_path), [_hand("late", AUG_10 + 900), _hand("early", AUG_10)])
        data = json.loads((tmp_path / "hands_2026-08-10.json").read_text())["data"]
        assert [h["id"] for h in data] == ["early", "late"]

    def test_rebuilds_corrupt_file_without_losing_new_hands(self, tmp_path):
        (tmp_path / "hands_2026-08-10.json").write_text("{not json")
        assert merge_raw_hands(str(tmp_path), [_hand("a", AUG_10)]) == 1
        assert set(load_raw_hands_by_id(str(tmp_path))) == {"a"}

    def test_skips_hands_without_an_id(self, tmp_path):
        assert merge_raw_hands(str(tmp_path), [{"timestamp": AUG_10}]) == 0


class TestLoadRawHands:
    def test_reads_legacy_page_files(self, tmp_path):
        (tmp_path / "page_00001.json").write_text(json.dumps({"data": [_hand("old", AUG_10)]}))
        merge_raw_hands(str(tmp_path), [_hand("new", AUG_10)])
        assert set(load_existing_hand_ids(str(tmp_path))) == {"old", "new"}

    def test_ignores_unrelated_json(self, tmp_path):
        (tmp_path / "notes.json").write_text(json.dumps({"data": [_hand("nope", AUG_10)]}))
        assert load_raw_hands_by_id(str(tmp_path)) == {}

    def test_missing_dir_is_empty(self, tmp_path):
        assert load_raw_hands_by_id(str(tmp_path / "absent")) == {}

    def test_survives_a_corrupt_file(self, tmp_path):
        merge_raw_hands(str(tmp_path), [_hand("good", AUG_10)])
        (tmp_path / "hands_2026-08-11.json").write_text("{broken")
        assert set(load_raw_hands_by_id(str(tmp_path))) == {"good"}


class TestSaveRawPageIsGone:
    def test_writing_by_page_index_raises(self, tmp_path):
        with pytest.raises(NotImplementedError):
            scraper._save_raw_page(str(tmp_path), 2, {"data": []})


def _stub_server(monkeypatch, pages):
    """Serve `pages` (1-indexed list of hand lists) and record what was fetched."""
    fetched = []

    async def fake_fetch_page(client, token, page, page_size, semaphore):
        fetched.append(page)
        if page < 1 or page > len(pages):
            return {"data": []}
        return {
            "metadata": {"total_pages": len(pages), "total": sum(len(p) for p in pages)},
            "data": pages[page - 1],
        }

    async def fake_fetch_metadata(client, token, page_size):
        return await fake_fetch_page(client, token, 1, page_size, None)

    monkeypatch.setattr(scraper, "fetch_page", fake_fetch_page)
    monkeypatch.setattr(scraper, "fetch_metadata", fake_fetch_metadata)
    return fetched


class TestScrapeAll:
    def test_fetches_every_page_ignoring_what_is_on_disk(self, monkeypatch, tmp_path):
        """The regression: a cached page must never stand in for a real fetch."""
        pages = [[_hand("p1", AUG_10)], [_hand("p2", AUG_10 - DAY)], [_hand("p3", AUG_10 - 2 * DAY)]]
        merge_raw_hands(str(tmp_path), [_hand("p2", AUG_10 - DAY)])
        fetched = _stub_server(monkeypatch, pages)

        hands = asyncio.run(scraper.scrape_all("tok", str(tmp_path), page_size=1))

        assert {1, 2, 3} <= set(fetched)
        assert {h["id"] for h in hands} == {"p1", "p2", "p3"}

    def test_captures_hands_between_page_one_and_a_stale_cache(self, monkeypatch, tmp_path):
        """The exact corpus failure: page 1 fresh, page 2 stale, days lost between."""
        pages = [
            [_hand("aug20", AUG_10 + 10 * DAY)],
            [_hand("aug15", AUG_10 + 5 * DAY)],   # never captured by the old scraper
            [_hand("aug12", AUG_10 + 2 * DAY)],   # never captured by the old scraper
            [_hand("aug10", AUG_10)],             # the stale cached page
        ]
        merge_raw_hands(str(tmp_path), [_hand("aug10", AUG_10)])
        _stub_server(monkeypatch, pages)

        asyncio.run(scraper.scrape_all("tok", str(tmp_path), page_size=1))

        assert set(load_existing_hand_ids(str(tmp_path))) == {
            "aug20", "aug15", "aug12", "aug10"
        }

    def test_retries_a_failed_page_instead_of_leaving_a_hole(self, monkeypatch, tmp_path):
        pages = [[_hand("p1", AUG_10)], [_hand("p2", AUG_10 - DAY)]]
        calls = {"n": 0}

        async def flaky(client, token, page, page_size, semaphore):
            if page == 2:
                calls["n"] += 1
                if calls["n"] == 1:
                    return None
            return {"metadata": {"total_pages": 2, "total": 2}, "data": pages[page - 1]}

        async def meta(client, token, page_size):
            return {"metadata": {"total_pages": 2, "total": 2}, "data": pages[0]}

        monkeypatch.setattr(scraper, "fetch_page", flaky)
        monkeypatch.setattr(scraper, "fetch_metadata", meta)

        asyncio.run(scraper.scrape_all("tok", str(tmp_path), page_size=1))
        assert set(load_existing_hand_ids(str(tmp_path))) == {"p1", "p2"}

    def test_picks_up_a_hand_that_drifts_mid_sweep(self, monkeypatch, tmp_path):
        """A hand played during the sweep shifts the pages; the drift check catches it."""
        state = {"swept": False}

        async def fake_fetch_page(client, token, page, page_size, semaphore):
            if not state["swept"]:
                pages = [[_hand("a", AUG_10 + DAY)], [_hand("b", AUG_10)]]
            else:  # a new hand arrived, everything shifted one page later
                pages = [[_hand("late", AUG_10 + 2 * DAY)], [_hand("a", AUG_10 + DAY)],
                         [_hand("b", AUG_10)]]
            if page >= len(pages) + 1:
                state["swept"] = True
                return {"data": []}
            if page == len(pages):
                state["swept"] = True
            return {"metadata": {"total_pages": 2, "total": 2}, "data": pages[page - 1]}

        async def meta(client, token, page_size):
            return {"metadata": {"total_pages": 2, "total": 2},
                    "data": [_hand("a", AUG_10 + DAY)]}

        monkeypatch.setattr(scraper, "fetch_page", fake_fetch_page)
        monkeypatch.setattr(scraper, "fetch_metadata", meta)

        asyncio.run(scraper.scrape_all("tok", str(tmp_path), page_size=1, confirm_pages=1))
        assert "late" in load_existing_hand_ids(str(tmp_path))


class TestScrapeUpdate:
    def test_fetches_new_hands_and_stops_once_confirmed(self, monkeypatch, tmp_path):
        pages = [[_hand("new1", AUG_10 + 2 * DAY)], [_hand("new2", AUG_10 + DAY)],
                 [_hand("known", AUG_10)], [_hand("older", AUG_10 - DAY)]]
        merge_raw_hands(str(tmp_path), [_hand("known", AUG_10), _hand("older", AUG_10 - DAY)])
        fetched = _stub_server(monkeypatch, pages)

        new = asyncio.run(scraper.scrape_update("tok", str(tmp_path), page_size=1, confirm_pages=1))

        assert {h["id"] for h in new} == {"new1", "new2"}
        assert 4 not in fetched  # stopped after one fully-known page

    def test_keeps_going_past_a_single_known_page(self, monkeypatch, tmp_path):
        """A known page is not proof of catching up — the server has its own holes."""
        pages = [[_hand("new1", AUG_10 + 3 * DAY)], [_hand("known", AUG_10 + 2 * DAY)],
                 [_hand("new2", AUG_10 + DAY)], [_hand("known2", AUG_10)]]
        merge_raw_hands(str(tmp_path), [_hand("known", AUG_10 + 2 * DAY),
                                       _hand("known2", AUG_10)])
        _stub_server(monkeypatch, pages)

        new = asyncio.run(scraper.scrape_update("tok", str(tmp_path), page_size=1, confirm_pages=2))
        assert {h["id"] for h in new} == {"new1", "new2"}

    def test_does_not_destroy_hands_stored_under_early_page_indexes(self, monkeypatch, tmp_path):
        """The old --update overwrote page_00001..N, punching holes in history."""
        (tmp_path / "page_00002.json").write_text(
            json.dumps({"data": [_hand("archived", AUG_10 - 30 * DAY)]})
        )
        _stub_server(monkeypatch, [[_hand("fresh", AUG_10)]])

        asyncio.run(scraper.scrape_update("tok", str(tmp_path), page_size=1, confirm_pages=1))
        assert "archived" in load_existing_hand_ids(str(tmp_path))
