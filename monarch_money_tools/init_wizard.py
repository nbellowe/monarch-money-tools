from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Literal

import typer
from rich.console import Console

console = Console()

AuthMethod = Literal["cookie", "session", "password", "skip", "unknown"]


def _read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _append_env(path: Path, new_keys: dict[str, str]) -> None:
    """Append missing keys to a .env file without overwriting existing values."""
    existing = _read_env(path)
    to_add = {key: value for key, value in new_keys.items() if key not in existing}
    if not to_add:
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    existing_text = path.read_text(encoding="utf-8") if path.exists() else ""
    needs_leading_newline = bool(existing_text) and not existing_text.endswith("\n")
    with path.open("a", encoding="utf-8") as file:
        if needs_leading_newline:
            file.write("\n")
        for key, value in to_add.items():
            file.write(f'{key}="{value}"\n')
    path.chmod(0o600)


def _auth_method_from_env(env: dict[str, str]) -> AuthMethod:
    if os.environ.get("MONARCH_COOKIE") or env.get("MONARCH_COOKIE"):
        return "cookie"
    if (
        os.environ.get("MONARCH_SESSION_TOKEN")
        or env.get("MONARCH_SESSION_TOKEN")
        or os.environ.get("MONARCH_SESSION_FILE")
        or env.get("MONARCH_SESSION_FILE")
    ):
        return "session"
    if (os.environ.get("MONARCH_EMAIL") or env.get("MONARCH_EMAIL")) and (
        os.environ.get("MONARCH_PASSWORD") or env.get("MONARCH_PASSWORD")
    ):
        return "password"
    return "unknown"


def _step_credentials(yes: bool, env_path: Path) -> AuthMethod:
    env = _read_env(env_path)
    email = os.environ.get("MONARCH_EMAIL") or env.get("MONARCH_EMAIL")
    password = os.environ.get("MONARCH_PASSWORD") or env.get("MONARCH_PASSWORD")
    cookie = os.environ.get("MONARCH_COOKIE") or env.get("MONARCH_COOKIE")
    session_token = os.environ.get("MONARCH_SESSION_TOKEN") or env.get("MONARCH_SESSION_TOKEN")
    session_file = os.environ.get("MONARCH_SESSION_FILE") or env.get("MONARCH_SESSION_FILE")

    console.print("\n[bold]Step 1: Credentials[/]")
    if cookie or session_token or session_file or (email and password):
        console.print("[green]ok[/] Auth settings already exist.")
        return _auth_method_from_env(env)

    if yes:
        console.print(
            "[yellow]--yes mode: skipping credential prompts. "
            "Set MONARCH_COOKIE, MONARCH_SESSION_TOKEN, or password credentials in .env.[/]"
        )
        return "unknown"

    console.print(
        "[dim]Recommended: use browser cookie or saved-session auth. "
        "Password auth is available as a fallback.[/]"
    )
    method = (
        typer.prompt(
            "Auth method: cookie, session, password, or skip",
            default="cookie",
        )
        .strip()
        .lower()
    )
    if method in {"skip", "s", ""}:
        console.print("[yellow]Skipped auth setup.[/]")
        return "skip"

    new_keys: dict[str, str] = {}
    auth_method: AuthMethod
    if method in {"cookie", "c"}:
        auth_method = "cookie"
        cookie = typer.prompt("Full Monarch Cookie header", hide_input=True)
        if cookie:
            new_keys["MONARCH_COOKIE"] = cookie
            from .monarch_api import csrf_from_cookie

            if not csrf_from_cookie(cookie):
                csrf = typer.prompt("CSRF token", hide_input=True)
                if csrf:
                    new_keys["MONARCH_CSRF_TOKEN"] = csrf
    elif method in {"session", "token", "t"}:
        auth_method = "session"
        token = typer.prompt("Monarch session token", hide_input=True)
        if token:
            new_keys["MONARCH_SESSION_TOKEN"] = token
    elif method in {"password", "p"}:
        auth_method = "password"
        email = typer.prompt("Monarch Money email")
        password = typer.prompt("Monarch Money password", hide_input=True)

        mfa = os.environ.get("MONARCH_MFA_SECRET") or env.get("MONARCH_MFA_SECRET")
        console.print(
            "[dim]Optional: MFA secret for automatic login.[/]\n"
            "[dim]To get it: disable 2FA in Monarch, re-enable it, click "
            "'Can't scan?', then copy the BASE32 secret.[/]"
        )
        mfa_input = typer.prompt("MFA secret (Enter to skip)", default="")
        mfa = mfa_input or None
        if email:
            new_keys["MONARCH_EMAIL"] = email
        if password:
            new_keys["MONARCH_PASSWORD"] = password
        if mfa:
            new_keys["MONARCH_MFA_SECRET"] = mfa
    else:
        console.print("[yellow]Unknown auth method; skipped auth setup.[/]")
        return "unknown"

    _append_env(env_path, new_keys)
    console.print("[green]ok[/] Auth settings written to .env")
    return auth_method


def _step_connection_test() -> bool:
    console.print("\n[bold]Step 2: Connection test[/]")
    try:
        from .monarch_api import create_monarch_client

        async def _test() -> None:
            client = await create_monarch_client()
            await client.get_transaction_categories()

        asyncio.run(_test())
        console.print("[green]ok[/] Connected to Monarch successfully.")
        return True
    except Exception as exc:
        console.print(f"[yellow]Connection test failed:[/] {exc}")
        console.print(
            "[dim]Check MONARCH_COOKIE, MONARCH_CSRF_TOKEN, MONARCH_SESSION_TOKEN, "
            "or password fallback settings in .env and try again.[/]"
        )
        return False


def _step_taxonomy_check(yes: bool) -> None:
    console.print("\n[bold]Step 3: Taxonomy check[/]")
    from .paths import canonical_taxonomy_file, local_taxonomy_file

    taxonomy_path = canonical_taxonomy_file()
    if not taxonomy_path.exists():
        console.print(f"[yellow]Taxonomy not found at {taxonomy_path}; skipping.[/]")
        return

    local_path = local_taxonomy_file()
    if not local_path.exists():
        should_copy = yes or typer.confirm(
            "Copy the starter taxonomy into ./taxonomy/canonical-taxonomy.yaml?",
            default=True,
        )
        if should_copy:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_text(taxonomy_path.read_text(encoding="utf-8"), encoding="utf-8")
            taxonomy_path = local_path
            console.print(f"[green]ok[/] Wrote {local_path}")

    try:
        import yaml

        taxonomy = yaml.safe_load(taxonomy_path.read_text(encoding="utf-8")) or {}
        canonical_names = {str(c["name"]) for c in (taxonomy.get("categories") or [])}

        async def _fetch_live() -> set[str]:
            from .monarch_api import create_monarch_client

            client = await create_monarch_client()
            result = await client.get_transaction_categories()
            return {str(c["name"]) for c in (result.get("categories") or [])}

        live_names = asyncio.run(_fetch_live())
        only_canonical = canonical_names - live_names
        only_live = live_names - canonical_names

        if not only_canonical and not only_live:
            console.print("[green]ok[/] Taxonomy matches Monarch categories.")
            return

        if only_canonical:
            console.print(
                f"[yellow]In taxonomy but not in Monarch ({len(only_canonical)}):[/] "
                + ", ".join(sorted(only_canonical))
            )
        if only_live:
            console.print(
                f"[yellow]In Monarch but not in taxonomy ({len(only_live)}):[/] "
                + ", ".join(sorted(only_live))
            )
    except Exception as exc:
        console.print(f"[yellow]Taxonomy check skipped:[/] {exc}")


def _step_profile_bootstrap(yes: bool) -> None:
    console.print("\n[bold]Step 4: Profile[/]")
    profile_path = Path("profile.yaml")
    if profile_path.exists():
        console.print("[green]ok[/] profile.yaml already exists.")
        return

    from .profile import PROFILE_TEMPLATE

    if not yes and not typer.confirm("Create a starter profile.yaml?", default=True):
        return

    profile_path.write_text(PROFILE_TEMPLATE, encoding="utf-8")
    url = "https://nbellowe.github.io/retirement-simulator"
    console.print(f"[green]ok[/] Visit {url} and drag in your profile.")


def _step_doctor() -> None:
    console.print("\n[bold]Step 5: Doctor[/]")
    from .doctor import collect_checks, has_python_project

    all_ok = True
    for name, ok, detail in collect_checks():
        status = "[green]ok[/]" if ok else "[red]missing[/]"
        console.print(f"  {status}  {name}: {detail}")
        if not ok:
            all_ok = False

    pyproject_ok = has_python_project()
    console.print(
        f"  {'[green]ok[/]' if pyproject_ok else '[red]missing[/]'}  python project: pyproject.toml"
    )
    if all_ok and pyproject_ok:
        console.print("[green]ok[/] All checks passed.")


def run_init_wizard(yes: bool = False) -> None:
    env_path = Path(".env")
    auth_method = _step_credentials(yes, env_path)
    connection_ok = _step_connection_test()
    if not connection_ok and auth_method == "password":
        console.print(
            "[red]Stopping init because password authentication failed.[/] "
            "Use cookie or saved-session auth, or retry after Monarch stops "
            "rate limiting login attempts."
        )
        raise typer.Exit(1)
    _step_taxonomy_check(yes)
    _step_profile_bootstrap(yes)
    _step_doctor()
