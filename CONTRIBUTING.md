# Contributing to the Measurement Axioms

The Measurement Axioms are a doctrine, a verdict grammar, and a small reference implementation with
frozen, checksummed artefacts. Contributions, independent implementations, and adversarial critique
are welcome — especially an independent implementation of the verdict semantics, or a case the
reference implementation gets wrong.

## Ground rules

1. **Claim ≤ Evidence.** Every claim in the spec, README, or docs must match what the reference
   implementation and tests actually establish. Use the weakest accurate word; do not describe the
   work as "verified" or "independently reproduced" while `audit/STATUS.md` says otherwise.
2. **A non-measurement is never a pass.** The whole point: `NOT_MEASURED`, `ERROR`, `INCONCLUSIVE`,
   and inapplicability must stay distinct from `PASS`. Any change that lets one collapse into a
   positive verdict is wrong by definition.
3. **Spec, tests, and frozen artefacts move in lockstep.** A change to a normative axiom or to the
   verdict grammar updates the reference implementation, the tests, and the frozen artefact, and
   **re-generates `spec/v1.0/CHECKSUMS.sha256`**. A spec change with stale checksums or tests will
   be rejected. A change to a released, DOI-anchored version is a new version, not an edit.
4. **Honesty over polish.** Regulatory or standards anchors are indicative until checked against the
   primary source.

## How to propose a change

Open an issue describing the change and which axiom(s) it touches. For a defect, include a minimal
input and the verdict you expected versus the one derived.

## Before you open a PR

```bash
cd spec/v1.0
sha256sum -c CHECKSUMS.sha256          # the frozen artefacts must all match
python -m pytest ../../tests/ -q       # the full suite passes, no new failures
```

If you changed a frozen artefact intentionally, regenerate and commit the updated
`CHECKSUMS.sha256` in the same PR and say so explicitly.

## Conduct

Be precise, be kind, assume good faith. Disagreements are resolved by what the verdict grammar and
the tests demonstrate, not by authority. No personal data or secrets in commits, issues, or PRs.

## License of contributions

This work is licensed **CC-BY-4.0**. By contributing, you agree your contributions are licensed
under the same terms. Note the project's standing scope boundary: this licence grants **no right to
describe any implementation as conformant**.
