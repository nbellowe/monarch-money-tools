from __future__ import annotations

from io import StringIO

from rich.console import Console

from monarch_money_tools.cmd._utils import print_dry_run_table


def _capture(fn) -> str:  # type: ignore[no-untyped-def]
    buf = StringIO()
    console = Console(file=buf, width=200)
    fn(console)
    return buf.getvalue()


def test_print_dry_run_table_shows_all_rows() -> None:
    rows = [
        {"merchant": "Coffee", "amount": "-$5.00", "cat": "Dining"},
        {"merchant": "Gas", "amount": "-$40.00", "cat": "Auto"},
    ]
    columns = [("Merchant", None), ("Amount", "right"), ("Category", None)]

    output = _capture(
        lambda c: print_dry_run_table(
            "Test Title",
            rows,
            columns,
            lambda r: (r["merchant"], r["amount"], r["cat"]),
            console=c,
        )
    )

    assert "Coffee" in output
    assert "Gas" in output
    assert "Test Title" in output


def test_print_dry_run_table_truncates_at_limit() -> None:
    rows = [{"merchant": f"Merchant{i}", "amount": f"-${i}.00"} for i in range(10)]
    columns = [("Merchant", None), ("Amount", "right")]

    output = _capture(
        lambda c: print_dry_run_table(
            "Truncation Test",
            rows,
            columns,
            lambda r: (r["merchant"], r["amount"]),
            console=c,
            limit=3,
        )
    )

    assert "Merchant0" in output
    assert "Merchant2" in output
    assert "Merchant3" not in output
    assert "7 more" in output
