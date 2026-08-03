"""Tests for main.py CLI argument validation and output routing."""

import json
import sys

import pytest

import main
from test_converter import SAMPLE_HAND_1, SAMPLE_HAND_2


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


class TestOutputFormats:
    def _run_convert(self, tmp_path, extra_argv):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        (raw_dir / "page_00001.json").write_text(
            json.dumps({"data": [SAMPLE_HAND_1, SAMPLE_HAND_2]})
        )
        argv = ["main.py", "--convert-only", "--output-dir", str(tmp_path)] + extra_argv
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sys, "argv", argv)
            main.main()

    def test_defaults_to_pokerstars(self, tmp_path):
        self._run_convert(tmp_path, [])
        assert (tmp_path / "pokerstars").is_dir()
        assert not (tmp_path / "ohh").exists()

    def test_ohh_writes_dot_ohh_files(self, tmp_path):
        self._run_convert(tmp_path, ["--format", "ohh"])
        assert not (tmp_path / "pokerstars").exists()
        files = sorted((tmp_path / "ohh").iterdir())
        assert files and all(f.suffix == ".ohh" for f in files)
        # Each file is a run of JSON objects separated by a blank line
        for f in files:
            for chunk in f.read_text().strip().split("\n\n"):
                assert "ohh" in json.loads(chunk)

    def test_both_writes_each_format(self, tmp_path):
        self._run_convert(tmp_path, ["--format", "both"])
        assert list((tmp_path / "pokerstars").iterdir())
        assert list((tmp_path / "ohh").iterdir())

    def test_unknown_format_rejected(self, monkeypatch):
        _run_main_expecting_exit(["--convert-only", "--format", "hm3"], monkeypatch)


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
