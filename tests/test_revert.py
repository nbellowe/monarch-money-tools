from __future__ import annotations

from monarch_money_tools.paths import cleanup_revert_dir, review_revert_dir, rules_revert_dir


def test_revert_dir_helpers_are_under_data(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert review_revert_dir() == tmp_path / "data" / "review" / "revert"
    assert cleanup_revert_dir() == tmp_path / "data" / "cleanup" / "revert"
    assert rules_revert_dir() == tmp_path / "data" / "rules" / "revert"
