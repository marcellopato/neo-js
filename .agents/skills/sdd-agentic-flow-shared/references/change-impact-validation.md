# Change-impact validation

Select validation from the behavior at risk, not from diff size or a fixed test
ladder. This reference is shared by `saf-check-task` and `saf-validate`.

## Inputs

Derive validation obligations from all of these signals:

- specification requirements and unchanged-behavior commitments;
- current diff and affected contractual seams;
- repository contracts, architecture, and configured gates;
- work intent, feature profile, and behavioral risk.

The specification remains the oracle. The diff is an impact signal, never the
oracle by itself.

## Validation obligations

Before running sensors, identify each obligation as:

```text
requirement → impacted seam → behavior/risk → adequate evidence
```

Choose the smallest sensor set that can falsify the behavior and relevant
failure modes. Minimize redundancy, never behavioral coverage.

Typical seams guide selection without becoming extension-based rules:

| Impacted seam | Minimum adequate evidence candidate |
| --- | --- |
| Local pure behavior | Focused unit or property sensor |
| Public module contract | Contract sensor plus focused behavior sensor |
| HTTP/API boundary | Endpoint or integration sensor, including negative cases |
| Persistence/query/transaction | Database-backed integration sensor |
| Schema or migration | Migration/schema/data compatibility sensor |
| Messaging/event boundary | Message-contract and consumer/producer integration sensor |
| Authorization/security boundary | Positive and negative boundary cases |
| Configuration/startup | Configuration startup or smoke sensor |
| CLI/package artifact | CLI journey or package dry-run |
| Cross-component workflow | End-to-end sensor when lower seams cannot cover the risk |

An omitted higher-level sensor is valid only when the report names it and gives
a seam- and requirement-based reason. A mock-only or static-only check is not
adequate evidence for an affected external boundary unless it can actually
falsify the required behavior.

## Scope

`saf-check-task` applies this model to one task and its current diff.
`saf-validate` re-applies it to the integrated feature, accumulated changes,
and unchanged acceptance criteria. Neither trusts implementation narrative or
prior results as current proof.
