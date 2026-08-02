"""The reference implementation must enforce what the specification requires.

`verdict.py` and `degenerate.py` are the executable half of the Measurement
Axioms. A specification whose reference implementation merely *documents* the
collapse prohibitions would be, by its own MA-7.1, an advisory control presented
as an intervention.

So these tests are adversarial against our own implementation: each attempts the
collapse the specification forbids, and passes only if the attempt fails.
"""
from __future__ import annotations

import ast
import dataclasses
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFORMANCE = (REPO_ROOT / "spec" / "v1.0" / "conformance")
SPEC_DIR = CONFORMANCE.parent
sys.path.insert(0, str(CONFORMANCE))

verdict = pytest.importorskip("verdict")
degenerate = pytest.importorskip("degenerate")

from verdict import (  # noqa: E402
    AggregateResult, CollapseError, Measurement, Verdict, aggregate,
    errored, inconclusive, measured_fail,
    AggregateResult, ScopeDecision, decision_outcome_permitted, measured_pass,
    merge_record_fields, not_applicable,
    not_measured, parse, require_handled,
    worst_case_policy,
)


class TestTheAlgebraItself:
    def test_six_values_and_no_more(self) -> None:
        assert {v.value for v in Verdict} == {
            "PASS", "FAIL", "NOT_MEASURED", "INCONCLUSIVE", "ERROR", "NOT_APPLICABLE"}

    def test_check_executed_separates_the_two_that_matter(self) -> None:
        """MA-3.1 — the distinction the doctrine turns on."""
        assert Verdict.INCONCLUSIVE.check_executed is True
        assert Verdict.NOT_MEASURED.check_executed is False
        assert Verdict.ERROR.check_executed is None, (
            "ERROR cannot say whether the check started; asserting False there "
            "claims something the verdict does not carry"
        )

    def test_only_pass_passes(self) -> None:
        passing = [v for v in Verdict if v.is_passing]
        assert passing == [Verdict.PASS]


class TestCollapseIsStructurallyPrevented:
    """MA-3.5. Each test attempts a documented collapse route."""

    def test_truthiness_raises(self) -> None:
        m = not_measured("telemetry file absent")
        with pytest.raises(CollapseError, match="not a boolean"):
            bool(m)
        with pytest.raises(CollapseError):
            if m:  # the exact line that turns a non-measurement into a pass
                pass

    def test_or_default_raises(self) -> None:
        """`m or default` is caught by __bool__, not __or__ — Python evaluates
        truth before reaching the operator. Either way the collapse fails."""
        m = not_measured("baseline missing")
        with pytest.raises(CollapseError, match="not a boolean"):
            _ = m or measured_pass(1)

    def test_bitwise_or_raises(self) -> None:
        """The operator __or__ actually guards."""
        m = not_measured("baseline missing")
        with pytest.raises(CollapseError, match="substitutes a passing value"):
            _ = m | measured_pass(1)

    def test_all_over_measurements_raises(self) -> None:
        """`all(...)` is the aggregate form of the same collapse."""
        with pytest.raises(CollapseError):
            all([measured_pass(1), not_measured("absent")])

    def test_truthiness_raises_even_for_a_passing_measurement(self) -> None:
        """The guard must not be selective, or callers will learn to rely on it."""
        with pytest.raises(CollapseError):
            bool(measured_pass(3))

    def test_combine_refuses_raw_booleans(self) -> None:
        with pytest.raises(CollapseError, match="takes Measurement objects"):
            worst_case_policy([measured_pass(1), True])  # type: ignore[list-item]


class TestConstructorsRefuseDishonestStates:
    def test_no_measured_verdict_may_claim_an_absent_input(self) -> None:
        """MA-3.8 — an input that could not be obtained yields NOT_MEASURED.

        The check named PASS only, so FAIL, INCONCLUSIVE and ERROR could each
        report a result reached from an input the same record says was
        unavailable. The rule is about measurement, not about passing.
        """
        for verdict in (Verdict.PASS, Verdict.FAIL, Verdict.INCONCLUSIVE,
                        Verdict.ERROR):
            with pytest.raises(CollapseError, match="MA-3.8"):
                Measurement(verdict, reason="r", inputs_present=False)
        Measurement(Verdict.NOT_MEASURED, reason="r", cause="input_absent",
                    inputs_present=False)

    def test_pass_over_zero_items_is_rejected(self) -> None:
        """MA-6.1 — the vacuous pass, refused at construction."""
        with pytest.raises(CollapseError, match="vacuous pass"):
            Measurement(Verdict.PASS, items_checked=0)

    def test_not_applicable_requires_a_scope_decision(self) -> None:
        """MA-3.3"""
        with pytest.raises(CollapseError, match="MA-3.3"):
            Measurement(Verdict.NOT_APPLICABLE)
        not_applicable(ScopeDecision("doc://scope/2026-08-01#out", True))  # accepted
        with pytest.raises(CollapseError, match="not a string"):
            not_applicable("doc://scope/2026-08-01#out")  # type: ignore[arg-type]
        with pytest.raises(CollapseError, match="did not resolve"):
            not_applicable(ScopeDecision("doc://gone", False))

    def test_a_negative_count_is_rejected(self) -> None:
        """The schema requires minimum 0; the runtime type accepted -1."""
        with pytest.raises(CollapseError, match="cannot be negative"):
            measured_pass(-1)

    def test_errored_asserts_no_input_state_by_default(self) -> None:
        """A crash *commonly* happens with its inputs in hand — commonly, not always.

        This test previously asserted `is True`, encoding that frequency as a
        fact. A crash may occur before the input was read, after it was read, or
        somewhere the caller cannot determine. The honest default is that the
        record does not say; a caller who knows passes the value.
        """
        assert errored("evaluator raised").inputs_present is None
        assert errored("read then crashed", inputs_present=True).inputs_present is True
        with pytest.raises(CollapseError, match="MA-3.8"):
            # An input that could not be obtained yields NOT_MEASURED, so ERROR
            # cannot carry it: the two statements describe different runs.
            errored("could not open source", inputs_present=False)

    def test_fail_is_available_and_is_a_measurement(self) -> None:
        """A measured negative is FAIL. Conflating it with NOT_MEASURED was a
        mistake this project made about its own evidence chain."""
        m = measured_fail("signature recomputable by any holder of the package",
                          items_checked=1)
        assert m.verdict is Verdict.FAIL
        assert m.verdict.check_executed is True


class TestAggregation:
    def test_an_unmeasured_constituent_propagates(self) -> None:
        assert worst_case_policy([measured_pass(3), not_measured("no telemetry")]) is Verdict.NOT_MEASURED

    def test_not_measured_outranks_fail(self) -> None:
        """A run that failed told you something; one that never ran told you less."""
        assert worst_case_policy([measured_fail("mismatch", 2), not_measured("absent")]) is Verdict.NOT_MEASURED

    def test_empty_aggregate_is_not_a_pass(self) -> None:
        """Aggregating nothing establishes nothing."""
        assert worst_case_policy([]) is Verdict.NOT_MEASURED

    def test_all_passing_aggregates_to_pass(self) -> None:
        assert worst_case_policy([measured_pass(1), measured_pass(2)]) is Verdict.PASS

    def test_all_out_of_scope_stays_out_of_scope(self) -> None:
        assert worst_case_policy([not_applicable(ScopeDecision("doc://a", True)), not_applicable(ScopeDecision("doc://b", True))]) is Verdict.NOT_APPLICABLE


class TestConsumerObligations:
    def test_unknown_wire_value_fails_closed(self) -> None:
        """MA-3.6"""
        assert parse("PASS") is Verdict.PASS
        with pytest.raises(CollapseError, match="MA-3.6"):
            parse("OK")

    def test_unhandled_non_passing_verdict_is_reported(self) -> None:
        """MA-3.4 — the requirement hardest to see in review."""
        with pytest.raises(CollapseError, match="MA-3.4"):
            require_handled([Verdict.PASS, Verdict.FAIL])
        with pytest.raises(CollapseError, match="MA-3.4"):
            require_handled([])   # the case the first version let through
        require_handled([Verdict.PASS, Verdict.FAIL, Verdict.NOT_MEASURED,
                         Verdict.INCONCLUSIVE, Verdict.ERROR])

    def test_unmeasured_may_not_allow(self) -> None:
        """MA-4.3"""
        assert decision_outcome_permitted(Verdict.NOT_MEASURED, "allow") is False
        for outcome in ("block", "escalate", "abstain"):
            assert decision_outcome_permitted(Verdict.NOT_MEASURED, outcome) is True
        assert decision_outcome_permitted(Verdict.PASS, "allow") is True


class TestRecordProjection:
    def test_not_measured_record_states_what_was_not_measured(self) -> None:
        """MA-3.10"""
        fields = not_measured("no baseline was stored for this descriptor",
                              cause="input_absent", inputs_present=False).to_record_fields()
        assert fields["measurement_status"] == "NOT_MEASURED"
        assert fields["measured"]["inputs_present"] is False
        assert "no baseline" in fields["reason"]

    def test_not_measured_does_not_assert_an_absence_by_default(self) -> None:
        """A skipped check says nothing about whether the input existed."""
        fields = not_measured("deeper evaluator was suppressed",
                              cause="suppressed_by_tier").to_record_fields()
        assert "measured" not in fields or "inputs_present" not in fields.get("measured", {})
        assert fields["non_measurement_cause"] == "suppressed_by_tier"

    def test_an_invented_cause_is_rejected(self) -> None:
        with pytest.raises(CollapseError, match="not one of"):
            not_measured("x", cause="because")

    def test_not_applicable_record_carries_its_scope_decision(self) -> None:
        fields = not_applicable(
            ScopeDecision("doc://scope#x", True, evaluated_version="1.2")
        ).to_record_fields()
        assert fields["scope_decision"]["ref"] == "doc://scope#x"
        assert fields["scope_decision"]["evaluated_version"] == "1.2"


class TestVerdictItselfRefusesTruthiness:
    """The half of the type that was not enforced.

    `Measurement.__bool__` raised from the start. `Verdict` did not, so
    `if measurement.verdict:` still collapsed. Found by external review
    2026-08-01.
    """

    @pytest.mark.parametrize("v", list(Verdict))
    def test_no_verdict_is_a_boolean(self, v: Verdict) -> None:
        with pytest.raises(CollapseError, match="not a boolean"):
            bool(v)

    def test_the_collapse_that_used_to_work(self) -> None:
        m = not_measured("telemetry absent")
        with pytest.raises(CollapseError):
            if m.verdict:      # this line used to allow()
                pass

    def test_comparison_still_works(self) -> None:
        """The guard must not break legitimate use."""
        assert Verdict.PASS is Verdict.PASS
        assert Verdict.NOT_MEASURED in {Verdict.NOT_MEASURED}
        assert Verdict.PASS.value == "PASS"
        assert f"{Verdict.FAIL.value}" == "FAIL"


class TestAggregateReportsDistributionNotOneVerdict:
    def test_aggregate_is_not_a_boolean(self) -> None:
        a = aggregate([not_measured("x")])
        with pytest.raises(CollapseError, match="not a boolean"):
            bool(a)

    def test_a_known_failure_is_not_hidden_under_an_unmeasured(self) -> None:
        """`combine` ranks and hides; `aggregate` counts and does not."""
        ms = [measured_fail("mismatch", 2), not_measured("absent")]
        assert worst_case_policy(ms) is Verdict.NOT_MEASURED       # the FAIL disappears
        a = aggregate(ms)
        assert a.counts[Verdict.FAIL] == 1               # it does not, here
        assert a.counts[Verdict.NOT_MEASURED] == 1
        assert a.any_unmeasured is True

    def test_empty_aggregate_counts_nothing_and_claims_nothing(self) -> None:
        a = aggregate([])
        assert a.total == 0 and not a.statuses_present

    def test_raw_booleans_refused(self) -> None:
        with pytest.raises(CollapseError):
            aggregate([measured_pass(1), True])  # type: ignore[list-item]


class TestPairedSelectivityProbe:
    """Five regressions. Each is a defect this module shipped with on 2026-08-01."""

    @staticmethod
    def _conformant_target(xs):
        if not xs:
            return not_measured("nothing to verify")
        return measured_pass(len(xs))

    def test_zero_coverage_is_not_measured_not_a_pass(self) -> None:
        """THE regression. It returned `conformant: True` while its own summary
        said NOTHING WAS EXERCISED."""
        # A signature that cannot take the case at all. The earlier version
        # used `lambda n: n > 0`, which binds fine and then raises comparing a
        # mapping to an int — that is a target that ran and crashed, and it is
        # now reported as ERROR rather than as coverage 0.
        report = degenerate.probe(lambda a, b: True,
                                  cases=[degenerate.EMPTY_MAPPING])
        assert report.coverage[0] == 0
        assert report.result is Verdict.NOT_MEASURED
        assert not hasattr(report, "conformant"), (
            "a boolean `conformant` is what allowed the vacuous pass; it must "
            "not come back"
        )

    def test_a_crash_is_an_error_not_a_pass(self) -> None:
        def crashes(x):
            raise RuntimeError("boom")
        assert degenerate.probe(
            crashes, cases=[degenerate.EMPTY_COLLECTION]).result is Verdict.ERROR

    def test_its_own_measurement_pass_is_recognised(self) -> None:
        """The two reference modules did not understand each other."""
        report = degenerate.probe(lambda xs: measured_pass(1),
                                  cases=[degenerate.EMPTY_COLLECTION])
        assert report.result is Verdict.FAIL
        assert report.observations[0].target_status is Verdict.PASS

    def test_an_uninterpretable_return_is_inconclusive(self) -> None:
        """A bare False may mean FAIL; guessing is not permitted."""
        assert degenerate.probe(
            lambda xs: False,
            cases=[degenerate.EMPTY_COLLECTION]).result is Verdict.INCONCLUSIVE

    def test_an_adapter_makes_interpretation_explicit(self) -> None:
        def legacy(xs):
            return {"valid": True} if not xs else {"valid": False}
        report = degenerate.probe(
            legacy, cases=[degenerate.EMPTY_COLLECTION],
            adapter=lambda v: Verdict.PASS if v["valid"] else Verdict.FAIL)
        assert report.result is Verdict.FAIL
        assert report.adapter_used is True

    def test_a_conformant_target_passes(self) -> None:
        """The guard must be able to say yes, or it measures nothing either."""
        assert degenerate.probe(
            self._conformant_target,
            cases=[degenerate.EMPTY_COLLECTION]).result is Verdict.PASS

    def test_a_broken_control_input_is_inconclusive_not_a_failure(self) -> None:
        """If the control cannot be measured either, the case proves nothing."""
        report = degenerate.probe(lambda xs: not_measured("always"),
                                  cases=[degenerate.EMPTY_COLLECTION])
        assert report.result is Verdict.INCONCLUSIVE

    def test_an_unclassified_control_cannot_yield_a_pass(self) -> None:
        """The hole left by the first correction. A pair whose control cannot be
        read establishes nothing, whatever the degenerate variant returned."""
        def target(xs):
            return not_measured("nothing to check") if not xs else False
        report = degenerate.probe(target, cases=[degenerate.EMPTY_COLLECTION])
        assert report.result is Verdict.INCONCLUSIVE
        assert report.observations[0].target_status is Verdict.NOT_MEASURED, (
            "the degenerate side was correct — which is exactly why reporting "
            "PASS here was tempting and wrong"
        )

    def test_an_adapter_returning_a_non_verdict_is_an_error(self) -> None:
        report = degenerate.probe(lambda xs: {"v": 1},
                                  cases=[degenerate.EMPTY_COLLECTION],
                                  adapter=lambda v: "PASS")
        assert report.result is Verdict.ERROR

    def test_an_adapter_that_raises_is_an_error(self) -> None:
        def boom(v):
            raise ValueError("bad adapter")
        report = degenerate.probe(lambda xs: {"v": 1},
                                  cases=[degenerate.EMPTY_COLLECTION],
                                  adapter=boom)
        assert report.result is Verdict.ERROR

    def test_probe_all_returns_reports_not_one_verdict(self) -> None:
        reports = degenerate.probe_all([self._conformant_target,
                                        self._conformant_target])
        assert isinstance(reports, list) and len(reports) == 2


class TestExclusionsExamineNothing:
    """MA-3.3 — found while binding sources for the pre-commit gate.

    `inputs_present` defaulted to True on the dataclass, so a directly-constructed
    NOT_APPLICABLE asserted the input was there. Nothing examined it: that is what
    out-of-scope means. The helper passed None and the type did not, which is the
    same helper-not-type split as the cause and scope-resolution invariants.
    """

    def test_the_type_refuses_an_exclusion_that_claims_its_input(self) -> None:
        with pytest.raises(CollapseError, match="establishes nothing"):
            Measurement(Verdict.NOT_APPLICABLE,
                        scope_decision=ScopeDecision("doc://s", True),
                        inputs_present=True)

    def test_the_helper_emits_no_input_claim(self) -> None:
        fields = not_applicable(ScopeDecision("doc://s", True)).to_record_fields()
        assert "measured" not in fields


class TestTheProbeStillHoldsAfterTheTypeTightened:
    """The probe is a consumer of Measurement, and Measurement got stricter.

    An external review flagged that the probe had not been re-validated after
    this round's type changes. A consumer can pass its own tests while the type
    it consumes moves underneath it, so this drives it through the real API with
    the tightened constructors in view.
    """

    CASE = degenerate.SelectivityCase(
        name="empty_collection", control=[{"id": 1}, {"id": 2}], degenerate=[],
        expects_on_degenerate=Verdict.NOT_MEASURED,
        rationale="an empty collection checks zero items and establishes nothing")

    def test_a_target_that_tells_them_apart_passes(self) -> None:
        def target(items):
            if not items:
                return not_measured("no items to check", cause="input_absent")
            return measured_pass(len(items))

        report = degenerate.probe(target, [self.CASE])
        assert report.result is Verdict.PASS, report.result

    def test_a_target_that_inherits_its_control_result_fails(self) -> None:
        """The invariance the paired model exists to catch."""
        report = degenerate.probe(lambda items: measured_pass(1), [self.CASE])
        assert report.result is Verdict.FAIL, report.result

    def test_a_crashing_target_is_an_error_not_a_pass(self) -> None:
        def target(items):
            raise RuntimeError("adapter blew up")

        report = degenerate.probe(target, [self.CASE])
        assert report.result is Verdict.ERROR, report.result


class TestTheTypeAssumesNoInputState:
    """The default that survived three rounds of fixing its wrappers.

    `errored()` was corrected, then `not_measured()`, then `not_applicable()` —
    while `Measurement.inputs_present` kept defaulting to True underneath all of
    them. Anyone constructing the type directly, which the module exports, got a
    record asserting an input state nobody had established. Fixing the callers
    of a bad default three times is how you learn it was the default.
    """

    def test_the_default_is_unknown(self) -> None:
        assert Measurement(Verdict.ERROR, reason="crash").inputs_present is None
        assert "measured" not in Measurement(
            Verdict.ERROR, reason="crash").to_record_fields()

    def test_each_constructor_states_what_it_knows(self) -> None:
        for m in (measured_pass(1), measured_fail("x", 1), inconclusive("y", 2)):
            assert m.inputs_present is True, (
                f"{m.verdict.value} examined items, so the inputs were there and "
                "the record should say so")
        assert errored("boom").inputs_present is None
        assert not_measured("skipped", cause="suppressed_by_tier").inputs_present is None

    @pytest.mark.parametrize("cause", ["input_absent", "input_unreadable"])
    def test_an_unobtainable_input_is_derived_in_one_place(self, cause: str) -> None:
        """Type and helper agreed only because the rule lives in one of them."""
        direct = Measurement(Verdict.NOT_MEASURED, reason="r", cause=cause)
        viaa = not_measured("r", cause=cause)
        assert direct.inputs_present is False
        assert viaa.inputs_present is False

    @pytest.mark.parametrize("cause", ["input_absent", "input_unreadable"])
    def test_the_contradiction_is_refused(self, cause: str) -> None:
        with pytest.raises(CollapseError, match="not established"):
            not_measured("r", cause=cause, inputs_present=True)


class TestDetailReachesTheRecord:
    """An API that takes data and emits nothing leaves the caller believing the
    record carries what it does not — the shape of claim this document refuses.

    `detail` was accepted by every constructor and read nowhere: `self.detail`
    appeared once in the file, at its own definition.
    """

    def test_detail_is_carried_under_the_reserved_extension_point(self) -> None:
        fields = measured_fail("threshold exceeded", 1,
                               policy="P1", threshold=0.5).to_record_fields()
        assert fields["profiles"]["reference_detail"] == {"policy": "P1",
                                                          "threshold": 0.5}

    def test_an_empty_detail_adds_nothing(self) -> None:
        assert "profiles" not in measured_pass(1).to_record_fields()

    def test_unserialisable_detail_fails_at_the_caller(self) -> None:
        """Not at serialisation, where the caller who wrote it is long gone."""
        with pytest.raises(CollapseError, match="no JSON representation"):
            measured_pass(1, handle=object())


class TestDetailIsCheckedAgainstJsonNotAgainstJsonDumps:
    """`json.dumps` is a producer, not a validator.

    The first check called it and caught the error, which answers "can I write
    something" rather than "is this JSON". It writes `NaN`, `Infinity` and
    `-Infinity`, which RFC 8259 does not define, and it silently converts a
    tuple to a list and an integer key to a string — so the record would carry
    a value the caller never wrote. Six behaviours passed a gate whose whole
    purpose was to stop them.
    """

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_a_number_json_cannot_write_is_refused(self, value: float) -> None:
        with pytest.raises(CollapseError, match="no literal"):
            measured_pass(1, score=value)

    def test_a_non_string_key_is_refused_rather_than_converted(self) -> None:
        with pytest.raises(CollapseError, match="non-string key"):
            Measurement(Verdict.PASS, items_checked=1, inputs_present=True,
                        detail={1: "v"})

    def test_a_tuple_is_refused_rather_than_flattened(self) -> None:
        with pytest.raises(CollapseError, match="tuple"):
            measured_pass(1, pair=(1, 2))

    def test_the_check_reaches_nested_values(self) -> None:
        """A top-level-only check would have passed all three of these."""
        for detail in ({"a": {"b": float("nan")}},
                       {"a": [1, {"b": float("inf")}]},
                       {"a": [[{"b": (1, 2)}]]}):
            with pytest.raises(CollapseError):
                Measurement(Verdict.PASS, items_checked=1, inputs_present=True,
                            detail=detail)

    def test_genuine_json_still_passes(self) -> None:
        m = measured_pass(1, ok={"a": [1, 2.5, True, None, {"b": "c"}]})
        carried = m.to_record_fields()["profiles"]["reference_detail"]
        assert carried == {"ok": {"a": [1, 2.5, True, None, {"b": "c"}]}}


class TestMergingKeepsOtherProfiles:
    """`record.update(fields)` replaces `profiles` wholesale.

    The subset returned is correct; the merge is the lossy step, so the merge is
    what gets a function rather than a note in a docstring nobody reads.
    """

    def test_update_would_discard_a_deployment_profile(self) -> None:
        record = {"profiles": {"deployment_extension": {"k": 1}}}
        naive = dict(record)
        naive.update(measured_pass(1, policy="P1").to_record_fields())
        assert "deployment_extension" not in naive["profiles"], (
            "if this ever passes, the shallow-merge hazard is gone and this "
            "test should be removed rather than left asserting nothing")

    def test_the_helper_keeps_both(self) -> None:
        merged = merge_record_fields({"profiles": {"deployment_extension": {"k": 1}}},
                                     measured_pass(1, policy="P1"))
        assert merged["profiles"] == {"deployment_extension": {"k": 1},
                                      "reference_detail": {"policy": "P1"}}

    def test_it_leaves_the_original_untouched(self) -> None:
        record = {"profiles": {"a": {"k": 1}}}
        merge_record_fields(record, measured_pass(1, policy="P1"))
        assert record == {"profiles": {"a": {"k": 1}}}

    def test_it_works_without_any_profiles(self) -> None:
        merged = merge_record_fields({"spec_version": "1.0"}, measured_pass(1))
        assert "profiles" not in merged and merged["spec_version"] == "1.0"


class TestValidationOutlivesTheMomentItRan:
    """A check on a value the caller still holds is a photograph, not a gate.

    `_require_json` was correct and ran once, at construction, on an object
    someone else could change afterwards. Turning a validated 1.0 into NaN after
    the fact put it straight into the record. Three separate symptoms — the
    caller's dict, the instance's own `detail`, and the emitted record — were one
    defect: validating what you do not own.
    """

    def test_the_declared_type_is_enforced_at_runtime(self) -> None:
        """Annotations do not run. `if self.detail:` skipped every falsy one."""
        for wrong in (1, "text", [1, 2], None, False, (), 0):
            with pytest.raises(CollapseError, match="mapping"):
                Measurement(Verdict.PASS, items_checked=1, inputs_present=True,
                            detail=wrong)

    def test_a_later_mutation_is_not_possible_at_any_depth(self) -> None:
        """Stronger than catching it at emission: there is nothing to catch.

        The snapshot is frozen all the way down, so `detail["nested"]["b"] = x`
        raises where it is written rather than producing a measurement that
        fails later. An earlier version froze only the top level, which made the
        word "snapshot" true of one layer and false of the rest.
        """
        m = measured_pass(1, nested={"a": 1}, items=[1, 2])
        with pytest.raises(TypeError):
            m.detail["nested"]["b"] = float("inf")   # type: ignore[index]
        with pytest.raises(TypeError):
            m.detail["items"][0] = 9                 # type: ignore[index]
        assert m.to_record_fields()["profiles"]["reference_detail"] == {
            "nested": {"a": 1}, "items": [1, 2]}

    def test_the_caller_keeps_no_handle_on_the_measurement(self) -> None:
        detail = {"nested": {"score": 1}, "items": [1]}
        m = measured_pass(1, **detail)
        detail["nested"]["score"] = 2
        detail["items"].append(3)
        assert m.to_record_fields()["profiles"]["reference_detail"] == {
            "nested": {"score": 1}, "items": [1]}, (
            "`**detail` gives a fresh top-level dict and shares every nested "
            "object, which is why a shallow copy was not enough")

    def test_the_record_and_the_measurement_do_not_share_objects(self) -> None:
        """MA-8.4 — a recorded payload does not change after the fact."""
        m = measured_pass(1, nested={"score": 1})
        record = m.to_record_fields()
        record["profiles"]["reference_detail"]["nested"]["score"] = 99
        assert m.to_record_fields()["profiles"]["reference_detail"] == {
            "nested": {"score": 1}}

    def test_two_records_from_one_measurement_are_independent(self) -> None:
        m = measured_pass(1, nested={"score": 1})
        first, second = m.to_record_fields(), m.to_record_fields()
        first["profiles"]["reference_detail"]["nested"]["score"] = 99
        assert second["profiles"]["reference_detail"]["nested"]["score"] == 1

    def test_an_empty_mapping_is_still_a_mapping(self) -> None:
        m = Measurement(Verdict.PASS, items_checked=1, inputs_present=True, detail={})
        assert "profiles" not in m.to_record_fields()


class TestMergingRefusesToOverwrite:
    """Silently replacing one measurement's context with another's leaves no
    trace that the first existed."""

    def test_a_collision_fails_loudly(self) -> None:
        with pytest.raises(CollapseError, match="already present"):
            merge_record_fields({"profiles": {"reference_detail": {"old": 1}}},
                                measured_pass(1, new=2))

    def test_an_unrelated_profile_still_merges(self) -> None:
        merged = merge_record_fields({"profiles": {"deployment": {"v": "1"}}},
                                     measured_pass(1, threshold=0.5))
        assert merged["profiles"] == {"deployment": {"v": "1"},
                                      "reference_detail": {"threshold": 0.5}}

    def test_a_measurement_without_detail_never_collides(self) -> None:
        merged = merge_record_fields({"profiles": {"reference_detail": {"old": 1}}},
                                     measured_pass(1))
        assert merged["profiles"] == {"reference_detail": {"old": 1}}


class TestTheValidatedValueIsTheStoredValue:
    """Validate one object, store another: the same defect in a narrower window.

    The order was `_require_json(self.detail)` then `deepcopy(dict(self.detail))`
    — two reads of the caller's mapping. A `Mapping` whose `__getitem__` answers
    differently on the second read got a valid value past the gate and an invalid
    one into the field. Emission caught it, so no bad record escaped, but the
    instance existed in a state its own constructor had rejected, and every other
    invariant in this type fails at construction.

    The fix is not to detect adversarial mappings. It is to read once.
    """

    class ShiftyMapping(Mapping):
        """Answers 1.0 the first time and NaN every time after."""

        def __init__(self) -> None:
            self.reads = 0

        def __iter__(self):
            return iter(["score"])

        def __len__(self) -> int:
            return 1

        def __getitem__(self, key: str) -> float:
            self.reads += 1
            return 1.0 if self.reads == 1 else float("nan")

    def test_the_field_holds_exactly_what_was_checked(self) -> None:
        shifty = self.ShiftyMapping()
        m = Measurement(Verdict.PASS, items_checked=1, inputs_present=True,
                        detail=shifty)
        assert m.to_record_fields()["profiles"]["reference_detail"] == {
            "score": 1.0}
        assert shifty.reads == 1, (
            f"the constructor read the caller's mapping {shifty.reads} times; "
            "each extra read is a window where the value can change between "
            "being checked and being kept")

    def test_the_record_carries_the_same_value(self) -> None:
        m = Measurement(Verdict.PASS, items_checked=1, inputs_present=True,
                        detail=self.ShiftyMapping())
        assert m.to_record_fields()["profiles"]["reference_detail"] == {"score": 1.0}

    def test_an_ordinary_mapping_is_unaffected(self) -> None:
        m = Measurement(Verdict.PASS, items_checked=1, inputs_present=True,
                        detail={"a": {"b": [1, 2]}})
        assert m.to_record_fields()["profiles"]["reference_detail"] == {
            "a": {"b": [1, 2]}}

    def test_an_invalid_mapping_still_fails_at_construction(self) -> None:
        with pytest.raises(CollapseError, match="no literal"):
            Measurement(Verdict.PASS, items_checked=1, inputs_present=True,
                        detail={"score": float("nan")})


class TestTheModuleCarriesNoUnusedImport:
    """`json` was imported for a check that no longer exists.

    Small, and the reason it is here rather than left alone: an import that
    nothing uses reads as a dependency the module has, and a reader deciding
    whether to vendor this file is entitled to a list that is true.
    """

    def test_every_import_is_used(self) -> None:
        import ast

        source = (SPEC_DIR / "conformance" / "verdict.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {(a.asname or a.name).split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
                imported |= {a.asname or a.name for a in node.names}
        used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        used |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                used.add(node.value.id)
        # annotations are strings under `from __future__ import annotations`
        used |= set(re.findall(r"\b(\w+)\b", "".join(
            ast.get_source_segment(source, n.annotation) or ""
            for n in ast.walk(tree)
            if isinstance(n, (ast.AnnAssign, ast.arg)) and n.annotation)))
        unused = sorted(imported - used)
        assert not unused, f"imported and never used: {unused}"


class TestAResultCannotBeRewrittenAfterItIsProduced:
    """`frozen=True` freezes the field, not the container behind it.

    Four structures carried a mutable container whose contents decide a verdict.
    The worst was `AggregateResult.counts`: anyone holding the result could write
    `counts[NOT_MEASURED] = 0; counts[PASS] = 1` and `any_unmeasured` went quiet
    — the exact conversion this module exists to refuse, performed on the
    module's own output, after every check had passed.
    """

    def test_an_aggregate_cannot_be_turned_into_a_pass(self) -> None:
        result = aggregate([not_measured("not run", cause="not_executed")])
        assert result.any_unmeasured is True
        with pytest.raises(TypeError):
            result.counts[Verdict.NOT_MEASURED] = 0
        with pytest.raises(TypeError):
            result.counts[Verdict.PASS] = 1
        assert result.any_unmeasured is True

    def test_a_hand_built_aggregate_is_checked(self) -> None:
        """Direct construction is a supported path and gets the same rules."""
        for counts, total, match in (
                ({Verdict.PASS: 1}, 2, "not measured"),
                ({Verdict.PASS: -1}, -1, "negative"),
                ({"PASS": 1}, 1, "not a Verdict"),
                ({Verdict.PASS: True}, 1, "not an integer")):
            with pytest.raises(CollapseError, match=match):
                AggregateResult(counts=counts, total=total)

    def test_a_probe_report_keeps_what_it_observed(self) -> None:
        """Emptying the list turned PASS into NOT_MEASURED; appending would have
        put an observation in that the probe never made."""
        case = degenerate.SelectivityCase(
            name="c", control=[{"id": 1}], degenerate=[],
            expects_on_degenerate=Verdict.NOT_MEASURED, rationale="r")

        def target(items):
            if not items:
                return not_measured("empty", cause="input_absent")
            return measured_pass(len(items))

        report = degenerate.probe(target, [case])
        assert report.result is Verdict.PASS
        assert isinstance(report.observations, tuple)
        with pytest.raises(AttributeError):
            report.observations.append(None)          # type: ignore[attr-defined]
        with pytest.raises(dataclasses.FrozenInstanceError):
            report.observations = ()                  # type: ignore[misc]
        assert report.result is Verdict.PASS

    #: Built instances, not declared defaults. A field may declare
    #: `default_factory=dict` and be normalised in `__post_init__`, so reading
    #: the declaration answers a different question from the one that matters:
    #: can a caller holding this object edit what it reports?
    SAMPLES = [
        lambda v_, d_: v_.aggregate([v_.measured_pass(1)]),
        lambda v_, d_: v_.measured_pass(1, k="v"),
        lambda v_, d_: v_.not_applicable(v_.ScopeDecision("doc://s", True)),
    ]

    def test_no_result_object_hands_out_a_writable_container(self) -> None:
        """The class, not the four instances of it."""
        offenders = []
        for build in self.SAMPLES:
            obj = build(verdict, degenerate)
            for f in dataclasses.fields(obj):
                value = getattr(obj, f.name)
                if isinstance(value, (list, set)):
                    offenders.append(f"{type(obj).__name__}.{f.name}: {type(value).__name__}")
                elif isinstance(value, dict):
                    offenders.append(f"{type(obj).__name__}.{f.name}: dict")
        assert not offenders, (
            "these hand callers a container they can edit after the object "
            f"reported its verdict: {offenders}")

    def test_the_detail_snapshot_is_not_writable(self) -> None:
        m = measured_pass(1, k="v")
        with pytest.raises(TypeError):
            m.detail["k"] = "other"       # type: ignore[index]


class TestJsonIsCheckedAndRebuilt:
    """`isinstance(x, Mapping)` is true of a UserDict the encoder cannot write.

    The check said "this is JSON" about a value the wire could not carry: the
    record built fine and `json.dumps` on it raised. Validating one tree and
    keeping another is the split behind every defect this field has had, so the
    validator now returns the tree it checked.
    """

    def test_a_nested_usermapping_becomes_a_plain_dict(self) -> None:
        from collections import UserDict

        m = measured_pass(1, nested=UserDict({"x": 1}))
        carried = m.to_record_fields()["profiles"]["reference_detail"]["nested"]
        assert type(carried) is dict, type(carried)
        json.dumps(m.to_record_fields())      # the check that used to raise

    def test_the_record_is_serialisable_end_to_end(self) -> None:
        from collections import OrderedDict

        m = measured_fail("x", 1, a=OrderedDict({"b": [1, {"c": 2}]}))
        assert json.loads(json.dumps(m.to_record_fields()))["profiles"][
            "reference_detail"] == {"a": {"b": [1, {"c": 2}]}}


class TestTheMa43HelperDoesNotFailOpen:
    """It returned True for `"NOT_MEASURED"` as a string.

    The identity test is false for the serialised form of a status, so a caller
    who had already stringified theirs fell through to `return True` and was
    told that allowing an unmeasured decision was permitted — this function
    failing open on the one rule it exists to enforce.
    """

    def test_a_stringified_status_is_refused_not_permitted(self) -> None:
        with pytest.raises(CollapseError, match="not a Verdict"):
            decision_outcome_permitted("NOT_MEASURED", "allow")

    def test_an_unrecognised_outcome_is_refused(self) -> None:
        with pytest.raises(CollapseError, match="not one of"):
            decision_outcome_permitted(Verdict.PASS, "garbage")

    def test_the_rule_itself_still_holds(self) -> None:
        assert decision_outcome_permitted(Verdict.NOT_MEASURED, "allow") is False
        for permitted in ("block", "escalate", "abstain"):
            assert decision_outcome_permitted(Verdict.NOT_MEASURED, permitted) is True
        assert decision_outcome_permitted(Verdict.PASS, "allow") is True


class TestTheProbeCannotBeRewrittenOrFooled:
    """The tool that tests for collapse, collapsing.

    `Observation` was not frozen, so `report.observations[0].probe_status =
    ERROR` changed a finished report's verdict. And `Observation(case,
    probe_status="PASS")` built cleanly: a string reaches no branch of `result`
    and lands on the passing one — the vacuous pass, inside the probe written to
    catch it.
    """

    CASE = degenerate.EMPTY_COLLECTION

    @staticmethod
    def _good(items):
        if not items:
            return not_measured("nothing to examine", cause="input_absent")
        return measured_pass(len(items))

    def test_a_finished_report_cannot_be_edited(self) -> None:
        report = degenerate.probe(self._good, [self.CASE])
        before = report.result
        with pytest.raises(dataclasses.FrozenInstanceError):
            report.observations[0].probe_status = Verdict.ERROR  # type: ignore[misc]
        assert report.result is before

    def test_a_status_that_is_not_a_verdict_is_refused(self) -> None:
        with pytest.raises(TypeError, match="not a Verdict"):
            degenerate.Observation(case=self.CASE, probe_status="PASS")

    def test_a_report_checks_what_it_was_handed(self) -> None:
        with pytest.raises(TypeError, match="Observation"):
            degenerate.ProbeReport(target="t", observations=("not an observation",))

    def test_a_malformed_case_is_refused_where_it_is_written(self) -> None:
        """It used to reach `expects_on_degenerate.value` and raise
        AttributeError from inside the probe — an error about the case,
        reported as a crash of the tool reading it."""
        with pytest.raises(TypeError, match="not a\\s+Verdict"):
            degenerate.SelectivityCase(
                name="bad", control=[1], degenerate=[],
                expects_on_degenerate="NOT_MEASURED", rationale="r")
        for kwargs in ({"name": "  "}, {"rationale": " "},
                       {"control_may_be": frozenset()}):
            with pytest.raises(TypeError):
                degenerate.SelectivityCase(
                    name="c", control=[1], degenerate=[],
                    expects_on_degenerate=Verdict.NOT_MEASURED,
                    rationale="r", **kwargs)

    def test_a_crash_inside_the_target_is_an_error_not_an_absence(self) -> None:
        """Every TypeError was read as "the signature refused the case", so a
        genuine bug in the target was recorded as *not tested*."""
        def buggy(value):
            raise TypeError("internal bug")

        report = degenerate.probe(buggy, [self.CASE])
        assert report.result is Verdict.ERROR, report.result
        assert "signature" not in report.observations[0].note

    def test_a_signature_that_cannot_take_the_case_is_still_not_measured(self) -> None:
        report = degenerate.probe(lambda a, b: True, [self.CASE])
        assert report.result is Verdict.NOT_MEASURED
        assert report.coverage[0] == 0

    def test_every_target_gets_the_same_cases(self) -> None:
        """A generator was exhausted by the first target and the rest reported
        NOT_MEASURED — which reads as "no coverage", not "already consumed"."""
        cases = (c for c in [degenerate.EMPTY_COLLECTION, degenerate.ABSENT_BASELINE])
        first, second = degenerate.probe_all([self._good, self._good], cases)
        assert len(first.observations) == len(second.observations) == 2
        assert first.result is second.result

    def test_a_target_cannot_edit_the_case_it_was_given(self) -> None:
        """The worst of the set: results that depend on what ran before them.

        A target appending to the list it receives edited the module-level
        `EMPTY_COLLECTION`, so a later, clean target was no longer probed with
        an empty collection at all — and failed.
        """
        def mutating(value):
            if isinstance(value, list):
                value.append("changed")
            if isinstance(value, dict):
                value["changed"] = True
            return (not_measured("empty", cause="input_absent") if not value
                    else measured_pass(1))

        degenerate.probe(mutating, [degenerate.EMPTY_COLLECTION,
                                    degenerate.EMPTY_MAPPING])
        assert degenerate.EMPTY_COLLECTION.degenerate == []
        assert degenerate.EMPTY_MAPPING.degenerate == {}
        assert degenerate.probe(self._good,
                                [degenerate.EMPTY_COLLECTION]).result is Verdict.PASS


class TestACycleHasNoRecord:
    """`_json_snapshot` promises "a canonical JSON tree, or raise" and recursed
    until the interpreter stopped it."""

    def test_a_self_referential_detail_is_refused(self) -> None:
        detail: dict = {}
        detail["self"] = detail
        with pytest.raises(CollapseError, match="refers back"):
            Measurement(Verdict.PASS, items_checked=1, inputs_present=True,
                        detail=detail)

    def test_a_cycle_through_a_list_is_refused(self) -> None:
        inner: list = []
        inner.append({"back": inner})
        with pytest.raises(CollapseError, match="refers back"):
            measured_pass(1, chain=inner)

    def test_a_shared_value_is_not_a_cycle(self) -> None:
        """The same object in two sibling branches serialises fine; only
        returning to a container still open above is a cycle."""
        shared = {"x": 1}
        m = measured_pass(1, a=shared, b=shared)
        assert m.to_record_fields()["profiles"]["reference_detail"] == {
            "a": {"x": 1}, "b": {"x": 1}}


class TestTheSignatureFixRemovedAFalsePass:
    """Correcting the misclassification changed a result, and it should have.

    A toy target that did `len(source)` crashed on the `Path` in
    `unreadable_source`. That TypeError was read as "the signature refused the
    case", recorded as NOT_MEASURED — which is what the case expects — and the
    probe reported PASS. The target had not handled the case at all; it had
    fallen over, and the fall was scored as the right answer.

    A target that handles the class honestly passes all four.
    """

    @staticmethod
    def _conformant(source):
        from pathlib import Path

        if isinstance(source, Path):
            if not source.exists():
                return not_measured("source unreadable", cause="input_unreadable")
            return measured_pass(1)
        if source is None:
            return not_measured("no baseline", cause="input_absent")
        if not source:
            return not_measured("nothing to examine", cause="input_absent")
        return measured_pass(len(source))

    def test_a_target_that_handles_every_class_passes(self) -> None:
        report = degenerate.probe(self._conformant)
        assert report.result is Verdict.PASS, report.summary()
        assert len(report.observations) == 4

    def test_a_target_that_crashes_on_one_class_does_not(self) -> None:
        """The old scoring gave this PASS."""
        report = degenerate.probe(lambda s: measured_pass(len(s)))
        assert report.result is Verdict.ERROR, report.summary()


class TestTheProbeCannotBeConfiguredIntoAPass:
    """Five ways a case or a call could be built so that PASS meant nothing."""

    @staticmethod
    def _blind(x):
        return not_measured("nothing", cause="input_absent")

    def test_a_control_that_may_be_unmeasured_is_not_a_control(self) -> None:
        """A target returning NOT_MEASURED for both inputs passed a test of
        whether it tells them apart."""
        with pytest.raises(TypeError, match="control input"):
            degenerate.SelectivityCase(
                name="bad", control=[1], degenerate=[],
                expects_on_degenerate=Verdict.NOT_MEASURED, rationale="r",
                control_may_be={Verdict.NOT_MEASURED})

    def test_the_required_status_cannot_also_be_permitted_for_the_control(self) -> None:
        with pytest.raises(TypeError, match="also permitted"):
            degenerate.SelectivityCase(
                name="bad", control=[1], degenerate=[],
                expects_on_degenerate=Verdict.PASS, rationale="r",
                control_may_be={Verdict.PASS})

    def test_not_applicable_is_not_a_probe_status(self) -> None:
        """It reached no branch of `result` and arrived at the passing one."""
        with pytest.raises(TypeError, match="NOT_APPLICABLE"):
            degenerate.Observation(case=degenerate.EMPTY_COLLECTION,
                                   probe_status=Verdict.NOT_APPLICABLE)

    def test_extra_kwargs_cannot_replace_the_case_input(self) -> None:
        """The probe reported a result about inputs it never sent."""
        with pytest.raises(TypeError, match="argument the cases"):
            degenerate.probe(lambda value: measured_pass(1),
                             [degenerate.EMPTY_COLLECTION],
                             argument="value",
                             extra_kwargs={"value": [{"forced": 1}]})

    def test_the_two_calls_get_independent_surroundings(self) -> None:
        """The degenerate call ran under conditions the control call created."""
        seen, config = [], {"config": []}

        def target(value, config):
            seen.append(list(config))
            config.append("changed")
            return measured_pass(1) if value else not_measured("e",
                                                               cause="input_absent")

        degenerate.probe(target, [degenerate.EMPTY_COLLECTION], extra_kwargs=config)
        assert seen == [[], []], f"the second call inherited {seen[1]}"
        assert config == {"config": []}, "the caller's own object was written to"

    def test_every_default_case_is_internally_coherent(self) -> None:
        for case in degenerate.DEFAULT_CASES:
            assert case.control_may_be <= degenerate.CONTROL_STATUSES
            assert case.expects_on_degenerate not in case.control_may_be


class TestProvenanceIsNotPresence:
    """`adapter_used` meant "an adapter was supplied", so a report whose target
    returned native Measurements still said *via adapter*."""

    def test_an_unused_adapter_is_not_reported_as_used(self) -> None:
        report = degenerate.probe(
            lambda x: measured_pass(1) if x else not_measured("e",
                                                              cause="input_absent"),
            [degenerate.EMPTY_COLLECTION], adapter=lambda o: None)
        assert report.adapter_used is False
        assert report.observations[0].adapted is False
        assert "via adapter" not in report.summary()

    def test_an_adapter_that_answers_is_reported(self) -> None:
        report = degenerate.probe(
            lambda x: "ok" if x else "nothing",
            [degenerate.EMPTY_COLLECTION],
            adapter=lambda o: Verdict.PASS if o == "ok" else Verdict.NOT_MEASURED)
        assert report.adapter_used is True
        assert report.observations[0].adapted is True


class TestTheProbeCallsTargetsItCanCall:
    def test_a_positional_only_target_is_probed_not_refused(self) -> None:
        """It had refused the *call form*, not the input — a fact about the
        probe, recorded as a fact about the target."""
        def positional(value, /):
            return measured_pass(1) if value else not_measured("e",
                                                               cause="input_absent")

        assert degenerate.probe(positional,
                                [degenerate.EMPTY_COLLECTION]).result is Verdict.PASS

    def test_a_keyword_only_target_is_probed(self) -> None:
        def keyword(*, value):
            return measured_pass(1) if value else not_measured("e",
                                                               cause="input_absent")

        assert degenerate.probe(keyword, [degenerate.EMPTY_COLLECTION],
                                argument="value").result is Verdict.PASS


class TestErrorsLandOnTheCallerNotInsideTheHelper:
    def test_merging_into_something_that_is_not_a_record(self) -> None:
        """Found by sweeping the public surface rather than by review: it raised
        AttributeError from inside `merge_record_fields`, reporting the fault as
        the merger's rather than the caller's."""
        with pytest.raises(CollapseError, match="not a mapping"):
            merge_record_fields("not a record", measured_pass(1))
        with pytest.raises(CollapseError, match="not a Measurement"):
            merge_record_fields({}, "not a measurement")


class TestFalsyWrongTypesAreNotEmptyConfig:
    """`dict(x or {})` accepts every falsy wrong type and drops it.

    `extra_kwargs=0`, `False`, `[]` all became an empty config and the probe ran
    on without them, reporting a result about a configuration the caller had
    supplied and the probe never used. The same idiom had already been fixed
    once in `Measurement.detail`; this was the second place it lived.
    """

    @staticmethod
    def _target(value):
        return (measured_pass(1) if value
                else not_measured("empty", cause="input_absent"))

    @pytest.mark.parametrize("wrong", [0, False, [], "", [("config", [])], 3])
    def test_a_non_mapping_extra_kwargs_is_refused(self, wrong) -> None:
        with pytest.raises(TypeError, match="Mapping"):
            degenerate.probe(self._target, [degenerate.EMPTY_COLLECTION],
                             extra_kwargs=wrong)

    def test_none_still_means_no_extra_arguments(self) -> None:
        assert degenerate.probe(self._target, [degenerate.EMPTY_COLLECTION],
                                extra_kwargs=None).result is Verdict.PASS


class TestProvenanceCannotBeAsserted:
    """`self.adapter_used or any(...)` let a hand-built report with no
    observations at all claim "via adapter". Provenance is a fact about the
    observations or it is nothing."""

    def test_a_claim_without_an_adapted_observation_does_not_survive(self) -> None:
        assert degenerate.ProbeReport("t", (), True).adapter_used is False

    def test_it_follows_the_observations(self) -> None:
        adapted = degenerate.Observation(
            case=degenerate.EMPTY_COLLECTION, probe_status=Verdict.PASS,
            adapted=True)
        assert degenerate.ProbeReport("t", (adapted,), False).adapter_used is True


class TestMergeChecksTheRecordItWasGiven:
    @pytest.mark.parametrize("profiles", [None, [], "text", 3])
    def test_a_malformed_profiles_field_fails_at_the_caller(self, profiles) -> None:
        with pytest.raises(CollapseError, match="not a mapping"):
            merge_record_fields({"profiles": profiles}, measured_pass(1, k=1))


class TestTheProbeConfigurationSpace:
    """The surface the schema sweep does not reach.

    Every finding of the last round lived here: in `probe()`'s own parameters,
    not in the records it produces. The combinatorial sweep in the spec tests
    covers the record space and says so; this covers the call space, and the
    two together are still not everything — what is left is named below.

    The rule this enforces: a malformed call raises. It never returns a verdict,
    because a verdict is a statement about the target, and a caller who wired
    the probe wrong has learned nothing about the target.
    """

    #: Not swept here: adapter behaviour beyond None/Verdict/raise, case
    #: contents, and the interaction of `argument` with *args/**kwargs targets.
    NOT_SWEPT = "adapter return shapes, case payloads, *args targets"

    HOSTILE = [None, "", "   ", 0, False, True, [], {}, 3.5, object()]

    @staticmethod
    def _target(value):
        return (measured_pass(1) if value
                else not_measured("empty", cause="input_absent"))

    def test_no_hostile_argument_value_yields_a_verdict(self) -> None:
        """`argument or params[0]` silently probed a different parameter and
        reported PASS about it."""
        offenders = []
        for value in self.HOSTILE:
            if value is None:
                continue                      # None means "use the first one"
            try:
                report = degenerate.probe(self._target,
                                          [degenerate.EMPTY_COLLECTION],
                                          argument=value)
                offenders.append(f"argument={value!r} -> {report.result.value}")
            except TypeError:
                pass
        assert not offenders, (
            "a call the probe could not honour returned a verdict about the "
            f"target instead of failing: {offenders}")

    def test_no_hostile_extra_kwargs_value_yields_a_verdict(self) -> None:
        offenders = []
        for value in [*self.HOSTILE, {1: "v"}, [("k", 1)]]:
            if value is None or (isinstance(value, dict)
                                 and all(isinstance(k, str) for k in value)):
                continue
            try:
                report = degenerate.probe(self._target,
                                          [degenerate.EMPTY_COLLECTION],
                                          extra_kwargs=value)
                offenders.append(f"extra_kwargs={value!r} -> {report.result.value}")
            except TypeError:
                pass
        assert not offenders, offenders

    def test_no_hostile_target_yields_a_verdict(self) -> None:
        offenders = []
        for value in self.HOSTILE:
            try:
                report = degenerate.probe(value, [degenerate.EMPTY_COLLECTION])
                offenders.append(f"target={value!r} -> {report.result.value}")
            except TypeError:
                pass
        assert not offenders, (
            "a non-callable was reported as a target that could not be "
            f"inspected: {offenders}")

    def test_a_well_formed_call_still_works(self) -> None:
        """The sweep must not pass by rejecting everything."""
        assert degenerate.probe(self._target, [degenerate.EMPTY_COLLECTION],
                                argument="value").result is Verdict.PASS
        assert degenerate.probe(self._target, [degenerate.EMPTY_COLLECTION],
                                extra_kwargs={}).result is Verdict.PASS


class TestProvenanceNamesWhatActuallyRan:
    def test_an_adapter_that_answers_nothing_is_not_an_answer(self) -> None:
        report = degenerate.probe(lambda x: "legacy",
                                  [degenerate.EMPTY_COLLECTION],
                                  adapter=lambda o: None)
        assert report.adapter_used is False
        assert report.observations[0].adapted is False
        assert report.result is Verdict.INCONCLUSIVE

    def test_a_native_record_that_raises_is_not_an_adapter_failure(self) -> None:
        """It named a component that was not in the run."""
        class Broken(dict):
            def __getitem__(self, key):
                raise RuntimeError("broken getter")

        report = degenerate.probe(lambda x: Broken(measurement_status="PASS"),
                                  [degenerate.EMPTY_COLLECTION])
        observation = report.observations[0]
        assert observation.probe_status is Verdict.ERROR
        assert observation.adapted is False
        assert "adapter" not in observation.note
        assert report.adapter_used is False

    def test_a_broken_adapter_is_named_as_one(self) -> None:
        def explode(value):
            raise RuntimeError("adapter boom")

        observation = degenerate.probe(lambda x: "legacy",
                                       [degenerate.EMPTY_COLLECTION],
                                       adapter=explode).observations[0]
        assert observation.adapted is True
        assert "the adapter failed" in observation.note

    def test_an_adapter_returning_a_non_verdict_is_refused(self) -> None:
        observation = degenerate.probe(lambda x: "legacy",
                                       [degenerate.EMPTY_COLLECTION],
                                       adapter=lambda o: "PASS").observations[0]
        assert observation.probe_status is Verdict.ERROR


class TestAFailureNamesItsOwnSource:
    """The handler guessed where the error came from, and the guess re-entered.

    Both sides were classified in one `try`, and the handler then re-inspected
    the payloads to decide whether the adapter or the native reader had failed.
    Two consequences, both real:

      * a native control paired with a legacy degenerate blamed "reading the
        native status" for an exception the adapter raised, and
      * re-inspecting a mapping whose `__contains__` raises re-raised the same
        error out of the handler, so the probe died where it should have
        returned ERROR.

    The failure now carries its own provenance. Nothing downstream infers it.
    """

    class Broken(dict):
        def __getitem__(self, key):
            raise RuntimeError("broken getter")

        def __contains__(self, key) -> bool:
            raise RuntimeError("broken getter")

    def test_an_adapter_failure_on_a_mixed_pair_is_named_correctly(self) -> None:
        case = degenerate.SelectivityCase(
            name="mixed", control=Verdict.PASS, degenerate="legacy",
            expects_on_degenerate=Verdict.NOT_MEASURED, rationale="r")

        def explode(value):
            raise RuntimeError("adapter boom")

        observation = degenerate.probe(lambda source: source, [case],
                                       adapter=explode).observations[0]
        assert observation.probe_status is Verdict.ERROR
        assert observation.adapted is True
        assert "the adapter failed on the degenerate input" in observation.note

    def test_a_broken_native_payload_does_not_kill_the_probe(self) -> None:
        """It raised out of the handler; the caller got an exception, not a
        report, and a probe that dies establishes nothing."""
        case = degenerate.SelectivityCase(
            name="mixed", control="legacy", degenerate=self.Broken(),
            expects_on_degenerate=Verdict.NOT_MEASURED, rationale="r")
        report = degenerate.probe(lambda source: source, [case],
                                  adapter=lambda o: Verdict.PASS)
        assert report.result is Verdict.ERROR
        observation = report.observations[0]
        assert observation.adapted is False
        assert "native status of the degenerate input" in observation.note

    def test_the_failing_side_is_identified(self) -> None:
        case = degenerate.SelectivityCase(
            name="control-side", control=self.Broken(), degenerate=[],
            expects_on_degenerate=Verdict.NOT_MEASURED, rationale="r")
        note = degenerate.probe(lambda source: source, [case]).observations[0].note
        assert "control input" in note

    def test_classification_errors_carry_their_type(self) -> None:
        """The two are distinguishable at the boundary, not by re-examination."""
        with pytest.raises(degenerate.AdapterClassificationError):
            degenerate.classify_with_provenance(
                "legacy", lambda o: (_ for _ in ()).throw(RuntimeError("x")))
        with pytest.raises(degenerate.AdapterClassificationError):
            degenerate.classify_with_provenance("legacy", lambda o: "PASS")
        with pytest.raises(degenerate.NativeClassificationError):
            degenerate.classify_with_provenance(self.Broken())

    @pytest.mark.parametrize("control,degen", [
        (Verdict.PASS, "legacy"), ("legacy", Verdict.PASS),
        ("legacy", "legacy"), (Verdict.PASS, Verdict.NOT_MEASURED)])
    def test_no_mixed_pair_escapes_as_an_exception(self, control, degen) -> None:
        """The call space again: every native/legacy combination returns a
        report, whatever the adapter does to it."""
        case = degenerate.SelectivityCase(
            name="pair", control=control, degenerate=degen,
            expects_on_degenerate=Verdict.NOT_MEASURED, rationale="r")
        for adapter in (None, lambda o: None, lambda o: Verdict.NOT_MEASURED,
                        lambda o: "not a verdict",
                        lambda o: (_ for _ in ()).throw(RuntimeError("x"))):
            report = degenerate.probe(lambda source: source, [case],
                                      adapter=adapter)
            assert isinstance(report.result, Verdict)


class TestThePayloadAndAdapterSpace:
    """Every native/legacy payload pair against every adapter shape.

    The classification boundary was the third defect found in code this sweep
    could have reached, so it is now swept: 7 payload shapes on each side times
    5 adapter behaviours. The rule is the same one the call-space sweep uses —
    a probe returns a report or raises a documented configuration error; it
    never dies partway through classifying.
    """

    class Broken(dict):
        def __getitem__(self, key):
            raise RuntimeError("broken getter")

        def __contains__(self, key) -> bool:
            raise RuntimeError("broken getter")

    def _payloads(self) -> dict:
        return {"native_verdict": Verdict.PASS,
                "native_measurement": measured_pass(1),
                "native_mapping": {"measurement_status": "PASS"},
                "legacy_str": "ok", "legacy_none": None, "legacy_bool": True,
                "broken_mapping": self.Broken()}

    @staticmethod
    def _adapters() -> dict:
        def raises(value):
            raise RuntimeError("boom")

        return {"none": None, "answers_none": lambda o: None,
                "answers_verdict": lambda o: Verdict.NOT_MEASURED,
                "answers_junk": lambda o: "PASS", "raises": raises}

    def test_no_combination_crashes_or_invents_provenance(self) -> None:
        payloads, adapters = self._payloads(), self._adapters()
        crashes, provenance = [], []
        examined = 0
        for cname, control in payloads.items():
            for dname, degen in payloads.items():
                for aname, adapter in adapters.items():
                    examined += 1
                    case = degenerate.SelectivityCase(
                        name=f"{cname}-{dname}", control=control, degenerate=degen,
                        expects_on_degenerate=Verdict.NOT_MEASURED, rationale="r")
                    try:
                        report = degenerate.probe(lambda source: source, [case],
                                                  adapter=adapter)
                    except Exception as exc:  # noqa: BLE001
                        crashes.append(f"{cname}/{dname}/{aname}: "
                                       f"{type(exc).__name__}")
                        continue
                    assert isinstance(report.result, Verdict)
                    if adapter is None and report.observations[0].adapted:
                        provenance.append(
                            f"{cname}/{dname}: adapted with no adapter present")
        assert examined == len(payloads) ** 2 * len(adapters)
        assert not crashes, f"the probe died instead of reporting: {crashes[:5]}"
        assert not provenance, provenance[:5]
