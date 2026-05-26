from __future__ import annotations

from pathlib import Path

import pytest
import typer

from monarch_money_tools.init_wizard import _append_env, _read_env, run_init_wizard


def test_read_env_parses_key_value_pairs(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text('MONARCH_EMAIL="test@example.com"\nMONARCH_PASSWORD=secret\n', encoding="utf-8")
    result = _read_env(env)
    assert result["MONARCH_EMAIL"] == "test@example.com"
    assert result["MONARCH_PASSWORD"] == "secret"


def test_read_env_returns_empty_for_missing_file(tmp_path: Path) -> None:
    result = _read_env(tmp_path / ".env")
    assert result == {}


def test_append_env_adds_missing_keys(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text('MONARCH_EMAIL="existing@example.com"\n', encoding="utf-8")
    _append_env(env, {"MONARCH_EMAIL": "other@example.com", "MONARCH_PASSWORD": "pw"})
    content = env.read_text(encoding="utf-8")

    assert 'MONARCH_EMAIL="other@example.com"' not in content
    assert "existing@example.com" in content
    assert "MONARCH_PASSWORD" in content
    assert "pw" in content


def test_append_env_creates_file_if_missing(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    _append_env(env, {"MONARCH_EMAIL": "new@example.com"})
    assert env.exists()
    assert "new@example.com" in env.read_text(encoding="utf-8")


def test_append_env_no_op_when_all_keys_exist(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text('MONARCH_EMAIL="a@b.com"\n', encoding="utf-8")
    _append_env(env, {"MONARCH_EMAIL": "other@b.com"})
    content = env.read_text(encoding="utf-8")
    assert content.count("MONARCH_EMAIL") == 1


def test_run_init_wizard_stops_after_password_connection_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_credentials(yes: bool, env_path: Path) -> str:
        calls.append("credentials")
        return "password"

    def fake_connection_test() -> bool:
        calls.append("connection")
        return False

    def unexpected_step(*args: object, **kwargs: object) -> None:
        raise AssertionError("init should stop before later steps")

    monkeypatch.setattr("monarch_money_tools.init_wizard._step_credentials", fake_credentials)
    monkeypatch.setattr(
        "monarch_money_tools.init_wizard._step_connection_test",
        fake_connection_test,
    )
    monkeypatch.setattr("monarch_money_tools.init_wizard._step_taxonomy_check", unexpected_step)
    monkeypatch.setattr("monarch_money_tools.init_wizard._step_profile_bootstrap", unexpected_step)
    monkeypatch.setattr("monarch_money_tools.init_wizard._step_doctor", unexpected_step)

    with pytest.raises(typer.Exit) as exc_info:
        run_init_wizard()

    assert exc_info.value.exit_code == 1
    assert calls == ["credentials", "connection"]
