"""Paired-control selectivity probe — Measurement Axioms v1.0, MA-6.1.

Normative source: ``MEASUREMENT_AXIOMS_SPECIFICATION.md`` §6.

WHY THIS IS PAIRED
------------------
The first version of this module tested one degenerate input at a time and asked
only "did a passing-looking value come back?". External review on 2026-08-01
showed that both the module and the requirement behind it were wrong, in the same
way.

A component that correctly implements the axioms returns ``NOT_MEASURED`` for the
empty collection, for the absent baseline, for the unreadable source — the same
value every time. It is *invariant across the degenerate class*, which the
original wording of MA-6.1 would have read as a failure of selectivity. The
requirement as written condemned exactly the behaviour it demanded.

Selectivity is not invariance-versus-variance over one class. It is: **does the
mapping distinguish inputs it is required to distinguish?** So every case here
carries a *control* input alongside its degenerate variant, and the test is that
the two produce the outcomes their class requires — the degenerate one in
particular must not inherit the control's passing result.

WHAT THIS MODULE REPORTS
------------------------
A ``Verdict``, not a boolean. The earlier version exposed ``conformant: bool``
computed over observations, treating an unexercised case as conformant — so a
probe that ran nothing reported success while its own summary said
``NOTHING WAS EXERCISED``. That is the vacuous pass this doctrine exists to
name, produced by its own reference implementation. It is now impossible to write
that: ``ProbeReport.result`` is one of PASS / FAIL / NOT_MEASURED / INCONCLUSIVE /
ERROR, and zero coverage yields ``NOT_MEASURED``.
"""
from __future__ import annotations

import inspect
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from verdict import Measurement, Verdict

#: Optional translator from a legacy return shape to a Verdict. Supplying one is
#: an explicit act: an adapted result is an *interpretation* of what the target
#: returned, and the report says so.
Adapter = Callable[[Any], Verdict | None]

#: What a control input may legitimately come back as. A control the target
#: cannot measure means the case was mis-built, not that the target failed.
CONTROL_STATUSES = frozenset({Verdict.PASS, Verdict.FAIL, Verdict.INCONCLUSIVE})

#: What the probe itself may conclude about one case. NOT_APPLICABLE is not
#: here: it describes an object outside an assessed scope, and a probe case is
#: never outside the probe's scope.
PROBE_STATUSES = frozenset({Verdict.PASS, Verdict.FAIL, Verdict.NOT_MEASURED,
                            Verdict.INCONCLUSIVE, Verdict.ERROR})


@dataclass(frozen=True)
class SelectivityCase:
    """A control input paired with the degenerate variant it must be told apart from."""

    name: str
    #: An input the target can genuinely measure.
    control: Any
    #: The degenerate variant: empty, absent, unreadable, unset.
    degenerate: Any
    #: What the degenerate variant MUST yield. Almost always NOT_MEASURED.
    expects_on_degenerate: Verdict
    rationale: str
    #: Verdicts the control input may legitimately yield. A control that itself
    #: comes back NOT_MEASURED means the case was mis-constructed, not that the
    #: target failed — reported as INCONCLUSIVE.
    control_may_be: frozenset[Verdict] = frozenset({Verdict.PASS, Verdict.FAIL,
                                                    Verdict.INCONCLUSIVE})

    def __post_init__(self) -> None:
        """A malformed case reaches `expects_on_degenerate.value` and dies there.

        The probe then raises AttributeError from inside its own loop — an error
        about the case, reported as a crash of the tool reading it.
        """
        if not isinstance(self.name, str) or not self.name.strip():
            raise TypeError("a case is identified by a name with text in it.")
        if not isinstance(self.expects_on_degenerate, Verdict):
            raise TypeError(
                f"expects_on_degenerate={self.expects_on_degenerate!r} is not a "
                "Verdict, so there is nothing to compare the target against.")
        if not isinstance(self.rationale, str) or not self.rationale.strip():
            raise TypeError("a case states why its degenerate variant is one.")
        allowed = frozenset(self.control_may_be)
        if not allowed or not all(isinstance(x, Verdict) for x in allowed):
            raise TypeError("control_may_be holds Verdict values, at least one.")
        if not allowed <= CONTROL_STATUSES:
            raise TypeError(
                f"control_may_be={sorted(x.value for x in allowed)}: a control "
                "input is one the target can genuinely measure, so it may come "
                f"back {sorted(x.value for x in CONTROL_STATUSES)} and nothing "
                "else. NOT_MEASURED from a control means the case was built "
                "wrong, which is INCONCLUSIVE, not a result about the target.")
        if self.expects_on_degenerate in allowed:
            raise TypeError(
                f"expects_on_degenerate={self.expects_on_degenerate.value} is "
                "also permitted for the control, so a target returning it for "
                "both inputs would pass a test of whether it tells them apart. "
                "The required degenerate status must be one the control cannot "
                "have.")
        object.__setattr__(self, "control_may_be", allowed)


EMPTY_COLLECTION = SelectivityCase(
    name="empty_collection",
    control=[{"id": 1}, {"id": 2}],
    degenerate=[],
    expects_on_degenerate=Verdict.NOT_MEASURED,
    rationale="TV-1: verifying an empty collection checks zero items and "
              "establishes nothing.",
)

ABSENT_BASELINE = SelectivityCase(
    name="absent_baseline",
    control="sha256:" + "a" * 64,
    degenerate=None,
    expects_on_degenerate=Verdict.NOT_MEASURED,
    rationale="TV-2: with no baseline there is nothing to compare against; "
              "coercing None to a passing branch is how an unmeasured comparison "
              "becomes a positive result.",
)

EMPTY_MAPPING = SelectivityCase(
    name="empty_mapping",
    control={"k": "v"},
    degenerate={},
    expects_on_degenerate=Verdict.NOT_MEASURED,
    rationale="TV-3: an empty denominator yields no metric.",
)

UNREADABLE_SOURCE = SelectivityCase(
    name="unreadable_source",
    control=Path(__file__),
    degenerate=Path("/nonexistent/measurement-axioms/probe/absent"),
    expects_on_degenerate=Verdict.NOT_MEASURED,
    rationale="TV-4: an unreadable source must not produce a fabricated value.",
)

DEFAULT_CASES: tuple[SelectivityCase, ...] = (
    EMPTY_COLLECTION, ABSENT_BASELINE, EMPTY_MAPPING, UNREADABLE_SOURCE,
)


class NativeClassificationError(RuntimeError):
    """Reading this specification's own vocabulary out of a value failed."""


class AdapterClassificationError(RuntimeError):
    """The adapter raised, or answered with something that is not a Verdict."""


def classify_with_provenance(value: Any,
                             adapter: Adapter | None = None) -> tuple[Verdict | None, bool]:
    """As :func:`classify`, and whether the adapter was the one that answered.

    Failures are raised as one of the two types above, so the caller knows which
    component failed because the failure said so. An earlier version caught
    everything in one place and then re-examined the payloads to work out where
    it had come from — a guess, and a re-entrant one: inspecting a mapping whose
    `__contains__` raises re-raised the same error out of the handler, and the
    probe died instead of reporting ERROR.
    """
    if isinstance(value, (Measurement, Verdict)):
        return classify(value, None), False
    if isinstance(value, Mapping):
        try:
            native = "measurement_status" in value
        except Exception as exc:  # noqa: BLE001
            raise NativeClassificationError(str(exc)) from exc
        if native:
            try:
                return classify(value, None), False
            except Exception as exc:  # noqa: BLE001
                raise NativeClassificationError(str(exc)) from exc
    if adapter is None:
        return None, False
    try:
        adapted = adapter(value)
    except Exception as exc:  # noqa: BLE001
        raise AdapterClassificationError(str(exc)) from exc
    if adapted is None:
        # Called, and produced no status: nothing in the record came from it.
        return None, False
    if not isinstance(adapted, Verdict):
        raise AdapterClassificationError(
            f"the adapter returned {adapted!r}, which is not a Verdict or None")
    return adapted, True


def classify(value: Any, adapter: Adapter | None = None) -> Verdict | None:
    """Read a Verdict out of what a target returned, or admit that we cannot.

    Recognises the vocabulary of this specification natively. Anything else —
    a bare ``True``, ``"ok"``, ``{"valid": ...}`` — is a legacy shape whose
    meaning we are not entitled to guess, and returns ``None`` unless an adapter
    is supplied. ``None`` becomes ``INCONCLUSIVE``, never ``PASS``.
    """
    if isinstance(value, Measurement):
        return value.verdict
    if isinstance(value, Verdict):
        return value
    if isinstance(value, Mapping) and "measurement_status" in value:
        try:
            return Verdict(value["measurement_status"])
        except ValueError:
            return None
    if adapter is not None:
        adapted = adapter(value)
        if adapted is None:
            return None
        if not isinstance(adapted, Verdict):
            raise TypeError(
                f"An adapter must return a Verdict or None; got "
                f"{type(adapted).__name__}. Guessing what it meant would be the "
                f"collapse this module exists to prevent."
            )
        return adapted
    return None


@dataclass(frozen=True)
class Observation:
    """What the target did on one case."""

    case: SelectivityCase
    #: The probe's own verdict on this case.
    probe_status: Verdict
    #: What the target returned on the degenerate input, once classified.
    target_status: Verdict | None = None
    control_status: Verdict | None = None
    note: str = ""
    adapted: bool = False

    def __post_init__(self) -> None:
        """`ProbeReport.result` reads these, so a wrong type here is a verdict.

        `Observation(case, probe_status="PASS")` built cleanly and the report
        answered PASS — a string that no branch of `result` recognises, falling
        through to the passing one. The vacuous pass, inside the probe written
        to catch it.
        """
        if not isinstance(self.case, SelectivityCase):
            raise TypeError("case must be a SelectivityCase.")
        if not isinstance(self.probe_status, Verdict):
            raise TypeError(
                f"probe_status={self.probe_status!r} is not a Verdict. A string "
                "reaches no branch of `result` and lands on the passing one.")
        if self.probe_status not in PROBE_STATUSES:
            raise TypeError(
                f"probe_status={self.probe_status.value} is not one of "
                f"{sorted(x.value for x in PROBE_STATUSES)}. NOT_APPLICABLE "
                "describes an object outside an assessed scope, which a probe "
                "case never is — and it reached no branch of `result`, so it "
                "arrived at the passing one.")
        for name in ("target_status", "control_status"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, Verdict):
                raise TypeError(f"{name} must be a Verdict or None.")
        if not isinstance(self.note, str):
            raise TypeError("note must be a string.")
        if not isinstance(self.adapted, bool):
            raise TypeError("adapted must be a bool.")


def _append(report: "ProbeReport", observation: "Observation") -> None:
    """Add an observation while the probe is still assembling the report.

    The report is frozen and its observations are a tuple, so building one takes
    an explicit function rather than `.append()`. That is the point: after the
    probe returns, there is no supported way to change what it observed.
    """
    object.__setattr__(report, "observations", report.observations + (observation,))
    if observation.adapted:
        object.__setattr__(report, "adapter_used", True)


@dataclass(frozen=True)
class ProbeReport:
    """One target's result. Carries a Verdict, never a boolean."""

    target: str
    observations: tuple[Observation, ...] = ()
    #: Whether an adapter actually answered for at least one observation.
    #: Derived from the observations rather than from whether one was supplied:
    #: a report whose target returned native Measurements said "via adapter"
    #: because one had been passed and never called.
    adapter_used: bool = False

    def __post_init__(self) -> None:
        """`result` is derived from `observations`, so the list is not left open.

        A caller holding a report could clear the list and watch PASS become
        NOT_MEASURED, or append an observation the probe never made. The same
        defect as a writable aggregate: a frozen dataclass freezes the field,
        not the container behind it.
        """
        if not isinstance(self.target, str) or not self.target.strip():
            raise TypeError("target names the thing probed; it must have text.")
        if not isinstance(self.adapter_used, bool):
            raise TypeError(
                f"adapter_used={self.adapter_used!r} is not a bool. A truthy "
                "string reads as 'via adapter' in the summary.")
        observations = tuple(self.observations)
        for o in observations:
            if not isinstance(o, Observation):
                raise TypeError(
                    f"observations carry Observation objects; found "
                    f"{type(o).__name__}. `result` reads their statuses.")
        object.__setattr__(self, "observations", observations)
        # Derived, not merged with what the caller passed: `self.adapter_used or
        # ...` let a hand-built report with no observations at all claim "via
        # adapter". Provenance is a fact about the observations or it is nothing.
        object.__setattr__(self, "adapter_used",
                           any(o.adapted for o in observations))

    @property
    def result(self) -> Verdict:
        """MA-6.1 outcome for this target.

        Zero exercised cases is ``NOT_MEASURED``. It was ``conformant: True`` in
        the first version of this file, which is the defect this doctrine names.
        """
        if not self.observations:
            return Verdict.NOT_MEASURED
        statuses = [o.probe_status for o in self.observations]
        if Verdict.ERROR in statuses:
            return Verdict.ERROR
        if Verdict.FAIL in statuses:
            return Verdict.FAIL
        exercised = [s for s in statuses if s is not Verdict.NOT_MEASURED]
        if not exercised:
            return Verdict.NOT_MEASURED
        if Verdict.INCONCLUSIVE in statuses or Verdict.NOT_MEASURED in statuses:
            return Verdict.INCONCLUSIVE
        unaccounted = set(statuses) - {Verdict.PASS}
        if unaccounted:
            # Reached only if PROBE_STATUSES and this chain disagree. `PASS` is
            # the wrong place to land when the branches above have not decided:
            # the last clause of a decision chain should never be the permissive
            # one, or every value the chain does not know becomes a pass.
            return Verdict.ERROR
        return Verdict.PASS

    @property
    def coverage(self) -> tuple[int, int]:
        exercised = sum(1 for o in self.observations
                        if o.probe_status is not Verdict.NOT_MEASURED)
        return exercised, len(self.observations)

    def summary(self) -> str:
        exercised, attempted = self.coverage
        lines = [f"{self.target}: {self.result.value} "
                 f"({exercised}/{attempted} cases exercised"
                 f"{', via adapter' if self.adapter_used else ''})"]
        for o in self.observations:
            got = o.target_status.value if o.target_status is not None else "unclassified"
            lines.append(f"  [{o.probe_status.value:13s}] {o.case.name}: {o.note}"
                         f"  (degenerate -> {got})")
        if exercised == 0:
            lines.append("  Nothing was exercised. This report establishes nothing "
                         "about the target: NOT_MEASURED, not a pass.")
        return "\n".join(lines)


class _SideFailure(Exception):
    """Which side failed, and which component failed on it."""

    def __init__(self, note: str, from_adapter: bool) -> None:
        super().__init__(note)
        self.note = note
        self.from_adapter = from_adapter


def _classify_side(side: str, payload: Any,
                   adapter: Adapter | None) -> tuple[Verdict | None, bool]:
    """Classify one half of the pair, naming the component that failed."""
    try:
        return classify_with_provenance(payload, adapter)
    except AdapterClassificationError as exc:
        raise _SideFailure(
            f"the adapter failed on the {side} input: {exc}", True) from exc
    except NativeClassificationError as exc:
        raise _SideFailure(
            f"reading the native status of the {side} input failed: {exc}",
            False) from exc
    except Exception as exc:  # noqa: BLE001
        raise _SideFailure(
            f"classifying the {side} input failed: "
            f"{type(exc).__name__}: {exc}", False) from exc


def _call(target: Callable[..., Any], name: str, value: Any,
          extra: dict[str, Any]) -> tuple[str, Any]:
    """Return ('ok'|'rejected'|'raised', payload).

    Binding is checked before the call, so a `TypeError` from inside the target
    is not read as a signature that refused the case. The earlier version
    caught every TypeError and reported `NOT_MEASURED — signature rejected`,
    turning a genuine crash into "not tested": a failure recorded as an absence,
    which is the substitution this whole document exists to name.
    """
    # A positional-only parameter cannot be passed by name, so binding it as a
    # keyword failed and the target was reported as refusing the case. It had
    # refused the *call form*, not the input — a fact about the probe, recorded
    # as a fact about the target.
    positional = False
    try:
        sig = inspect.signature(target)
        param = sig.parameters.get(name)
        positional = (param is not None
                      and param.kind is inspect.Parameter.POSITIONAL_ONLY)
        if positional:
            sig.bind(value, **extra)
        else:
            sig.bind(**{name: value}, **extra)
    except TypeError as exc:
        return "rejected", exc
    except (ValueError, AttributeError):
        pass                       # not introspectable; the call decides
    try:
        if positional:
            return "ok", target(value, **extra)
        return "ok", target(**{name: value}, **extra)
    except Exception as exc:  # noqa: BLE001 — the target ran, so this is ERROR
        return "raised", exc


def probe(
    target: Callable[..., Any],
    cases: Iterable[SelectivityCase] = DEFAULT_CASES,
    *,
    argument: str | None = None,
    extra_kwargs: dict[str, Any] | None = None,
    adapter: Adapter | None = None,
) -> ProbeReport:
    """Run each case's control and degenerate inputs and compare the outcomes."""
    report = ProbeReport(target=getattr(target, "__qualname__", repr(target)),
                         adapter_used=False)
    if not callable(target):
        raise TypeError(
            f"target={target!r} is not callable. A non-callable was reported as "
            "'signature could not be inspected' — a malformed probe call, "
            "recorded as a fact about a target.")
    if extra_kwargs is not None and not isinstance(extra_kwargs, Mapping):
        raise TypeError(
            f"extra_kwargs={extra_kwargs!r} is not a Mapping. `dict(x or {{}})` "
            "turned every falsy wrong type into an empty config and probed on "
            "without it — the caller's configuration dropped in silence.")
    extra = dict(extra_kwargs or {})
    bad_keys = [k for k in extra if not isinstance(k, str)]
    if bad_keys:
        raise TypeError(
            f"extra_kwargs keys are argument names: {bad_keys!r} cannot be one, "
            "and the call would fail as a signature mismatch.")

    try:
        params = list(inspect.signature(target).parameters)
    except (TypeError, ValueError):
        params = []
    if argument is not None:
        if not isinstance(argument, str) or not argument.strip():
            raise TypeError(
                f"argument={argument!r} names the parameter the cases are passed "
                "through, so it is a non-empty string. `argument or params[0]` "
                "treated every falsy value as 'not given' and silently probed a "
                "different parameter — then reported PASS about it.")
        name = argument
    else:
        name = params[0] if params else None
    if name is not None and name in (extra or {}):
        raise TypeError(
            f"extra_kwargs carries {name!r}, which is the argument the cases are "
            "passed through. Every control and degenerate input would be "
            "replaced by it, and the probe would report a result about inputs it "
            "never sent.")
    try:
        base_extra = deepcopy(dict(extra or {}))
    except Exception as exc:  # noqa: BLE001
        raise TypeError(
            f"extra_kwargs could not be copied ({type(exc).__name__}), so the "
            "control and degenerate calls cannot be given independent ones."
        ) from exc

    for case in cases:
        if name is None:
            _append(report, Observation(
                case, Verdict.NOT_MEASURED,
                note="target signature could not be inspected; case not exercised"))
            continue

        # Fresh inputs per invocation. A target that appends to the list it is
        # given otherwise edits the module-level case itself, and every probe
        # after it in the process tests something else — results that depend on
        # what ran before them.
        try:
            control_input = deepcopy(case.control)
            degenerate_input = deepcopy(case.degenerate)
        except Exception as exc:  # noqa: BLE001
            _append(report, Observation(
                case, Verdict.ERROR,
                note=f"the case inputs could not be isolated for this call "
                     f"({type(exc).__name__}), so running it would let the "
                     f"target alter the case"))
            continue
        # A fresh `extra` per call: a target that appends to something it was
        # handed otherwise runs the degenerate input under conditions the
        # control input created, and the pair is no longer a pair.
        c_kind, c_payload = _call(target, name, control_input, deepcopy(base_extra))
        d_kind, d_payload = _call(target, name, degenerate_input, deepcopy(base_extra))

        if c_kind == "rejected" or d_kind == "rejected":
            _append(report, Observation(
                case, Verdict.NOT_MEASURED,
                note="signature rejected the case inputs; case not exercised"))
            continue

        if d_kind == "raised":
            _append(report, Observation(
                case, Verdict.ERROR,
                note=f"raised {type(d_payload).__name__} on the degenerate input — "
                     f"a crash is not a conformance result"))
            continue
        if c_kind == "raised":
            _append(report, Observation(
                case, Verdict.ERROR,
                note=f"raised {type(c_payload).__name__} on the CONTROL input, so "
                     f"the pair could not be compared"))
            continue

        try:
            control_status, c_adapted = _classify_side(
                "control", c_payload, adapter)
            target_status, d_adapted = _classify_side(
                "degenerate", d_payload, adapter)
            adapted = c_adapted or d_adapted
        except _SideFailure as failure:
            _append(report, Observation(
                case, Verdict.ERROR, adapted=failure.from_adapter,
                note=failure.note))
            continue

        if control_status is None:
            _append(report, Observation(
                case, Verdict.INCONCLUSIVE, target_status=target_status,
                control_status=None, adapted=adapted,
                note=f"the control result {c_payload!r} carries no interpretable "
                     f"measurement status, so the pair cannot establish "
                     f"selectivity — whatever the degenerate variant returned"))
            continue

        if target_status is None:
            _append(report, Observation(
                case, Verdict.INCONCLUSIVE, target_status=None,
                control_status=control_status, adapted=adapted,
                note=f"returned {d_payload!r}, which carries no measurement status. "
                     f"Supply an adapter to state what that shape means — it will "
                     f"not be guessed"))
            continue

        if control_status is not None and control_status not in case.control_may_be:
            _append(report, Observation(
                case, Verdict.INCONCLUSIVE, target_status=target_status,
                control_status=control_status, adapted=adapted,
                note=f"the control input itself yielded {control_status.value}, so "
                     f"this case does not distinguish anything; construct a control "
                     f"the target can measure"))
            continue

        if target_status is case.expects_on_degenerate:
            _append(report, Observation(
                case, Verdict.PASS, target_status=target_status,
                control_status=control_status, adapted=adapted,
                note=f"control -> {control_status.value if control_status is not None else '?'}, "
                     f"degenerate -> {target_status.value} as required"))
        else:
            _append(report, Observation(
                case, Verdict.FAIL, target_status=target_status,
                control_status=control_status, adapted=adapted,
                note=f"degenerate input yielded {target_status.value}, required "
                     f"{case.expects_on_degenerate.value} — {case.rationale}"))

    return report


def probe_all(
    targets: Sequence[Callable[..., Any]],
    cases: Iterable[SelectivityCase] = DEFAULT_CASES,
    **kwargs: Any,
) -> list[ProbeReport]:
    """Probe several targets. Returns one report each and aggregates nothing.

    A suite-level "all good" is the shape MA-3.5 forbids: it reports the
    remainder as passing.
    """
    # Materialised once: a generator is exhausted by the first target, and the
    # rest are probed against nothing while reporting NOT_MEASURED — which reads
    # as "no coverage" rather than "the cases were already consumed".
    materialised = tuple(cases)
    return [probe(t, materialised, **kwargs) for t in targets]
