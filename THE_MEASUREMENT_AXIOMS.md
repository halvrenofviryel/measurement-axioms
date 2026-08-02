# The Measurement Axioms

### A doctrine for AI systems that must produce evidence, not assurances

**Ali Toygar Abak** · ORCID [0009-0002-3718-4010](https://orcid.org/0009-0002-3718-4010)
**Phionyx** · 1 August 2026 · Baseline edition

---

## I. The position

AI governance today is overwhelmingly **content evaluation**: is this output
harmful, false, biased, misaligned? That work is necessary and this document does
not compete with it.

It sits on top of an unexamined assumption. Every content evaluation produces a
**verdict**, and the verdict is treated as a fact about the output. It is not. It
is a *measurement* — an act performed by a component that may or may not have
executed, may or may not have had anything to look at, and may or may not be able
to demonstrate afterwards which of those was the case.

> **The question this doctrine exists to make askable:
> when your evaluator returned `safe`, did it look at anything — and can you prove
> it?**

An organisation can hold a complete set of policies, a mature risk register, a
model card for every deployment, and a governance layer that returns `pass` on
every turn *without ever having measured anything*.

**Bounded claim.** Within the frameworks and literature we have actually read —
listed in *Related work*, chiefly NIST AI RMF 1.0's MEASURE function and the
runtime-verification, vacuity-detection, fail-safe-default and attestation
literature — we found requirements to *document* what cannot be measured and to
assess control effectiveness, **but no rule prohibiting a governance component
from emitting `PASS` or `VALID` when the claimed measurement did not execute.**
We have not reviewed the ISO/IEC 42001 family, IEEE 7009's normative text, the
EU AI Act's harmonised standards, or the 2026 OWASP agentic guidance. Under
**Boundary 4** this is a statement about our search, not about the field, and it
is offered to be falsified.

This document states the axioms under which a governance runtime produces evidence
rather than assurance, the properties that distinguish the two, and the checks by
which the distinction is decided.

**It is a design discipline, not an ethics framework.** Its claims are engineering
claims and are meant to be falsified.

---

## II. The seven axioms

### M1 — Output is measurement, not truth

> No measurement → no trust → no state update.

A model's output is a sensor reading. So is an agent's report that it acted. So —
and this is where the axiom does work that is not being done elsewhere — **is a
governance gate's own verdict**. A verifier that checked nothing and returned
`valid` is a sensor with its wire cut, reporting zero and being believed.

Three levels of judgement, and they are not interchangeable:

| | Level | The object judged |
|---|---|---|
| **L1** | Model output | one generation |
| **L2** | Agent action | a decision with effects |
| **L3** | Governance verdict | a claim *about* L1 or L2 |

Most safety work operates at L1, increasingly at L2. **L3 is where a governance
system either earns its name or does not**, and it is the level this doctrine is
about.

#### M1.1 — Absence and proxy are both non-measurements

M1 states the consequence of *no measurement* and never defines what counts as
one. Two families slip through.

**Absence read as confirmation.** A verifier with nothing to check returns the
passing value. An empty set verifies vacuously. A missing baseline reports no
change. An unreadable input yields a fabricated denominator. A monitor whose
telemetry is absent does not fire, and its silence is indistinguishable from
approval.

**Proxy read as the thing.** A content digest is present, so the material is
marked fetchable. A verdict label is emitted, so attenuation is assumed to have
occurred. A field named `signature` is populated with the string `unsigned`. A
component named for auditing is assumed to produce an audit record. A citation is
present, so evidence is assumed to exist behind it.

> **M1.1.** The absence of a check, and a proxy for a check, are both
> non-measurements. A verifier that checked nothing MUST NOT report valid. A
> signal merely *correlated* with verification — a digest, a label, a declared
> directive, a name in an architecture, a citation nobody resolved — MUST NOT be
> recorded as verification. **The honest result for non-execution must be a
> distinct value, never the passing one.**

The third value is not an invention of this doctrine: three-valued runtime
verification has carried `inconclusive` for two decades (§*Related work*). But
`inconclusive` is not the value most of these failures need, and collapsing the
two is itself an M1.1 error:

- **`INCONCLUSIVE`** — the check ran; the evidence it obtained was insufficient to
  decide.
- **`NOT_MEASURED`** — the check did not run, or could not reach what it was
  supposed to examine.

Every one of the eleven findings in the linked self-audit belongs to the second
category. A verdict type offering only the first has nowhere honest to put them.

#### The verdict algebra

The operational product of M1.1 is a verdict type the caller cannot collapse:

| Verdict | Meaning |
|---|---|
| `PASS` | the check ran and its success criterion was met |
| `FAIL` | the check ran and its success criterion was not met |
| `NOT_MEASURED` | the check did not run, or its required input was unobtainable |
| `INCONCLUSIVE` | the check ran; the evidence did not decide |
| `ERROR` | the check could not complete for a technical reason |
| `NOT_APPLICABLE` | out of scope by a documented decision |

Two rules make the type load-bearing rather than decorative:

> A caller MUST handle `NOT_MEASURED`, `INCONCLUSIVE` and `ERROR` distinctly from
> `PASS`. An aggregate that maps any of them to `PASS` — by default, by
> truthiness, by `or False`, or by omission from a summary — has re-created the
> defect the type exists to prevent.

> `NOT_APPLICABLE` MUST carry the scope decision that justifies it. Without one it
> is `NOT_MEASURED` wearing a better name.

The contribution is not the third value. It is the separation above, plus the
observation that the passing value is used where `NOT_MEASURED` belongs:
**§VII reports eleven instances of this in one governance runtime — ours.** Whether
it is a systematic property of the class is not something eleven findings in one
system can establish, and we do not claim it.

### M2 — The deciding layer must not be the measured layer

An independently checkable control layer overrules probabilistic generation. If
the constraint rejects the output, the output changes. *(In Phionyx that layer is
symbolic and deterministic; the axiom requires independent checkability, not any
particular implementation.)*

**A language model judging a language model is a sensor — not, by itself, an
independently checkable governance layer.** It may supply measurement evidence,
often good evidence. What it cannot be alone is the authority, because it shares a
failure family with what it judges.

> A probabilistic evaluator MAY provide measurement evidence, but MUST NOT be the
> sole authority for an irreversible state transition unless its verdict is
> independently constrained, attributable and replayable.

A system whose only oversight is another model has two measurements and a hope
that they fail independently.

And the corollary that binds the author as much as anyone: **if the deciding layer
is not itself checkable, trust has been relocated, not reduced.**

### M3 — Order is the invariant

`build context → generate → validate → if allowed, commit.`

The load-bearing word is *order*. Possessing the steps is not running them in
sequence, and **the distance between an architecture diagram and a runtime is
exactly this axiom**. "We have a safety check" and "the safety check runs before
the action, every time, and the record proves it" are different claims. The second
is rarely made because it is rarely checkable; making it checkable is the work.

A declared order that no assertion enforces is documentation. An order followed by
a sequential loop is a convention. Only an order asserted against an **observed
execution trace** is an invariant.

### M4 — Evaluation is unconditional

> Every governance-relevant decision and every state-changing action MUST be
> accompanied by a recorded `measurement_status` drawn from the algebra in M1.1.
> The decision outcome and the execution status MUST be recorded separately —
> an action does not itself produce `PASS` or `NOT_MEASURED`; its evaluation does.

The point is not that every interaction is scored — many change no state, call no
tool and decide nothing. The point is that **the set of turns the evaluator never
saw must itself be recorded**, rather than being inferred from the absence of a
finding. The risk dimensions may be profile-bound. Under M6 a profile MAY add dimensions
to the applicable baseline schema but MUST NOT remove any the schema designates
mandatory. This doctrine does not fix that baseline schema; naming it belongs to a
specification, not to an axiom.

Tiered evaluation, where a cheap scorer decides whether an expensive deliberative
check runs, is a legitimate engineering choice with a property that must be stated
rather than discovered: **the component deciding whether to look closely is the
component being looked at.** Anything the cheap scorer rates low is never seen by
the layer built to catch what cheap scorers miss.

Stating that as a limitation is not sufficient. By M5, a limitation with no
mechanism attached is a warning. The mechanism that discharges it is a recorded,
replayable attestation naming the turns the deliberative layer never saw.

### M5 — A warning without damping is invalid

Forced attenuation must be real: reduce amplitude, raise the uncertainty floor,
override tone. **A warning that changes nothing is not weak governance; it is
invalid governance**, in the sense that an unsigned contract is not a weak
contract.

**The scope is enforcement, not disclosure.** A policy document, a model card or
a risk register is an *advisory control*: its job is to inform, and it discharges
that job without touching the runtime. M5 does not invalidate those.

What M5 governs is the second class:

| | |
|---|---|
| **Advisory control** | informs a human or a downstream process; valid without runtime effect |
| **Intervention control** | claims to constrain the system; valid only if it materially changes the system's output, action, state transition, authority or control flow |

> A runtime mitigation verdict that produces no material change to the system's
> output, action, state transition, authority or control flow MUST NOT be
> represented as an enforced mitigation.

The failure this catches is the reclassification: an advisory control presented,
in an audit or a compliance mapping, as though it were an intervention. A
governance finding that changes no system behaviour is a finding about the
organisation, not an intervention control on the system.

### M6 — Context changes thresholds, never rules

Deployment profiles adjust strictness. They never remove a rule.

"We relaxed the guardrails for this deployment" collapses two different acts.
Lowering a threshold is bounded and auditable: the rule still runs, the record
shows that it ran, and the profile that set the threshold is itself an artefact
someone can read. Removing a rule leaves **no trace of what is no longer being
checked**. Only the first is defensible, and the difference is invisible unless the
architecture enforces it.

### M7 — Decision evidence must be replayable

> A record supporting a claim of independently reproducible governance MUST
> contain sufficient inputs to re-derive the measurement mapping, the verdict and
> the state transition.

A record that cannot be replayed is still a record and may still be probative. It
is not *replayable decision evidence*, and a system should not describe it as
though it were.

The defensible form of this claim is not "deterministic AI" — that invites a weak
reading and is false anyway. It is:

> **Deterministic governance around probabilistic generation.**

The model may be stochastic. The draw is recorded. The same record replayed must
yield the same governance verdict. What is required is determinism *at the verdict
layer*, which is achievable precisely because that layer is code rather than a
model (M2).

**Evidence is graded, not binary.** A record without a signature is still a
record and may still be probative; what changes across the levels is what an
independent party can establish from it.

| | Level | What it supports |
|---|---|---|
| **E0** | Raw record | the producer's own account |
| **E1** | Integrity-protected | it has not been altered undetectably |
| **E2** | Key-attributable | which key signed it |
| **E3** | Identity-bound and independently verifiable | a third party can bind that key to an identity and check it without the producer |
| **E4** | Replayable attested decision | the verdict can be re-derived from the record |

**The levels are cumulative.** An E4 claim requires E0 through E3 in addition to
replayability; a record that replays but carries no attribution is not E4.

**E3 begins to support a non-repudiation claim**, subject to the applicable
identity, trust and legal context — it does not establish one by itself. And it is
not achieved by taking the key away from the producer: a producer holding its own
private key is normal and correct.
What E3 requires is: secure custody of the private key, the public key bound to a
verified identity, an independent trust anchor, a recorded rotation and
revocation history, and an unambiguous statement of what was signed and when.

**Most systems do not say which level they are at.** A claim of "signed audit
trail" spans E1 to E4 and means something different at each.

---

## III. Five properties of a governance measurement path

The axioms state what must hold. These five properties characterise the path by
which a measurement is persisted, propagated and allowed to affect a system. They
are not all evidence requirements, and which combination is mandatory depends on
the decision type.

| | Property | The question |
|---|---|---|
| **P1** | **Persistence** | Does the step write a value that outlasts it? |
| **P2** | **Delay** | Does the effect extend beyond the immediate call? |
| **P3** | **Propagation** | Does any reader receive *that exact* value? |
| **P4** | **Selectivity** | Does the output vary with the input? |
| **P5** | **Feedback** | Does the value reach a branch, or only a log line? |

They are **conservatively approximable** by static analysis rather than decidable —
exact reader- and branch-reachability are undecidable in general, so an
implementation yields sound over-approximations. That is sufficient: a governance
defect surviving a sound over-approximation is a defect worth reporting.

**P2 is not an evidence requirement.** Delay is a real property of an effect and
belongs in the set for completeness, but a measurement produced, persisted,
propagated and acted on within a single call is not weaker evidence for being
prompt. The evidence gate below draws on **P1, P3, P4, P5** plus two properties
carried by M7 — **attribution** and **replayability**. Delay, long-horizon
propagation and retroactive reinterpretation are temporal properties of the
system, treated in §IV, not conditions on a record being evidence.

### P4 is the load-bearing property, and it must be quantified correctly

A naïve selectivity pass finds almost nothing, because the components that fail
this test *do* vary with their inputs in general. They are constant only within a
**degenerate class**: the empty collection, the absent baseline, the missing file,
the unreadable source, the unset optional argument.

But invariance over that class is not itself the defect — a component that
correctly answers *not measured* to every degenerate input is invariant too, and
is behaving exactly as required.

> **The check is a control input paired with its degenerate variant.** Selectivity
> holds when the mapping distinguishes what it is required to distinguish: the
> control yields a measured result, the degenerate one yields *not measured*, and
> the degenerate one does not inherit the control's pass.

Only the pair separates a component that refuses to guess from one that never
looked.

### Why a threshold is the wrong gate

First, a distinction that is easy to lose. A **demarcation test** asks whether a
phenomenon belongs to a class — it is answering a question about something you did
not design, and a count is a reasonable instrument for it. A **conformance gate**
asks whether a particular instance is adequate — you designed this one, and you
know which property is load-bearing for it. Using a demarcation threshold as a
conformance gate is a category error, and the properties below are being put to
the second use, not the first.

The temptation is to require "at least three of five". Take a chain verifier that
returns `valid` for an empty chain:

| | | |
|---|---|---|
| P1 Persistence | no record of the verdict is written | ❌ |
| P2 Delay | no effect beyond this call | ❌ |
| P3 Propagation | the verdict reaches the caller | ✅ |
| **P4 Selectivity** | **the empty input inherited the valid control's passing outcome** | ❌ |
| P5 Feedback | the caller branches on it | ✅ |

Two of five here — but move P1 to "the verdict persists into the caller's
decision", a reading the property equally supports, and it scores three and passes.
**A count is decided by which reading you pick. The defect is not.**

Requiring all five fails in the other direction: **P2 is not always desirable.** A
verdict that correctly changes nothing downstream is a correct verdict. Requiring
all five forces every decision to mutate state in order to pass.

**Gate on named properties, chosen by decision type:**

| Decision type | Required | Conditional |
|---|---|---|
| A **measurement verdict** — gate, verifier, monitor | **P4 through paired control–degenerate tests**, **P1** | P3, when a consumer must act on it |
| An **intervention verdict** — claims to constrain the system | P4 (paired), P1, **P3, P5** | attribution and replay, per the assurance claim made |
| An **action** — tool call, state write | P1, P3 | P5, when the outcome should update a model |
| An **answer** — no side effects | P1, bounded as below | — |

**P1 is bounded by retention, not by universality.** Persisting every output
conflicts with data minimisation and with legitimate ephemeral processing. The
requirement is narrower:

> A claim represented as auditable assurance MUST persist for the retention period
> required to verify that claim.

An answer that makes no assurance claim need not be retained at all.

---

## IV. Decision, time and remedy

The axioms govern what a verdict must be. These four govern what a *record* must
contain for the decision to remain accountable afterwards.

### D1 — Reproducibility is keyed on the decision, not the clock

> *The wheel carries the decision, not the clock.*

A replay keyed on wall-clock time is irreproducible by construction: time has
moved. A replay keyed on the recorded decision inputs — state, policy version,
profile, thresholds, measurements, and the recorded time value **as one of those
inputs** — reproduces faithfully from the record itself.

This is what makes M7 achievable rather than aspirational, and it is the property
that separates an evidence record from a timestamped log.

### D2 — There is no null action

> *Every decision moves the wheel.*

Abstention is a decision. So are timeout, tool-unavailability, policy-not-loaded,
human-override, and silent failure. Each must be recorded as a distinct outcome:

These are **not one enumeration.** They are orthogonal dimensions of a single
event, and a record that collapses them into one field cannot express what
happened:

| Dimension | Values |
|---|---|
| decision outcome | `allow` · `block` · `attenuate` · `escalate` · `abstain` |
| measurement status | the verdict algebra of M1.1 |
| execution status | `completed` · `timeout` · `tool_unavailable` · `policy_unavailable` · `failed` |
| authority | `autonomous` · `human_confirmed` · `human_overridden` |
| observation | `recorded` · `detected_after_execution` · `previously_silent_failure` |

A single event can carry `decision: block`, `measurement: inconclusive`,
`execution: completed` and `authority: human_overridden` at once.

Most logging systems today cannot distinguish **"no record exists"** from **"the
system deliberately declined"**. Under M1.1 that is the same defect as a vacuous
pass: an absence read as a state it was never shown to be.

### D3 — The trace is immutable; its meaning is not

> *The past is not corrupted, but its echo is rewritten.*

Audit integrity and post-market learning appear to conflict: integrity demands that
records never change, learning demands that a past decision be re-evaluated when
new evidence arrives. The conflict dissolves once the two are separated:

```
recorded event
  ├─ immutable payload
  ├─ the verdict as issued
  ├─ integrity chain
  └─ interpretation revisions   (append-only, each dated and attributed)
       ├─ revision 1 — policy changed
       ├─ revision 2 — incident evidence
       └─ revision 3 — external audit finding
```

History is never edited. Meaning is versioned alongside it. **A system that
rewrites a record to correct an interpretation has destroyed the evidence it was
correcting.**

### D4 — Irreversibility is not irremediability

> *Once the wheel turns it cannot be turned back. The scales, you can still
> balance.*

A control plane built only for prevention is incomplete. Once an action has
occurred, the governance question is no longer whether to allow it but what
remediation, compensation or containment is owed — and whether that path exists, is
recorded, and can be shown to have been taken.

Prevention that fails silently and offers no remedy is not a control. It is a
prevented-in-principle claim.

---

## V. Reflexive assurance

### R1 — An assurance claim is itself subject to evidence verification

The axioms turn on their author. Applied reflexively:

- An agent's *"I did it"* is a sensor reading, not a fact.
- A project's *"we are compliant"* is a claim, not evidence.
- **Having authored a standard is not conformance to it.**
- A module named `audit_layer` producing an audit record is an assumption, not an
  observation.
- A compliance mapping citing evidence is not evidence; **the citation has to
  resolve.**

The term for the discipline this requires:

> **Reflexive Conformance Assurance** — every assurance claim is itself subject to
> the evidence standard it asserts.

### R2 — Independent reading is a mechanism, not a courtesy

A blind spot is by definition invisible to the system that has it. In the audit
reported in §VII, **every finding of this class was surfaced by an independent
reader of the same source — never by the system's own gates**, which were running,
were correctly configured, and were structurally incapable of noticing.

**Independent reading** means a review path operationally separate from the
implementation and from its existing gates. It does not by itself constitute
independent assessment under Boundary 2.

This is not an argument for more review. It is an argument that **independent
reading is a required control with a defined trigger**, and that a governance
architecture which does not budget for it has an unclosable gap by construction.

---

## VI. Boundaries

Normative limits on what may be claimed under this doctrine.

1. **No consciousness claim.** Nothing here depends on machine consciousness,
   implies it, or is evidence for it. Where the underlying framework uses
   phenomenological vocabulary, that vocabulary is internal definition, not
   assertion about experience.
2. **Conformance is not self-awarded, and the word is used precisely.** Standards practice recognises first-, second- and third-party assessment, and conformance is not the same thing as certification. This doctrine does not redefine that vocabulary; it reserves a term within it. Positions are stated on the ladder `mapped` → `self_assessed` → `self_declared_conformance` → `independently_assessed` → `third_party_verified` → `certified`, and never above the rung reached. **Under this doctrine the term *verified conformance* is reserved for named independent assessment.** Mapping a system against a standard is `mapped`; authoring a standard is neither.
3. **No conformance to unpublished drafts.** A standard at draft stage can be
   contributed to; it cannot be conformed to, by anyone.
4. **No coverage claim without a named search domain.** "No standard covers X" and
   "this does not exist" are claims about where one looked. The domain must be
   stated or the claim withdrawn.
5. **These axioms are not proven.** They are a design stance whose consequences are
   checkable. They are not theorems and nothing derives them.
6. **The set is open.** M1.1 exists because M1 was incomplete. Further
   incompleteness is expected and will be published as it is found.

---

## VII. Self-audit: summary

A doctrine that has never been turned on its author is marketing. On 1 August 2026
we audited Phionyx's own governance runtime against these axioms, reading source
rather than documentation.

**The audit identified eleven instances in which a component or an assurance
artefact represented a non-measurement as a positive or completed result**, in two
families: *absence read as confirmation* (five) and *proxy read as the thing*
(six). Applying P1–P5 to the same execution graph surfaced at least four further
defects of a different kind — values written and never read, computed and never
branched on, or guarded by a detector reading a field that is empty everywhere.

The sharpest of the eleven is the one that concerns this document directly. We
published a compliance mapping rating a control **Full** on four cited evidence
artefacts, none of which has ever existed in any repository that could hold them.
Our own specification contains the rule that forbids exactly this:

> *"A verifier MUST NOT treat an entry with `resolvable: false` as verified
> evidence. This prevents an unverifiable pointer from being counted as proof."*
> — AIREP v0.1 §4

We wrote that rule, then broke it in prose, in a public document. Nobody resolved
the pointers; the presence of an evidence block was read as the presence of
evidence. That is R1, and it is why R1 exists.

```yaml
claim_status:                SUPPORTED_NARRATIVE
independent_reproducibility: NOT_MEASURED
```

**Full findings, per-finding detail and where each can be checked:**
[Phionyx self-audit, 1 August 2026](./PHIONYX_MEASUREMENT_AXIOMS_SELF_AUDIT_2026-08-01.md).

### The measured position

The framework does not certify us. Our conformance register separates what a single
ratio would hide:

| Axis | Measured |
|---|---|
| What each foundation item requires of us | 14 of 31 |
| Whether our code does it | 6 of 31 |
| How it relates to an external framework | 2 of 31 |
| **Whether a third party has evaluated us** | **0 of 31** |

The last row is the one that governs. Under **Boundary 2** it stays at zero until an
independent assessment exists.

---

## Related work

The formal core of M1.1 has been established for decades. This doctrine's
contribution is its application to AI governance runtimes and the reported
self-audit findings in §VII, not the underlying results.

- **Three-valued runtime verification.** LTL₃ carries `true`, `false` and
  **`inconclusive`** over partial observations — Bauer, Leucker & Schallhart,
  *Runtime Verification for LTL and TLTL*, ACM TOSEM 2011; monitorability, Pnueli &
  Zaks, FM 2006. LTL₃ establishes that partial observation need not collapse into
  `true` or `false`, and this doctrine adopts that refusal to collapse. It does not
  adopt the value: `INCONCLUSIVE` denotes a check that ran without deciding,
  whereas `NOT_MEASURED` denotes a check that did not execute or could not reach
  its object. **What is new here is not a third value but the separation of
  non-execution from inconclusive observation as a distinct governance verdict.**
- **Vacuity detection.** "The property passed without being exercised", formalised —
  Beer, Ben-David, Eisner & Rodeh, FMSD 2001; Kupferman & Vardi, STTT 2003.
- **Fail-safe defaults.** Deny on failure rather than permit — Saltzer & Schroeder,
  *The Protection of Information in Computer Systems*, Proc. IEEE 1975, design
  principle 2.
- **Measurement validity for AI evaluation.** Jacobs & Wallach, *Measurement and
  Fairness*, FAccT 2021.
- **Assurance and safety cases.** GSN and confidence arguments already treat evidence
  sufficiency as a first-class object; M7 will be contested from that direction,
  reasonably.
- **Replayable attestation.** in-toto, SLSA provenance, Sigstore/Rekor, W3C PROV-O —
  signed per-step evidence rather than logs. This is the shape M7 and D1 argue AI
  observability should adopt.
- **Tamper-evident logging.** Haber & Stornetta 1991; Crosby & Wallach, USENIX
  Security 2009.
- **NIST AI RMF 1.0, MEASURE 1.1**: *"the risks or trustworthiness characteristics
  that will not – or cannot – be measured are properly documented."* This is a
  disclosure duty on the organisation. M1.1 is a type constraint on the verdict. A
  deployment can satisfy MEASURE 1.1 in full and still ship a verifier returning
  `valid` after checking nothing — because that is not a risk anyone *decided* not
  to measure; it is a measurement that silently did not happen and was never
  enumerated.

Where P1–P5 overlap with classical dataflow analysis — def-use chains, reachability,
liveness — they overlap completely. The contribution is where they are pointed.

---

## How to use this document

**As a design discipline.** Take any component in a governance path and ask three
questions in order: *Does its verdict vary with its input, including when the input
is empty or absent? Does the verdict reach something that acts on it? Can the
decision be re-derived from the record?* A component failing the first is not
measuring. Failing the second is not governing. Failing the third is not producing
evidence.

**As a review instrument.** §VII is a worked example. The eleven findings take four
shapes, and those shapes recur: vacuous pass, fabricated denominator, unverified
proxy recorded as verified, and named-but-absent behaviour.

**As a map.** Where this doctrine sits relative to a runtime that applies it and
a protocol that carries its records — and the two directions the relationship does
*not* run — is set out in
[The Evidence Stack](./THE_EVIDENCE_STACK.md).

**As a normative specification.** The requirements implied by this doctrine are
extracted, numbered and made testable in
[Governance Verdict Validity — Normative Specification v1.0](./spec/measurement-axioms/v1.0/MEASUREMENT_AXIOMS_SPECIFICATION.md),
with a machine-readable record schema and a conformance requirement set beside it.
Where the doctrine argues, the specification requires.

**As a standards position.** Six statements here are executable, testable, and
address gaps we did not find closed in the frameworks named in *Related work*.
That search domain is small and stated so it can be attacked:

1. Absence of evidence must not be serialised as positive assurance. *(M1.1)*
2. A measured risk must reach a control branch. *(P5)*
3. A warning without material mitigation is invalid. *(M5)*
4. A recorded value must reach its intended consumer. *(P3)*
5. Probabilistic generation can carry deterministic governance replay. *(M7, D1)*
6. Every assurance claim must itself be independently evidenced. *(R1)*

**As something to attack.** The axioms are engineering claims. If one fails against
its own author, that is the intended use, and we will publish the failure rather
than the correction. §VII is what that looks like.

---

*Phionyx is the reference implementation of this doctrine, not its proof. The
doctrine is intended to outlive any particular implementation, including ours.*
