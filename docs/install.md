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

The CLI supports several auth modes for API write-back. Browser cookie or saved-session auth is
recommended because it avoids storing your Monarch password locally.

### Browser Cookie Auth

After logging in to [monarchmoney.com](https://monarchmoney.com):

1. Open DevTools -> **Application** -> **Cookies**
2. Copy the full cookie header for Monarch
3. Put it in `.env`:

```bash
MONARCH_COOKIE="session_id=...; csrftoken=..."
```

If the cookie does not contain `csrftoken`, also set:

```bash
MONARCH_CSRF_TOKEN="..."
```

### Session Token Auth

```bash
MONARCH_SESSION_TOKEN="..."
```

### Password Fallback

Password auth is available, but it is not the preferred default:

```bash
MONARCH_EMAIL="you@example.com"
MONARCH_PASSWORD="..."
MONARCH_MFA_SECRET="..."  # optional
```

`monarch init` can help populate `.env`. The file is local-only and should remain gitignored.

---

## Verify Setup

```bash
monarch doctor
```

This checks for required config files and artifacts. All checks should pass before running
write-back commands. Data artifact checks will show as missing until you run `monarch pull` or
`monarch run <csv>`.
