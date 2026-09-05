"""Tests for the Developer CLI interface."""

from pathlib import Path

import pytest

from app.lab.cli import main


def test_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    """CLI --help should display commands and exit with 0."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "RecoveryOS Synthetic Payment Laboratory CLI" in captured.out


def test_cli_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """--dry-run should print execution summary and write zero files."""
    code = main(
        [
            "generate",
            "--seed",
            "123",
            "--journeys",
            "15",
            "--merchants",
            "5",
            "--output",
            str(tmp_path),
            "--dry-run",
        ]
    )
    assert code == 0
    captured = capsys.readouterr()
    assert "Synthetic Lab Dry Run" in captured.out
    assert "No files or database records written." in captured.out
    # Output directory must be empty
    assert len(list(tmp_path.iterdir())) == 0


def test_cli_generate_and_validate_e2e(tmp_path: Path) -> None:
    """Full CLI generate followed by CLI validate roundtrip."""
    gen_code = main(
        [
            "generate",
            "--seed",
            "456",
            "--journeys",
            "20",
            "--merchants",
            "10",
            "--output",
            str(tmp_path),
        ]
    )
    assert gen_code == 0

    ds_dir = tmp_path / "ds_syn_default_s456_n20"
    assert ds_dir.exists()

    val_code = main(["validate", str(ds_dir)])
    assert val_code == 0
