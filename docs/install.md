# Installation

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended package manager)
- A Monarch Money account

---

## Install

```bash
uv tool install monarch-money-tools
```

This installs the `monarch` command globally via uv's tool environment.

For a development install from a cloned repo:

```bash
git clone https://github.com/nbellowe/monarch-money-tools.git
cd monarch-money-tools
uv sync --extra dev --extra api --extra llm --extra docs
```

---

## Setup Wizard

```bash
monarch init
```

The wizard helps populate `.env`, tests the Monarch connection, checks taxonomy alignment,
creates a starter `profile.yaml` if needed, and runs `monarch doctor`.

---

## Auth Setup

The CLI uses browser cookie auth by default. After logging in to [monarchmoney.com](https://monarchmoney.com):

1. Open DevTools → **Application** → **Cookies**
2. Copy the session cookie value for `monarchmoney.com`
3. Either:
    - Set `MONARCH_SESSION_TOKEN=<value>` in a `.env` file at your working directory, **or**
    - Let the `monarchmoney` library auto-detect your browser session

Alternatively, set `MONARCH_EMAIL`, `MONARCH_PASSWORD`, and optionally
`MONARCH_MFA_SECRET` in `.env`, then run `monarch pull`.

---

## Verify Setup

```bash
monarch doctor
```

This checks for required config files and artifacts. All checks should pass before running
other commands.
