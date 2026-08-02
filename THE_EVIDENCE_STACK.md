# The Evidence Stack

### Rules, runtime, record — and why they are three things, not one

**Ali Toygar Abak** · ORCID [0009-0002-3718-4010](https://orcid.org/0009-0002-3718-4010)
**Phionyx** · 1 August 2026

> Companion to [The Measurement Axioms](./THE_MEASUREMENT_AXIOMS.md). That document
> states the rules. This one says where they sit relative to everything else we
> have built, and what the arrangement means for AI governance.

---

## I. The one distinction that organises everything

Two questions look alike and are not:

> **Was this record altered?**
> **Was the claim in this record measured?**

The first is answered by a format: canonical serialisation, a content hash, a
chain link, a signature. Anyone can check it offline, without access to the
system that produced it.

The second cannot be answered by a format at all. A record can be perfectly
formed, correctly hashed, validly signed, properly chained — and assert something
that never happened.

**We have the case, and it is ours.** In our own runtime, a descriptor
verification step received `None` — never measured — coerced it to `False`, and
wrote into the evidence chain:

```
disposition: admit
reason:      "descriptor hash matches user-approved baseline"
```

No baseline was compared. The envelope carrying that sentence was schema-valid,
hash-chained and signed. **The format did its job flawlessly and preserved a
falsehood.**

That is not a defect in the format. It is the boundary of what a format can do,
and it is why the rules are a separate artefact.

---

## II. The stack

```
              THE MEASUREMENT AXIOMS
       when a governance verdict counts as a measurement
                          │
                          ▼
                PHIONYX RUNTIME FAMILY
         makes, constrains and evaluates decisions
                          │
       ┌──────────────────┼──────────────────┐
       ▼                  ▼                  ▼
  Phionyx Core    phionyx-pipeline-mcp   phionyx-mcp-server
  46-block        inward: agent          outward: third-party
  runtime engine  self-claim gate        tool boundary
       └──────────────────┼──────────────────┘
                          ▼
                    PHIONYX RGE
          Phionyx's producer and profile for AIREP
                          │
                          ▼
                        AIREP
       neutral, offline-checkable decision receipt
                          │
                          ▼
                 external verifier
```

Four verbs:

> **The doctrine defines. Phionyx governs. The MCP gates challenge and observe.
> AIREP records.**

And a fifth that is not in the column, because it is applied **to** the column
rather than being a stage in it:

```
   ┌─────────────────────────────────────────────┐
   │  CDE-12 — Control-Delivery Evidence         │
   │  rates what a record lets a later reader     │──▶ applied to the
   │  establish. Twelve criteria, five values,    │    record any layer
   │  an evidence tier on every cell.             │    above produces
   └─────────────────────────────────────────────┘
```

> **CDE-12 rates.**

---

## III. What each piece is, precisely

### The Measurement Axioms — a design discipline

Not a product, not a format, not a standard. A normative discipline stating when
a governance verdict deserves to count as a measurement: non-execution must not
collapse into success; a measured value must reach its intended consumer; an
intervention claim requires material effect; a replay claim requires sufficient
decision inputs. It enforces nothing. It states what an implementation must
satisfy, and supplies the checks by which the question is decided.

### Phionyx Core — a deterministic runtime around probabilistic generation

Published as `phionyx-core`. Its job is not to define an evidence format. Its job
is to put a deterministic governance path between a model's output and an action:
a canonical execution order, structured state, pre-response gates, a kill switch,
a human-in-the-loop queue, and an audit trail.

> **Phionyx Core governs probabilistic output before it becomes action.**

### The two MCP gates — different boundaries, different questions

These are frequently collapsed into "the Phionyx pipeline" and they should not
be. They are separate packages governing separate boundaries, and one of them
shares a word with something else entirely.

| | `phionyx-pipeline-mcp` | `phionyx-mcp-server` |
|---|---|---|
| **Faces** | inward, at our own agent | outward, at third-party tools |
| **Question** | does the agent's *"I fixed / tested / changed it"* match what the repository shows? | what crossed the tool boundary, did its descriptor change, and is there a record? |
| **Produces** | a claim verdict and reviewer-runnable evidence | hash-chained tool-call envelope records, with production signing under active alignment |

**A naming hazard worth stating once.** "The Phionyx pipeline" is ambiguous
between the **46-block canonical runtime path inside Core** and the package
**`phionyx-pipeline-mcp`**, which is a narrow self-claim gate and not the engine.
We use the full names.

### RGE — the bridge, not a synonym

RGE is Phionyx's producer for AIREP and its profile of that format. It is not
another name for AIREP, and AIREP is not Phionyx's format.

> **RGE is AIREP's first reference producer, currently being aligned against the
> specification** — not a conformant one. Our own audit found the exporter
> violating four of AIREP's MUST requirements on its default path.

### CDE-12 — an instrument, not a layer

*Added 2026-08-02, after the v1.0 release of the doctrine. The Zenodo deposit
of v1.0 predates this section; the repository is the current text.*

[CDE-12](https://doi.org/10.5281/zenodo.21631868) — *Control-Delivery
Evidence*, v0.2, 27 July 2026 — is an instrument for reporting what a system
can and cannot **record** about a control decision and its fate. Twelve
criteria, a five-value scale, and an evidence tier on every cell.

**It measures records, not behaviour.** A system may enforce perfectly and
score badly; that is not a contradiction. The question throughout is what a
later reader can establish from what the system wrote down.

That makes it a different kind of thing from everything else on this page, and
the difference is worth stating rather than leaving to be inferred:

| | |
|---|---|
| The doctrine | says when a verdict counts as a measurement |
| The runtime, the gates, RGE, AIREP | produce decisions and records |
| **CDE-12** | **rates the record somebody else produced** |

Two consequences follow.

**It applies to systems other than ours.** Nothing in CDE-12 is Phionyx-shaped:
its subject is any artifact that governs or records agent actions at runtime and
produces a record intended for later inspection. That is deliberate, and it is
the reason it sits beside the column rather than inside it.

**It is the missing half of this doctrine's own weakest claim.** The self-audit
reports `independent_reproducibility: NOT_MEASURED`, and its design intent is
exactly the remedy: *two people applying this to the same system, without
speaking to each other, should reach the same cells. Where they cannot, the
criterion is defective and the defect is ours.* An assessment that two readers
can reach independently is what turns a source reading into a measurement.

**Version asymmetry, stated.** CDE-12 is at v0.2 and this doctrine is at v1.0.
They are not co-equal releases and should not be cited as though they were. The
instrument is published, DOI'd and usable; it has not been through the freezing
and conformance-suite discipline the specification has.

---

### AIREP — a neutral protocol

`ai-runtime-evidence-protocol`. One signed, hash-chained, canonical-JSON record
per decision, checkable offline by someone with neither the runtime nor its
source. Vendor- and model-independent by construction, and explicit that a valid
record attests the path, not the truth of the output.

---

## IV. Two directions the relationship does not run

**A valid record does not imply a valid measurement.** The descriptor case in §I
is exactly this: everything the format checks passed, and the claim was empty.

**A valid measurement does not require this format.** A runtime satisfying the
Measurement Axioms may emit its evidence in any schema it likes. The axioms are
not a marketing surface for AIREP, and adopting AIREP is not conformance to them.

```
Measurement Axioms conformant   ≠   AIREP conformant
```

A system wanting both needs both: **semantic validity from the doctrine, record
and interchange validity from the protocol.**

---

## V. Where they touch, and how they should be joined

`measurement_status` and AIREP's `directive.verb` are not the same field and must
not be merged.

| | Values | Answers |
|---|---|---|
| `directive.verb` | `release` · `block` · `defer` · `redact` · `escalate_to_human` · `kill` | what was done |
| `measurement_status` | `PASS` · `FAIL` · `NOT_MEASURED` · `INCONCLUSIVE` · `ERROR` · `NOT_APPLICABLE` | what the evaluation behind it establishes |

They are orthogonal, and both combinations below are recordable:

```yaml
directive: { verb: block }        # coherent: undecided, so fail safe
measurement_status: INCONCLUSIVE

directive: { verb: release }      # recordable, and not acceptable governance:
measurement_status: NOT_MEASURED  # nothing was measured, yet action proceeded
```

The second is exactly what the doctrine forbids and what a format alone will
happily preserve.

**The join belongs in a profile, not in the core.** AIREP reserves `profiles` for
implementation- and domain-specific content, and this is what that reservation is
for:

```yaml
profiles:
  measurement_axioms:
    measurement_status:   NOT_MEASURED
    execution_status:     policy_unavailable
    enforcement_status:   requested
    evidence_status:      E0
    required_consumer:    release_gate
    consumer_acknowledged: false
```

This keeps AIREP's core neutral, lets any runtime carry the semantics without
adopting Phionyx, and leaves a later core change to be argued on evidence of
common need rather than asserted now.

---

## VI. Two guarantees that share a word

**Replay** means different things in the two layers, and the difference matters
to anyone reading a conformance claim.

| | What is re-derived |
|---|---|
| AIREP verification | the record's canonical bytes, hash, signature and chain position |
| Measurement Axioms **E4** | the measurement mapping, the verdict and the state transition |

A record can satisfy the first and not the second. Passing an AIREP verifier is
not evidence-level E4.

---

## VII. What this arrangement means for AI governance

**The field checks content. It rarely checks whether the check ran.** Regulatory
and standards instruments ask what an organisation decided, documented and
disclosed. We have not found one that asks whether the deciding component
performed an act whose outcome could have differed — the domain of that search is
stated in the doctrine's *Related work*, and it is small.

Three consequences follow from separating the layers.

**A format is falsifiable from the record; a runtime is not.** AIREP conformance
can be checked by anyone holding the record. Measurement Axioms conformance
cannot be established from a decision record alone: some requirements are
black-box testable, and full assessment needs implementation access, execution
evidence, or both. **The asymmetry is the
argument for independent assessment**, and it is why our own audit is published
as `SUPPORTED_NARRATIVE` with `independent_reproducibility: NOT_MEASURED` rather
than as evidence.

**Neither layer belongs to one vendor.** We authored a format and a discipline,
and separating them is the mechanism by which either can be adopted without the
other — or without us. A rule and a record owned as one product is a lock-in
surface wearing a governance jacket.

**Authorship is not conformance.** Our reference exporter violates four MUSTs of
the specification we wrote. That is in the audit rather than in a backlog,
because a project that cannot say this about itself has no standing to ask it of
anyone else.

---

## VIII. What we do not claim

Stated as prohibitions on our own copy, because each is a sentence we could
plausibly have written.

| Not this | Because |
|---|---|
| "AIREP is the implementation of the Measurement Axioms" | AIREP is a record format. It enforces no ordering, selectivity, propagation or control-efficacy requirement. |
| "An AIREP-valid record proves the decision was correct" | The specification says a record attests the path, not the truth of the output. |
| "`phionyx-pipeline-mcp` is the 46-block pipeline" | One is a self-claim gate package; the other is Core's canonical runtime path. |
| "`phionyx-mcp-server` is Phionyx" | It is the outward-facing tool boundary in a family. Its own README states five of eight capabilities implemented and three explicit stubs. |
| "RGE is fully AIREP-conformant" | Our audit found four MUST violations on its default export path. |
| "Phionyx conforms to the Measurement Axioms" | Runtime enforcement is measured for 6 of 31 foundation items; third-party evaluation for 0. |
| "AIREP replay equals E4" | §VI. |

**The supportable statement, today:**

> **Phionyx is the doctrine's reference implementation project, under explicit
> self-audited alignment.**

---

## IX. The short version

> The Measurement Axioms define when an AI governance verdict deserves to count
> as a real measurement. Phionyx is the reference implementation project being aligned to apply
> that discipline across its runtime family — Core governs model output before it becomes action,
> `phionyx-pipeline-mcp` checks what an agent claims it changed, and
> `phionyx-mcp-server` records the third-party tool boundary. Their decisions can
> be emitted through RGE, the reference producer for AIREP. AIREP does not prove
> a decision was correct; it gives an outsider a neutral, checkable receipt of
> what was recorded.

And the sentence the arrangement exists to make possible:

> **Phionyx does not own the evidence rule and the evidence format as one
> product. The doctrine defines the rule, Phionyx tests it in a runtime, and
> AIREP lets any runtime carry the resulting evidence beyond itself.**
