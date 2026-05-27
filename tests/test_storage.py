import pytest

from monarch_money_tools.storage import JsonObject, load_bundle, now_iso, round2, write_json


def test_json_object_importable() -> None:
    obj: JsonObject = {"key": "value"}
    assert obj["key"] == "value"


def test_now_iso_format() -> None:
    result = now_iso()
    assert result.endswith("Z")
    assert "T" in result
    assert "+" not in result


def test_round2_rounds_to_two_places() -> None:
    assert round2(0.956) == 0.96
    assert round2(0.554) == 0.55
    assert round2(1.0) == 1.0


def test_load_bundle_raises_when_missing(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError, match="monarch pull"):
        load_bundle()


def test_load_bundle_returns_parsed_data(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    bundle = {"transactions": [{"id": "t1"}], "categories": []}
    write_json(tmp_path / "data/normalized/latest/bundle.json", bundle)
    result = load_bundle()
    assert result["transactions"][0]["id"] == "t1"
