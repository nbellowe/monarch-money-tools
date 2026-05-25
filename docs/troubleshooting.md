# Troubleshooting

## `monarch run` says no CSV or pulled data was found

Use one of these paths:

```bash
monarch pull
monarch run
```

or:

```bash
monarch run ~/Downloads/monarch_transactions.csv
```

`monarch run` can reuse an existing `data/normalized/latest/bundle.json`, but it cannot create
one unless you pull from Monarch or pass a CSV.

## `monarch doctor` says private paths are not ignored

Add these entries to the workspace `.gitignore`:

```gitignore
data/
reports/
backups/
.env
.monarch-home/
exported/
private/
/profile.yaml
*.session
*.pickle
```

## Taxonomy cleanup cannot find the taxonomy

Packaged installs include a default taxonomy. If you want to customize it, run:

```bash
monarch init
```

and allow the wizard to copy `taxonomy/canonical-taxonomy.yaml` into the current workspace.

## API login is rate-limited

Wait before retrying. Prefer session or browser-cookie auth so the CLI can reuse an existing
login instead of repeatedly submitting a password.

## A plan has too many updates

Use limits and filters before applying:

```bash
monarch review apply --dry-run --limit 25
monarch cleanup apply --dry-run --source taxonomy_migration
monarch rules apply --dry-run --rule RULE_ID
```

Then apply only after the dry run matches what you expected.
