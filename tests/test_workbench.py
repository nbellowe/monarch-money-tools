from __future__ import annotations

from pathlib import Path

from monarch_money_tools.storage import write_json
from monarch_money_tools.workbench import load_latest_dataset, today_utc, write_investigation_artifacts


def test_workbench_loads_scopes_and_writes_artifacts(tmp_path: Path) -> None:
    bundle = {
        "exportedAt": "2026-05-20T00:00:00Z",
        "transactions": [
            {
                "id": "1",
                "date": today_utc().isoformat(),
                "accountName": "Nathan Checking",
                "owner": "",
                "isPending": False,
                "signedAmount": 100,
            },
            {
                "id": "2",
                "date": today_utc().isoformat(),
                "accountName": "Shared Checking",
                "owner": "Shared",
                "isPending": False,
                "signedAmount": -25,
            },
        ],
        "accounts": [{"id": "a1", "displayName": "Nathan Checking"}],
        "categories": [{"id": "c1", "name": "Paychecks"}],
    }
    write_json(tmp_path / "data/normalized/latest/bundle.json", bundle)

    dataset = load_latest_dataset(tmp_path)
    rows = dataset.scoped_transactions(owner="Nathan")
    output_dir = write_investigation_artifacts(
        "sample",
        summary={"count": len(rows)},
        rows=rows,
        markdown="# Sample\n",
        root=tmp_path,
    )

    assert len(rows) == 1
    assert rows[0]["id"] == "1"
    assert (output_dir / "result.json").exists()
    assert (output_dir / "result.csv").exists()
    assert (tmp_path / "reports/latest/sample.md").exists()
