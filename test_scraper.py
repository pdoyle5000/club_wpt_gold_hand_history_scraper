"""Tests for scraper page-freshness helpers."""

import asyncio
import json
import time

import scraper
from scraper import _page_is_stale

CUTOFF = 1_000_000  # ms


def _page(*timestamps):
    return {"data": [{"timestamp": ts} for ts in timestamps]}


class TestPageIsStale:
    def test_all_hands_newer_than_cutoff(self):
        assert _page_is_stale(_page(CUTOFF + 1, CUTOFF + 500), CUTOFF) is False

    def test_all_hands_older_than_cutoff(self):
        assert _page_is_stale(_page(CUTOFF - 500, CUTOFF - 1), CUTOFF) is True

    def test_mixed_hands_not_stale(self):
        assert _page_is_stale(_page(CUTOFF - 500, CUTOFF + 1), CUTOFF) is False

    def test_hand_exactly_at_cutoff_counts_as_fresh(self):
        assert _page_is_stale(_page(CUTOFF), CUTOFF) is False

    def test_empty_page_is_stale(self):
        assert _page_is_stale(_page(), CUTOFF) is True

    def test_missing_data_key_is_stale(self):
        assert _page_is_stale({}, CUTOFF) is True

    def test_missing_timestamp_field_treated_as_old(self):
        assert _page_is_stale({"data": [{}]}, CUTOFF) is True


class TestScrapeAllRefreshRecent:
    """Verify --refresh-recent actually gates the cache bypass in scrape_all."""

    def _stub(self, monkeypatch, raw_dir, now_ms, fetch_page_impl):
        raw_dir.mkdir(exist_ok=True)
        (raw_dir / "page_00002.json").write_text(json.dumps({
            "data": [{"id": "cached_hand", "timestamp": now_ms}]
        }))

        async def fake_fetch_metadata(client, token, page_size):
            return {
                "metadata": {"total_pages": 2, "total": 2},
                "data": [{"id": "page1_hand", "timestamp": now_ms}],
            }

        monkeypatch.setattr(scraper, "fetch_metadata", fake_fetch_metadata)
        monkeypatch.setattr(scraper, "fetch_page", fetch_page_impl)

    def test_refresh_recent_true_bypasses_cache_for_recent_page(self, monkeypatch, tmp_path):
        now_ms = time.time() * 1000
        raw_dir = tmp_path / "raw"

        async def fake_fetch_page(client, token, page, page_size, semaphore):
            assert page == 2
            return {"data": [{"id": "fresh_fetched_hand", "timestamp": now_ms}]}

        self._stub(monkeypatch, raw_dir, now_ms, fake_fetch_page)

        hands = asyncio.run(scraper.scrape_all(
            "tok", str(raw_dir), page_size=1, refresh_recent=True,
        ))

        hand_ids = {h["id"] for h in hands}
        assert "fresh_fetched_hand" in hand_ids
        assert "cached_hand" not in hand_ids

    def test_refresh_recent_false_trusts_cache_for_page(self, monkeypatch, tmp_path):
        now_ms = time.time() * 1000
        raw_dir = tmp_path / "raw"

        async def fake_fetch_page(client, token, page, page_size, semaphore):
            raise AssertionError(
                f"fetch_page should not be called for page {page} when "
                "refresh_recent=False and a cache file already exists"
            )

        self._stub(monkeypatch, raw_dir, now_ms, fake_fetch_page)

        hands = asyncio.run(scraper.scrape_all(
            "tok", str(raw_dir), page_size=1, refresh_recent=False,
        ))

        hand_ids = {h["id"] for h in hands}
        assert "cached_hand" in hand_ids
        assert "fresh_fetched_hand" not in hand_ids
