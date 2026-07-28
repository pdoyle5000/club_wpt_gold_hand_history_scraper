"""Tests for scraper page-freshness helpers."""

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
