# Phionyx self-audit against The Measurement Axioms

**Audit date:** 1 August 2026
**Subject:** the Phionyx governance runtime and its published assurance artefacts
**Method:** source reading against the axioms, properties and principles of
[The Measurement Axioms](./THE_MEASUREMENT_AXIOMS.md)

```yaml
doctrine_title:              The Measurement Axioms
doctrine_edition:            Baseline edition
doctrine_version:            "1.0.0"
doctrine_date:               2026-08-01
specification:               Governance Verdict Validity v1.0

claim_status:                SUPPORTED_NARRATIVE
independent_reproducibility: NOT_MEASURED
independent_review:          NOT_REQUESTED
```

> **What this report is.** A source reading, published so the reading can be
> checked. It is not an evidence bundle: no commit is pinned, no line ranges are
> given, no reproduction command is published, and no per-finding record is
> machine-readable. Under M1.1 the honest label for its reproducibility is
> `NOT_MEASURED` — not `PASS`, and not `FAIL`.
>
> The bundle would make these findings independently *reproducible*. A named
> independent review would still be required before the status could become
> `independently_assessed`. Neither exists yet.

---
## Findings

**Eleven instances, in which a component or an assurance artefact represented a
non-measurement as a positive or completed result**, in two families.

**Absence read as confirmation** — five:

- A chain-integrity verifier returns `valid` for an empty chain. Three packages
  carry passing tests that enshrine this; a fourth implementation does the same,
  untested.
- The same verifier takes an optional signature-checker. Called without one — as
  every caller in the published package does but one — **a record whose signature
  has been tampered with returns `valid`**. A passing test asserts this as
  documented default behaviour.
- A declaration-coverage metric computed against a repository the process could not
  read returns a fabricated constant: `1.0` when nothing was declared, `0.5`
  otherwise. Neither was measured; the denominator was empty.
- A descriptor-verification step receives `None` — never measured — coerces it to
  `False`, and records the disposition `admit` together with the reason
  **"descriptor hash matches user-approved baseline"**. No baseline was compared.
  That sentence is then hash-chained and signed into the evidence record.
- A commit gate whose telemetry file is missing does not fire at all, and its
  silence is indistinguishable from approval.

**Proxy read as the thing** — six:

- A content digest is present, therefore the material is marked **resolvable** —
  fetchable and checkable by a verifier. Our own specification names the exact
  counter-case ("the material is redacted but its `content_hash` is still
  recorded") as one that must be marked unresolvable.
- A gate escalates to *attenuate* while attaching no attenuation parameters, and no
  downstream consumer recognises the verdict. Structurally, not incidentally: the
  parameters are populated only for a different verdict.
- A record carries a `signature` field whose algorithm reads `"unsigned"`.
- A pipeline stage named for auditing returns a status object and writes no record
  — including on the exception path, where it still returns `ok`.
- Our own reference exporter violates **four** MUST requirements of the
  specification we authored, on its default code path.
- A published compliance mapping rates one control **Full** on the strength of four
  cited evidence artefacts. **No commit in either of the two repositories that
  could hold them has ever added a file matching any of the four**, and the
  mechanism claims were already false at the last commit before the date the
  mapping states it was verified.

The last is the doctrine in miniature, and it is why R1 exists:

> *"A verifier MUST NOT treat an entry with `resolvable: false` as verified
> evidence. This prevents an unverifiable pointer from being counted as proof."*
> — AIREP v0.1 §4

**We wrote that rule, then broke it in prose, in a public document.** Nobody
resolved the pointers. The presence of an evidence block was read as the presence
of evidence.

### What the properties found

Applied as a dead-branch detector over the same execution graph, P1–P5 surface a
further class of defect that no test suite was positioned to see:

- A safety component reads a key under a name **no producer writes**. Three
  consumers read it; none writes it. The nearest producer sits twenty-two positions
  later in the declared order, so a matching name would still be read before it was
  written. *(P3, P2)*
- A conflict score is computed and reaches no branch. *(P5)*
- A second key has two readers and zero writers anywhere in the codebase. *(P3)*
- A write-conflict detector reads a schema field present on zero entries and reports
  "no conflict" for every pair, while the concurrency it guards is on by default.
  *(P4)*


### Appendix — where each finding can be checked

Ten of the eleven sit in artefacts anyone can obtain. Versions verified
1 August 2026.

| Finding | Where |
|---|---|
| Empty chain returns `valid` | `phionyx-mcp-server` **0.2.0** on PyPI — and two further packages carry the same behaviour |
| Verifier-less call passes a tampered signature | `phionyx-mcp-server` 0.2.0, including its own test asserting it |
| `resolvable` derived from a digest | `phionyx-mcp-server` 0.2.0 |
| `signature.alg == "unsigned"` | `phionyx-mcp-server` 0.2.0 |
| Exporter violates four spec MUSTs | `phionyx-mcp-server` 0.2.0 against the published AIREP v0.1 specification |
| Unmeasured descriptor admitted with a positive reason | `phionyx-mcp-server` 0.2.0 |
| Fabricated coverage constant | development harness, in the public research mirror |
| Commit gate silent without telemetry | development harness, in the public research mirror |
| Attenuation verdict with no parameters, ignored by consumers | development harness, in the public research mirror |
| Compliance mapping rating a control Full on citations that resolve to nothing | public research mirror |

**One is not externally checkable.** The audit-named stage that writes no record:
the pipeline block is in `phionyx-core` **0.9.0**, but the wiring that makes it a
no-op lives in a bridge layer that is not published. That finding rests on our
authority and an external reader cannot confirm or refute it. It is marked rather
than allowed to pass as verified.

**What the bundle will add**, and what its absence currently costs: commit pins, a
source snapshot digest, file and line ranges per finding, the reproduction command
for each, the static-analysis queries used, and one machine-readable record per
finding carrying `expected: NOT_MEASURED` against `observed: PASS`. Until it
exists, §VII is a reading, not a measurement, and it says so.

---

## Addendum — the twelfth, and it is in the doctrine's own tooling

Found by external review on the day of writing, in the reference implementation
published alongside the doctrine.

**The first conformance probe for the Measurement Axioms returned a positive
result when it had measured nothing.** `ProbeReport.conformant` was a boolean
computed over observations, and an unexercised case counted as conformant — so a
run that exercised zero cases reported success while its own summary printed
`NOTHING WAS EXERCISED`.

That is M1.1 exactly, produced by the artefact written to detect it.

Four more in the same two modules:

| | |
|---|---|
| A target that raised was recorded as a pass | a crash is not a conformance result |
| The probe did not recognise its own companion type's `PASS` | the two reference modules did not understand each other |
| A bare `False` was treated as conformant | it may mean `FAIL`, which is a different claim; guessing is not permitted |
| `Verdict` was truthy, so `if measurement.verdict:` still collapsed | `Measurement.__bool__` raised; the enum did not. The type enforced half of what it claimed |

And one defect in the specification itself, which the probe made visible: **MA-6.1
as written condemned the correct behaviour.** A component that answers
`NOT_MEASURED` to every degenerate input is invariant over that class — and the
requirement read invariance as proof of non-measurement. Selectivity needs a
*control* input paired with the degenerate one; only the pair separates a
component that refuses to guess from one that never looked.

**All six are corrected**, with a regression test for each, and the corrected
probe now reports a `Verdict` rather than a boolean: zero coverage yields
`NOT_MEASURED`, a crash yields `ERROR`, an uninterpretable return yields
`INCONCLUSIVE`.

Two things worth stating plainly. **None of this was caught by us** — it came from
an independent reader of the same source, which is R2 with a date on it. And while
fixing it, the newly added `Verdict.__bool__` guard raised on a line *inside the
probe*, where the correction itself had been written as
`x.value if x else "?"` — the guard catching its own author committing the
collapse it forbids.

---

## Remediation

Tracked in an internal remediation plan, which is **not published**: it carries
the authors' own migration record and release sequencing, neither of which is
part of this doctrine. Each finding carries a `work_status` and a
`verification_status` there.

That the tracker is unpublished is itself a limit on this report, and is named
rather than papered over with a link a reader cannot follow — this report's own
finding #11 is a compliance mapping rating a control on citations that resolved
to nothing. A dead pointer here would repeat it.

### Status note — 2 August 2026

The sentence this section carried on 1 August — *"No finding in this report is
closed"* — was true when written and is no longer precise. Work continued the
next day, and a report whose value rests on its statements being true does not
get to leave one standing past its date.

What is accurate as of 2 August: **no finding has `verification_status: pass`.**
Some have moved, and the movement is smaller than a reader might assume from a
list of commits, so it is stated at the resolution it actually happened at:

| Finding | What changed | What did **not** |
|---|---|---|
| **#9** — audit-named stage writes no record | Its exception path no longer returns a bare `ok`; it now carries `block_run_status: FAILED`, an `ERROR` measurement and `operating_mode: degraded`, and a test asserts the module still contains no signing so the four public mappings cannot silently re-acquire the claim | **The finding stands.** The remediation was "write a record or stop naming it for auditing", and neither has been done. The block still writes no `AuditRecord`, no hash chain and no signature |
| **#4** — unmeasured descriptor admitted with a positive reason | The `None` path now returns `non_measurement_cause: input_absent` and no longer reaches the admitting branch. The sentence *"descriptor hash matches user-approved baseline"* survives only where a comparison actually ran | Verification is a source reading, as everywhere else in this report |
| **§2 dataflow** — a safety component reading a key no producer writes | Three producer→consumer key mismatches were repaired, so the revision gate's confidence, arbitration and drift rules can now fire | The conflict-score wiring is **not** done: the metric's current formula rates agreement and disagreement in a way that would make module *agreement* rewrite responses, and changing it touches claim references. It is a founder decision, recorded as one |

A separate class of finding was produced by the same reading and is **not** in the
eleven, because it was found after this report was written: the runtime's own
canonical pipeline was audited block by block, and fabricated values were found on
paths that report success — a midpoint published as a measurement from a crash,
and seeded into the next turn as the previous turn's result. That work is partly
done and partly open. It belongs in the next edition of this report rather than
being folded into this one, because this report is anchored to 1 August and
retro-fitting it would defeat the point of dating it.
