# Installation

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended package manager)
- A Monarch Money account

---

## Install

```bash
uv tool install .
```

This installs the `monarch` command globally via uv's tool environment.

For a development install (editable, with all optional dependencies):

```bash
uv sync --extra dev --extra api --extra llm
```

---

## Auth Setup

The CLI uses browser cookie auth by default. After logging in to [monarchmoney.com](https://monarchmoney.com):

1. Open DevTools → **Application** → **Cookies**
2. Copy the session cookie value for `monarchmoney.com`
3. Either:
    - Set `MONARCH_SESSION_TOKEN=<value>` in a `.env` file at your working directory, **or**
    - Let the `monarchmoney` library auto-detect your browser session

Alternatively, run `monarch pull` and follow the interactive login prompt on first use.

---

## Verify Setup

```bash
monarch doctor
```

This checks for required config files and artifacts. All checks should pass before running
other commands.
