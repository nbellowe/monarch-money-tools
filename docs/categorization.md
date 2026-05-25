# Categorization Cleanup

Categorization work usually moves through three layers: review existing Needs-Review
transactions, clean up historical taxonomy drift, then create rules for repeated patterns.

## Needs-Review Flow

```mermaid
flowchart TD
  A["Needs-Review transactions"] --> B["monarch review plan"]
  B --> C["data/review/latest/review-plan.md"]
  C --> D{"Plan looks right?"}
  D -->|No| E["Rerun with different threshold or inspect deferred rows"]
  E --> B
  D -->|Yes| F["monarch review apply --dry-run"]
  F --> G{"Dry run matches plan?"}
  G -->|No| E
  G -->|Yes| H["monarch review apply --yes"]
```

The plan uses reviewed merchant history to propose category changes and review clears. Pending
transactions are skipped unless you opt in.

```bash
monarch review plan
open reports/latest/review-plan.md
monarch review apply --dry-run
monarch review apply --yes
```

## Trusted Clear-Review Flow

Use this when categories are already trusted and the only action is clearing the Needs-Review
flag.

```bash
monarch review clear-plan
open reports/latest/clear-review-plan.md
monarch review clear-apply --dry-run
monarch review clear-apply --yes
```

## Taxonomy Cleanup Flow

```mermaid
flowchart TD
  A["Canonical taxonomy"] --> B["monarch cleanup plan"]
  C["Merchant history"] --> B
  B --> D["cleanup-plan.md and cleanup-blocked.csv"]
  D --> E{"Manual review needed?"}
  E -->|Yes| F["monarch cleanup review"]
  E -->|No| G["monarch cleanup apply --dry-run"]
  F --> G
  G --> H{"Safe?"}
  H -->|Yes| I["monarch cleanup apply --yes"]
  H -->|No| B
```

`cleanup plan` combines deterministic taxonomy migrations with merchant-history consistency
candidates. Blocked rows usually mean the category does not exist in Monarch yet.

## Rule Creation Flow

```mermaid
flowchart TD
  A["Analyzed transaction history"] --> B["monarch rules suggest"]
  B --> C["rule-suggestions.md"]
  C --> D{"What action?"}
  D -->|Apply local suggestion to matching transactions| E["monarch rules apply --dry-run"]
  E --> F["monarch rules apply --rule RULE_ID --yes"]
  D -->|Create live Monarch rule| G["monarch rules push RULE_ID"]
  G --> H["Rule exists in Monarch for future transactions"]
```

`rules apply` updates transactions that match enabled local suggestions. `rules push` creates a
live Monarch rule but does not apply it to existing transactions unless Monarch changes that API
behavior.

## LLM Review Flow

```mermaid
flowchart TD
  A["Ambiguous Needs-Review rows"] --> B["monarch review llm --dry-run"]
  B --> C{"Scope acceptable?"}
  C -->|No| D["Change focus categories or skip P2P settings"]
  D --> B
  C -->|Yes| E["monarch review llm"]
  E --> F["llm-review-plan.md"]
  F --> G["monarch review llm-apply --dry-run"]
  G --> H["monarch review llm-apply --yes"]
```

LLM review can send merchant names, account names, date ranges, amount ranges, and category
names to the selected LLM backend. See [Privacy & Security](privacy-security.md) before using it.
