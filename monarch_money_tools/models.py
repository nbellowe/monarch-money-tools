from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    monarch_email: str | None = Field(default=None, alias="MONARCH_EMAIL")
    monarch_password: str | None = Field(default=None, alias="MONARCH_PASSWORD")
    monarch_mfa_secret: str | None = Field(default=None, alias="MONARCH_MFA_SECRET")
    monarch_session_token: str | None = Field(default=None, alias="MONARCH_SESSION_TOKEN")
    monarch_session_file: str | None = Field(default=None, alias="MONARCH_SESSION_FILE")
    monarch_cookie: str | None = Field(default=None, alias="MONARCH_COOKIE")
    monarch_csrf_token: str | None = Field(default=None, alias="MONARCH_CSRF_TOKEN")
    monarch_api_url: str = Field(default="https://api.monarch.com/graphql", alias="MONARCH_API_URL")
    monarch_client: str = Field(default="monarch-core-web-app-graphql", alias="MONARCH_CLIENT")
    monarch_client_version: str | None = Field(default=None, alias="MONARCH_CLIENT_VERSION")
    monarch_device_uuid: str | None = Field(default=None, alias="MONARCH_DEVICE_UUID")
    monarch_user_agent: str = Field(
        default=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
        ),
        alias="MONARCH_USER_AGENT",
    )
    monarch_csv_path: str | None = Field(default=None, alias="MONARCH_CSV_PATH")
    monarch_start_date: str = Field(default="2018-01-01", alias="MONARCH_START_DATE")
    monarch_page_size: int = Field(default=500, alias="MONARCH_PAGE_SIZE")
    monarch_max_pages: int = Field(default=200, alias="MONARCH_MAX_PAGES")
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-haiku-4-5-20251001", alias="ANTHROPIC_MODEL")


class ImportResult(BaseModel):
    transactions: list[dict[str, Any]]
    accounts: list[dict[str, Any]]
    categories: list[dict[str, Any]]
