import json

import pytest

from app.classifier.models import ClassificationResult
from app.classifier.preprocessor import ImagePreprocessor
from app.classifier.service import ClassifierService
from app.coach.coach import (
    BaseCoach,
    CoachAdvice,
    CoachService,
    OfflineCoach,
    OpenAICoach,
    PromptBuilder,
)
from app.errors import CoachError, CoachErrorHandler, CoachUnavailableError
from tests.helpers import StubClassifier, error_client, install_fake_openai, make_image_bytes

from app.coach.stream import (AdviceStage, CoachEvent, CoachPipeline, CoachStage, DecisionStream,
                              PromptStage, TipCleaner, TipLimiter)

unit = pytest.mark.unit
integration = pytest.mark.integration
functional = pytest.mark.functional
regression = pytest.mark.regression


GOOD_REPLY = json.dumps({"headline": "Great!", "tips": ["Rinse it", "Bin it"], "fun_fact": "Fact."})


@pytest.fixture
def prompts():
    return PromptBuilder("Dortmund")


@pytest.fixture
def trash_decision(engine):
    return engine.decide(ClassificationResult("chip bag", 0.7, "trash"))


class _FixedCoach(BaseCoach):
    def __init__(self, advice=None, error=None):
        super().__init__(PromptBuilder())
        self.advice, self.error, self.calls = advice, error, 0

    def advise(self, decision):
        self.calls += 1
        if self.error:
            raise self.error
        return self.advice


class CountingCoach(BaseCoach):
    def __init__(self):
        super().__init__(PromptBuilder())
        self.calls = 0

    def advise(self, decision):
        self.calls += 1
        return CoachAdvice("H", ["tip"])

#unit tests
@unit
def test_unit_01_prompt_contains_decision_details(prompts, decision):
    text = prompts.build(decision)
    for part in ("Dortmund", "tin can", "metal", decision.bin_name, "English", "JSON"):
        assert part in text


@unit
def test_unit_02_prompt_setters_change_output(prompts, decision):
    prompts.region, prompts.language = "Berlin", "German"
    text = prompts.build(decision)
    assert "Berlin" in text and "German" in text and "Dortmund" not in text


@unit
def test_unit_03_advice_to_dict():
    advice = CoachAdvice("Head", ["a", "b"], "fact", "offline")
    assert advice.to_dict() == {"headline": "Head", "tips": ["a", "b"],
                                "fun_fact": "fact", "source": "offline"}


@unit
def test_unit_04_advice_copies_the_tips_list():
    tips = ["a"]
    advice = CoachAdvice("Head", tips)
    tips.append("b")
    assert advice.tips == ["a"] and advice.fun_fact == "" and advice.source == "offline"


@unit
def test_unit_05_base_coach_is_abstract():
    with pytest.raises(TypeError):
        BaseCoach(PromptBuilder())


@unit
def test_unit_06_prompts_property_can_be_replaced(prompts):
    coach = OfflineCoach(prompts)
    other = PromptBuilder("Berlin")
    coach.prompts = other
    assert coach.prompts is other


@unit
def test_unit_07_offline_coach_names_the_bin_and_material(prompts, decision):
    advice = OfflineCoach(prompts).advise(decision)
    assert advice.source == "offline" and "metal" in advice.headline
    assert advice.tips[0] == f"Put it in: {decision.bin_name}."
    assert decision.instructions in advice.tips


@unit
def test_unit_08_offline_coach_adds_a_tip_for_non_recyclables(prompts, decision, trash_decision):
    recyclable = OfflineCoach(prompts).advise(decision)
    residual = OfflineCoach(prompts).advise(trash_decision)
    assert len(residual.tips) == len(recyclable.tips) + 1


@unit
@pytest.mark.parametrize("material", sorted(OfflineCoach.FACTS))
def test_unit_09_offline_coach_has_a_fact_for_every_material(prompts, engine, material):
    decision = engine.decide(ClassificationResult("x", 0.9, material))
    assert OfflineCoach(prompts).advise(decision).fun_fact


@unit
def test_unit_10_offline_coach_handles_unknown_material(prompts, engine):
    decision = engine.decide(ClassificationResult("x", 0.9, "mystery"))
    advice = OfflineCoach(prompts).advise(decision)
    assert advice.tips[0].startswith("Put it in:")


@unit
def test_unit_11_ai_coach_needs_an_api_key(prompts, decision):
    with pytest.raises(CoachUnavailableError) as info:
        OpenAICoach(prompts, api_key="").advise(decision)
    assert info.value.status_code == 502


@unit
def test_unit_12_ai_coach_parses_a_json_reply(monkeypatch, prompts, decision):
    seen = install_fake_openai(monkeypatch, content=GOOD_REPLY)
    advice = OpenAICoach(prompts, "secret", "my-model").advise(decision)
    assert (advice.headline, advice.tips, advice.fun_fact) == ("Great!", ["Rinse it", "Bin it"], "Fact.")
    assert advice.source == "kiconnect"
    assert seen["model"] == "my-model" and "tin can" in seen["messages"][0]["content"]


@unit
def test_unit_13_ai_coach_uses_the_kiconnect_endpoint(monkeypatch, prompts, decision):
    seen = install_fake_openai(monkeypatch, content=GOOD_REPLY)
    OpenAICoach(prompts, "secret").advise(decision)
    kwargs = seen["client_kwargs"]
    assert kwargs["api_key"] == "secret" and "kiconnect" in kwargs["base_url"]
    assert kwargs["timeout"] == 15


@unit
@pytest.mark.parametrize("content", ["not json at all", json.dumps({"tips": []}), None])
def test_unit_14_ai_coach_wraps_bad_replies(monkeypatch, prompts, decision, content):
    install_fake_openai(monkeypatch, content=content)
    with pytest.raises(CoachUnavailableError):
        OpenAICoach(prompts, "secret").advise(decision)


@unit
def test_unit_15_ai_coach_wraps_api_errors(monkeypatch, prompts, decision):
    install_fake_openai(monkeypatch, error=TimeoutError("slow"))
    with pytest.raises(CoachUnavailableError) as info:
        OpenAICoach(prompts, "secret").advise(decision)
    assert "slow" in info.value.details["reason"]


@unit
def test_unit_16_ai_coach_model_setter(prompts):
    coach = OpenAICoach(prompts, "k", "a")
    coach.model = "b"
    assert coach.model == "b"


@unit
def test_unit_17_service_uses_primary_when_it_works(decision):
    primary = _FixedCoach(CoachAdvice("primary", [], source="x"))
    fallback = _FixedCoach(CoachAdvice("fallback", []))
    assert CoachService(primary, fallback).advise(decision).headline == "primary"
    assert fallback.calls == 0


@unit
def test_unit_18_service_falls_back_on_coach_errors(decision):
    primary = _FixedCoach(error=CoachUnavailableError("down"))
    fallback = _FixedCoach(CoachAdvice("fallback", []))
    assert CoachService(primary, fallback).advise(decision).headline == "fallback"


@unit
def test_unit_19_service_does_not_hide_programming_errors(decision):
    primary = _FixedCoach(error=ValueError("bug"))
    with pytest.raises(ValueError):
        CoachService(primary, _FixedCoach(CoachAdvice("fallback", []))).advise(decision)


@unit
def test_unit_20_service_primary_setter(decision):
    service = CoachService(_FixedCoach(error=CoachError("x")), _FixedCoach(CoachAdvice("fb", [])))
    new_primary = _FixedCoach(CoachAdvice("new", []))
    service.primary = new_primary
    assert service.primary is new_primary and service.advise(decision).headline == "new"


@unit
def test_unit_21_coach_error_handler_returns_json():
    res = error_client(CoachErrorHandler, CoachUnavailableError("down")).get("/boom")
    assert res.status_code == 502
    assert res.get_json()["error"]["subsystem"] == "coach"


@unit
def test_unit_22_decision_stream_is_an_iterator_of_events(decision):
    stream = DecisionStream([decision])
    assert iter(stream) is stream
    event = next(stream)
    assert event.decision is decision and event.prompt is None and event.advice is None
    with pytest.raises(StopIteration):
        next(stream)


@unit
def test_unit_23_prompt_stage_adds_the_prompt(prompts, decision):
    event = next(iter(PromptStage(prompts)(DecisionStream([decision]))))
    assert "tin can" in event.prompt and event.advice is None


@unit
def test_unit_24_stages_reject_collaborators_without_the_needed_method():
    with pytest.raises(CoachError):
        PromptStage(object())
    with pytest.raises(CoachError):
        AdviceStage(None)
    stage = AdviceStage(OfflineCoach(PromptBuilder()))
    with pytest.raises(CoachError):
        stage.coach = "nope"
    assert hasattr(stage.coach, "advise")


@unit
def test_unit_25_advice_stage_asks_the_coach(prompts, decision):
    stage = AdviceStage(OfflineCoach(prompts))
    event = next(iter(stage(DecisionStream([decision]))))
    assert event.advice.source == "offline" and event.advice.tips


@unit
def test_unit_26_tip_cleaner_strips_blanks_and_duplicates(decision):
    advice = CoachAdvice("H", ["  Rinse it ", "", "rinse it", "Bin it", "   "], "fact", "x")
    event = CoachEvent(decision, advice=advice)
    cleaned = next(iter(TipCleaner()(iter([event])))).advice
    assert cleaned.tips == ["Rinse it", "Bin it"] and cleaned.headline == "H"
    assert (cleaned.fun_fact, cleaned.source) == ("fact", "x")


@unit
def test_unit_27_tip_limiter_keeps_the_first_tips_and_validates(decision):
    event = CoachEvent(decision, advice=CoachAdvice("H", ["a", "b", "c"]))
    assert next(iter(TipLimiter(2)(iter([event])))).advice.tips == ["a", "b"]
    limiter = TipLimiter()
    assert limiter.max_tips == 3
    with pytest.raises(CoachError):
        limiter.max_tips = 0
    assert limiter.max_tips == 3


@unit
def test_unit_28_stages_compose_with_or_and_add(prompts):
    a, b, c = PromptStage(prompts), AdviceStage(OfflineCoach(prompts)), TipLimiter(1)
    piped, added = a | b | c, a + b + c
    assert isinstance(piped, CoachPipeline) and len(piped) == len(added) == 3
    assert repr(piped) == "PromptStage | AdviceStage | TipLimiter"


@unit
def test_unit_29_stages_that_need_advice_fail_clearly_when_run_too_early(decision):
    with pytest.raises(CoachError):
        list(TipLimiter()(DecisionStream([decision])))
    with pytest.raises(CoachError):
        list(TipCleaner()(DecisionStream([decision])))


@unit
def test_unit_30_coach_stage_is_abstract_and_events_are_not_mutated(decision):
    with pytest.raises(TypeError):
        CoachStage()
    event = CoachEvent(decision)
    updated = event.with_prompt("p").with_advice(CoachAdvice("H", []))
    assert event.prompt is None and event.advice is None and updated.prompt == "p"


@unit
def test_unit_31_the_coach_stream_is_lazy_until_consumed(decision):
    coach = CountingCoach()
    stream = AdviceStage(coach)(DecisionStream([decision, decision]))
    assert coach.calls == 0
    next(stream)
    assert coach.calls == 1

#integration tests
@integration
def test_integration_01_rules_decision_feeds_the_coach(engine):
    svc = ClassifierService(StubClassifier([["glass jar", 0.9]]), ImagePreprocessor(), 0.35)
    decision = engine.decide(svc.classify(make_image_bytes())[0])
    prompts = PromptBuilder("Dortmund")
    coach = CoachService(OpenAICoach(prompts, ""), OfflineCoach(prompts))
    advice = coach.advise(decision)
    assert advice.source == "offline" and decision.bin_name in advice.tips[0]


@integration
def test_integration_02_missing_coach_key_falls_back_inside_the_route(client, upload):
    body = upload(client).get_json()
    assert body["advice"]["source"] == "offline" and body["advice"]["tips"]


@integration
def test_integration_03_a_failing_primary_coach_does_not_break_the_scan(client, upload, monkeypatch):
    services = client.application.extensions["services"]

    class Broken:
        def advise(self, decision):
            raise CoachUnavailableError("down")

    services.coach.primary = Broken()
    res = upload(client)
    assert res.status_code == 200 and res.get_json()["advice"]["source"] == "offline"


@integration
def test_integration_04_ai_coach_reply_reaches_the_scan_response(make_app, upload, monkeypatch):
    install_fake_openai(monkeypatch, content=GOOD_REPLY)
    client = make_app(KICONNECT_API_KEY="secret").test_client()
    advice = upload(client).get_json()["advice"]
    assert advice["source"] == "kiconnect" and advice["headline"] == "Great!"


@integration
def test_integration_05_full_pipeline_from_rules_decisions_to_clean_advice(engine, prompts):
    decisions = [engine.decide(ClassificationResult("x", 0.9, m)) for m in ("metal", "trash")]
    pipeline = PromptStage(prompts) | AdviceStage(OfflineCoach(prompts)) | TipCleaner() | TipLimiter(2)
    events = list(pipeline(DecisionStream(decisions)))
    assert [e.decision.material for e in events] == ["metal", "trash"]
    assert all(e.prompt and 1 <= len(e.advice.tips) <= 2 for e in events)


@integration
def test_integration_06_the_pipeline_works_with_the_fallback_service(engine, prompts):
    service = CoachService(OpenAICoach(prompts, ""), OfflineCoach(prompts))
    decision = engine.decide(ClassificationResult("x", 0.9, "glass"))
    event = next(iter((AdviceStage(service) | TipLimiter(1))(DecisionStream([decision]))))
    assert event.advice.source == "offline" and len(event.advice.tips) == 1

#functional tests
@functional
def test_functional_01_scan_response_contains_coaching_advice(client, upload):
    advice = upload(client).get_json()["advice"]
    assert advice["headline"] and len(advice["tips"]) >= 2 and advice["fun_fact"]
    assert advice["source"] == "offline"

#regression tests
@regression
def test_regression_01_invalid_ai_reply_still_gives_advice(make_app, upload, monkeypatch):
    install_fake_openai(monkeypatch, content="not json")
    client = make_app(KICONNECT_API_KEY="secret").test_client()
    res = upload(client)
    assert res.status_code == 200 and res.get_json()["advice"]["source"] == "offline"


@regression
def test_regression_02_ai_coach_source_name_is_kiconnect(monkeypatch, decision):
    install_fake_openai(monkeypatch, content=GOOD_REPLY)
    assert OpenAICoach(PromptBuilder(), "secret").advise(decision).source == "kiconnect"