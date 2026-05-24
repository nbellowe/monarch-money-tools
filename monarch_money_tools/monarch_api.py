from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from .env import get_config
from .normalizer import (
    normalize_accounts,
    normalize_categories,
    normalize_transaction_rules,
    normalize_transactions,
)
from .paths import normalized_latest_dir, raw_history_dir, raw_latest_dir, root_dir
from .storage import iso_date, reset_dir, timestamp_slug, write_csv, write_json

JsonObject = dict[str, Any]

GET_TRANSACTIONS_QUERY = """
query GetTransactionsList(
  $offset: Int,
  $limit: Int,
  $filters: TransactionFilterInput,
  $orderBy: TransactionOrdering
) {
  allTransactions(filters: $filters) {
    totalCount
    results(offset: $offset, limit: $limit, orderBy: $orderBy) {
      id
      amount
      pending
      date
      hideFromReports
      plaidName
      notes
      isRecurring
      reviewStatus
      needsReview
      isSplitTransaction
      createdAt
      updatedAt
      category {
        id
        name
        group {
          id
          name
          type
          __typename
        }
        __typename
      }
      merchant {
        name
        id
        transactionsCount
        __typename
      }
      account {
        id
        displayName
        __typename
      }
      tags {
        id
        name
        color
        order
        __typename
      }
      __typename
    }
    __typename
  }
}
"""

GET_ACCOUNTS_QUERY = """
query GetAccounts {
  accounts {
    id
    displayName
    isHidden
    displayBalance
    signedBalance
    updatedAt
    type {
      name
      display
      __typename
    }
    subtype {
      name
      display
      __typename
    }
    institution {
      id
      name
      __typename
    }
    __typename
  }
}
"""

GET_CATEGORIES_QUERY = """
query GetCategories {
  categories {
    id
    name
    group {
      id
      name
      type
      __typename
    }
    __typename
  }
}
"""

UPDATE_TRANSACTION_QUERY = """
mutation Web_TransactionDrawerUpdateTransaction($input: UpdateTransactionMutationInput!) {
  updateTransaction(input: $input) {
    transaction {
      id
      amount
      pending
      date
      hideFromReports
      needsReview
      category {
        id
        name
        __typename
      }
      merchant {
        id
        name
        __typename
      }
      __typename
    }
    errors {
      fieldErrors {
        field
        messages
        __typename
      }
      message
      code
      __typename
    }
    __typename
  }
}
"""

GET_TAGS_QUERY = """
query GetHouseholdTransactionTags {
  householdTransactionTags {
    id
    name
    color
    order
    __typename
  }
}
"""

CREATE_TAG_QUERY = """
mutation CreateTransactionTag($input: CreateTransactionTagInput!) {
  createTransactionTag(input: $input) {
    tag {
      id
      name
      color
      order
      __typename
    }
    errors {
      fieldErrors {
        field
        messages
        __typename
      }
      message
      code
      __typename
    }
    __typename
  }
}
"""

SET_TRANSACTION_TAGS_QUERY = """
mutation SetTransactionTags($input: SetTransactionTagsInput!) {
  setTransactionTags(input: $input) {
    errors {
      fieldErrors {
        field
        messages
        __typename
      }
      message
      code
      __typename
    }
    transaction {
      id
      tags {
        id
        name
        color
        order
        __typename
      }
      __typename
    }
    __typename
  }
}
"""

GET_TRANSACTION_RULES_QUERY = """
query GetTransactionRules {
  transactionRules {
    id
    order
    lastAppliedAt
    recentApplicationCount
    merchantCriteriaUseOriginalStatement
    merchantCriteria { operator value }
    originalStatementCriteria { operator value }
    merchantNameCriteria { operator value }
    amountCriteria { operator isExpense value valueRange { lower upper } }
    categoryIds
    accountIds
    categories { id name }
    accounts { id displayName }
    setMerchantAction { id name }
    setCategoryAction { id name }
    addTagsAction { id name color }
    reviewStatusAction
    setHideFromReportsAction
    sendNotificationAction
  }
}
"""

CREATE_TRANSACTION_RULE_QUERY = """
mutation Common_CreateTransactionRuleMutationV2($input: CreateTransactionRuleInput!) {
  createTransactionRuleV2(input: $input) {
    transactionRule {
      id
      order
      merchantCriteria { operator value }
      merchantNameCriteria { operator value }
      originalStatementCriteria { operator value }
      setCategoryAction { id name }
      reviewStatusAction
      setHideFromReportsAction
    }
    errors {
      message
      code
    }
  }
}
"""

UPDATE_TRANSACTION_RULE_QUERY = """
mutation Common_UpdateTransactionRuleMutationV2($input: UpdateTransactionRuleInput!) {
  updateTransactionRuleV2(input: $input) {
    transactionRule {
      id
      order
      merchantCriteria { operator value }
      merchantNameCriteria { operator value }
      originalStatementCriteria { operator value }
      setCategoryAction { id name }
      reviewStatusAction
      setHideFromReportsAction
    }
    errors {
      message
      code
    }
  }
}
"""

DELETE_TRANSACTION_RULE_QUERY = """
mutation Common_DeleteTransactionRule($id: ID!) {
  deleteTransactionRule(id: $id) {
    deleted
    errors {
      message
      code
    }
  }
}
"""

GET_PORTFOLIO_HOLDINGS_QUERY = """
query GetPortfolioHoldings {
  portfolio {
    aggregateHoldings {
      edges {
        node {
          id
          quantity
          basis
          totalValue
          security {
            id
            name
            ticker
            typeDisplay
            closingPrice
            __typename
          }
          __typename
        }
      }
    }
  }
}
"""


class MonarchApiUnavailableError(RuntimeError):
    pass


class BrowserCookieMonarchClient:
    def __init__(
        self,
        *,
        api_url: str,
        cookie: str,
        csrf_token: str,
        device_uuid: str | None,
        monarch_client: str,
        monarch_client_version: str | None,
        user_agent: str,
    ) -> None:
        self.api_url = api_url
        self.headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "client-platform": "web",
            "content-type": "application/json",
            "dnt": "1",
            "monarch-client": monarch_client,
            "origin": "https://app.monarch.com",
            "priority": "u=1, i",
            "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": user_agent,
            "x-csrftoken": csrf_token,
            "cookie": clean_cookie_header(cookie),
        }
        if monarch_client_version:
            self.headers["monarch-client-version"] = monarch_client_version
        if device_uuid:
            self.headers["device-uuid"] = device_uuid

    async def graphql(self, operation_name: str, query: str, variables: JsonObject) -> JsonObject:
        try:
            import aiohttp
        except ImportError as error:
            raise MonarchApiUnavailableError(
                "Install API support with `uv sync --extra api --extra dev`."
            ) from error

        async with (
            aiohttp.ClientSession(headers=self.headers) as session,
            session.post(
                self.api_url,
                json={
                    "operationName": operation_name,
                    "variables": variables,
                    "query": query,
                },
            ) as response,
        ):
            response_text = await response.text()
            if response.status >= 400:
                raise RuntimeError(
                    f"Monarch GraphQL {operation_name} failed with HTTP {response.status}: "
                    f"{response_text[:500]}"
                )
            data = await response.json()
            if data.get("errors"):
                raise RuntimeError(
                    f"Monarch GraphQL {operation_name} returned errors: {data['errors']}"
                )
            result = data.get("data")
            return result if isinstance(result, dict) else {}

    async def get_transactions(
        self,
        limit: int,
        offset: int | None,
        start_date: str | None,
        end_date: str | None,
    ) -> JsonObject:
        filters: JsonObject = {
            "search": "",
            "categories": [],
            "accounts": [],
            "tags": [],
        }
        if start_date and end_date:
            filters["startDate"] = start_date
            filters["endDate"] = end_date
        variables = {
            "offset": offset,
            "limit": limit,
            "orderBy": "date",
            "filters": filters,
        }
        return await self.graphql("GetTransactionsList", GET_TRANSACTIONS_QUERY, variables)

    async def get_accounts(self) -> JsonObject:
        return await self.graphql("GetAccounts", GET_ACCOUNTS_QUERY, {})

    async def get_transaction_categories(self) -> JsonObject:
        return await self.graphql("GetCategories", GET_CATEGORIES_QUERY, {})

    async def update_transaction(
        self,
        transaction_id: str,
        category_id: str | None = None,
        needs_review: bool | None = None,
    ) -> JsonObject:
        input_data: JsonObject = {"id": transaction_id}
        if category_id:
            input_data["category"] = category_id
        if needs_review is not None:
            input_data["needsReview"] = bool(needs_review)
        return await self.graphql(
            "Web_TransactionDrawerUpdateTransaction",
            UPDATE_TRANSACTION_QUERY,
            {"input": input_data},
        )

    async def get_tags(self) -> JsonObject:
        return await self.graphql("GetHouseholdTransactionTags", GET_TAGS_QUERY, {})

    async def create_tag(self, name: str, color: str = "#5B36F2") -> JsonObject:
        return await self.graphql(
            "CreateTransactionTag",
            CREATE_TAG_QUERY,
            {"input": {"name": name, "color": color}},
        )

    async def set_transaction_tags(self, transaction_id: str, tag_ids: list[str]) -> JsonObject:
        return await self.graphql(
            "SetTransactionTags",
            SET_TRANSACTION_TAGS_QUERY,
            {"input": {"transactionId": transaction_id, "tagIds": tag_ids}},
        )

    async def get_transaction_rules(self) -> list[JsonObject]:
        result = await self.graphql("GetTransactionRules", GET_TRANSACTION_RULES_QUERY, {})
        return result.get("transactionRules") or []

    async def create_transaction_rule(self, input: JsonObject) -> JsonObject:
        result = await self.graphql(
            "Common_CreateTransactionRuleMutationV2",
            CREATE_TRANSACTION_RULE_QUERY,
            {"input": input},
        )
        return result.get("createTransactionRuleV2") or {}

    async def update_transaction_rule(self, input: JsonObject) -> JsonObject:
        result = await self.graphql(
            "Common_UpdateTransactionRuleMutationV2",
            UPDATE_TRANSACTION_RULE_QUERY,
            {"input": input},
        )
        return result.get("updateTransactionRuleV2") or {}

    async def delete_transaction_rule(self, rule_id: str) -> JsonObject:
        result = await self.graphql(
            "Common_DeleteTransactionRule",
            DELETE_TRANSACTION_RULE_QUERY,
            {"id": rule_id},
        )
        return result.get("deleteTransactionRule") or {}

    async def get_portfolio_holdings(self) -> list[JsonObject]:
        result = await self.graphql("GetPortfolioHoldings", GET_PORTFOLIO_HOLDINGS_QUERY, {})
        edges = ((result.get("portfolio") or {}).get("aggregateHoldings") or {}).get("edges") or []
        return [e["node"] for e in edges if "node" in e]


async def pull_from_monarch_api() -> Path:
    config = get_config()
    client = await create_monarch_client()
    transactions = await fetch_all_transactions(client)
    accounts_response = await client.get_accounts()
    categories_response = await client.get_transaction_categories()
    accounts = extract_collection(accounts_response, ["accounts"])
    categories = extract_collection(categories_response, ["categories"])
    exported_at = iso_datetime()

    raw_bundle = {
        "exportedAt": exported_at,
        "dateRange": {"startDate": config.monarch_start_date, "endDate": iso_date()},
        "source": {"type": "api"},
        "transactions": transactions,
        "transactionRules": [],
        "accounts": accounts,
        "categories": categories,
        "budgets": None,
        "cashflowSummary": None,
        "netWorthHistory": None,
    }
    normalized_bundle = {
        "exportedAt": exported_at,
        "dateRange": raw_bundle["dateRange"],
        "transactions": normalize_transactions(transactions, accounts, categories),
        "transactionRules": normalize_transaction_rules([]),
        "accounts": normalize_accounts(accounts),
        "categories": normalize_categories(categories),
        "budgets": None,
        "cashflowSummary": None,
        "netWorthHistory": None,
    }

    raw_history = raw_history_dir() / timestamp_slug()
    reset_dir(raw_latest_dir())
    reset_dir(normalized_latest_dir())
    raw_history.mkdir(parents=True, exist_ok=True)

    write_json(raw_history / "bundle.json", raw_bundle)
    write_json(raw_latest_dir() / "bundle.json", raw_bundle)
    write_json(normalized_latest_dir() / "bundle.json", normalized_bundle)
    write_json(normalized_latest_dir() / "transactions.json", normalized_bundle["transactions"])
    write_json(
        normalized_latest_dir() / "transaction-rules.json", normalized_bundle["transactionRules"]
    )
    write_json(normalized_latest_dir() / "accounts.json", normalized_bundle["accounts"])
    write_json(normalized_latest_dir() / "categories.json", normalized_bundle["categories"])
    write_csv(normalized_latest_dir() / "transactions.csv", normalized_bundle["transactions"])
    write_csv(
        normalized_latest_dir() / "transaction-rules.csv", normalized_bundle["transactionRules"]
    )
    write_csv(normalized_latest_dir() / "accounts.csv", normalized_bundle["accounts"])
    write_csv(normalized_latest_dir() / "categories.csv", normalized_bundle["categories"])
    return normalized_latest_dir() / "bundle.json"


async def get_or_create_tag(client: Any, name: str) -> str:
    """Return the tag ID for *name*, creating it if it doesn't exist."""
    tags_response = await client.get_tags()
    tags: list[JsonObject] = tags_response.get("householdTransactionTags") or []
    for tag in tags:
        if tag.get("name", "").lower() == name.lower():
            return str(tag["id"])
    create_response = await client.create_tag(name)
    tag = (create_response.get("createTransactionTag") or {}).get("tag") or {}
    tag_id = tag.get("id")
    if not tag_id:
        raise RuntimeError(f"Failed to create tag '{name}': {create_response}")
    return str(tag_id)


async def fetch_transaction_rules() -> list[JsonObject]:
    client = await create_monarch_client()
    return await client.get_transaction_rules()


async def create_monarch_rule(input: JsonObject) -> JsonObject:
    client = await create_monarch_client()
    return await client.create_transaction_rule(input)


async def update_monarch_rule(input: JsonObject) -> JsonObject:
    client = await create_monarch_client()
    return await client.update_transaction_rule(input)


async def delete_monarch_rule(rule_id: str) -> JsonObject:
    client = await create_monarch_client()
    return await client.delete_transaction_rule(rule_id)


async def fetch_portfolio_allocation() -> dict[str, object]:
    """Return holdings list + allocation summary from Monarch portfolio."""
    client = await create_monarch_client()
    holdings = await client.get_portfolio_holdings()
    total = sum(float(h.get("totalValue") or 0) for h in holdings)

    by_type: dict[str, float] = {}
    for h in holdings:
        sec = h.get("security") or {}
        t = sec.get("typeDisplay") or "Unknown"
        by_type[t] = by_type.get(t, 0.0) + float(h.get("totalValue") or 0)

    holdings_sorted = sorted(holdings, key=lambda h: float(h.get("totalValue") or 0), reverse=True)
    return {
        "holdings": holdings_sorted,
        "totalValue": total,
        "byType": by_type,
        "count": len(holdings),
    }


async def tag_transactions(transaction_ids: list[str], tag_name: str) -> list[JsonObject]:
    """Add *tag_name* to each transaction, preserving any existing tags."""
    client = await create_monarch_client()
    tag_id = await get_or_create_tag(client, tag_name)
    results: list[JsonObject] = []
    for txn_id in transaction_ids:
        response = await client.set_transaction_tags(txn_id, [tag_id])
        results.append({"transactionId": txn_id, "tagId": tag_id, "response": response})
    return results


async def apply_transaction_updates(updates: list[JsonObject]) -> list[JsonObject]:
    client = await create_monarch_client()
    results: list[JsonObject] = []
    for update in updates:
        needs_review = (
            None
            if "setNeedsReview" not in update or update.get("setNeedsReview") is None
            else bool(update.get("setNeedsReview"))
        )
        response = await client.update_transaction(
            transaction_id=str(update["transactionId"]),
            category_id=string_or_none(update.get("categoryId")),
            needs_review=needs_review,
        )
        results.append(
            {
                "transactionId": update["transactionId"],
                "merchantName": update.get("merchantName", ""),
                "categoryName": update.get("suggestedCategory", ""),
                "setNeedsReview": update.get("setNeedsReview"),
                "response": response,
            }
        )
    return results


async def create_monarch_client() -> Any:
    config = get_config()
    if config.monarch_cookie:
        csrf_token = config.monarch_csrf_token or csrf_from_cookie(config.monarch_cookie)
        if not csrf_token:
            raise MonarchApiUnavailableError(
                "MONARCH_COOKIE is set, but no csrftoken cookie or MONARCH_CSRF_TOKEN was found."
            )
        return BrowserCookieMonarchClient(
            api_url=config.monarch_api_url,
            cookie=config.monarch_cookie,
            csrf_token=csrf_token,
            device_uuid=config.monarch_device_uuid,
            monarch_client=config.monarch_client,
            monarch_client_version=config.monarch_client_version,
            user_agent=config.monarch_user_agent,
        )

    try:
        from monarchmoney import MonarchMoney
    except ImportError as error:
        raise MonarchApiUnavailableError(
            "Install API support with `uv sync --extra api --extra dev`."
        ) from error

    session_file = resolve_session_file(config.monarch_session_file)
    session_token = (
        config.monarch_session_token
        or read_session_token(config.monarch_session_file)
        or read_session_token(str(root_dir() / ".monarch-home" / ".mm" / "session.json"))
    )

    if session_token:
        return MonarchMoney(session_file=str(session_file), token=session_token)

    client = MonarchMoney(session_file=str(session_file))
    await client.login(
        email=config.monarch_email,
        password=config.monarch_password,
        use_saved_session=True,
        save_session=True,
        mfa_secret_key=config.monarch_mfa_secret,
    )
    return client


async def fetch_all_transactions(client: Any) -> list[JsonObject]:
    config = get_config()
    all_transactions: list[JsonObject] = []
    offset = 0

    for _page in range(config.monarch_max_pages):
        response = await client.get_transactions(
            limit=config.monarch_page_size,
            offset=offset,
            start_date=config.monarch_start_date,
            end_date=iso_date(),
        )
        page_items = extract_collection(response, ["allTransactions.results"])
        if not page_items:
            break
        all_transactions.extend(page_items)
        if len(page_items) < config.monarch_page_size:
            break
        offset += len(page_items)

    return all_transactions


def resolve_session_file(configured_path: str | None) -> Path:
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    return root_dir() / ".monarch-home" / "monarchmoney-session.pickle"


def read_session_token(configured_path: str | None) -> str | None:
    if not configured_path:
        return None
    path = Path(configured_path).expanduser().resolve()
    if path.suffix.lower() != ".json" or not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    token = data.get("token") if isinstance(data, dict) else None
    return token if isinstance(token, str) and token else None


def extract_collection(value: object, paths: list[str]) -> list[JsonObject]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not isinstance(value, dict):
        return []

    for path in paths:
        candidate: object = value
        for part in path.split("."):
            candidate = candidate.get(part) if isinstance(candidate, dict) else None
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
    return []


def string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def clean_cookie_header(value: str) -> str:
    cookie = value.strip()
    if cookie.startswith("-b "):
        cookie = cookie[3:].strip()
    if cookie.startswith("cookie:"):
        cookie = cookie.split(":", 1)[1].strip()
    return cookie.strip("'\"")


def csrf_from_cookie(cookie: str) -> str | None:
    for chunk in clean_cookie_header(cookie).split(";"):
        name, separator, value = chunk.strip().partition("=")
        if separator and name == "csrftoken" and value:
            return unquote(value)
    return None


def iso_datetime() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
