from __future__ import annotations

from pathlib import Path


def root_dir() -> Path:
    return Path.cwd()


def data_dir() -> Path:
    return root_dir() / "data"


def raw_latest_dir() -> Path:
    return data_dir() / "raw" / "latest"


def raw_history_dir() -> Path:
    return data_dir() / "raw" / "history"


def normalized_latest_dir() -> Path:
    return data_dir() / "normalized" / "latest"


def analysis_latest_dir() -> Path:
    return data_dir() / "analysis" / "latest"


def reports_latest_dir() -> Path:
    return root_dir() / "reports" / "latest"


def review_latest_dir() -> Path:
    return data_dir() / "review" / "latest"


def cleanup_latest_dir() -> Path:
    return data_dir() / "cleanup" / "latest"


def taxonomy_dir() -> Path:
    return root_dir() / "taxonomy"


def local_taxonomy_file() -> Path:
    return taxonomy_dir() / "canonical-taxonomy.yaml"


def bundled_taxonomy_file() -> Path:
    return Path(__file__).parent / "taxonomy" / "canonical-taxonomy.yaml"


def canonical_taxonomy_file() -> Path:
    """Return a workspace taxonomy when present, otherwise the packaged default."""
    local = local_taxonomy_file()
    return local if local.exists() else bundled_taxonomy_file()


def rules_latest_dir() -> Path:
    return data_dir() / "rules" / "latest"


def review_revert_dir() -> Path:
    return data_dir() / "review" / "revert"


def cleanup_revert_dir() -> Path:
    return data_dir() / "cleanup" / "revert"


def rules_revert_dir() -> Path:
    return data_dir() / "rules" / "revert"


def cashflow_latest_dir() -> Path:
    return data_dir() / "cashflow" / "latest"


def backups_dir() -> Path:
    return data_dir() / "backups"


def exported_dir() -> Path:
    return root_dir() / "exported"


def private_exports_dir() -> Path:
    return root_dir() / "private" / "monarch" / "exports"


def retirement_dir() -> Path:
    return root_dir() / "reports" / "retirement"
