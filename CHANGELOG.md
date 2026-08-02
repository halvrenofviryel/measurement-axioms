# Changelog — The Measurement Axioms

All notable changes to the doctrine, the specification and the bundled
artefacts. Versions follow the doctrine, not the repository.

## [1.0.0] — 2026-08-02

Baseline edition. First public release.

### The doctrine

- Seven axioms (M1–M7), five properties of a governance measurement path
  (P1–P5), decision/time/remedy (D1–D3), reflexive assurance (R1–R2) and two
  boundaries.
- The verdict algebra: six values — PASS, FAIL, NOT_MEASURED, INCONCLUSIVE,
  ERROR, NOT_APPLICABLE — with two collapse prohibitions. An absent measurement
  and a proxy for one are both non-measurements, and neither may be reported as
  a result.

### The specification

- `MEASUREMENT_AXIOMS_SPECIFICATION.md` — the normative extract. The doctrine
  is the argument; this is what a committee can adopt.
- `conformance-requirements.yaml` — numbered requirements an assessor can
  apply and an implementer can fail.
- `verdict-outcome.schema.json` — the record schema, machine-readable.
- `conformance/verdict.py` and `conformance/degenerate.py` — reference
  implementation and the paired-control selectivity probe.
- `CHECKSUMS.sha256` over the five frozen artefacts. A frozen version that
  cannot be checked is a claim about itself.

### The self-audit

- `PHIONYX_MEASUREMENT_AXIOMS_SELF_AUDIT_2026-08-01.md` applies the doctrine
  to its authors' own runtime: eleven findings plus one found by an independent
  reader **in the doctrine's own conformance probe**, which reported a positive
  result having measured nothing. No finding carries
  `verification_status: pass`.
- Status note added 2026-08-02 recording what moved since, and — more usefully —
  what did not.

### Known and stated

- `claim_status: SUPPORTED_NARRATIVE`. The self-audit is a source reading, not
  an evidence bundle: no commit pins, no line ranges, no reproduction commands,
  no per-finding machine-readable record. Under M1.1 its reproducibility is
  `NOT_MEASURED` — not PASS, and not FAIL.
- `independent_review: NOT_REQUESTED`.
- No prevalence claim is made. Establishing that this failure class is common
  would require systems other than ours.
- Conformance test suite: 319 tests at commit 3fd2f6ac.
