from __future__ import annotations

from monarch_money_tools.paths import normalized_latest_dir


def test_normalized_bundle_fixture_writes_bundle_json(normalized_bundle, tmp_path):
    path = normalized_latest_dir() / "bundle.json"
    assert path.exists()
    assert "transactions" in normalized_bundle
    assert "accounts" in normalized_bundle
    assert "categories" in normalized_bundle
    assert len(normalized_bundle["transactions"]) > 0


def test_monarch_data_dir_fixture_returns_tmp_path(monarch_data_dir, tmp_path):
    assert monarch_data_dir == tmp_path
    assert (tmp_path / "data/normalized/latest/bundle.json").exists()
