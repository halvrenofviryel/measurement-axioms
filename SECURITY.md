# Security policy

The Measurement Axioms are a doctrine plus a verdict grammar and a small reference implementation
(`spec/v1.0/conformance/verdict.py`, `degenerate.py`) with frozen, checksummed artefacts. Their
value rests on one property: a non-measurement must never derive to a positive verdict, and the
frozen artefacts must be exactly what they claim. If you find a way to break either, please report
it **privately**.

## Report privately

Use GitHub's private vulnerability reporting — the **Report a vulnerability** button under this
repository's **Security** tab — not a public issue. If that is unavailable, email
**founder@phionyx.ai** with `[SECURITY] measurement-axioms` in the subject.

## In scope

- A **verdict-derivation defect**: an input the reference implementation maps to `PASS` / success
  when the axioms require `FAIL`, `NOT_MEASURED`, `INCONCLUSIVE`, or `ERROR` (e.g. an unmeasured,
  errored, or inapplicable result collapsing into a positive verdict).
- A **frozen-artefact / checksum bypass**: a modified spec or reference artefact that still passes
  `CHECKSUMS.sha256`, or a mismatch between the published DOI artefact and the repository.
- A totality defect in the reference implementation that turns a malformed input into a crash or an
  incorrect verdict instead of a determinate outcome.

## Out of scope (by design, disclosed — not vulnerabilities)

- The honest status of the work itself: `audit/STATUS.md` records
  `independent_reproducibility: NOT_MEASURED` and `independent_review: NOT_REQUESTED`. Those are
  disclosed, tracked states, not defects.
- The licence note that the CC-BY grant conveys **no right to describe an implementation as
  conformant** — that is a deliberate scope boundary, not a bug.
- The truth of any external system's claims: the axioms govern verdict *honesty*, not whether a
  measured system is otherwise correct.

Thank you for helping keep the verdicts honest.
