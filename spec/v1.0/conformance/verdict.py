"""Reference implementation of the verdict algebra — Measurement Axioms v1.0.

Normative source: ``MEASUREMENT_AXIOMS_SPECIFICATION.md`` §3.

The point of this module is not that it defines six constants. Any enum does
that. The point is that the collapse prohibitions of MA-3.4 to MA-3.6 are
enforced *by the type*, so that the ways a non-measurement historically becomes a
pass are unavailable rather than merely discouraged:

    if result:                      # truthiness   -> __bool__ raises
    result or PASS                  # or-default   -> __bool__ raises (Python
                                    #                 evaluates truth first)
    result | PASS                   # bitwise or   -> __or__ raises
    all(results)                    # aggregate    -> __bool__ raises
    aggregate([m, True])            # raw booleans -> aggregate() refuses

A type that can be misused silently is a warning. This one fails loudly, which is
the only form the specification recognises.

No dependencies beyond the standard library, so an implementer can vendor this
file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import re
from enum import Enum
from types import MappingProxyType
from typing import Any, Iterable, Mapping


class CollapseError(TypeError):
    """Raised where a non-passing verdict was about to become a passing one.

    Named for what it prevents rather than what triggered it, because the
    message a developer sees at 2am should say which rule they hit.
    """


class Verdict(str, Enum):
    """MA-3.1. Six values. ``NOT_MEASURED`` and ``INCONCLUSIVE`` are not
    interchangeable: the first says the check did not run, the second says it ran
    and did not decide."""

    PASS = "PASS"
    FAIL = "FAIL"
    NOT_MEASURED = "NOT_MEASURED"
    INCONCLUSIVE = "INCONCLUSIVE"
    ERROR = "ERROR"
    NOT_APPLICABLE = "NOT_APPLICABLE"

    def __bool__(self) -> bool:
        """MA-3.5. `Measurement.__bool__` raised; this one did not, so
        ``if measurement.verdict:`` still collapsed every non-passing value into a
        pass. Found by external review on 2026-08-01 — the type claimed to enforce
        what it only half-enforced."""
        raise CollapseError(
            f"MA-3.5: a Verdict is not a boolean. This one is {self.value}; "
            f"truthiness would have made it pass. Compare explicitly: "
            f"`verdict is Verdict.PASS`, or use `verdict.is_passing`."
        )

    @property
    def check_executed(self) -> bool | None:
        """Did a check run at all? The distinction MA-3.1 turns on.

        ``None`` for ``ERROR`` and ``NOT_APPLICABLE``: a technical failure may
        have occurred before the check started or half-way through it, and the
        verdict alone cannot say which. Returning ``False`` there asserted
        something the value does not carry. Where the distinction matters,
        record ``execution_status`` beside the measurement.
        """
        if self in (Verdict.PASS, Verdict.FAIL, Verdict.INCONCLUSIVE):
            return True
        if self is Verdict.NOT_MEASURED:
            return False
        return None

    @property
    def is_passing(self) -> bool:
        """Only ``PASS`` passes. Stated as a property so that no caller has to
        write the comparison — and get it wrong — themselves."""
        return self is Verdict.PASS


#: Verdicts a caller MUST handle distinctly from PASS (MA-3.4).
REQUIRES_DISTINCT_HANDLING = frozenset(
    {Verdict.NOT_MEASURED, Verdict.INCONCLUSIVE, Verdict.ERROR}
)

#: Decision outcomes permitted when nothing was measured (MA-4.3).
#: A digest a reader can recompute the shape of.
#: Digest length is a property of the algorithm, not a range across all of them.
#: A single {64,128} range accepted sha256 at 128 characters and sha512 at 64 —
#: values no implementation produces and no reader can recompute. Must stay
#: identical to the schema's `$defs.digest`; a test compares the two.
_DIGEST_LENGTHS = {"sha256": 64, "sha384": 96, "sha512": 128,
                   "blake2b": 128, "blake3": 64}
_DIGEST = re.compile(
    "|".join(f"{alg}:[0-9a-f]{{{n}}}" for alg, n in sorted(_DIGEST_LENGTHS.items())))

OUTCOMES_ALLOWED_WHEN_UNMEASURED = frozenset({"block", "escalate", "abstain"})


def _json_snapshot(value: Any, path: str = "detail",
                   active: set[int] | None = None) -> Any:
    """Return a canonical JSON tree, or raise. Validation and conversion in one.

    Two earlier versions each got half of this. The first called ``json.dumps``
    and caught the error — but ``json.dumps`` is a producer, not a validator: it
    writes ``NaN`` and silently turns a tuple into a list. The second checked
    types recursively and kept the caller's objects — but ``isinstance(x,
    Mapping)`` is true of a ``UserDict``, which the JSON encoder cannot write.
    So the check said "this is JSON" about a value the wire could not carry.

    Checking a tree and keeping a different tree is the same split that produced
    every other defect in this field's history. Here the value that survives is
    the value that was checked, built out of ``dict``, ``list`` and scalars.
    """
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        raise CollapseError(
            f"{path} is {value!r}: JSON has no literal for it, so a reader "
            "outside this process cannot receive the value you recorded.")
    if isinstance(value, (Mapping, list)):
        # `active` holds the containers on the current descent, not every one
        # seen: the same object appearing in two sibling branches is a shared
        # value and perfectly serialisable, while returning to one already open
        # is a cycle. Without this the function recursed until the interpreter
        # stopped it — a RecursionError where a docstring promises "or raise".
        if active is None:
            active = set()
        marker = id(value)
        if marker in active:
            raise CollapseError(
                f"{path} refers back to a container that already encloses it. A "
                "cycle has no JSON form, so there is no record to write.")
        active.add(marker)
        try:
            if isinstance(value, Mapping):
                out: dict[str, Any] = {}
                for key, item in value.items():
                    if not isinstance(key, str):
                        raise CollapseError(
                            f"{path} has a non-string key {key!r}. Serialisation "
                            "would convert it, so the record would carry a key "
                            "the caller never wrote.")
                    out[key] = _json_snapshot(item, f"{path}.{key}", active)
                return out
            return [_json_snapshot(item, f"{path}[{i}]", active)
                    for i, item in enumerate(value)]
        finally:
            active.discard(marker)
    if isinstance(value, tuple):
        raise CollapseError(
            f"{path} is a tuple. JSON has one sequence type, so this would be "
            "recorded as a list — a different value from the one passed. Pass a "
            "list to say so explicitly.")
    raise CollapseError(
        f"{path} is {type(value).__name__}, which has no JSON representation.")


def _freeze(value: Any) -> Any:
    """Make a canonical JSON tree unwritable, all the way down.

    The stored `detail` claimed to be a snapshot while its nested containers
    stayed open: `m.detail["nested"]["value"] = 2` changed what the next record
    said. Freezing only the top level made the claim true of one layer and false
    of the rest, which is worse than not making it — a reader checks the outside
    and concludes the inside holds.
    """
    if isinstance(value, Mapping):
        return MappingProxyType({k: _freeze(x) for k, x in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(x) for x in value)
    return value


def _thaw(value: Any) -> Any:
    """Rebuild plain JSON containers for emission.

    The frozen form cannot be written by a JSON encoder, and every call returns
    fresh objects, so a record can be edited without reaching the measurement it
    came from.
    """
    if isinstance(value, Mapping):
        return {k: _thaw(x) for k, x in value.items()}
    if isinstance(value, tuple):
        return [_thaw(x) for x in value]
    return value


@dataclass(frozen=True)
class ScopeDecision:
    """MA-3.3 — why an object lies outside the assessed scope.

    A free string is not a scope decision. It cannot be resolved by a reader, so
    it establishes nothing that distinguishes a genuine exclusion from a check
    that was never run. The reference must name a document a third party can
    fetch, and the producer must say whether it resolved at emission.

    ``resolvable: False`` is honest and it is not NOT_APPLICABLE. A pointer the
    producer could not resolve leaves the exclusion unestablished, so the honest
    status is NOT_MEASURED. The constructor enforces that here rather than
    leaving it to the schema.
    """

    ref: str
    resolvable: bool
    evaluated_version: str | None = None
    content_hash: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.ref, str) or not self.ref.strip():
            raise CollapseError("MA-3.3: a scope decision requires a reference.")
        if not isinstance(self.resolvable, bool):
            raise CollapseError(
                f"resolvable={self.resolvable!r}: this field decides whether the "
                "exclusion is established, so a truthy string is not an answer.")
        if self.evaluated_version is not None and (
                not isinstance(self.evaluated_version, str)
                or not self.evaluated_version.strip()):
            raise CollapseError("evaluated_version, where given, names a version.")
        if self.content_hash is not None and (
                not isinstance(self.content_hash, str)
                or not _DIGEST.fullmatch(self.content_hash)):
            raise CollapseError(
                f"content_hash={self.content_hash!r}: a digest a reader cannot "
                "recompute the shape of is not a digest. Expected an "
                "algorithm-prefixed lowercase hex string — an object whose "
                "__str__ happens to produce one is not one, and coercing it "
                "here would hide the difference from the record.")

    def to_record_fields(self) -> dict[str, Any]:
        out: dict[str, Any] = {"ref": self.ref, "resolvable": self.resolvable}
        if self.evaluated_version is not None:
            out["evaluated_version"] = self.evaluated_version
        if self.content_hash is not None:
            out["content_hash"] = self.content_hash
        return out


@dataclass(frozen=True)
class Measurement:
    """One measurement result, in a container that resists collapse.

    ``Measurement`` deliberately does not implement ``__bool__``. Truthiness is
    the most common route by which ``NOT_MEASURED`` becomes a pass — the value is
    non-null, so ``if result:`` succeeds — and MA-3.5 names it explicitly. Asking
    for the boolean raises rather than guessing.
    """

    verdict: Verdict
    #: MA-3.10 — where the verdict is NOT_MEASURED this states what was not
    #: measured. It MUST NOT assert an operation that did not occur.
    reason: str | None = None
    #: MA-3.3 — REQUIRED when verdict is NOT_APPLICABLE.
    scope_decision: ScopeDecision | None = None
    #: How many items the check actually examined. Zero with PASS is a defect.
    items_checked: int | None = None
    #: False where the required input was absent or unreadable (MA-3.8). None
    #: where nobody established either way — recording an unknown as a known
    #: negative is itself a claim that was not measured.
    #: MUST be None for NOT_APPLICABLE: an exclusion examines nothing.
    #: Defaults to None — unknown. A default of True was the last place in this
    #: type where a state nobody established was written as a fact, and it
    #: survived two rounds of fixing the helpers that wrap it. Each constructor
    #: below states what it actually knows.
    inputs_present: bool | None = None
    #: For NOT_MEASURED: why. See NON_MEASUREMENT_CAUSES.
    cause: str | None = None
    #: Caller-supplied context. Serialised under `profiles.reference_detail`,
    #: the schema's reserved extension point. An earlier version accepted it and
    #: emitted nothing — an API that takes data and silently drops it leaves the
    #: caller believing the record carries what it does not, which is the shape
    #: of claim this whole document exists to refuse.
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Type checks first: every invariant below reads these fields, and a
        # wrong type makes the answer meaningless rather than false. `bool` is
        # excluded from the integer check explicitly — in Python it *is* an int,
        # so `items_checked=True` would otherwise read as "one item examined".
        if not isinstance(self.verdict, Verdict):
            raise CollapseError(
                f"verdict={self.verdict!r} is not a Verdict. A string survives "
                "construction and fails at serialisation, which puts the error "
                "in the wrong place: the record is already believed by then.")
        if self.items_checked is not None and (
                isinstance(self.items_checked, bool)
                or not isinstance(self.items_checked, int)):
            raise CollapseError(
                f"items_checked={self.items_checked!r}: a count of examined "
                "objects is an integer. True reads as 1 and 1.5 counts nothing.")
        if self.reason is not None and (
                not isinstance(self.reason, str) or not self.reason.strip()):
            raise CollapseError(
                f"reason={self.reason!r}: the reason states what was or was not "
                "measured, in words a reader can check against the record. An "
                "empty one occupies the field without answering it — and the "
                "schema rejects it, so accepting it here emits a record this "
                "implementation's own validator refuses.")
        if self.scope_decision is not None and not isinstance(
                self.scope_decision, ScopeDecision):
            raise CollapseError(
                f"scope_decision={self.scope_decision!r} is not a ScopeDecision. "
                "A bare string reaches the resolvability check and raises "
                "AttributeError there — an error at the wrong boundary, blaming "
                "the reader of the field rather than its writer.")
        if self.inputs_present is not None and not isinstance(
                self.inputs_present, bool):
            raise CollapseError(
                f"inputs_present={self.inputs_present!r}: this field carries "
                "present, absent or unknown. A truthy string is none of them.")

        # Unconditional: `if self.detail:` skipped the check for every falsy
        # wrong type — None, 0, False, () were accepted and then vanished, which
        # is the silent-drop defect this field was fixed for once already.
        if not isinstance(self.detail, Mapping):
            raise CollapseError(
                f"detail={self.detail!r}: detail is a mapping of string keys to "
                "JSON values. A scalar or sequence here survives construction "
                "and fails at serialisation, or disappears without failing.")
        # Snapshot first, then validate the snapshot, then store that same
        # object. Validating `self.detail` and storing a copy of it reads the
        # caller's mapping twice, and a Mapping whose __getitem__ answers
        # differently on the second read gets a validated value past the gate
        # and an invalid one into the field. Emission catches it, but the
        # instance exists in a state its own constructor rejected — and every
        # other invariant in this type fails at construction.
        # MappingProxyType so the stored snapshot is not writable either.
        # Nested containers remain plain dict/list — `to_record_fields` rebuilds
        # and re-validates the tree on every call, so a mutation inside one
        # raises rather than reaching a record, and the emitted tree is a fresh
        # object that shares nothing with this one.
        object.__setattr__(self, "detail", _freeze(_json_snapshot(self.detail)))

        if self.verdict is Verdict.NOT_APPLICABLE and self.scope_decision is None:
            raise CollapseError(
                "MA-3.3: NOT_APPLICABLE requires a ScopeDecision naming the "
                "documented decision that placed this check out of scope. "
                "Without one it is NOT_MEASURED wearing a better name."
            )
        if self.verdict is Verdict.NOT_MEASURED and self.cause is None:
            raise CollapseError(
                "MA-3.11: NOT_MEASURED requires a non_measurement_cause. A record "
                "that does not say why nothing was measured cannot distinguish a "
                "check that never ran from an object that could not be reached.")

        if self.cause is not None and self.cause not in NON_MEASUREMENT_CAUSES:
            raise CollapseError(
                f"non_measurement_cause={self.cause!r} is not one of "
                f"{sorted(NON_MEASUREMENT_CAUSES)}. The vocabulary is closed so "
                "that the distinction survives aggregation; free text does not.")

        if self.verdict is not Verdict.NOT_MEASURED and self.cause is not None:
            raise CollapseError(
                f"a non_measurement_cause is meaningful only with NOT_MEASURED; "
                f"this record is {self.verdict.value} and would state both that a "
                "measurement was taken and why none was.")

        if (self.verdict is Verdict.NOT_APPLICABLE
                and self.scope_decision is not None
                and not self.scope_decision.resolvable):
            raise CollapseError(
                "MA-3.3: the scope decision did not resolve, so the exclusion is "
                "unestablished. The honest status is NOT_MEASURED with "
                "cause='object_unreachable'.")

        if (self.verdict is Verdict.NOT_APPLICABLE
                and self.inputs_present is not None):
            raise CollapseError(
                "MA-3.3: an out-of-scope object was not examined, so the record "
                "establishes nothing about whether its input was present. Leave "
                "inputs_present as None.")

        if (self.scope_decision is not None
                and self.verdict is not Verdict.NOT_APPLICABLE):
            raise CollapseError(
                f"a scope_decision says why an object was not assessed, so it "
                f"belongs only to NOT_APPLICABLE; this record is "
                f"{self.verdict.value} and would state both that the object was "
                "assessed and that it was out of scope.")

        if self.verdict is Verdict.NOT_APPLICABLE and self.items_checked is not None:
            raise CollapseError(
                "MA-3.3: an out-of-scope object was not examined, so there is no "
                "count of examined items to record.")

        if self.cause in ("input_absent", "input_unreadable"):
            if self.inputs_present is True:
                raise CollapseError(
                    f"cause={self.cause!r} says the required input could not be "
                    "obtained for measurement, and inputs_present=True says it "
                    "could. One of the two was not established.")
            if self.inputs_present is None:
                # The cause already established this. Derived in one place so the
                # type and the constructors that wrap it cannot drift apart —
                # which they did when the same coercion lived in a helper.
                object.__setattr__(self, "inputs_present", False)

        if self.inputs_present is False and self.verdict is not Verdict.NOT_MEASURED:
            raise CollapseError(
                f"MA-3.8: inputs_present=False says the required input could not "
                f"be obtained or read, so no measurement was taken from it and "
                f"the status is NOT_MEASURED — not {self.verdict.value}. The "
                "earlier form of this check named PASS only, which left FAIL, "
                "INCONCLUSIVE and ERROR free to report a result reached from an "
                "input the same record says was unavailable.")
        if self.items_checked is not None and self.items_checked < 0:
            raise CollapseError(
                f"items_checked={self.items_checked}: a count of examined objects "
                f"cannot be negative. The schema requires minimum 0."
            )
        if self.verdict is Verdict.PASS and self.items_checked == 0:
            raise CollapseError(
                "MA-3.9/MA-6.1: PASS over zero items is a vacuous pass. Nothing "
                "was examined, so nothing was established: use NOT_MEASURED."
            )

    def __bool__(self) -> bool:  # noqa: D105 - the docstring is the error message
        raise CollapseError(
            f"MA-3.5: a Measurement is not a boolean. This one is "
            f"{self.verdict.value}; truthiness would have made it pass. Test "
            f"`m.verdict.is_passing` if that is what you mean, and handle "
            f"NOT_MEASURED, INCONCLUSIVE and ERROR separately (MA-3.4)."
        )

    def __or__(self, other: Any) -> Any:
        raise CollapseError(
            "MA-3.5: `measurement or default` substitutes a passing value for a "
            "verdict that is not passing. Branch on m.verdict instead."
        )

    def to_record_fields(self) -> dict[str, Any]:
        """The subset of a decision record this measurement determines."""
        out: dict[str, Any] = {"measurement_status": self.verdict.value}
        if self.reason is not None:
            out["reason"] = self.reason
        if self.scope_decision is not None:
            out["scope_decision"] = self.scope_decision.to_record_fields()
        measured: dict[str, Any] = {}
        if self.inputs_present is not None:
            measured["inputs_present"] = self.inputs_present
        if self.items_checked is not None:
            measured["items_checked"] = self.items_checked
        if measured:
            out["measured"] = measured
        if self.cause is not None:
            out["non_measurement_cause"] = self.cause
        if self.detail:
            # Re-validated because `detail` is reachable through the instance,
            # and deep-copied so the emitted record and the measurement do not
            # share nested objects — MA-8.4 forbids a recorded payload changing
            # after the fact, and aliasing is one way it does.
            # No re-validation: the stored tree cannot have changed, and a
            # thaw produces fresh containers each time.
            out["profiles"] = {"reference_detail": _thaw(self.detail)}
        return out


# ── constructors ─────────────────────────────────────────────────────────────
# Named so that the honest result is the convenient one to write.

def merge_record_fields(record: Mapping[str, Any],
                        measurement: Measurement) -> dict[str, Any]:
    """Fold a measurement into a record without discarding other profiles.

    ``to_record_fields()`` returns the subset a measurement determines, so the
    natural use is ``record.update(fields)`` — and that replaces `profiles`
    wholesale, dropping any a deployment had already put there. The subset is
    correct and the merge is the lossy part, so the merge is what gets a
    function.
    """
    if not isinstance(record, Mapping):
        raise CollapseError(
            f"record={record!r} is not a mapping, so there is nothing to merge "
            "into. Reaching `.get` on it raises somewhere inside this function, "
            "which reports the fault as the merger's rather than the caller's.")
    if not isinstance(measurement, Measurement):
        raise CollapseError(
            f"measurement={measurement!r} is not a Measurement.")
    fields = dict(measurement.to_record_fields())
    profiles = fields.pop("profiles", None)
    existing = record.get("profiles", {})
    if not isinstance(existing, Mapping):
        raise CollapseError(
            f"record['profiles']={existing!r} is not a mapping. Reaching into it "
            "raises inside this function, which reports the caller's malformed "
            "record as a fault of the merge.")
    if profiles and "reference_detail" in existing:
        raise CollapseError(
            "profiles.reference_detail is already present in this record. "
            "Overwriting it would replace one measurement's context with "
            "another's and leave no trace that the first existed; merge the two "
            "deliberately, or record the second measurement separately.")
    merged = {**record, **fields}
    if profiles:
        merged["profiles"] = {**existing, **profiles}
    return merged


def measured_pass(items_checked: int, **detail: Any) -> Measurement:
    """A check ran over ``items_checked`` items and its criterion was met."""
    return Measurement(Verdict.PASS, items_checked=items_checked,
                       inputs_present=True, detail=detail)


def measured_fail(reason: str, items_checked: int | None = None, **detail: Any) -> Measurement:
    """A check ran and its criterion was not met. This is a *measurement*."""
    return Measurement(Verdict.FAIL, reason=reason, inputs_present=True,
                       items_checked=items_checked,
                       detail=detail)


#: Why a measurement did not happen. `NOT_MEASURED` alone does not say, and the
#: reasons carry different remedies.
NON_MEASUREMENT_CAUSES = frozenset({
    "not_executed",        # the component never ran
    "suppressed_by_tier",  # a cheaper check decided this one was unnecessary
    "input_absent",        # the required input does not exist
    "input_unreadable",    # it exists and could not be read
    "object_unreachable",  # the check ran but could not reach what it examines
    "unknown",
})


def not_measured(reason: str, *, cause: str = "unknown",
                 inputs_present: bool | None = None, **detail: Any) -> Measurement:
    """The check did not run, or could not reach what it was to examine.

    MA-3.10: ``reason`` states what was not measured. It must not describe an
    operation that did not occur.

    ``inputs_present`` defaults to **None**, not False. An earlier version wrote
    False unconditionally, which asserted an absence nobody had established: a
    tiered evaluator that skipped this check, or a component that never entered
    the execution path, says nothing about whether the input existed. Recording
    an unknown as a known negative is the defect this specification is about,
    committed by its own helper.
    """
    if cause not in NON_MEASUREMENT_CAUSES:
        raise CollapseError(
            f"cause={cause!r} is not one of {sorted(NON_MEASUREMENT_CAUSES)}. "
            f"'unknown' is available and honest; inventing a cause is not."
        )
    return Measurement(Verdict.NOT_MEASURED, reason=reason,
                       inputs_present=inputs_present, items_checked=None,
                       cause=cause, detail=detail)


def inconclusive(reason: str, items_checked: int, **detail: Any) -> Measurement:
    """The check ran; the evidence it obtained did not decide (MA-3.2)."""
    return Measurement(Verdict.INCONCLUSIVE, reason=reason, inputs_present=True,
                       items_checked=items_checked, detail=detail)


def errored(reason: str, *, inputs_present: bool | None = None,
            items_checked: int | None = None, **detail: Any) -> Measurement:
    """The check could not complete for a technical reason.

    ``inputs_present`` defaults to **None**. A crash may occur before the input
    was read, after it was read, or at a point the caller cannot determine, so
    the honest default is that the record does not say. Two earlier versions each
    picked a side — False, then True — and both asserted an input state nothing
    had established. A caller that does know passes the value explicitly.
    """
    return Measurement(Verdict.ERROR, reason=reason, inputs_present=inputs_present,
                       items_checked=items_checked, detail=detail)


def not_applicable(scope_decision: ScopeDecision, **detail: Any) -> Measurement:
    """Out of scope by a documented decision (MA-3.3)."""
    if not isinstance(scope_decision, ScopeDecision):
        raise CollapseError(
            "MA-3.3: not_applicable() takes a ScopeDecision, not a string. A "
            "reference a reader cannot resolve does not establish an exclusion.")
    if not scope_decision.resolvable:
        raise CollapseError(
            "MA-3.3: the scope decision did not resolve, so the exclusion is "
            "unestablished. Use not_measured(cause='object_unreachable').")
    return Measurement(Verdict.NOT_APPLICABLE, scope_decision=scope_decision,
                       inputs_present=None, detail=detail)


# ── aggregation ──────────────────────────────────────────────────────────────

#: Severity for aggregation. Higher wins. Deliberately places NOT_MEASURED above
#: FAIL: a run that failed a check told you something, and a run that never
#: performed it told you less.
_SEVERITY: dict[Verdict, int] = {
    Verdict.NOT_APPLICABLE: 0,
    Verdict.PASS: 1,
    Verdict.INCONCLUSIVE: 2,
    Verdict.FAIL: 3,
    Verdict.NOT_MEASURED: 4,
    Verdict.ERROR: 5,
}


@dataclass(frozen=True)
class AggregateResult:
    """Counts per verdict, not one verdict standing for many.

    ``conformance-requirements.yaml`` forbids reporting a single overall
    PASS/FAIL over a set, for the reason visible here: severity-ranking collapses
    a known FAIL underneath a NOT_MEASURED and the failure stops being visible.
    An aggregate reports the distribution; a *policy* turns that into a decision,
    and that is a separate function with its own name.
    """

    counts: Mapping[Verdict, int]
    total: int

    def __post_init__(self) -> None:
        """The distribution is the result, so it is not left writable.

        `frozen=True` freezes the field, not the dict behind it. Anyone holding
        the result could write `counts[NOT_MEASURED] = 0; counts[PASS] = 1` and
        `any_unmeasured` would go quiet — the exact conversion this module
        exists to refuse, performed on the module's own output.
        """
        if not isinstance(self.counts, Mapping):
            raise CollapseError("counts is a mapping of Verdict to count.")
        if isinstance(self.total, bool) or not isinstance(self.total, int):
            raise CollapseError(f"total={self.total!r} is not an integer.")
        if self.total < 0:
            raise CollapseError(f"total={self.total}: a count of measurements "
                                "cannot be negative.")
        snapshot = {verdict: 0 for verdict in Verdict}
        for verdict, count in self.counts.items():
            if not isinstance(verdict, Verdict):
                raise CollapseError(
                    f"{verdict!r} is not a Verdict, so it names no measurement "
                    "status the algebra recognises.")
            if isinstance(count, bool) or not isinstance(count, int):
                raise CollapseError(
                    f"count for {verdict.value} is {count!r}, not an integer.")
            if count < 0:
                raise CollapseError(
                    f"count for {verdict.value} is {count}: negative.")
            snapshot[verdict] = count
        if sum(snapshot.values()) != self.total:
            raise CollapseError(
                f"counts sum to {sum(snapshot.values())} and total says "
                f"{self.total}. One of the two was not measured.")
        object.__setattr__(self, "counts", MappingProxyType(snapshot))

    def __bool__(self) -> bool:
        raise CollapseError(
            "MA-3.5: an AggregateResult is not a boolean. Read `counts`, or ask "
            "a named policy function for a decision."
        )

    @property
    def statuses_present(self) -> frozenset[Verdict]:
        return frozenset(v for v, n in self.counts.items() if n)

    @property
    def any_unmeasured(self) -> bool:
        """True where anything in the set was not measured, inconclusive or errored."""
        return bool(self.statuses_present & REQUIRES_DISTINCT_HANDLING)

    def summary(self) -> str:
        parts = [f"{v.value}={n}" for v, n in self.counts.items() if n]
        return f"{self.total} measurement(s): " + (", ".join(parts) or "none")


def aggregate(measurements: Iterable[Measurement]) -> AggregateResult:
    """Count measurements by verdict. Reports the distribution, decides nothing."""
    counts: dict[Verdict, int] = {v: 0 for v in Verdict}
    total = 0
    for m in measurements:
        if not isinstance(m, Measurement):
            raise CollapseError(
                "MA-3.5: aggregate() takes Measurement objects. Passing raw "
                "booleans is how an unmeasured check becomes a passing total."
            )
        counts[m.verdict] += 1
        total += 1
    return AggregateResult(counts=counts, total=total)


def worst_case_policy(measurements: Iterable[Measurement]) -> Verdict:
    """Aggregate several measurements into one verdict, without collapsing.

    MA-3.5. The rule an aggregate most often breaks is not that it maps
    ``NOT_MEASURED`` to ``PASS`` deliberately, but that it counts failures and
    reports the remainder as passing. This function cannot do that: any verdict
    more severe than ``PASS`` propagates.

    An empty input yields ``NOT_MEASURED``, never ``PASS`` — aggregating nothing
    establishes nothing (MA-6.1).

    **This is a deployment policy, not a conformance aggregate.** Reducing a set
    to one verdict hides a known ``FAIL`` underneath a ``NOT_MEASURED``, and the
    conformance requirements forbid reporting one overall result. Use
    :func:`aggregate` for anything that reports; use this only where a caller
    genuinely needs a single worst-case value to act on. It was named ``combine``
    until 2026-08-01, which read like the aggregate and was not one.
    """
    worst: Verdict | None = None
    for m in measurements:
        if not isinstance(m, Measurement):
            raise CollapseError(
                "MA-3.5: worst_case_policy() takes Measurement objects. Passing raw "
                "booleans or truthy values is how an unmeasured check becomes a "
                "passing aggregate."
            )
        if worst is None or _SEVERITY[m.verdict] > _SEVERITY[worst]:
            worst = m.verdict
    if worst is None:
        return Verdict.NOT_MEASURED
    if worst is Verdict.NOT_APPLICABLE:
        # every constituent was out of scope; the aggregate is too
        return Verdict.NOT_APPLICABLE
    return worst


def require_handled(handled: Iterable[Verdict]) -> None:
    """MA-3.4. Assert that a consumer's branch set covers every non-passing value.

    Call this from a consumer's tests, passing the verdicts its code actually
    branches on.

    The first version took a verdict as well and only complained when *that*
    verdict was unhandled — so ``require_handled(Verdict.PASS, handled=[])``
    passed while no non-passing branch existed at all. The check is about the
    branch set, not about one value passing through it.
    """
    missing = REQUIRES_DISTINCT_HANDLING - set(handled)
    if missing:
        raise CollapseError(
            f"MA-3.4: no branch distinct from PASS handles "
            f"{sorted(v.value for v in missing)}. A consumer must handle "
            f"NOT_MEASURED, INCONCLUSIVE and ERROR separately."
        )


def parse(value: str) -> Verdict:
    """MA-3.6. Turn a wire value into a Verdict, failing closed on the unknown.

    A consumer that receives an unrecognised status must not fall through to a
    passing path. Raising is the fail-closed behaviour; a caller that prefers
    ``ERROR`` should catch this and record it.
    """
    try:
        return Verdict(value)
    except ValueError as exc:
        raise CollapseError(
            f"MA-3.6: unrecognised measurement_status {value!r}. A consumer must "
            f"fail closed or record ERROR; it must not fall through to a passing "
            f"path. Known values: {sorted(v.value for v in Verdict)}."
        ) from exc


#: The decision vocabulary of Section 4.1. Closed, so that an outcome this
#: function does not recognise is an error rather than a permission.
DECISION_OUTCOMES = frozenset({"allow", "block", "attenuate", "escalate", "abstain"})


def decision_outcome_permitted(verdict: Verdict, outcome: str) -> bool:
    """MA-4.3. May this decision outcome accompany this measurement status?

    Both arguments are checked before either is used. The identity test below
    is false for the *string* ``"NOT_MEASURED"``, so a caller passing a status
    they had already serialised fell through to ``return True`` and was told
    that allowing an unmeasured decision was permitted — this function failing
    open on the one rule it exists to enforce. An unrecognised outcome did the
    same. Neither is answered with ``False``, which would be a verdict about a
    question that was not asked; both raise.
    """
    if not isinstance(verdict, Verdict):
        raise CollapseError(
            f"verdict={verdict!r} is not a Verdict. The string form of a status "
            "is not the status: it silently misses every identity test here.")
    if not isinstance(outcome, str) or outcome not in DECISION_OUTCOMES:
        raise CollapseError(
            f"decision_outcome={outcome!r} is not one of "
            f"{sorted(DECISION_OUTCOMES)}. Answering `permitted` about an "
            "outcome that means nothing would permit it.")
    if verdict is Verdict.NOT_MEASURED:
        return outcome in OUTCOMES_ALLOWED_WHEN_UNMEASURED
    return True

