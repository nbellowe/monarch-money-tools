from __future__ import annotations

import typer

from .cmd.cleanup import apply_cleanup_command, cleanup_app
from .cmd.data import data_app, doctor_command, import_command, pull_command, run_command
from .cmd.misc import init_command, init_profile_command, portfolio_command, retire_command
from .cmd.review import (
    apply_clear_reviews_command,
    apply_llm_review_command,
    apply_reviews_command,
    bulk_clear_reviews_command,
    review_app,
)
from .cmd.rules import rules_app

app = typer.Typer(
    help="Local-first Monarch Money export analysis and planning CLI.",
    no_args_is_help=True,
)

app.add_typer(data_app, name="data")
app.add_typer(review_app, name="review")
app.add_typer(cleanup_app, name="cleanup")
app.add_typer(rules_app, name="rules")

# Primary flat shortcuts (visible at top level)
app.command("doctor")(doctor_command)
app.command("import")(import_command)
app.command("run")(run_command)
app.command("pull")(pull_command)
app.command("init")(init_command)
app.command("retire")(retire_command)
app.command("init-profile")(init_profile_command)
app.command("portfolio")(portfolio_command)

# Legacy flat aliases (hidden – kept for backward-compat with tests and scripts)
app.command("apply-reviews", hidden=True)(apply_reviews_command)
app.command("apply-clear-reviews", hidden=True)(apply_clear_reviews_command)
app.command("apply-llm-review", hidden=True)(apply_llm_review_command)
app.command("bulk-clear-reviews", hidden=True)(bulk_clear_reviews_command)
app.command("apply-cleanup", hidden=True)(apply_cleanup_command)
