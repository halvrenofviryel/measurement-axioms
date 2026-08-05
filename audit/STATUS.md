# Audit bundle status

This file describes the **status of the evidence bundle**, not the findings.
It exists so that a reader arriving at the audit report knows what it is before
reading it, and so that a link from a website points at a status rather than at
an implication.

```yaml
report:                        PHIONYX_MEASUREMENT_AXIOMS_SELF_AUDIT_2026-08-01.md
report_date:                   2026-08-01
status_notes_added:            [2026-08-02, 2026-08-05]
bundle_status:                 NOT_AVAILABLE
claim_status:                  SUPPORTED_NARRATIVE
independent_reproducibility:   NOT_MEASURED
independent_review:            NOT_REQUESTED
findings_with_verification_pass: 0
```

## What the report is

A source reading, published so the reading can be checked.

## What it is not

An evidence bundle. No commit is pinned, no line ranges are given, no
reproduction command is published, and no per-finding record is
machine-readable.

Under **M1.1** the honest label for its reproducibility is `NOT_MEASURED` — not
`PASS`, because nothing was reproduced, and not `FAIL`, because nothing was
tried and failed. Recording it as either would be the error the doctrine names.

## What the bundle would add

Commit pins · a source snapshot digest · file and line ranges per finding · the
reproduction command for each · the static-analysis queries used · one
machine-readable record per finding carrying `expected: NOT_MEASURED` against
`observed: PASS`.

Until it exists, the audit section of the doctrine is a reading rather than a
measurement, and it says so in the document itself.

## Independent review

Not requested. A named independent review would be required before the status
could become `independently_assessed`. Note that this is a separate condition
from reproducibility: a bundle makes findings checkable; it does not make them
checked.

One finding **was** contributed by an independent reader, on the day of
writing, in the doctrine's own conformance probe. That is one reader on one
artefact, and it is not an independent review of the report.
