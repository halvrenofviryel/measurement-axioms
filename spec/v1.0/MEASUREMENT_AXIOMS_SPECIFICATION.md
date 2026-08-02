# Governance Verdict Validity — Normative Specification (v1.0)

**Status:** Frozen at v1.0 on 2026-08-02. The requirement identifiers, their
wording and the companion artefacts below do not change from here; a correction
or an addition becomes v1.1 and says what it changed. A requirement is never
renumbered and a withdrawn one keeps its identifier.

This specification is the normative extract of
[The Measurement Axioms](../../../THE_MEASUREMENT_AXIOMS.md). Where the doctrine
argues, this document requires.

It is not, at this stage, a standards-body specification; it adopts the
requirement discipline below without claiming any standards track.

**Companion artefacts:** [`verdict-outcome.schema.json`](./verdict-outcome.schema.json)
· [`conformance-requirements.yaml`](./conformance-requirements.yaml)

---

## 1. Conventions

The key words "MUST", "MUST NOT", "REQUIRED", "SHALL", "SHALL NOT", "SHOULD",
"SHOULD NOT", "RECOMMENDED", "MAY" and "OPTIONAL" in this document are to be
interpreted as described in BCP 14 [RFC2119] [RFC8174] when, and only when, they
appear in all capitals, as shown here.

A **governance component** is any component whose output is used to decide
whether, how, or under what constraint an AI system's output or action proceeds.
Gates, verifiers, monitors, policy engines, guardrails and evaluators are
governance components.

A **decision record** is one JSON object describing one governance decision.

A **measurement** is an executed procedure that obtains and evaluates its
declared object under a specified mapping.

Invariance alone does not establish that no measurement occurred. A component
that correctly returns `NOT_MEASURED` for every degenerate input is invariant
over that class *and* is measuring correctly. Non-measurement is established by
**paired inputs the mapping is required to distinguish** producing outcomes it
does not distinguish.

Requirement identifiers are `MA-n.m` and are stable across revisions of this
document. A requirement is never renumbered; a withdrawn requirement retains its
identifier and is marked withdrawn.

---

## 2. Scope and conformance classes

This specification defines requirements on **what a governance component records
about its own act of deciding**. It does not define what the component should
decide, what policy it should apply, or how it should evaluate content.

Two conformance classes:

- A **producer** emits decision records.
- A **consumer** reads decision records and acts on them. An aggregator, a
  dashboard, a commit gate and a compliance report are all consumers.

**A conformance assessment MUST produce one result for every applicable
requirement in `conformance-requirements.yaml`.** A producer or consumer may be
reported conformant only where every applicable MUST or MUST NOT requirement is
`PASS` or a justified `NOT_APPLICABLE`, and no applicable requirement is `FAIL`,
`NOT_MEASURED`, `INCONCLUSIVE` or `ERROR`.

The checks in Section 9 are a **minimum assessment procedure**, not the
definition of conformance. Passing them while violating a requirement they do not
reach is not conformance — and an earlier version of this document said otherwise,
binding conformance to eleven checks over thirty-nine requirements.

---

## 3. The verdict algebra

### 3.1 Values

`measurement_status` MUST be exactly one of:

| Value | Meaning |
|---|---|
| `PASS` | the check ran and its success criterion was met |
| `FAIL` | the check ran and its success criterion was not met |
| `NOT_MEASURED` | the check did not run, or its required input was unobtainable |
| `INCONCLUSIVE` | the check ran; the evidence obtained did not decide |
| `ERROR` | the check could not complete for a technical reason |
| `NOT_APPLICABLE` | out of scope by a documented decision |

**MA-3.1.** `NOT_MEASURED` and `INCONCLUSIVE` MUST NOT be used interchangeably.
`INCONCLUSIVE` asserts that a check executed. Where a check did not execute, or
could not reach the object it was to examine, a producer MUST record
`NOT_MEASURED`.

**MA-3.2.** A producer MUST NOT record `NOT_MEASURED` for a check that executed
and returned an undecided result; that is `INCONCLUSIVE`.

**MA-3.3.** `NOT_APPLICABLE` MUST be accompanied by `scope_decision`, a reference
to the documented decision placing the check out of scope. A `NOT_APPLICABLE`
without a resolvable `scope_decision` is `NOT_MEASURED`.

### 3.2 Collapse prohibition

**MA-3.4.** A consumer MUST handle `NOT_MEASURED`, `INCONCLUSIVE` and `ERROR`
distinctly from `PASS`.

**MA-3.5.** An aggregate MUST NOT map `NOT_MEASURED`, `INCONCLUSIVE` or `ERROR` to
`PASS`. This prohibition applies to every mechanism by which such a mapping can
occur, including:

- a default branch that treats unrecognised values as passing;
- coercion to a boolean, where a non-empty or non-null value evaluates as true;
- a null-coalescing or `or`-style default that substitutes a passing value;
- omission of the record from a summary whose absence is read as success;
- counting only `FAIL` records and reporting the remainder as passing.

**MA-3.6.** A consumer that encounters a `measurement_status` value it does not
recognise MUST fail closed or record `ERROR`. It MUST NOT fall through to a
passing path.

**MA-3.7.** Where a producer emits `measurement_status` values that a legacy
consumer cannot interpret, compatibility MUST be provided by a versioned adapter
that handles every value explicitly. Additive emission alone does not satisfy this
requirement, because an unaware consumer may satisfy none of MA-3.4 to MA-3.6.

### 3.3 Absence

**MA-3.8.** Where a required input — context, telemetry, policy, baseline,
evidence or prior state — is absent or unreadable, a producer MUST record
`measurement_status: NOT_MEASURED`.

`inputs_present: false` covers both an input that was not there and one that
was there and could not be read; which of the two is carried by `non_measurement_cause`.
The field answers only whether a measurement could be taken from the input, and
is omitted where nobody established either way.

**MA-3.9.** A producer MUST NOT emit a derived value in place of a measurement it
did not take. Where a denominator, baseline or comparand is empty, the derived
value MUST be omitted or null and the status MUST be `NOT_MEASURED`.

**MA-3.10.** A record MUST NOT contain a natural-language reason asserting an
operation that did not occur. Where `measurement_status` is `NOT_MEASURED`, any
`reason` field MUST state what was not measured.

---

**MA-3.11.** A record whose `measurement_status` is `NOT_MEASURED` MUST carry a
`non_measurement_cause` drawn from the closed vocabulary in Section 4.1. Free
text does not survive aggregation, and the distinction MA-3.1 turns on — a check
that did not run against an object that could not be reached — is precisely what
a consumer must be able to recover without reading prose. `unknown` is a
permitted value and an honest one; it is not a default to be reached for where
the cause is known.

## 4. The decision record

### 4.1 Orthogonal dimensions

A governance event has independent dimensions. A record MUST NOT encode two of
them in one field.

| Field | Values |
|---|---|
| `measurement_status` | Section 3.1 |
| `decision_outcome` | `allow` · `block` · `attenuate` · `escalate` · `abstain` |
| `execution_status` | `completed` · `timeout` · `tool_unavailable` · `policy_unavailable` · `failed` |
| `operating_mode` | `normal` · `degraded` |
| `authority` | `autonomous` · `human_confirmed` · `human_overridden` |
| `observation` | `recorded` · `detected_after_execution` · `previously_silent_failure` |
| `non_measurement_cause` | `not_executed` · `suppressed_by_tier` · `input_absent` · `input_unreadable` · `object_unreachable` · `unknown` |

**MA-4.1.** A decision record MUST carry `measurement_status` and
`decision_outcome` as separate fields.

**MA-4.2.** An action does not itself produce a `measurement_status`; the
evaluation of that action does. A producer MUST NOT derive `measurement_status`
from `decision_outcome` or the reverse.

**MA-4.3.** Where `measurement_status` is `NOT_MEASURED`, `decision_outcome` MUST
NOT be `allow` for a governance-relevant decision or a state-changing action. It
MUST be `block`, `escalate` or `abstain`.

**MA-4.4.** A deployment MAY define a bounded degradation for read-only,
reversible, low-consequence operations. Where it does, the record MUST carry
`operating_mode: degraded` together with the honest `measurement_status`, and MUST
NOT record the operation as passing.

### 4.2 No null action

**MA-4.5.** Abstention, timeout, tool unavailability, policy unavailability,
human override and detected-after-execution failure MUST each be recorded as a
decision. Absence of a record MUST NOT be the representation of any of them.

**MA-4.6.** A consumer MUST NOT infer a decision outcome from the absence of a
record.

### 4.3 Unconditional evaluation

**MA-4.7.** Every governance-relevant decision and every state-changing action
MUST be accompanied by a recorded `measurement_status`.

**MA-4.8.** Where a tiered evaluation suppresses a deeper check, the set of
decisions the deeper layer did not see MUST be recorded, and each MUST carry
`NOT_MEASURED` for that layer. It MUST NOT be inferable only from the absence of a
finding.

### 4.4 Profiles

**MA-4.9.** A deployment profile MAY adjust thresholds and MAY add dimensions to
the applicable baseline schema. It MUST NOT remove a dimension the schema
designates mandatory, and MUST NOT remove a requirement of this specification.

**MA-4.10.** The profile in force MUST be identified in the record.

---

## 5. Evidence levels

`evidence_status` MUST be exactly one of `E0` … `E4`:

| Level | The record supports |
|---|---|
| `E0` | the producer's own account |
| `E1` | that it has not been altered undetectably |
| `E2` | which key signed it |
| `E3` | that a third party can bind that key to an identity and check it without the producer |
| `E4` | that the verdict can be re-derived from the record |

**MA-5.1.** The levels are cumulative. A claim of `En` asserts satisfaction of
`E0` through `En`.

**MA-5.2.** A record MUST state its `evidence_status`. A system that describes a
record as "signed", "audited" or "tamper-evident" without stating the level makes
a claim spanning `E1` to `E4` and is non-conformant.

**MA-5.3.** `E1` MUST NOT be claimed where the integrity mechanism can be
recomputed by a party able to alter the record. A construction whose secret is
distributed with the implementation satisfies `E0` only, and any narrower claim
MUST state the threat model under which it holds.

**MA-5.4.** Non-repudiation MUST NOT be claimed below `E3`, and `E3` supports such
a claim only subject to the applicable identity, trust and legal context. `E3`
requires: secure custody of the signing key; the public key bound to a verified
identity; an independent trust anchor; a recorded rotation and revocation history;
and an unambiguous statement of what was signed and when.

**MA-5.5.** Holding the signing private key is normal for a producer and does not
by itself reduce the achievable level.

---

**MA-5.6.** A record naming an integrity mechanism MUST carry that mechanism's
artefact: a signature construction carries the signature, the key identifier and
the fields covered; an external timestamp carries the token and the issuing
authority; a witnessed ledger carries the receipt and the ledger identifier; a
hash chain carries the link to the preceding entry. Naming a mechanism and
omitting what makes it that mechanism is the same empty claim as an evidence
level with no basis at all — it states a construction a verifier cannot begin
to check.


The first entry of a chain has nothing preceding it. Such an entry MAY omit
`previous_digest` only where it declares `chain_position: genesis` and carries a
`chain_context_ref` identifying the chain it opens; a genesis entry MUST NOT
carry `previous_digest`. Every other chain entry MUST carry it. A record
asserting both states at once that nothing precedes it and what precedes it.

## 6. Path properties
Five properties of the path by which a measurement is persisted, propagated and
allowed to affect a system. They are stated as predicates so an implementation can
test them. They are **conservatively approximable** by static analysis; exact
reader- and branch-reachability are undecidable in general, so an implementation
MUST report an over-approximation rather than a false negative.

| | Property | Predicate |
|---|---|---|
| **P1** | Persistence | the step writes a value that outlasts its own execution |
| **P2** | Delay | the effect extends beyond the immediate call |
| **P3** | Propagation | at least one reader receives the exact key or value written |
| **P4** | Selectivity | the output varies with the input |
| **P5** | Feedback | the value reaches a branch condition, not only a log or format string |

**MA-6.1.** P4 MUST be tested with a **valid control input paired with its
degenerate, absent or adversarial variant**. The degenerate variant MUST produce
the status its class requires — normally `NOT_MEASURED` — and MUST NOT inherit
the control input's passing result.

Testing a degenerate input alone establishes nothing. A component returning the
passing value for it may be failing to measure, and a component returning
`NOT_MEASURED` for every such input is behaving exactly as required; only the
pair distinguishes them.

Earlier wording of this requirement read invariance over a degenerate class as
proof of non-measurement, which condemned the correct behaviour. It was corrected
on 2026-08-01 after the executable probe made the contradiction visible.

**MA-6.2.** P2 is not an evidence requirement. A measurement produced, persisted,
propagated and acted upon within a single call is not weaker for being prompt.

**MA-6.3.** Required properties by decision type:

| Decision type | REQUIRED | Conditional |
|---|---|---|
| measurement verdict | P4 through paired control–degenerate tests, P1 | P3 where a consumer must act on it |
| intervention verdict | P4 (paired), P1, P3, P5 | attribution and replay per the assurance claim made |
| action — tool call, state write | P1, P3 | P5 where the outcome updates a model or policy |
| answer making no assurance claim | none by this specification | retention per applicable policy |

**MA-6.4.** P1 is bounded by retention, not by universality. A record represented
as auditable assurance MUST persist for the retention period required to verify
that claim. An output making no assurance claim need not be retained by this
specification.

---

## 7. Intervention claims

**MA-7.1.** An **advisory control** informs a human or a downstream process. It is
conformant without runtime effect and MUST NOT be represented as an intervention.

**MA-7.2.** An **intervention control** claims to constrain the system. A verdict
MUST NOT be represented as an enforced intervention unless it materially changed
the system's output, action, state transition, authority or control flow.

**MA-7.3.** Where a verdict requires downstream action, `enforcement_status` MUST
be recorded: `not_required` · `not_performable` · `requested` · `acknowledged` · `applied` · `failed`.
A verdict whose `enforcement_status` is `requested` MUST NOT be reported as
applied.

| `enforcement_status` | Meaning |
|---|---|
| `not_required` | the decision did not call for an intervention |
| `not_performable` | the decision called for an effect; the directive produced could not be performed (MA-7.9) |
| `requested` | a performable directive was sent to its consumer |
| `acknowledged` | the consumer accepted it |
| `applied` | the material effect occurred (MA-7.2) |
| `failed` | application was attempted and did not complete |

The values are not ordered stages of one process. `not_required` and
`not_performable` describe decisions that never reached a consumer, and they
describe different situations: the first that no effect was called for, the
second that one was and nothing performable came of it.

**MA-7.4.** A verdict carrying an attenuation, modification or deferral directive
MUST carry the parameters required to perform it. A directive without them is
advisory.

Every non-`allow` decision outcome requires an `enforcement_status`, whether
the enforcement is performed locally or by a downstream consumer. Absence of
the field does not record that nothing was enforced — by MA-4.6 it records
nothing at all.

**MA-7.5.** A probabilistic evaluator MAY provide measurement evidence but MUST
NOT be the sole authority for an irreversible state transition unless its verdict
is independently constrained, attributable and replayable.

---

**MA-7.6.** Where `enforcement_status` is `applied` for an intervening
`decision_outcome`, the record MUST carry an intervention object naming the
directive type, its intended consumer and a `material_effect` — a resolvable reference
to the observed change in output, action, state transition, authority or control
flow. Without one, `applied` asserts the material effect MA-7.2 requires and
evidences none of it, which places the claim exactly where MA-9.1 places an
unresolvable citation. Whether the reference resolves, and whether what it names
is in fact a material change, is not decidable from the record alone and is
assessed dynamically.


**MA-7.7.** `decision_outcome` names the class of effect a decision called for;
`intervention.type` names the mechanism intended to perform it, or that performed it. A record MUST NOT pair
them incompatibly, and `allow` MUST NOT carry an intervention record at all.

| `decision_outcome` | permitted `intervention.type` |
|---|---|
| `allow` | none — the decision was not to intervene |
| `block` | `block` |
| `attenuate` | `attenuate` · `redact` · `rate_limit` |
| `escalate` | `escalate` · `defer` |
| `abstain` | `defer` |

The distinction is not decorative. A record stating `decision_outcome: block`
with `intervention.type: attenuate` describes two different things happening and
leaves a reader unable to say which one the system did. Where an implementation
needs a mechanism this table does not list, it belongs in a profile under
`profiles`, not in a reinterpretation of these values.

The same table governs `advisory.type` (MA-7.9). An advisory names the mechanism
its producer would have applied, so a recommendation the decision did not call
for describes two different things by the same argument as above.

---

**MA-7.8.** The intervention lifecycle is closed in both directions.

| `decision_outcome` | `intervention` | `enforcement_status` |
|---|---|---|
| `allow` | neither `intervention` nor `advisory` | `not_required`, or absent |
| `block` · `attenuate` · `escalate` · `abstain` | exactly one of `intervention` or `advisory` | `requested` · `acknowledged` · `applied` · `failed` — or `not_performable` with an `advisory` |

A decision that called for an effect names the mechanism from the moment it is
requested, not only once it is applied. `enforcement_status: requested` with no
directive attached names nothing for a consumer to perform, and by MA-7.4 an
unperformable directive is advisory whatever the record calls it. In the other
direction, `not_required` on an intervening outcome contradicts the outcome that
required it, and any live enforcement state on `allow` reports an effect the
decision declined to call for.

**MA-7.9.** Where a decision called for an effect but the directive produced lacks
what MA-7.4 requires in order to perform it, the record MUST carry an `advisory`
object naming what is missing, MUST NOT carry an `intervention`, and MUST record
`enforcement_status: not_performable`.

`not_performable` is a distinct state and MUST NOT be collapsed into a neighbouring
one. `failed` claims an attempt that was not made; `not_required` claims the
decision did not call for the effect, when it did. Either substitution records a
measurement nobody took, which is the error this document exists to name.

The lifecycle table above therefore reads: an intervening outcome carries exactly
one of `intervention` or `advisory` — the first with a live enforcement state, the
second with `not_performable`.

## 8. Replay

**MA-8.1.** A record supporting a claim of independently reproducible governance
MUST contain sufficient inputs to re-derive the measurement mapping, the verdict
and the state transition.

**MA-8.2.** Reproducibility MUST be keyed on the recorded decision inputs — state,
policy version, profile, thresholds, measurements and any stochastic draw — and
MUST NOT be keyed on wall-clock time. Where a time value affects the decision it
MUST be recorded as an input.

**MA-8.3.** Order requirements are invariants only where asserted against an
observed execution trace. A declared order enforced solely by the structure of the
implementation MUST NOT be described as enforced.

**MA-8.4.** The recorded payload of a decision MUST NOT be modified after the
fact. A revised interpretation MUST be recorded as an append-only revision
alongside the original, each dated and attributed.

---

## 9. Conformance check

A verifier reports a **producer** as conformant only when all of the following
hold:

1. every decision record validates against
   [`verdict-outcome.schema.json`](./verdict-outcome.schema.json);
2. `measurement_status` and `decision_outcome` are present and distinct fields
   (MA-4.1, MA-4.2);
3. for every applicable paired case, the control input yields an interpretable
   status permitted by that case, and the degenerate variant yields the exact
   status its class requires (MA-3.8, MA-6.1). Not emitting `PASS` is
   insufficient: `FAIL` asserts that a check ran, which for an absent input is
   its own false claim;
4. no record carries a reason asserting an operation that did not occur
   (MA-3.10);
5. every `NOT_APPLICABLE` carries a resolvable `scope_decision` (MA-3.3);
6. `evidence_status` is stated, and no claim exceeds the level supported
   (MA-5.2 … MA-5.6);
7. every verdict represented as an enforced intervention carries
   `enforcement_status: applied` and evidence of material change, and that a
   directive lacking what it needs to be performed is recorded as an advisory
   rather than an intervention (MA-7.2 … MA-7.9).

A verifier reports a **consumer** as conformant only when all of the following
hold:

8. `NOT_MEASURED`, `INCONCLUSIVE` and `ERROR` reach handling distinct from `PASS`
   (MA-3.4);
9. no aggregation path maps any of them to `PASS` by any mechanism in MA-3.5;
10. an unrecognised `measurement_status` fails closed or yields `ERROR`
    (MA-3.6);
11. no decision outcome is inferred from the absence of a record (MA-4.6).

**Conformance is not self-awarded.** A system's position MUST be stated on the
ladder `mapped` → `self_assessed` → `self_declared_conformance` →
`independently_assessed` → `third_party_verified` → `certified`, and never above
the rung reached. **The term *verified conformance* is reserved for named
independent assessment.**

**MA-9.1.** A conformance claim MUST resolve every cited evidence artefact and
MUST name the version against which it was evaluated. A citation that does not
resolve is not evidence.

---

## 10. Test vectors

An implementation SHOULD be exercised against at least these cases. Each states
the input class and the required `measurement_status`.

Each vector states a control input and its degenerate variant. The REQUIRED
result is what the **degenerate** variant must yield; the control must yield
something else.

| # | Input class | REQUIRED result on the degenerate variant |
|---|---|---|
| TV-1 | verification called over an empty collection | `NOT_MEASURED`, not `PASS` |
| TV-2 | comparison against an absent baseline | `NOT_MEASURED`, and `baseline_present: false` |
| TV-3 | metric whose denominator is empty | `NOT_MEASURED`, derived value null |
| TV-4 | required source unreadable | `NOT_MEASURED` |
| TV-5 | optional verifier not supplied, subject tampered | `NOT_MEASURED` for that dimension, not `PASS` |
| TV-6 | required telemetry absent | `NOT_MEASURED`; `decision_outcome` not `allow` |
| TV-7 | unknown `measurement_status` presented to a consumer | fail closed or `ERROR` |
| TV-8 | attenuation directive with no parameters | `advisory` with `not_performable_because`; `enforcement_status: not_performable`; MUST NOT be recorded as an intervention |
| TV-9 | evidence pointer that does not resolve | `resolvable: false`; not counted as evidence |
| TV-10 | `NOT_APPLICABLE` with no `scope_decision` | treated as `NOT_MEASURED` |
| TV-11 | producer secret distributed with the implementation | `evidence_status: E0` |
| TV-12 | record replayed from its own inputs | same verdict, or the claim of MA-8.1 fails |

---

## 11. Security and privacy considerations

This specification governs what is recorded about a decision, not the content of
the decision. Records carry pointers, digests and status values; they are not a
place for the material being governed.

`NOT_MEASURED` is a disclosure. A record stating that a check did not run tells an
adversary where checks do not run. Deployments SHOULD consider whether decision
records are readable by parties whose access to that information is itself a risk,
and MAY restrict the audience of a record without changing its content — but MUST
NOT substitute a passing value to conceal a non-measurement.

MA-6.4 bounds retention to what an assurance claim requires. Retaining records
that make no assurance claim conflicts with data minimisation and is not required
here.

---

## 12. References

- [RFC2119] Bradner, S., *Key words for use in RFCs to Indicate Requirement
  Levels*, BCP 14, RFC 2119, March 1997.
- [RFC8174] Leiba, B., *Ambiguity of Uppercase vs Lowercase in RFC 2119 Key
  Words*, BCP 14, RFC 8174, May 2017.
- [DOCTRINE] Abak, A. T., *The Measurement Axioms*, Baseline Edition,
  1 August 2026.
