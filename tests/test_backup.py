from __future__ import annotations

from pathlib import Path

from monarch_money_tools.backup import create_pre_cleanup_backup, verify_pre_cleanup_backup


def test_create_pre_cleanup_backup_excludes_recursive_backups(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    for path in [
        "data/raw/latest",
        "data/normalized/latest",
        "data/rules/latest",
        "data/review/latest",
        "data/backups/old",
        "reports/latest",
    ]:
        (tmp_path / path).mkdir(parents=True)
    (tmp_path / "data/raw/latest/bundle.json").write_text("{}", encoding="utf-8")
    (tmp_path / "data/backups/old/recursive.txt").write_text("bad", encoding="utf-8")
    (tmp_path / "reports/latest/summary.md").write_text("# Summary\n", encoding="utf-8")

    manifest = create_pre_cleanup_backup()

    backup_path = Path(str(manifest["backupPath"]))
    assert (backup_path / "manifest.json").exists()
    assert not (backup_path / "data/backups/old/recursive.txt").exists()
    assert verify_pre_cleanup_backup(manifest) == []
    assert manifest["fileCounts"]["data"] == 1
    assert manifest["fileCounts"]["reports"] == 1
