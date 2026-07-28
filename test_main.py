"""Tests for main.py CLI argument validation."""

import sys

import pytest

import main


def _run_main_expecting_exit(argv, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["main.py"] + argv)
    with pytest.raises(SystemExit):
        main.main()


class TestMutualExclusivity:
    def test_refresh_recent_with_update_errors(self, monkeypatch, capsys):
        _run_main_expecting_exit(["--token", "x", "--update", "--refresh-recent"], monkeypatch)
        assert "--refresh-recent and --update are mutually exclusive" in capsys.readouterr().err

    def test_refresh_recent_with_convert_only_errors(self, monkeypatch, capsys):
        _run_main_expecting_exit(["--convert-only", "--refresh-recent"], monkeypatch)
        assert "--refresh-recent and --convert-only are mutually exclusive" in capsys.readouterr().err

    def test_overwrite_with_update_errors(self, monkeypatch, capsys):
        _run_main_expecting_exit(["--token", "x", "--update", "--overwrite"], monkeypatch)
        assert "--overwrite and --update are mutually exclusive" in capsys.readouterr().err

    def test_overwrite_with_convert_only_errors(self, monkeypatch, capsys):
        _run_main_expecting_exit(["--convert-only", "--overwrite"], monkeypatch)
        assert "--overwrite and --convert-only are mutually exclusive" in capsys.readouterr().err


class TestFlagDefaults:
    def test_no_flags_does_not_trigger_mutual_exclusivity_errors(self, monkeypatch, tmp_path, capsys):
        """--convert-only alone (no --overwrite/--refresh-recent) should reach the
        'no raw files' exit path, not one of the new mutual-exclusivity errors."""
        monkeypatch.setattr(
            sys, "argv",
            ["main.py", "--convert-only", "--output-dir", str(tmp_path)],
        )
        with pytest.raises(SystemExit) as exc_info:
            main.main()
        assert exc_info.value.code == 1
        assert "No raw JSON files found" in capsys.readouterr().out
