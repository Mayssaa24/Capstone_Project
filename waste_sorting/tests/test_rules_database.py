import pytest

from app.classifier.models import ClassificationResult
from app.classifier.preprocessor import ImagePreprocessor
from app.classifier.service import ClassifierService
from app.dashboard.analytics import DashboardService
from app.errors import DatabaseErrorHandler, InvalidRuleError, RulesErrorHandler, StorageError
from app.rules.engine import RulesEngine
from app.rules.models import Decision, Rule, RuleSet
from tests.helpers import StubClassifier, error_client, make_image_bytes

from app.rules.stream import (DecisionMapper, RoutedDecision, RoutingCodeAssigner,
                               ScanRecorder)
from app.streaming.processors import (ConfidenceFilter, LabelNormalizer, Pipeline,
                                      ResultStream)

unit = pytest.mark.unit
integration = pytest.mark.integration
functional = pytest.mark.functional
regression = pytest.mark.regression


def result(label="tin can", material="metal", confidence=0.8):
    return ClassificationResult(label, confidence, material)


class RecordingRepository:

    def __init__(self):
        self.saved = []

    def add(self, decision):
        self.saved.append(decision)


class ScanRecorderAfterMapping(ScanRecorder):

    def process(self, stream):
        for decision in stream:
            self._repository.add(decision)
            yield decision

#unit tests
@unit
def test_unit_01_rule_normalises_material_and_bin():
    rule = Rule("  PLASTIC ", " Yellow bin ", 1, "Empty it")
    assert (rule.material, rule.bin_name, rule.recyclable) == ("plastic", "Yellow bin", True)


@unit
@pytest.mark.parametrize("material,bin_name", [("", "bin"), ("  ", "bin"), ("glass", ""), ("glass", None)])
def test_unit_02_rule_rejects_empty_material_or_bin(material, bin_name):
    with pytest.raises(InvalidRuleError):
        Rule(material, bin_name, True, "x")


@unit
def test_unit_03_rule_instructions_default_to_empty_text():
    assert Rule("glass", "Container", True, None).instructions == ""


@unit
def test_unit_04_rule_setters_update_state():
    rule = Rule("glass", "Container", True, "a")
    rule.material, rule.bin_name, rule.recyclable, rule.instructions = "metal", "Yellow", 0, "b"
    assert (rule.material, rule.bin_name, rule.recyclable, rule.instructions) == ("metal", "Yellow", False, "b")


@unit
def test_unit_05_ruleset_loads_all_default_rules(ruleset):
    assert ruleset.region == "Dortmund"
    for material, *_ in RuleSet.DEFAULTS:
        assert ruleset.get_rule(material).material == material
    assert len(RuleSet.DEFAULTS) == 9


@unit
@pytest.mark.parametrize("material,recyclable", [("plastic", True), ("metal", True), ("paper", True),
                                                 ("cardboard", True), ("glass", True), ("organic", True),
                                                 ("textile", True), ("e-waste", True), ("trash", False)])
def test_unit_06_default_recyclable_flags(ruleset, material, recyclable):
    assert ruleset.get_rule(material).recyclable is recyclable


@unit
@pytest.mark.parametrize("material", ["mystery", "", None])
def test_unit_07_unknown_material_falls_back_to_residual_waste(ruleset, material):
    assert ruleset.get_rule(material).material == "trash"


@unit
def test_unit_08_get_rule_is_case_insensitive(ruleset):
    assert ruleset.get_rule("GLASS").material == "glass"


@unit
def test_unit_09_add_rule_overrides_and_load_defaults_restores(ruleset):
    ruleset.add_rule(Rule("glass", "Custom bin", True, "custom"))
    assert ruleset.get_rule("glass").bin_name == "Custom bin"
    ruleset.load_defaults()
    assert ruleset.get_rule("glass").bin_name != "Custom bin"


@unit
def test_unit_10_region_setter_validates(ruleset):
    ruleset.region = "Berlin"
    assert ruleset.region == "Berlin"
    with pytest.raises(InvalidRuleError):
        ruleset.region = ""


@unit
def test_unit_11_engine_builds_a_decision(engine):
    d = engine.decide(result())
    assert isinstance(d, Decision)
    assert (d.label, d.material, d.recyclable, d.region) == ("tin can", "metal", True, "Dortmund")
    assert "Yellow" in d.bin_name and d.instructions


@unit
def test_unit_12_decision_to_dict_has_all_fields(decision):
    assert set(decision.to_dict()) == {"label", "confidence", "material", "bin", "recyclable",
                                       "instructions", "region"}


@unit
def test_unit_13_engine_maps_unknown_material_to_trash(engine):
    assert engine.decide(result("???", "mystery")).material == "trash"


@unit
def test_unit_14_engine_ruleset_setter_changes_region(engine):
    engine.ruleset = RuleSet("Berlin")
    assert engine.region == "Berlin" and engine.decide(result()).region == "Berlin"


@unit
def test_unit_15_database_rejects_an_invalid_url():
    from app.rules.database import Database
    with pytest.raises(StorageError):
        Database("not-a-database-url")


@unit
def test_unit_16_unreachable_server_raises_storage_error():
    from app.rules.database import Database
    with pytest.raises(StorageError):
        Database("mysql+pymysql://user:pw@127.0.0.1:1/none").create_tables()


@unit
def test_unit_17_create_tables_is_idempotent(database):
    database.create_tables()
    database.create_tables()


@unit
def test_unit_18_url_setter_reinitialises_the_engine(database):
    database.url = "sqlite://"
    assert database.url == "sqlite://"
    database.create_tables()


@unit
def test_unit_19_add_stores_a_scan(repository, decision):
    scan = repository.add(decision)
    assert scan.id is not None and scan.material == "metal" and scan.region == "Dortmund"
    assert repository.list_scans()[0].label == "tin can"


@unit
def test_unit_20_list_scans_keeps_insertion_order(repository, engine):
    for label in ("a", "b", "c"):
        repository.add(engine.decide(result(label)))
    assert [s.label for s in repository.list_scans()] == ["a", "b", "c"]


@unit
def test_unit_21_list_scans_filters_by_region(repository, ruleset, engine):
    repository.add(engine.decide(result("home")))
    ruleset.region = "Berlin"
    repository.add(engine.decide(result("away")))
    assert [s.label for s in repository.list_scans("Dortmund")] == ["home"]
    assert len(repository.list_scans()) == 2


@unit
def test_unit_22_scan_to_dict_exposes_a_bin_key(repository, decision):
    data = repository.add(decision).to_dict()
    assert data["bin"] == decision.bin_name
    assert set(data) == {"id", "created_at", "label", "material", "bin", "recyclable",
                         "confidence", "region"}


@unit
def test_unit_23_missing_tables_become_storage_errors(decision):
    from app.rules.database import Database, ScanRepository
    repo = ScanRepository(Database("sqlite://"))
    with pytest.raises(StorageError):
        repo.add(decision)
    with pytest.raises(StorageError):
        repo.list_scans()


@unit
def test_unit_24_repository_database_setter(repository, database):
    repository.database = database
    assert repository.database is database


@unit
def test_unit_25_error_handlers_return_json():
    res = error_client(RulesErrorHandler, InvalidRuleError("bad rule")).get("/boom")
    assert res.status_code == 400 and res.get_json()["error"]["subsystem"] == "rules"
    res = error_client(DatabaseErrorHandler, StorageError("db down")).get("/boom")
    assert res.status_code == 500 and res.get_json()["error"]["subsystem"] == "database"


@unit
def test_unit_26_decision_mapper_turns_results_into_decisions(engine):
    out = list(DecisionMapper(engine)(ResultStream([ClassificationResult("tin can", 0.8, "metal")])))
    assert out[0].material == "metal" and out[0].region == "Dortmund"


@unit
def test_unit_27_decision_mapper_rejects_a_bad_engine_and_keeps_the_old_one(engine):
    mapper = DecisionMapper(engine)
    with pytest.raises(InvalidRuleError):
        mapper.engine = None
    assert mapper.engine is engine
    with pytest.raises(InvalidRuleError):
        DecisionMapper("nope")


@unit
def test_unit_28_routing_codes_default_table_and_fallback(decision):
    assigner = RoutingCodeAssigner()
    assert assigner.code_for("metal") == "YEL-2" and assigner.code_for("glass") == "GLS-1"
    assert assigner.code_for("unknown") == "RES-1" and assigner.code_for(None) == "RES-1"
    routed = list(assigner(iter([decision])))[0]
    assert routed.lane_code == "YEL-2" and routed.decision is decision


@unit
def test_unit_29_routing_codes_custom_table_is_normalised():
    assigner = RoutingCodeAssigner({" Glass ": "g-9"}, fallback="x-0")
    assert assigner.code_for("GLASS") == "G-9" and assigner.code_for("metal") == "X-0"
    assert assigner.codes == {"glass": "G-9"}


@unit
def test_unit_30_routing_assigner_setters_validate():
    assigner = RoutingCodeAssigner()
    for bad in ({}, None):
        with pytest.raises(InvalidRuleError):
            assigner.codes = bad
    with pytest.raises(InvalidRuleError):
        assigner.fallback = "  "
    assigner.fallback = "oth-1"
    assert assigner.fallback == "OTH-1"


@unit
def test_unit_31_routed_decision_validates_and_serialises(decision):
    routed = RoutedDecision(decision, " yel-2 ")
    assert routed.lane_code == "YEL-2" and routed.to_dict()["lane_code"] == "YEL-2"
    assert routed.to_dict()["material"] == "metal"
    with pytest.raises(InvalidRuleError):
        routed.lane_code = ""
    with pytest.raises(AttributeError):
        routed.decision = None


@unit
def test_unit_32_recorder_saves_each_event_and_passes_it_on(engine):
    repo = RecordingRepository()
    pipeline = DecisionMapper(engine) | RoutingCodeAssigner() | ScanRecorder(repo)
    out = list(pipeline(ResultStream([ClassificationResult("a", 0.8, "metal"),
                                      ClassificationResult("b", 0.5, "unknown")])))
    assert [r.lane_code for r in out] == ["YEL-2", "RES-1"]
    assert [d.material for d in repo.saved] == ["metal", "trash"]


@unit
def test_unit_33_recorder_accepts_any_object_with_add_and_rejects_others():
    ScanRecorder(RecordingRepository())
    with pytest.raises(InvalidRuleError):
        ScanRecorder(object())
    with pytest.raises(InvalidRuleError):
        ScanRecorder(None)


@unit
def test_unit_34_rule_stages_compose_with_or_and_add(engine):
    a, b, c = DecisionMapper(engine), RoutingCodeAssigner(), ScanRecorder(RecordingRepository())
    piped, added = a | b | c, a + b + c
    assert isinstance(piped, Pipeline) and len(piped) == len(added) == 3
    assert repr(piped) == "DecisionMapper | RoutingCodeAssigner | ScanRecorder"


@unit
def test_unit_35_the_rules_stream_is_lazy_until_consumed(engine):
    repo = RecordingRepository()
    stream = (DecisionMapper(engine) | ScanRecorderAfterMapping(repo))(
        ResultStream([ClassificationResult("jar", 0.9, "glass")]))
    assert repo.saved == []
    next(stream)
    assert len(repo.saved) == 1

#integration tests
@integration
def test_integration_01_decisions_saved_by_the_database_reach_the_dashboard(repository, engine):
    svc = ClassifierService(StubClassifier(), ImagePreprocessor(), 0.35)
    for _ in range(2):
        repository.add(engine.decide(svc.classify(make_image_bytes())[0]))
    data = DashboardService(repository, "Dortmund").build()
    assert data["summary"]["total"] == 2 and data["summary"]["recycling_rate"] == 100.0
    assert data["charts"]["materials"]["labels"] == ["plastic"]
    assert data["charts"]["materials"]["values"] == [2]


@integration
def test_integration_02_dashboard_only_counts_its_own_region(repository, ruleset, engine):
    svc = ClassifierService(StubClassifier(), ImagePreprocessor(), 0.35)
    repository.add(engine.decide(svc.classify(make_image_bytes())[0]))
    ruleset.region = "Berlin"
    repository.add(engine.decide(svc.classify(make_image_bytes())[0]))
    assert DashboardService(repository, "Dortmund").build()["summary"]["total"] == 1
    assert DashboardService(repository, "Berlin").build()["summary"]["total"] == 1


@integration
def test_integration_03_scans_persist_between_requests(client, upload):
    upload(client)
    upload(client)
    assert client.get("/api/dashboard").get_json()["summary"]["total"] == 2


@integration
def test_integration_04_classifier_and_rules_streams_join_into_one_pipeline(engine, repository):
    pipeline = (ConfidenceFilter(0.35) | LabelNormalizer() | DecisionMapper(engine)
                | RoutingCodeAssigner() | ScanRecorder(repository))
    raw = ResultStream([ClassificationResult("tin can", 0.9), ClassificationResult("paper", 0.1),
                        ClassificationResult("glass jar", 0.7)])
    routed = list(pipeline(raw))
    assert [r.lane_code for r in routed] == ["YEL-2", "GLS-1"]
    assert [s.material for s in repository.list_scans()] == ["metal", "glass"]
    assert repository.count() == 2

#functional tests
@functional
def test_functional_01_scan_result_names_the_local_bin(client, upload):
    d = upload(client).get_json()["decision"]
    assert d["region"] == "Dortmund" and "Yellow" in d["bin"] and d["recyclable"] is True


@functional
def test_functional_02_scanned_items_are_stored_and_listed_as_recent(client, upload):
    upload(client)
    recent = client.get("/api/dashboard").get_json()["recent"]
    assert recent[0]["label"] == "plastic bottle" and recent[0]["bin"]

#regression tests
@regression
def test_regression_01_unknown_materials_use_residual_waste_instead_of_crashing():
    decision = RulesEngine(RuleSet()).decide(ClassificationResult("???", 0.9, "mystery"))
    assert decision.material == "trash" and decision.recyclable is False


@regression
def test_regression_02_scans_with_equal_timestamps_keep_insertion_order(repository, engine):
    from app.rules.database import Scan
    from datetime import datetime
    stamp = datetime(2026, 11, 1, 12)
    with repository.database.session() as session:
        session.add_all([Scan(label=n, material="paper", bin_name="b", recyclable=True,
                              confidence=0.5, region="Dortmund", created_at=stamp)
                         for n in ("first", "second", "third")])
        session.commit()
    assert [s.label for s in repository.list_scans()] == ["first", "second", "third"]