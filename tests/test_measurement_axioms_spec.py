"""The specification must not be able to lie about itself.

A specification with no executable check is, by its own MA-7.1, an advisory
control — it may not be represented as an enforced one. These tests are what
makes it enforceable at all.

Three things are checked here:

  1. The schema does what the normative text says. Every conditional rule in
     `verdict-outcome.schema.json` corresponds to a numbered requirement, and
     the test vectors in §10 are executed against it.
  2. The specification, the schema and the conformance requirements stay in
     sync. A requirement present in one and absent from another is a citation
     that does not resolve, which is MA-9.1.
  3. The requirement set states honestly what an automated run cannot decide.
     If every requirement claimed to be machine-assessable, the file would be
     asserting a coverage it does not have.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")
jsonschema = pytest.importorskip("jsonschema")

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_DIR = REPO_ROOT / "spec" / "v1.0"
SPEC_MD = SPEC_DIR / "MEASUREMENT_AXIOMS_SPECIFICATION.md"
SCHEMA = SPEC_DIR / "verdict-outcome.schema.json"
REQUIREMENTS = SPEC_DIR / "conformance-requirements.yaml"

VALID_ASSESSABLE = {"schema", "schema_and_dynamic", "static", "dynamic", "review"}
VERDICTS = {"PASS", "FAIL", "NOT_MEASURED", "INCONCLUSIVE", "ERROR", "NOT_APPLICABLE"}


@pytest.fixture(scope="module")
def schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def requirements() -> dict:
    return yaml.safe_load(REQUIREMENTS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def spec_text() -> str:
    return SPEC_MD.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def validator(schema: dict):
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    return cls(schema)


#: MA-7.8 — the minimum directive an intervening outcome must carry. Tests that
#: are about something else should not have to spell this out, but they must not
#: be exempt from it either: a fixture that skips a requirement quietly tests a
#: record shape the specification forbids.
DEFAULT_INTERVENTION = {
    "block": {"type": "block", "intended_consumer": "executor"},
    "attenuate": {"type": "attenuate", "intended_consumer": "renderer",
                  "parameters": {"factor": 0.5}},
    "escalate": {"type": "escalate", "intended_consumer": "review_queue"},
    "abstain": {"type": "defer", "intended_consumer": "scheduler",
                "parameters": {"until": "human_review"}},
}


def _complete(base: dict) -> dict:
    outcome = base["decision_outcome"]
    if outcome == "allow":
        return base
    base.setdefault("enforcement_status", "requested")
    if "intervention" not in base:
        base["intervention"] = dict(DEFAULT_INTERVENTION[outcome])
    return base


def record(**overrides) -> dict:
    """A minimal conformant record, before overrides."""
    base = {
        "spec_version": "1.0",
        "subject": {"component": "test.gate", "profile": "default",
                    "timestamp_utc": "2026-08-01T00:00:00Z"},
        "measurement_status": "PASS",
        "decision_outcome": "allow",
        "evidence_status": "E0",
    }
    base.update(overrides)
    return _complete(base)


class TestSchemaIsWellFormed:
    def test_schema_is_a_valid_json_schema(self, validator) -> None:
        assert validator is not None  # check_schema ran in the fixture

    def test_the_verdict_algebra_has_exactly_six_values(self, schema: dict) -> None:
        assert set(schema["properties"]["measurement_status"]["enum"]) == VERDICTS

    def test_measurement_and_decision_are_separate_required_fields(
        self, schema: dict
    ) -> None:
        """MA-4.1 — the conflation the whole specification exists to prevent."""
        assert "measurement_status" in schema["required"]
        assert "decision_outcome" in schema["required"]
        assert set(schema["properties"]["measurement_status"]["enum"]).isdisjoint(
            schema["properties"]["decision_outcome"]["enum"]
        ), "a value appearing in both fields would let one be read as the other"

    def test_a_minimal_conformant_record_validates(self, validator) -> None:
        validator.validate(record())


class TestNormativeRulesAreEnforced:
    """Each maps to a numbered requirement, and each must be able to fail."""

    def test_not_applicable_requires_a_scope_decision(self, validator) -> None:
        """MA-3.3"""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(record(measurement_status="NOT_APPLICABLE",
                                      decision_outcome="abstain"))
        validator.validate(record(measurement_status="NOT_APPLICABLE",
                                  decision_outcome="abstain",
                                  scope_decision={"ref": "doc://scope#gate",
                                                  "resolvable": True}))

    def test_not_measured_cannot_allow(self, validator) -> None:
        """MA-4.3 — the single most important rule in the schema."""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(record(measurement_status="NOT_MEASURED",
                                      decision_outcome="allow"))
        for outcome in ("block", "escalate", "abstain"):
            validator.validate(record(measurement_status="NOT_MEASURED",
                                      decision_outcome=outcome,
                                      non_measurement_cause="not_executed"))

    def test_pass_cannot_be_claimed_with_absent_inputs(self, validator) -> None:
        """MA-3.9 — a fabricated denominator is the shape this catches."""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(record(measurement_status="PASS",
                                      measured={"inputs_present": False}))
        validator.validate(record(measurement_status="NOT_MEASURED",
                                  decision_outcome="escalate",
                                  non_measurement_cause="input_absent",
                                  measured={"inputs_present": False}))

    def test_enforcement_binds_to_the_decision_not_the_measurement(
        self, validator
    ) -> None:
        """MA-7.3, corrected.

        The first version of this test asserted that `NOT_MEASURED + block +
        applied` was invalid — coupling enforcement to measurement, which is the
        conflation MA-4.1 forbids. Blocking *because* nothing could be measured,
        and carrying that block out, is the fail-safe path the doctrine asks for.
        """
        validator.validate(record(measurement_status="NOT_MEASURED",
                                  decision_outcome="block",
                                  non_measurement_cause="input_unreadable",
                                  enforcement_status="applied",
                                  intervention={"type": "block", "intended_consumer": "gate",
                                            "material_effect": {"ref": "t://1",
                                                  "resolvable": True}}))
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(record(decision_outcome="allow",
                                      enforcement_status="applied"))

    def test_unknown_verdict_values_are_rejected(self, validator) -> None:
        """MA-3.6's producer-side counterpart: the enum is closed."""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(record(measurement_status="OK"))

    def test_degraded_is_a_mode_not_an_execution_status(self, schema: dict) -> None:
        """MA-4.4 — the dimensions stay orthogonal."""
        assert "degraded" not in schema["properties"]["execution_status"]["enum"]
        assert "degraded" in schema["properties"]["operating_mode"]["enum"]


class TestTestVectors:
    """§10 of the specification, executed rather than asserted."""

    def test_tv1_empty_collection_is_not_measured(self, validator) -> None:
        validator.validate(record(measurement_status="NOT_MEASURED",
                                  decision_outcome="escalate",
                                  non_measurement_cause="input_absent",
                                  measured={"inputs_present": False, "items_checked": 0}))
        for bad in ({"inputs_present": False, "items_checked": 0},
                    {"inputs_present": True, "items_checked": 0}):
            with pytest.raises(jsonschema.ValidationError):
                validator.validate(record(measurement_status="PASS", measured=bad))

    def test_tv9_an_unresolvable_pointer_is_marked_so(self, validator) -> None:
        """MA-9.1 — the presence of a digest does not make a pointer resolvable."""
        validator.validate(record(
            measured={"inputs_present": True, "items_checked": 1},
            evidence=[{"ref": "store://opaque/key",
                       "content_hash": "sha256:" + "0" * 64, "resolvable": False}]))

    def test_tv10_not_applicable_without_scope_is_rejected(self, validator) -> None:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(record(measurement_status="NOT_APPLICABLE",
                                      decision_outcome="abstain",
                                      scope_decision=None))
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(record(measurement_status="NOT_APPLICABLE",
                                      decision_outcome="abstain",
                                      scope_decision="a free string"))


class TestSpecAndRequirementsStayInSync:
    """A requirement in one file and not the other is MA-9.1 applied to us."""

    _ID = re.compile(r"\*\*(MA-\d+\.\d+)\.\*\*")

    def test_every_numbered_requirement_appears_in_both(
        self, spec_text: str, requirements: dict
    ) -> None:
        in_spec = set(self._ID.findall(spec_text))
        in_yaml = {r["id"] for r in requirements["requirements"]}
        assert in_spec, "no numbered requirements found — the regex or the spec changed"
        assert in_spec == in_yaml, (
            f"only in spec: {sorted(in_spec - in_yaml)}; "
            f"only in requirements: {sorted(in_yaml - in_spec)}"
        )

    def test_requirement_ids_are_unique(self, requirements: dict) -> None:
        ids = [r["id"] for r in requirements["requirements"]]
        assert len(ids) == len(set(ids))

    def test_every_cited_test_vector_exists_in_the_spec(
        self, spec_text: str, requirements: dict
    ) -> None:
        in_spec = set(re.findall(r"\| (TV-\d+) \|", spec_text))
        cited = {t for r in requirements["requirements"]
                 for t in (r.get("test_vectors") or [])}
        assert cited <= in_spec, f"cited but not defined: {sorted(cited - in_spec)}"

    def test_the_schema_named_by_the_requirements_exists(
        self, requirements: dict
    ) -> None:
        assert (SPEC_DIR / requirements["schema"]).exists()
        assert (SPEC_DIR / requirements["normative_source"]).exists()


class TestTheRequirementsAreHonestAboutTheirOwnCoverage:
    """If everything claimed to be machine-checkable, that would be the defect."""

    def test_assessability_uses_the_controlled_vocabulary(
        self, requirements: dict
    ) -> None:
        for r in requirements["requirements"]:
            assert r["assessable"] in VALID_ASSESSABLE, f"{r['id']}: {r['assessable']}"

    def test_some_requirements_are_declared_review_only(
        self, requirements: dict
    ) -> None:
        review = [r["id"] for r in requirements["requirements"]
                  if r["assessable"] == "review"]
        assert review, (
            "no requirement is marked review-only. Either the specification "
            "became fully machine-checkable, or the file is claiming a coverage "
            "it does not have — which is the failure it exists to prevent"
        )

    def test_reporting_uses_the_same_algebra_it_specifies(
        self, requirements: dict
    ) -> None:
        assert set(requirements["reporting"]["per_requirement_result"]["enum"]) == VERDICTS

    def test_a_single_aggregate_pass_is_prohibited(self, requirements: dict) -> None:
        assert "prohibited" in requirements["reporting"]["aggregate"]

    def test_the_conformance_ladder_is_stated_and_ordered(
        self, requirements: dict
    ) -> None:
        ladder = requirements["reporting"]["position"]["ladder"]
        assert ladder[0] == "mapped" and ladder[-1] == "certified"
        assert "independently_assessed" in ladder


def _record(**overrides) -> dict:
    """A minimal record that validates, before overrides."""
    base = {
        "spec_version": "1.0",
        "subject": {"component": "t", "profile": "default",
                    "timestamp_utc": "2026-08-01T00:00:00Z"},
        "measurement_status": "PASS",
        "decision_outcome": "allow",
        "evidence_status": "E0",
    }
    base.update(overrides)
    return _complete(base)


class TestSchemaEnforcesTheNormativeText:
    """Every case below was VALID against the first schema and should not have been.

    A schema that carries its requirements in `description` is documentation. The
    conformance requirements mark these `assessable: schema`, which is a claim
    that a validator decides them — so these tests are what makes that claim true.
    """

    def test_the_profile_in_force_is_required(self, validator) -> None:
        """MA-4.10"""
        r = _record()
        r["subject"] = {"component": "t", "timestamp_utc": "2026-08-01T00:00:00Z"}
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(r)

    def test_a_pass_over_zero_objects_is_rejected(self, validator) -> None:
        """MA-3.9 / MA-6.1 — the vacuous pass, in record form."""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(measured={"inputs_present": True,
                                                 "items_checked": 0}))

    def test_degraded_operation_is_never_passing(self, validator) -> None:
        """MA-4.4"""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(operating_mode="degraded"))
        validator.validate(_record(operating_mode="degraded",
                                   measurement_status="NOT_MEASURED",
                                   decision_outcome="escalate",
                                   non_measurement_cause="suppressed_by_tier"))

    def test_fail_safe_enforcement_on_an_unmeasured_decision_is_legitimate(
        self, validator
    ) -> None:
        """The rule that had it backwards.

        `NOT_MEASURED + block + applied` reads: nothing could be measured, so the
        action was blocked, and the block was carried out. The first schema
        rejected it, re-coupling enforcement to measurement — the conflation the
        whole specification exists to prevent.
        """
        validator.validate(_record(measurement_status="NOT_MEASURED",
                                   decision_outcome="block",
                                   non_measurement_cause="object_unreachable",
                                   enforcement_status="applied",
                                   intervention={"type": "block", "intended_consumer": "gate",
                                             "material_effect": {"ref": "t://1",
                                                  "resolvable": True}}))

    def test_enforcement_applied_requires_a_decision_that_needed_it(
        self, validator
    ) -> None:
        """MA-7.3 — `allow` enforces nothing."""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(decision_outcome="allow",
                                       enforcement_status="applied"))

    def test_an_unsupported_evidence_level_is_rejected(self, validator) -> None:
        """MA-5.4 — E4 without a basis is a self-declared label."""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(evidence_status="E4"))
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(
                evidence_status="E3",
                integrity={"algorithm": "ed25519", "signature": "x", "key_id": "k"}))
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(evidence_status="E1"))
        validator.validate(_record(evidence_status="E4", integrity=FULL_INTEGRITY,
                                   replay={"policy_version": "1.2", "state_ref": "s://1"}))

    def test_a_scope_decision_must_be_a_resolvable_reference(self, validator) -> None:
        """MA-3.3 — a free string cannot be resolved, so it establishes nothing."""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(measurement_status="NOT_APPLICABLE",
                                       decision_outcome="abstain",
                                       scope_decision="anything"))
        validator.validate(_record(measurement_status="NOT_APPLICABLE",
                                   decision_outcome="abstain",
                                   scope_decision={"ref": "doc://scope#7",
                                                   "resolvable": True}))

    def test_vendor_fields_cannot_hide_in_core_sub_objects(self, validator) -> None:
        """`profiles` is the single extension point, or it is not one."""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(measured={"inputs_present": True,
                                                 "vendor_thing": 1}))
        validator.validate(_record(profiles={"vendor": {"anything": 1}}))


class TestEverySchemaAssessableRequirementHasARule:
    """A requirement labelled `schema` must be decided by the schema.

    Four were labelled `schema` while the validator accepted every violation.
    The label is a claim about the tooling and gets checked like any other.
    """

    #: Requirements decided by the schema's own structure rather than by a
    #: conditional rule. Listed explicitly, because the alternative is to search
    #: the schema text — and a requirement mentioned in a `description` is
    #: documented, not decided. The first version of this test did search the
    #: text, and passed MA-3.11 on a mention while the validator accepted every
    #: record that violated it.
    STRUCTURAL = {
        "MA-4.1": "measurement_status and decision_outcome are both root-required",
        "MA-4.10": "subject.profile is required",
        "MA-5.2": "evidence_status is root-required",
    }

    def test_no_requirement_claims_schema_assessability_without_a_rule(
        self, requirements: dict, schema: dict
    ) -> None:
        cited = {rid for rule in schema.get("allOf", [])
                 for rid in re.findall(r"MA-\d+\.\d+", rule.get("$comment", ""))}
        decided = cited | set(self.STRUCTURAL)
        schema_assessed = {r["id"] for r in requirements["requirements"]
                           if r["assessable"].startswith("schema")}
        assert schema_assessed, "no requirement is schema-assessable — check the labels"
        missing = sorted(schema_assessed - decided)
        assert not missing, (
            "labelled `assessable: schema` but no conditional rule cites them and "
            f"they are not structurally decided: {missing}. Add the rule, add it "
            "to STRUCTURAL with a reason, or relabel the requirement."
        )

    def test_the_structural_exemptions_are_real(self, validator) -> None:
        """An exemption list is a place to hide. Each entry must bite."""
        base = _record()
        for field in ("measurement_status", "decision_outcome", "evidence_status"):
            with pytest.raises(jsonschema.ValidationError,
                               match="required property"):
                validator.validate({k: v for k, v in base.items() if k != field})

    def test_a_not_measured_record_must_name_its_cause(self, validator) -> None:
        """MA-3.11 — the requirement that exposed the mention-as-rule gap."""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(measurement_status="NOT_MEASURED",
                                       decision_outcome="escalate"))
        validator.validate(_record(measurement_status="NOT_MEASURED",
                                   decision_outcome="escalate",
                                   non_measurement_cause="suppressed_by_tier"))


FULL_INTEGRITY = {
    "mechanism": "signature_chain", "algorithm": "ed25519",
    "previous_digest": "sha256:" + "c" * 64,
    "digest": "sha256:" + "a" * 64, "signature": "sig", "key_id": "k1",
    "signed_at": "2026-08-01T00:00:00Z", "signed_fields": ["measurement_status"],
    "identity_binding_ref": "id://org/a", "trust_anchor_ref": "ta://root",
    "revocation_status_ref": "crl://ok",
}


class TestEvidenceLevelsRequireTheirBasis:
    """A level is a claim about a mechanism, not a label a producer selects.

    The first schema modelled only E2 and E4, so `evidence_status: E1` with no
    integrity mechanism at all validated — the record asserting it had not been
    altered undetectably, and evidencing nothing.
    """

    def test_e1_requires_an_integrity_mechanism(self, validator) -> None:
        """MA-5.3"""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(evidence_status="E1"))
        validator.validate(_record(evidence_status="E1", integrity={
            "mechanism": "hash_chain", "algorithm": "sha256",
            "digest": "sha256:" + "b" * 64,
            "previous_digest": "sha256:" + "c" * 64}))

    def test_e3_fields_present_but_null_do_not_establish_e3(self, validator) -> None:
        """Presence was the whole test before; a null value passed it."""
        holed = dict(FULL_INTEGRITY, identity_binding_ref=None)
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(evidence_status="E3", integrity=holed))
        validator.validate(_record(evidence_status="E3", integrity=FULL_INTEGRITY))

    def test_an_unresolved_scope_pointer_is_not_an_exclusion(self, validator) -> None:
        """MA-3.3 — `resolvable: false` leaves the exclusion unestablished."""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(measurement_status="NOT_APPLICABLE",
                                       decision_outcome="abstain",
                                       scope_decision={"ref": "doc://s",
                                                       "resolvable": False}))


class TestAppliedInterventionsEvidenceTheirEffect:
    """MA-7.2 — `applied` is a claim of material change."""

    def test_applied_without_an_intervention_record_is_rejected(self, validator) -> None:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(decision_outcome="attenuate",
                                       enforcement_status="applied"))

    def test_applied_with_a_material_effect_reference_is_accepted(
        self, validator
    ) -> None:
        validator.validate(_record(
            decision_outcome="attenuate", enforcement_status="applied",
            intervention={"type": "attenuate", "intended_consumer": "renderer",
                          "acknowledged_by": "renderer",
                          "material_effect": {"ref": "trace://run/7#out", "resolvable": True},
                          "parameters": {"factor": 0.5}}))

    def test_a_parameterised_directive_without_parameters_is_advisory(
        self, validator
    ) -> None:
        """MA-7.4 — `attenuate` by how much? Unanswered, it names no act."""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(
                decision_outcome="attenuate", enforcement_status="applied",
                intervention={"type": "attenuate", "intended_consumer": "r",
                              "material_effect": {"ref": "t://1",
                                                  "resolvable": True}}))


class TestTheReferenceImplementationSatisfiesItsOwnSchema:
    """The gap that both artefacts passing their own tests could not show.

    `verdict.py` was checked against its own assertions and the schema against
    hand-written records. Neither run put the producer in front of the
    validator, and two incompatibilities lived in between: a `detail` wrapper
    the schema rejected outright, and a `scope_decision` string where the schema
    required an object. Each file was internally consistent and the pair was not.
    """

    @staticmethod
    def _project(measurement, **over) -> dict:
        rec = {"spec_version": "1.0",
               "subject": {"component": "t", "profile": "default",
                           "timestamp_utc": "2026-08-01T00:00:00Z"},
               "decision_outcome": "escalate", "evidence_status": "E0"}
        rec.update(measurement.to_record_fields())
        rec.update(over)
        return _complete(rec)

    @pytest.mark.parametrize("name", [
        "measured_pass", "measured_fail", "not_measured", "inconclusive",
        "errored", "not_applicable"])
    def test_every_constructor_projects_to_a_valid_record(
        self, validator, name: str
    ) -> None:
        v = _verdict_module()
        cases = {
            "measured_pass": (v.measured_pass(3), {}),
            "measured_fail": (v.measured_fail("mismatch", items_checked=3),
                              {"decision_outcome": "block",
                               "enforcement_status": "applied",
                               "intervention": {"type": "block",
                                                "intended_consumer": "gate",
                                                "material_effect": {
                                                    "ref": "t://1",
                                                    "resolvable": True}}}),
            "not_measured": (v.not_measured("tier skipped",
                                            cause="suppressed_by_tier"), {}),
            "inconclusive": (v.inconclusive("ambiguous", items_checked=2), {}),
            "errored": (v.errored("adapter raised"), {}),
            "not_applicable": (v.not_applicable(
                v.ScopeDecision("doc://scope#7", True, evaluated_version="1.2")),
                {"decision_outcome": "abstain"}),
        }
        measurement, over = cases[name]
        rec = self._project(measurement, **over)
        errors = sorted(validator.iter_errors(rec), key=lambda e: list(e.path))
        assert not errors, (
            f"{name}() emits a record its own schema rejects: "
            + "; ".join(e.message for e in errors) + f"\nrecord={rec}")

    def test_the_cause_vocabulary_matches_the_schema_enum(self, schema: dict) -> None:
        v = _verdict_module()
        assert set(v.NON_MEASUREMENT_CAUSES) == set(
            schema["properties"]["non_measurement_cause"]["enum"]), (
            "the producer and the validator disagree about what may be recorded "
            "as a reason for non-measurement")


def _verdict_module():
    """The reference implementation, loaded the way a consumer would."""
    import sys
    sys.path.insert(0, str(SPEC_DIR / "conformance"))
    return pytest.importorskip("verdict")


class TestPresenceIsNotEvidence:
    """Three rules required a field and accepted a null in it.

    `material_effect_ref: null`, `parameters: null`, `parameters: {}` all
    satisfied a `required` clause while carrying nothing. A schema that checks
    for a key and not for a value tests the producer's vocabulary, not its
    claim — which is MA-3.9 committed by the validator instead of the emitter.
    """

    @staticmethod
    def _applied(**iv) -> dict:
        base = {"type": "attenuate", "intended_consumer": "renderer",
                "material_effect": {"ref": "t://1", "resolvable": True},
                "parameters": {"factor": 0.5}}
        base.update(iv)
        return _record(decision_outcome="attenuate", enforcement_status="applied",
                       intervention=base)

    def test_a_null_material_effect_is_not_a_material_effect(self, validator) -> None:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(self._applied(material_effect=None))
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(self._applied(material_effect={"ref": "", "resolvable": True}))

    def test_an_unresolved_material_effect_is_not_evidence(self, validator) -> None:
        """MA-7.6 — the same rule the scope decision gets, for the same reason."""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(self._applied(
                material_effect={"ref": "t://1", "resolvable": False}))

    @pytest.mark.parametrize("params", [None, {}])
    def test_empty_parameters_name_no_performable_act(self, validator, params) -> None:
        """MA-7.4"""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(self._applied(parameters=params))


class TestOutcomeAndMechanismAgree:
    """MA-7.7 — `block` decided, `attenuate` performed: which did the system do?"""

    def test_an_incompatible_pair_is_rejected(self, validator) -> None:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(
                decision_outcome="block", enforcement_status="applied",
                intervention={"type": "attenuate", "intended_consumer": "r",
                              "parameters": {"factor": 0.5},
                              "material_effect": {"ref": "t://1", "resolvable": True}}))

    def test_a_mechanism_refining_its_outcome_is_accepted(self, validator) -> None:
        validator.validate(_record(
            decision_outcome="attenuate", enforcement_status="applied",
            intervention={"type": "redact", "intended_consumer": "r",
                          "parameters": {"spans": [[0, 4]]},
                          "material_effect": {"ref": "t://1", "resolvable": True}}))

    def test_allow_carries_no_intervention(self, validator) -> None:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(decision_outcome="allow", intervention={
                "type": "block", "intended_consumer": "r",
                "material_effect": {"ref": "t://1", "resolvable": True}}))

    def test_the_normative_table_and_the_schema_agree(
        self, spec_text: str, schema: dict
    ) -> None:
        """The table is the specification's; the rules are the schema's.

        Two places state the same mapping, so they can disagree. This reads the
        table out of the document and checks each row against the validator.
        """
        # Scoped to MA-7.7's own table: MA-7.8 has a table with an `allow` row
        # too, and an unscoped pattern silently merged the two.
        section = spec_text[spec_text.index("**MA-7.7.**"):
                            spec_text.index("**MA-7.8.**")]
        rows = re.findall(r"^\| `(allow|block|attenuate|escalate|abstain)` \| (.+?) \|$",
                          section, re.M)
        assert len(rows) == 5, f"the MA-7.7 table has {len(rows)} rows, expected 5"
        cls = jsonschema.validators.validator_for(schema)(schema)
        for outcome, permitted in rows:
            types = re.findall(r"`(\w+)`", permitted)
            for t in ("block", "attenuate", "redact", "rate_limit", "escalate", "defer"):
                rec = _record(decision_outcome=outcome, intervention={
                    "type": t, "intended_consumer": "r",
                    "parameters": {"x": 1},
                    "material_effect": {"ref": "t://1", "resolvable": True}})
                assert cls.is_valid(rec) is (t in types), (
                    f"the table says {outcome} -> {types or 'none'}, "
                    f"but the schema {'accepts' if t not in types else 'rejects'} "
                    f"intervention.type={t}")


class TestTheTypeCarriesItsOwnInvariants:
    """A rule enforced only in a helper is enforced only on the convenient path.

    Every invariant below was in a constructor function while the public
    dataclass accepted the violation directly. A caller reaching for
    `Measurement(...)` — which the module exports — bypassed all of them.
    """

    def test_not_measured_without_a_cause_is_refused(self) -> None:
        v = _verdict_module()
        with pytest.raises(v.CollapseError, match="MA-3.11"):
            v.Measurement(v.Verdict.NOT_MEASURED, reason="did not run")

    def test_a_cause_on_a_measured_verdict_is_refused(self) -> None:
        v = _verdict_module()
        with pytest.raises(v.CollapseError, match="only with NOT_MEASURED"):
            v.Measurement(v.Verdict.PASS, items_checked=1, cause="unknown")

    def test_an_unresolved_scope_decision_is_refused_on_the_type(self) -> None:
        v = _verdict_module()
        with pytest.raises(v.CollapseError, match="did not resolve"):
            v.Measurement(v.Verdict.NOT_APPLICABLE,
                          scope_decision=v.ScopeDecision("doc://gone", False))

    def test_error_asserts_no_input_state_by_default(self) -> None:
        v = _verdict_module()
        assert v.errored("crashed").inputs_present is None
        assert "measured" not in v.errored("crashed").to_record_fields()


class TestTheRulesDoNotContradictEachOther:
    """Two rules in one schema disagreed about the same set.

    MA-7.6 listed the intervening outcomes as block/attenuate/escalate/abstain;
    a rule left from an earlier round listed three of them. Each rule was
    defensible read alone, and together they rejected the abstain/defer pair
    MA-7.7 permits. Nothing tested the rules against each other, so the
    contradiction survived a green suite.
    """

    INTERVENING = {"block", "attenuate", "escalate", "abstain"}

    #: MA-4.3 constrains a different set — which outcomes an *unmeasured*
    #: decision may take. Three artefacts already agree on it and the
    #: specification enumerates it, so it is excluded here by name rather than
    #: silently swept in. Conflating the two sets is what the first version of
    #: this test did, and it read a deliberate closed list as a contradiction.
    OTHER_SETS = {"MA-4.3"}

    def _rule_sets(self, schema: dict) -> list[tuple[str, set[str]]]:
        found = []
        for rule in schema.get("allOf", []):
            comment = rule.get("$comment", "?")
            if any(comment.startswith(x) for x in self.OTHER_SETS):
                continue
            for node in (rule.get("if", {}), rule.get("then", {})):
                enum = (node.get("properties", {})
                            .get("decision_outcome", {}).get("enum"))
                if enum and set(enum) & self.INTERVENING:
                    found.append((comment[:24], set(enum)))
        return found

    def test_every_rule_naming_the_intervening_set_names_the_same_set(
        self, schema: dict
    ) -> None:
        found = self._rule_sets(schema)
        assert found, "no rule constrains decision_outcome — the check is vacuous"
        odd = [(c, s) for c, s in found if s != self.INTERVENING]
        assert not odd, f"rules disagree about the intervening set: {odd}"

    def test_the_unmeasured_set_is_the_one_the_document_enumerates(
        self, spec_text: str, schema: dict
    ) -> None:
        """MA-4.3's set is narrower on purpose, and all three artefacts hold it.

        `attenuate` is absent because attenuating by a stated amount presupposes
        a measurement. The excluded-by-name rule above must not become a place
        where a real drift hides, so the set is checked against the sentence.
        """
        sentence = spec_text[spec_text.index("**MA-4.3.**"):][:400]
        tail = sentence[sentence.index("`allow`") + 7:]
        documented = {w for w in ("block", "escalate", "abstain", "attenuate")
                      if f"`{w}`" in tail}
        rule = next(r for r in schema["allOf"]
                    if r.get("$comment", "").startswith("MA-4.3"))
        in_schema = set(rule["then"]["properties"]["decision_outcome"]["enum"])
        assert in_schema == documented, (
            f"the specification enumerates {sorted(documented)} for an unmeasured "
            f"decision; the schema permits {sorted(in_schema)}")
        v = _verdict_module()
        assert set(v.OUTCOMES_ALLOWED_WHEN_UNMEASURED) == documented, (
            "the reference implementation disagrees with the document it implements")

    def test_abstain_may_defer_and_have_it_applied(self, validator) -> None:
        """The record the contradiction rejected."""
        validator.validate(_record(
            decision_outcome="abstain", enforcement_status="applied",
            intervention={"type": "defer", "intended_consumer": "task_scheduler",
                          "parameters": {"until": "human_review"},
                          "material_effect": {"ref": "trace://d/123",
                                              "resolvable": True}}))

    def test_a_deferral_states_what_it_waits_on(self, validator) -> None:
        """MA-7.4 names deferral directives, and the rule had omitted `defer`."""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(
                decision_outcome="escalate", enforcement_status="requested",
                intervention={"type": "defer", "intended_consumer": "queue"}))

    @pytest.mark.parametrize("outcome", sorted(INTERVENING))
    def test_an_intervening_outcome_records_its_enforcement(
        self, validator, outcome: str
    ) -> None:
        """MA-7.3 — the schema checked the value and never required the field.

        By MA-4.6 an absent field records nothing, so silence here is not
        evidence that no enforcement happened.
        """
        rec = _record(decision_outcome=outcome)
        rec.pop("enforcement_status")
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(rec)

    def test_allow_needs_no_enforcement_status(self, validator) -> None:
        rec = _record(decision_outcome="allow")
        rec.pop("enforcement_status", None)
        validator.validate(rec)


class TestTheLifecycleIsClosedBothWays:
    """MA-7.8 — the schema had one direction and called it a model.

    An intervention was required once `applied`, so `attenuate` +
    `requested` with no directive at all validated: a decision that called for
    an effect, naming no mechanism for anyone to perform. And `not_required`
    sat happily on `block`, contradicting the outcome that required it.
    """

    @pytest.mark.parametrize("outcome", ["block", "attenuate", "escalate", "abstain"])
    def test_an_intervening_outcome_names_its_mechanism_when_requested(
        self, validator, outcome: str
    ) -> None:
        rec = _record(decision_outcome=outcome, enforcement_status="requested")
        rec.pop("intervention")
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(rec)

    @pytest.mark.parametrize("outcome", ["block", "attenuate", "escalate", "abstain"])
    def test_an_intervening_outcome_cannot_be_not_required(
        self, validator, outcome: str
    ) -> None:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(decision_outcome=outcome,
                                       enforcement_status="not_required"))

    @pytest.mark.parametrize("status", ["requested", "acknowledged", "applied", "failed"])
    def test_allow_carries_no_live_enforcement_state(
        self, validator, status: str
    ) -> None:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(decision_outcome="allow",
                                       enforcement_status=status))

    def test_the_lifecycle_table_and_the_schema_agree(
        self, spec_text: str, validator
    ) -> None:
        """MA-7.8's table read out of the document and executed."""
        section = spec_text[spec_text.index("**MA-7.8.**"):]
        assert "`not_required`, or absent" in section, "the allow row moved"
        rec = _record(decision_outcome="allow")
        rec.pop("enforcement_status", None)
        validator.validate(rec)
        validator.validate({**rec, "enforcement_status": "not_required"})


class TestAMechanismCarriesItsArtefact:
    """MA-5.6 — `mechanism: signature` with no signature named a construction
    that was not there. Four mechanisms were in the vocabulary and none of them
    had to show anything for itself."""

    BASE = {"algorithm": "sha256", "digest": "sha256:" + "0" * 64}

    @pytest.mark.parametrize("mechanism,artefact", [
        ("signature", {"signature": "s", "key_id": "k", "signed_fields": ["a"]}),
        ("external_timestamp", {"timestamp_token_ref": "t://1",
                                "timestamp_authority_ref": "tsa://a"}),
        ("witnessed_ledger", {"ledger_receipt_ref": "r://1", "ledger_id": "L"}),
        ("hash_chain", {"previous_digest": "sha256:" + "1" * 64}),
        ("signature_chain", {"signature": "s", "key_id": "k",
                             "signed_fields": ["a"],
                             "previous_digest": "sha256:" + "1" * 64}),
    ])
    def test_naming_a_mechanism_requires_showing_it(
        self, validator, mechanism: str, artefact: dict
    ) -> None:
        bare = {**self.BASE, "mechanism": mechanism}
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(evidence_status="E1", integrity=bare))
        validator.validate(_record(evidence_status="E1",
                                   integrity={**bare, **artefact}))


class TestScopeBelongsOnlyToExclusions:
    """A scope decision on a PASS states both that the object was assessed and
    that it was out of scope. The forward rule existed; the inverse did not."""

    def test_a_scope_decision_elsewhere_is_rejected(self, validator) -> None:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(scope_decision={"ref": "doc://s",
                                                       "resolvable": True}))

    def test_an_exclusion_counts_nothing(self, validator) -> None:
        for measured in ({"items_checked": 1}, {"inputs_present": True}):
            with pytest.raises(jsonschema.ValidationError):
                validator.validate(_record(
                    measurement_status="NOT_APPLICABLE", decision_outcome="abstain",
                    scope_decision={"ref": "doc://s", "resolvable": True},
                    measured=measured))


class TestTheTypeIsAsStrictAsTheSchema:
    """Four invariants lived in helpers or in type hints and nowhere enforceable.

    Last round I moved the *presence* of a non-measurement cause onto the type
    and left the *vocabulary* in the helper — the same instance-not-class split
    the round before that. These close the remaining gap by constructing the
    violating object directly, which is what a consumer of this module can do.
    """

    def test_an_invented_cause_is_refused_by_the_type(self) -> None:
        v = _verdict_module()
        with pytest.raises(v.CollapseError, match="not one of"):
            v.Measurement(v.Verdict.NOT_MEASURED, reason="r", cause="bogus")

    def test_a_string_verdict_fails_at_construction_not_serialisation(self) -> None:
        """It used to survive construction and raise AttributeError later —
        after the record was already believed."""
        v = _verdict_module()
        with pytest.raises(v.CollapseError, match="not a Verdict"):
            v.Measurement("PASS", items_checked=1)

    @pytest.mark.parametrize("count", [True, 1.5, "1"])
    def test_a_count_that_is_not_an_integer_is_refused(self, count) -> None:
        """`True` is an int in Python and would have read as one item examined."""
        v = _verdict_module()
        with pytest.raises(v.CollapseError, match="integer"):
            v.measured_pass(count)

    def test_a_truthy_string_is_not_an_input_state(self) -> None:
        v = _verdict_module()
        with pytest.raises(v.CollapseError, match="present, absent or unknown"):
            v.Measurement(v.Verdict.PASS, items_checked=1, inputs_present="yes")

    def test_scope_decision_fields_are_checked(self) -> None:
        v = _verdict_module()
        with pytest.raises(v.CollapseError, match="not an answer"):
            v.ScopeDecision("doc://x", "yes")
        with pytest.raises(v.CollapseError, match="lowercase hex"):
            v.ScopeDecision("doc://x", True, content_hash="abc")

    def test_scope_and_counts_obey_the_same_inverses_as_the_schema(self) -> None:
        v = _verdict_module()
        with pytest.raises(v.CollapseError, match="out of scope"):
            v.Measurement(v.Verdict.PASS, items_checked=1,
                          scope_decision=v.ScopeDecision("d://s", True))
        with pytest.raises(v.CollapseError, match="no\\s+count"):
            v.Measurement(v.Verdict.NOT_APPLICABLE, inputs_present=None,
                          items_checked=1,
                          scope_decision=v.ScopeDecision("d://s", True))


class TestNoFieldAcceptsAnEmptyValue:
    """A required field that accepts "" is a field the schema does not require.

    Fourteen string properties had no `minLength`. An external review named six;
    walking the schema found the rest. This test replaces the enumeration — it
    fails on any string property added later without a length, so the next one
    cannot be missed the same way.
    """

    @staticmethod
    def _string_fields(node: dict, path: str = ""):
        """Every string reachable in the schema, not every string with a name.

        The first version descended into `items` and then looked for
        `properties` there — so an array of plain strings had nothing to
        enumerate and vanished. `signed_fields` kept accepting "   " for exactly
        that reason: the sweep written to replace enumeration had a hole in the
        same shape as the thing it was replacing.
        """
        if not isinstance(node, dict):
            return
        declared = node.get("type")
        # A nullable field declares `["string", "null"]`, and an equality test
        # against "string" does not see it. Seven fields were invisible to both
        # the hardening pass and this sweep — the guard shared the blind spot of
        # the code it guards, so it could not have caught what that code missed.
        is_string = declared == "string" or (
            isinstance(declared, list) and "string" in declared)
        if is_string and not (node.get("enum") or node.get("const")):
            yield path or "<root>", node
        for key, sub in (node.get("properties") or {}).items():
            yield from TestNoFieldAcceptsAnEmptyValue._string_fields(
                sub, f"{path}.{key}".lstrip("."))
        if "items" in node:
            yield from TestNoFieldAcceptsAnEmptyValue._string_fields(
                node["items"], f"{path}[]")
        for combiner in ("allOf", "anyOf", "oneOf"):
            for i, sub in enumerate(node.get(combiner, [])):
                yield from TestNoFieldAcceptsAnEmptyValue._string_fields(
                    sub, f"{path}({combiner}{i})")

    def test_every_free_string_states_a_minimum_length(self, schema: dict) -> None:
        fields = list(self._string_fields(schema))
        assert len(fields) > 20, "the walk found too few fields — check it still works"
        empty_ok = [p for p, s in fields if not s.get("minLength")]
        assert not empty_ok, (
            f"these accept an empty string, so requiring them requires nothing: "
            f"{empty_ok}")
        blank_ok = [p for p, s in fields if not s.get("pattern")]
        assert not blank_ok, (
            f"these accept a string of spaces, which names nothing while "
            f"satisfying minLength: {blank_ok}")

    @pytest.mark.parametrize("path", [
        "subject.component", "subject.profile", "intervention.intended_consumer"])
    def test_a_named_field_that_names_nothing_is_rejected(
        self, validator, path: str
    ) -> None:
        rec = _record(decision_outcome="block")
        outer, _, inner = path.partition(".")
        rec[outer] = dict(rec.get(outer, {}), **{inner: ""})
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(rec)

    def test_an_e4_replay_reference_that_points_nowhere_is_rejected(
        self, validator
    ) -> None:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(
                evidence_status="E4", integrity=FULL_INTEGRITY,
                replay={"policy_version": "", "state_ref": ""}))

    #: Comparing two regex strings only proves they were typed the same way.
    #: These are the values that separate a per-algorithm grammar from a single
    #: length range — the defect a string comparison would have passed.
    DIGESTS = [
        ("sha256:" + "a" * 64, True), ("sha384:" + "a" * 96, True),
        ("sha512:" + "a" * 128, True), ("blake3:" + "a" * 64, True),
        ("sha256:" + "a" * 128, False), ("sha512:" + "a" * 64, False),
        ("sha256:" + "a" * 65, False), ("sha256:" + "A" * 64, False),
        ("md5:" + "a" * 32, False), ("a" * 64, False),
    ]

    @pytest.mark.parametrize("digest,accepted", DIGESTS)
    def test_producer_and_validator_accept_the_same_digests(
        self, schema: dict, digest: str, accepted: bool
    ) -> None:
        """Behavioural, not textual.

        Both sides accepted sha256 at 128 characters and sha512 at 64 while
        sharing one pattern — agreeing with each other and with no hash function
        that exists. Two artefacts can agree and both be wrong, so the check is
        against the algorithms rather than against each other.
        """
        cls = jsonschema.validators.validator_for(schema)(schema)
        rec = _record(measurement_status="NOT_APPLICABLE", decision_outcome="abstain",
                      scope_decision={"ref": "doc://s", "resolvable": True,
                                      "content_hash": digest})
        assert cls.is_valid(rec) is accepted, f"schema disagrees on {digest[:20]}..."
        v = _verdict_module()
        ok = bool(v._DIGEST.fullmatch(digest))
        assert ok is accepted, f"the reference implementation disagrees on {digest[:20]}..."


class TestACompoundMechanismShowsBothHalves:
    """MA-5.6 — `signature_chain` claims signed AND chained.

    The rule grouped it with plain `signature` and required only the signature
    half, so a record could name a chain and carry no link to one. Two claims
    were checked as one because they shared a rule.
    """

    SIGNED = {"mechanism": "signature_chain", "algorithm": "ed25519",
              "digest": "sha256:" + "0" * 64, "signature": "s", "key_id": "k",
              "signed_fields": ["measurement_status"]}

    def test_a_chain_without_a_link_is_rejected(self, validator) -> None:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(evidence_status="E1", integrity=self.SIGNED))

    def test_the_link_to_the_preceding_entry_satisfies_it(self, validator) -> None:
        validator.validate(_record(
            evidence_status="E1",
            integrity={**self.SIGNED, "previous_digest": "sha256:" + "1" * 64}))

    def test_a_context_reference_does_not_stand_in_for_the_link(
        self, validator
    ) -> None:
        """`chain_context_ref` says where the chain may be read.

        It does not carry this entry's link to the one before it, so it answers a
        different question. An earlier rule accepted either, which let a record
        name a chain while carrying nothing that chains it.
        """
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(
                evidence_status="E1",
                integrity={**self.SIGNED, "chain_context_ref": "chain://ledger/7"}))

    def test_the_genesis_entry_is_the_documented_exception(self, validator) -> None:
        validator.validate(_record(
            evidence_status="E1",
            integrity={**self.SIGNED, "chain_position": "genesis",
                       "chain_context_ref": "chain://ledger/7"}))

    def test_a_plain_signature_needs_no_link(self, validator) -> None:
        validator.validate(_record(
            evidence_status="E1",
            integrity={**self.SIGNED, "mechanism": "signature"}))


class TestAnAdvisoryHasARecordShape:
    """TV-8 had no conformant representation — a contradiction I introduced.

    MA-7.4 says a directive lacking what it needs to be performed *is* advisory:
    a classification, not an error. MA-7.8 then required every intervening
    outcome to carry an intervention, so there was no record in which MA-7.4's
    sentence could be true. Closing a lifecycle by conflating "the decision
    called for an effect" with "a performable directive was produced" is the
    same collapse the document forbids elsewhere.
    """

    ADVISORY = {"type": "attenuate",
                "intended_consumer": "human_reviewer",
                "not_performable_because": "no attenuation factor was produced"}

    def test_tv8_now_has_a_conformant_record(self, validator, spec_text: str) -> None:
        row = next(line for line in spec_text.splitlines()
                   if line.startswith("| TV-8 |"))
        assert "not_performable" in row and "advisory" in row, row
        rec = _record(decision_outcome="attenuate",
                      enforcement_status="not_performable", advisory=self.ADVISORY)
        rec.pop("intervention", None)
        validator.validate(rec)

    def test_an_advisory_is_never_also_an_intervention(self, validator) -> None:
        """MA-7.1"""
        rec = _record(decision_outcome="attenuate",
                      enforcement_status="not_performable", advisory=self.ADVISORY)
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(rec)          # still carries the default intervention

    @pytest.mark.parametrize("status", ["requested", "applied", "failed", "not_required"])
    def test_an_advisory_carries_no_other_enforcement_state(
        self, validator, status: str
    ) -> None:
        """`failed` claims an attempt not made; `not_required` claims the decision
        did not call for the effect, when it did."""
        rec = _record(decision_outcome="attenuate", enforcement_status=status,
                      advisory=self.ADVISORY)
        rec.pop("intervention", None)
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(rec)

    def test_not_performable_requires_the_advisory_that_explains_it(
        self, validator
    ) -> None:
        rec = _record(decision_outcome="attenuate",
                      enforcement_status="not_performable")
        rec.pop("intervention", None)
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(rec)

    def test_allow_carries_neither(self, validator) -> None:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(decision_outcome="allow",
                                       advisory=self.ADVISORY))

    def test_the_advisory_says_what_is_missing(self, validator) -> None:
        """An advisory that does not name the gap leaves a reader to infer it."""
        rec = _record(decision_outcome="attenuate",
                      enforcement_status="not_performable",
                      advisory={k: v for k, v in self.ADVISORY.items()
                                if k != "not_performable_because"})
        rec.pop("intervention", None)
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(rec)


class TestAlgorithmAndDigestAgreeWhereTheyAreOneClaim:
    """MA-5.6 — `algorithm: sha512` over a `sha256:` digest names two hashes."""

    def test_a_hash_mechanism_must_agree_with_its_digest(self, validator) -> None:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(evidence_status="E1", integrity={
                "mechanism": "hash", "algorithm": "sha512",
                "digest": "sha256:" + "a" * 64}))
        validator.validate(_record(evidence_status="E1", integrity={
            "mechanism": "hash", "algorithm": "sha256",
            "digest": "sha256:" + "a" * 64}))

    def test_a_signature_mechanism_may_name_a_different_algorithm(
        self, validator
    ) -> None:
        """Here they are two claims, not one: the digest names the hash, the
        algorithm names the signature scheme."""
        validator.validate(_record(evidence_status="E1", integrity={
            "mechanism": "signature", "algorithm": "ed25519",
            "digest": "sha256:" + "a" * 64, "signature": "s", "key_id": "k",
            "signed_fields": ["measurement_status"]}))


class TestAnIdentifierOfSpacesIdentifiesNothing:
    @pytest.mark.parametrize("value", ["   ", "\t", "\n ", "\u00a0"])
    def test_whitespace_only_identifiers_are_rejected(
        self, validator, value: str
    ) -> None:
        """`minLength: 1` is satisfied by a space, which names nothing."""
        rec = _record()
        rec["subject"] = dict(rec["subject"], component=value)
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(rec)


class TestTheThreeArtefactsSayTheSameThing:
    """The recurring failure of this package, in test form.

    `not_performable`, the advisory model and the genesis exception were each
    added to the schema and left out of the normative text, the YAML, or both.
    Identifier parity passed the whole time — the *names* matched while the
    *statements* diverged. These read values out of the document and the
    requirement file and compare them to what the validator enforces.
    """

    def test_the_enforcement_vocabulary_is_the_same_in_all_three(
        self, spec_text: str, schema: dict, requirements: dict
    ) -> None:
        in_schema = set(schema["properties"]["enforcement_status"]["enum"])
        header = "| `enforcement_status` | Meaning |"
        table = spec_text[spec_text.index(header) + len(header):]
        documented = set(re.findall(r"^\| `(\w+)` \|", table[:700], re.M))
        assert documented == in_schema, (
            f"the specification documents {sorted(documented)}; the schema "
            f"enforces {sorted(in_schema)}")
        text = json.dumps(requirements)
        missing = [v for v in in_schema if v not in text]
        assert not missing, (
            f"the requirement file never mentions {missing}, so a conformance "
            "run has no requirement to assess them under")

    def test_the_advisory_path_reaches_the_requirement_file(
        self, requirements: dict
    ) -> None:
        ma78 = next(r for r in requirements["requirements"] if r["id"] == "MA-7.8")
        assert "advisor" in ma78["statement"], (
            "MA-7.8's machine-readable statement still requires an intervention "
            "outright, which excludes the advisory path MA-7.9 mandates")

    def test_the_genesis_exception_is_normative_not_only_schematic(
        self, spec_text: str, requirements: dict
    ) -> None:
        section = spec_text[spec_text.index("**MA-5.6.**"):][:1200]
        assert "genesis" in section, (
            "the schema permits a genesis entry to omit previous_digest; the "
            "specification it implements does not say so")
        ma56 = next(r for r in requirements["requirements"] if r["id"] == "MA-5.6")
        assert "genesis" in json.dumps(ma56)

    def test_the_advisory_vocabulary_matches_the_intervention_vocabulary(
        self, schema: dict
    ) -> None:
        """MA-7.7 governs both, so one vocabulary — not two that drift."""
        assert (set(schema["properties"]["advisory"]["properties"]["type"]["enum"])
                == set(schema["properties"]["intervention"]["properties"]["type"]["enum"]))


class TestAGenesisEntryClaimsOneThing:
    SIGNED = {"mechanism": "signature_chain", "algorithm": "ed25519",
              "digest": "sha256:" + "0" * 64, "signature": "s", "key_id": "k",
              "signed_fields": ["measurement_status"]}

    def test_it_cannot_also_carry_a_predecessor(self, validator) -> None:
        """`anyOf` let a record say both that nothing precedes it and what does."""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(evidence_status="E1", integrity={
                **self.SIGNED, "chain_position": "genesis",
                "chain_context_ref": "chain://l/1",
                "previous_digest": "sha256:" + "1" * 64}))

    def test_it_must_name_the_chain_it_opens(self, validator) -> None:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(evidence_status="E1", integrity={
                **self.SIGNED, "chain_position": "genesis"}))

    def test_signed_fields_name_fields(self, validator) -> None:
        for bad in (["   "], ["a", "a"]):
            with pytest.raises(jsonschema.ValidationError):
                validator.validate(_record(evidence_status="E1", integrity={
                    **self.SIGNED, "signed_fields": bad,
                    "previous_digest": "sha256:" + "1" * 64}))


class TestAnAdvisoryRecommendsWhatTheOutcomeCalledFor:
    ADV = {"intended_consumer": "reviewer", "not_performable_because": "no factor"}

    def test_a_mismatched_recommendation_is_rejected(self, validator) -> None:
        """MA-7.7 applied to `advisory.type`."""
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(
                decision_outcome="block", enforcement_status="not_performable",
                advisory={**self.ADV, "type": "attenuate"},
                intervention=None) | {"intervention": None})

    def test_a_matching_recommendation_is_accepted(self, validator) -> None:
        rec = _record(decision_outcome="attenuate",
                      enforcement_status="not_performable",
                      advisory={**self.ADV, "type": "redact"})
        rec.pop("intervention", None)
        validator.validate(rec)


class TestNullableFieldsAreNotInvisible:
    """The guard shared the blind spot of the code it guarded.

    Both the hardening pass and the sweep above tested `type == "string"`. A
    nullable field declares `["string", "null"]`, so seven of them — `reason`,
    `acknowledged_by`, two `evaluated_version`s, `objects_examined`,
    `stochastic_draw`, `recorded_time_value` — were invisible to both. The sweep
    reported zero gaps while `reason: "   "` validated. A test written from the
    same assumption as the fix cannot catch what the fix missed.
    """

    def test_the_sweep_sees_nullable_strings(self, schema: dict) -> None:
        seen = {p for p, _ in TestNoFieldAcceptsAnEmptyValue._string_fields(schema)}
        for path in ("reason", "scope_decision.evaluated_version",
                     "intervention.acknowledged_by"):
            assert path in seen, (
                f"{path} declares ['string', 'null'] and the sweep does not see "
                "it, so its constraints are unchecked")

    @pytest.mark.parametrize("field,value", [
        ("reason", "   "), ("reason", "")])
    def test_a_nullable_field_still_may_not_be_blank(
        self, validator, field: str, value: str
    ) -> None:
        with pytest.raises(jsonschema.ValidationError):
            validator.validate(_record(**{field: value}))

    def test_null_remains_a_legitimate_value(self, validator) -> None:
        """Hardening must not turn `absent` into `invalid`: null says the
        producer had nothing to record, which is a different claim from a blank
        string pretending it did."""
        validator.validate(_record(reason=None))


class TestEveryRequirementLivesUnderItsOwnSection:
    """The placement error, caught by its number rather than by reading.

    MA-7.7 landed under `## 8. Replay`; the genesis clause of MA-5.6 landed
    under `## 6. Path properties`. Both came from the same habit — inserting
    after the second blank line following a requirement, which walks straight
    past a section boundary. A requirement's number already says where it
    belongs, so this needs no judgement.
    """

    def test_requirement_numbers_match_their_headings(self, spec_text: str) -> None:
        section = None
        misplaced = []
        for line in spec_text.splitlines():
            heading = re.match(r"^## (\d+)\.", line)
            if heading:
                section = heading.group(1)
                continue
            req = re.match(r"^\*\*MA-(\d+)\.\d+\.\*\*", line)
            if req and section and req.group(1) != section:
                misplaced.append((req.group(0).strip("*."), f"section {section}"))
        assert not misplaced, f"requirements under the wrong heading: {misplaced}"

    def test_the_genesis_clause_sits_with_the_requirement_it_qualifies(
        self, spec_text: str
    ) -> None:
        """Prose has no number, so it needs its own check."""
        genesis = spec_text.index("The first entry of a chain")
        heading = spec_text.rindex("\n## ", 0, genesis)
        assert spec_text[heading:heading + 30].startswith("\n## 5."), (
            "the genesis exception qualifies MA-5.6 and must sit in Section 5, "
            f"not under {spec_text[heading:heading + 30].strip()}")
        assert spec_text.index("**MA-5.6.**") < genesis

    def test_the_enforcement_enumeration_matches_the_table_below_it(
        self, spec_text: str
    ) -> None:
        """MA-7.3's prose list and its own table disagreed for two rounds."""
        header = "| `enforcement_status` | Meaning |"
        prose = spec_text[spec_text.index("**MA-7.3.**"):spec_text.index(header)]
        table = spec_text[spec_text.index(header) + len(header):]
        documented = set(re.findall(r"^\| `(\w+)` \|", table[:700], re.M))
        enumerated = {v for v in documented if f"`{v}`" in prose}
        assert enumerated == documented, (
            f"the table defines {sorted(documented)}; the sentence above it "
            f"lists {sorted(enumerated)}")


class TestTheProducerRefusesWhatTheValidatorRefuses:
    """A blank string passed the type and failed the schema.

    `measured_fail("", 1)` built a Measurement and produced a record its own
    validator rejects. The type checked that `reason` was a string; the schema
    checked that it said something. Fixing `reason` alone would leave the class
    open, so this drives every constructor that takes text through both sides.
    """

    BLANKS = ["", "   ", "\t", " "]

    @pytest.mark.parametrize("blank", BLANKS)
    def test_no_constructor_accepts_a_blank_reason(self, blank: str) -> None:
        v = _verdict_module()
        for build in (lambda: v.measured_fail(blank, 1),
                      lambda: v.not_measured(blank, cause="not_executed"),
                      lambda: v.inconclusive(blank, 1),
                      lambda: v.errored(blank)):
            with pytest.raises(v.CollapseError):
                build()

    @pytest.mark.parametrize("blank", BLANKS)
    def test_no_scope_field_accepts_a_blank(self, blank: str) -> None:
        v = _verdict_module()
        with pytest.raises(v.CollapseError):
            v.ScopeDecision(blank, True)
        with pytest.raises(v.CollapseError):
            v.ScopeDecision("doc://x", True, evaluated_version=blank)

    def test_a_digest_is_a_string_not_something_that_prints_like_one(self) -> None:
        """Coercing with str() would have hidden the difference from the record."""
        v = _verdict_module()

        class PrintsLikeADigest:
            def __str__(self) -> str:
                return "sha256:" + "a" * 64

        with pytest.raises(v.CollapseError):
            v.ScopeDecision("doc://x", True, content_hash=PrintsLikeADigest())

    def test_whatever_the_type_accepts_the_schema_accepts(self, validator) -> None:
        """The direction that matters: no constructor may emit an invalid record."""
        v = _verdict_module()
        cases = [v.measured_pass(1), v.measured_fail("mismatch", 1),
                 v.not_measured("skipped", cause="suppressed_by_tier"),
                 v.inconclusive("ambiguous", 2), v.errored("raised"),
                 v.not_applicable(v.ScopeDecision("doc://s", True,
                                                  evaluated_version="1.2"))]
        for m in cases:
            rec = {"spec_version": "1.0",
                   "subject": {"component": "t", "profile": "default",
                               "timestamp_utc": "2026-08-01T00:00:00Z"},
                   "decision_outcome": "escalate", "enforcement_status": "requested",
                   "intervention": {"type": "escalate", "intended_consumer": "q"},
                   "evidence_status": "E0", **m.to_record_fields()}
            if m.verdict is _verdict_module().Verdict.NOT_APPLICABLE:
                rec["decision_outcome"] = "abstain"
                rec["intervention"] = {"type": "defer", "intended_consumer": "s",
                                       "parameters": {"until": "review"}}
            errors = list(validator.iter_errors(rec))
            assert not errors, f"{m.verdict.value}: {errors[0].message}"


class TestTheWholeCombinationSpace:
    """Every combination of the orthogonal dimensions, not the ones a review found.

    Nine rounds of review each surfaced the next instance of a class I had
    already fixed once. The reason is structural: fixing a reported defect and
    adding a test for it covers that defect. It does not cover the space the
    defect came from, so the next instance is found by whoever looks next.

    This enumerates measurement_status x decision_outcome x enforcement_status x
    intervention.type x advisory and checks the validator against an independent
    restatement of the requirement texts. A disagreement means the schema and
    the document have drifted — in either direction.
    """

    COMPAT = {"block": {"block"}, "attenuate": {"attenuate", "redact", "rate_limit"},
              "escalate": {"escalate", "defer"}, "abstain": {"defer"}}
    UNMEASURED_MAY = {"block", "escalate", "abstain"}
    MATERIAL = {"ref": "trace://1", "resolvable": True}

    @classmethod
    def _restated(cls, ms: str, do: str, es: str,
                  itype: str | None, advtype: str | None) -> str | None:
        """The requirement texts, restated from the document rather than the schema."""
        if ms == "NOT_MEASURED" and do not in cls.UNMEASURED_MAY:
            return "MA-4.3"
        if do == "allow":
            return "MA-7.8" if (es != "not_required" or itype or advtype) else None
        if es == "not_required":
            return "MA-7.8"
        if advtype:
            if es != "not_performable":
                return "MA-7.9"
            return None if advtype in cls.COMPAT[do] else "MA-7.7"
        if es == "not_performable":
            return "MA-7.9"
        if not itype:
            return "MA-7.8"
        return None if itype in cls.COMPAT[do] else "MA-7.7"

    #: What this sweep does NOT vary, stated because the previous version
    #: implied completeness it did not have. It swept five dimensions and I
    #: described it as covering the space; `measured.inputs_present` was not
    #: among them, and the next defect was found there. A sweep with an unstated
    #: boundary reads as exhaustive to whoever comes after it.
    NOT_SWEPT = ("evidence_status and integrity (covered by the evidence-level "
                 "tests), scope_decision contents, profiles, replay, and every "
                 "field's string-shape constraints")

    def test_the_sweep_states_what_it_does_not_cover(self) -> None:
        assert self.NOT_SWEPT, (
            "if this sweep is extended, say what it still leaves out; an "
            "unbounded claim of coverage is the failure this class was written "
            "after")

    def test_the_schema_and_the_document_agree_everywhere(
        self, schema: dict, validator
    ) -> None:
        P = schema["properties"]
        types = P["intervention"]["properties"]["type"]["enum"]
        disagreements = []
        examined = 0
        for ms in P["measurement_status"]["enum"]:
            for do in P["decision_outcome"]["enum"]:
                for es in P["enforcement_status"]["enum"]:
                    for itype in [None, *types]:
                        for advisory in (False, True):
                          for inputs in (None, True, False):
                            examined += 1
                            rec = _record(measurement_status=ms, decision_outcome=do,
                                          enforcement_status=es)
                            rec.pop("intervention", None)
                            if inputs is not None:
                                rec["measured"] = {"inputs_present": inputs,
                                                   "items_checked": 1}
                            if ms == "NOT_MEASURED":
                                rec["non_measurement_cause"] = "not_executed"
                            if ms == "NOT_APPLICABLE":
                                rec["scope_decision"] = {"ref": "doc://s",
                                                         "resolvable": True}
                            advtype = None
                            if advisory:
                                advtype = itype or "defer"
                                rec["advisory"] = {
                                    "type": advtype, "intended_consumer": "c",
                                    "not_performable_because": "no parameters"}
                            elif itype:
                                iv = {"type": itype, "intended_consumer": "c"}
                                if itype in ("attenuate", "redact", "rate_limit",
                                             "defer"):
                                    iv["parameters"] = {"k": 1}
                                if es == "applied":
                                    iv["material_effect"] = self.MATERIAL
                                rec["intervention"] = iv
                            accepted = validator.is_valid(rec)
                            forbidden = self._restated(ms, do, es,
                                                        None if advisory else itype,
                                                        advtype)
                            if inputs is False and ms != "NOT_MEASURED":
                                forbidden = forbidden or "MA-3.8"
                            if inputs is not None and ms == "NOT_APPLICABLE":
                                forbidden = forbidden or "MA-3.3"
                            if accepted and forbidden:
                                disagreements.append(
                                    f"schema accepts what {forbidden} forbids: "
                                    f"{ms}/{do}/{es}/it={itype}/adv={advtype}/"
                                    f"inputs={inputs}")
                            elif not accepted and not forbidden:
                                disagreements.append(
                                    f"schema rejects what the text permits: "
                                    f"{ms}/{do}/{es}/it={itype}/adv={advtype}/"
                                    f"inputs={inputs}")
        assert examined > 7000, f"only {examined} combinations — check the loop"
        assert not disagreements, (
            f"{len(disagreements)} of {examined} combinations disagree; first "
            f"five:\n  " + "\n  ".join(disagreements[:5]))


class TestTheFrozenVersionIsActuallyFrozen:
    """"Frozen" is a claim about a file, so it is checked like any other.

    The specification says its identifiers, wording and companion artefacts do
    not change from v1.0 onward. Without a check, that sentence is enforced by
    whoever remembers reading it — which is the shape of assurance this whole
    document declines to accept. Editing any of the five artefacts fails this
    test; the correct response is to open v1.1, not to update the digest.
    """

    MANIFEST = SPEC_DIR / "CHECKSUMS.sha256"

    def _entries(self) -> list[tuple[str, str]]:
        rows = []
        for line in self.MANIFEST.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith("#"):
                digest, _, name = line.partition("  ")
                rows.append((digest, name))
        return rows

    def test_the_manifest_covers_the_named_artefacts(self) -> None:
        named = {name for _, name in self._entries()}
        assert named == {"MEASUREMENT_AXIOMS_SPECIFICATION.md",
                         "verdict-outcome.schema.json",
                         "conformance-requirements.yaml",
                         "conformance/verdict.py",
                         "conformance/degenerate.py"}, named

    def test_every_artefact_still_matches_its_digest(self) -> None:
        import hashlib

        drifted = []
        for digest, name in self._entries():
            actual = hashlib.sha256((SPEC_DIR / name).read_bytes()).hexdigest()
            if actual != digest:
                drifted.append(name)
        assert not drifted, (
            f"these changed after v1.0 was frozen: {drifted}. A frozen version "
            "is not edited — open v1.1, state what it changes, and give it its "
            "own manifest.")

    def test_the_documents_agree_that_it_is_frozen(
        self, spec_text: str, requirements: dict
    ) -> None:
        assert "Frozen at v1.0" in spec_text
        assert requirements["status"] == "frozen"
        assert requirements["frozen_on"] == "2026-08-02"

# ---------------------------------------------------------------------------
# Two classes present in the authors' monorepo are absent here, deliberately.
#
# `TestTheSilentFailureInventoryTracksTheCode` and `TestThePatternCannotComeBack`
# (five tests) read a strategic inventory file and walk a pipeline package that
# exist only in the private repository. They guard the authors' own remediation
# against drift; they assert nothing about the specification and would fail here
# for lack of files rather than for lack of conformance.
#
# So this file carries 161 of the monorepo's 166 specification tests. The
# difference is not a gap in what the specification checks — it is the removal
# of two checks about somebody's private codebase from a public specification
# suite.
# ---------------------------------------------------------------------------
