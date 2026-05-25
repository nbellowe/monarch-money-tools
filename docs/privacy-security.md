# Privacy & Security

monarch-money-tools is local-first, but some commands intentionally talk to external services.
Know which boundary each workflow crosses before running it.

## Local Files

The CLI writes generated data and reports under your current working directory:

| Path | Contents |
| --- | --- |
| `data/` | Raw API pulls, normalized bundles, plans, apply results |
| `reports/` | Human-readable Markdown and CSV reports |
| `.env` | Optional local credentials/session settings |
| `.monarch-home/` | Saved unofficial API session files |
| `profile.yaml` | Retirement simulator inputs |

These paths are gitignored by default. `monarch doctor` checks that the important private paths
are ignored in the current workspace.

## Auth Modes

Preferred:

- `MONARCH_COOKIE` with `MONARCH_CSRF_TOKEN` when needed
- `MONARCH_SESSION_TOKEN`
- `MONARCH_SESSION_FILE`

Fallback:

- `MONARCH_EMAIL`
- `MONARCH_PASSWORD`
- `MONARCH_MFA_SECRET`

Password fallback is supported for convenience, but browser-cookie or session auth usually
reduces local credential exposure. `monarch init` writes `.env` with owner-only permissions when
it creates or appends credentials.

## API Write-Back

These commands can modify Monarch data:

- `monarch review apply`
- `monarch review clear-apply`
- `monarch review llm-apply`
- `monarch cleanup apply`
- `monarch rules apply`
- `monarch rules push`
- `monarch rules delete`

Run the corresponding plan command first and use `--dry-run` before `--yes`.

## LLM Review

`monarch review llm` can send transaction context to Claude through either the local `claude`
CLI or the Anthropic API backend. The prompt can include:

- Merchant display names
- Normalized merchant keys
- Account names
- Date ranges
- Amount ranges
- Current categories
- Canonical category names

It does not send raw full transaction notes by default. Use `monarch review llm --dry-run` to
inspect the size of the batch before sending anything.

## Unofficial API Notice

Monarch's GraphQL API is unofficial and can change without notice. Keep plans reviewable and
avoid relying on unattended bulk write-back.
