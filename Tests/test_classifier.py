from contextlib import contextmanager
from pathlib import Path
import importlib
import io
import math
import subprocess
import sys
import types

from PIL import Image
import pytest

from app import create_app
from app.classifier.backends import BaseClassifier, SigLIP2Classifier
from app.classifier.models import ClassificationResult
from app.classifier.preprocessor import ImagePreprocessor
from app.classifier.service import ClassifierService
from app.config import load_config
from app.errors import ClassifierErrorHandler, InferenceError, InvalidImageError, ModelLoadError
from app.streaming.processors import (
    ConfidenceFilter,
    LabelNormalizer,
    Pipeline,
    Processor,
    ResultStream,
    TopKLimiter,
)
from tests.helpers import (
    FailingClassifier,
    StubClassifier,
    error_client,
    install_fake_oop,
    make_image_bytes,
)

unit = pytest.mark.unit
integration = pytest.mark.integration
functional = pytest.mark.functional
regression = pytest.mark.regression


def events():
    return [ClassificationResult("plastic bottle", 0.9), ClassificationResult("paper", 0.2),
            ClassificationResult("tin can", 0.6)]


class _Scalar:
    def __init__(self, value):
        self._value = value

    def item(self):
        return self._value


class _Row:
    def __init__(self, values):
        self._values = values

    def __getitem__(self, i):
        return _Scalar(self._values[i])


class _Probabilities:
    def __init__(self, rows):
        self._rows = rows

    def argmax(self, dim):
        row = self._rows[0]
        return _Scalar(row.index(max(row)))

    def __getitem__(self, i):
        return _Row(self._rows[i])


@pytest.fixture
def oop(monkeypatch):
    """Imports classifier_oop with tiny fake torch/transformers modules."""
    torch = types.ModuleType("torch")

    def softmax(logits, dim):
        rows = []
        for row in logits:
            exps = [math.exp(v) for v in row]
            rows.append([e / sum(exps) for e in exps])
        return _Probabilities(rows)

    @contextmanager
    def inference_mode():
        yield

    torch.softmax, torch.inference_mode = softmax, inference_mode
    torch.Tensor = type("Tensor", (), {})        # scipy/sklearn probe torch.Tensor

    class Processor_:
        @classmethod
        def from_pretrained(cls, name):
            return lambda images, return_tensors: {"pixel_values": images}

    class Model:
        config = types.SimpleNamespace(id2label={0: "plastic", 1: "glass"})

        @classmethod
        def from_pretrained(cls, name):
            return cls()

        def eval(self):
            pass

        def __call__(self, **inputs):
            return types.SimpleNamespace(logits=[[0.1, 3.0]])

    transformers = types.ModuleType("transformers")
    transformers.AutoImageProcessor = Processor_
    transformers.SiglipForImageClassification = Model
    monkeypatch.setitem(sys.modules, "torch", torch)
    monkeypatch.setitem(sys.modules, "transformers", transformers)
    sys.modules.pop("app.classifier.classifier_oop", None)
    module = importlib.import_module("app.classifier.classifier_oop")
    yield module
    sys.modules.pop("app.classifier.classifier_oop", None)


ROOT = Path(__file__).resolve().parents[1]


# unit tests
@unit
def test_unit_01_result_stores_label_and_confidence():
    r = ClassificationResult("glass jar", 0.75)
    assert (r.label, r.confidence, r.material) == ("glass jar", 0.75, None)


@unit
@pytest.mark.parametrize("bad", [-0.1, 1.5])
def test_unit_02_result_rejects_confidence_out_of_range(bad):
    with pytest.raises(InferenceError):
        ClassificationResult("glass", bad)


@unit
@pytest.mark.parametrize("bad", ["", "   ", None])
def test_unit_03_result_rejects_empty_label(bad):
    with pytest.raises(InferenceError):
        ClassificationResult(bad, 0.5)


@unit
def test_unit_04_result_strips_label_and_to_dict_rounds():
    r = ClassificationResult("  paper ", 0.123456, "paper")
    assert r.label == "paper"
    assert r.to_dict() == {"label": "paper", "confidence": 0.1235, "material": "paper"}


@unit
def test_unit_05_result_setters_update_state():
    r = ClassificationResult("x", 0.1)
    r.label, r.confidence, r.material = "metal can", 0.9, "metal"
    assert (r.label, r.confidence, r.material) == ("metal can", 0.9, "metal")


@unit
def test_unit_06_preprocessor_returns_rgb_image():
    image = ImagePreprocessor().prepare(make_image_bytes())
    assert image.mode == "RGB" and image.size == (64, 64)


@unit
@pytest.mark.parametrize("fmt,mode", [("PNG", "RGBA"), ("JPEG", "RGB"), ("BMP", "RGB")])
def test_unit_07_preprocessor_accepts_common_formats(fmt, mode):
    color = (10, 20, 30, 128) if mode == "RGBA" else (10, 20, 30)
    image = ImagePreprocessor().prepare(make_image_bytes(color, fmt=fmt, mode=mode))
    assert image.mode == "RGB"


@unit
def test_unit_08_preprocessor_rejects_empty_upload():
    with pytest.raises(InvalidImageError):
        ImagePreprocessor().prepare(b"")


@unit
def test_unit_09_preprocessor_rejects_oversized_upload():
    with pytest.raises(InvalidImageError) as info:
        ImagePreprocessor(max_bytes=10).prepare(make_image_bytes())
    assert info.value.details == {"max_bytes": 10}


@unit
def test_unit_10_preprocessor_rejects_non_image_bytes():
    with pytest.raises(InvalidImageError):
        ImagePreprocessor().prepare(b"definitely not an image")


@unit
def test_unit_11_preprocessor_downsizes_large_images():
    image = ImagePreprocessor(max_side=100).prepare(make_image_bytes(size=(400, 300)))
    assert max(image.size) == 100


@unit
def test_unit_12_preprocessor_setters_validate():
    pre = ImagePreprocessor()
    pre.max_bytes, pre.max_side = 5000, 256
    assert (pre.max_bytes, pre.max_side) == (5000, 256)
    with pytest.raises(ValueError):
        pre.max_bytes = 0
    with pytest.raises(ValueError):
        pre.max_side = 8


@unit
def test_unit_13_base_classifier_is_abstract():
    with pytest.raises(TypeError):
        BaseClassifier("x")


@unit
def test_unit_14_ensure_ready_initialises_only_once_and_name_setter():
    clf = StubClassifier()
    assert clf.is_ready is False
    clf.ensure_ready()
    clf.ensure_ready()
    assert clf.init_calls == 1 and clf.is_ready is True
    clf.name = "renamed"
    assert clf.name == "renamed"


@unit
def test_unit_21_siglip2_classifier_delegates_to_waste_classifier(monkeypatch):
    install_fake_oop(monkeypatch, label="glass", confidence=0.8)
    clf = SigLIP2Classifier()
    clf.ensure_ready()
    image = Image.new("RGB", (8, 8))
    results = clf.predict(image)
    assert [(r.label, r.confidence) for r in results] == [("glass", 0.8)]


@unit
def test_unit_22_siglip2_classifier_wraps_errors(monkeypatch):
    install_fake_oop(monkeypatch, init_error=RuntimeError("no weights"))
    with pytest.raises(ModelLoadError):
        SigLIP2Classifier().ensure_ready()
    install_fake_oop(monkeypatch, classify_error=RuntimeError("bad tensor"))
    with pytest.raises(InferenceError):
        SigLIP2Classifier().predict(Image.new("RGB", (8, 8)))


@unit
def test_unit_23_waste_image_validates_path_and_loads_rgb(oop, tmp_path):
    path = tmp_path / "a.png"
    Image.new("RGBA", (4, 4)).save(path)
    waste = oop.WasteImage(path)
    assert waste.get_image_path() == str(path) and waste.load_image().mode == "RGB"
    with pytest.raises(FileNotFoundError):
        oop.WasteImage(tmp_path / "missing.png")


@unit
def test_unit_24_prediction_result_validates(oop):
    p = oop.PredictionResult(" glass ", 1)
    assert (p.get_label(), p.get_confidence()) == ("glass", 1.0)
    with pytest.raises(ValueError):
        p.set_label("")
    with pytest.raises(ValueError):
        p.set_confidence(1.5)


@unit
def test_unit_25_waste_classifier_classifies_pil_image_and_path(oop, tmp_path):
    clf = oop.WasteClassifier("some/model")
    from_pil = clf.classify(Image.new("RGB", (8, 8)))
    path = tmp_path / "b.png"
    Image.new("RGB", (8, 8)).save(path)
    from_path = clf.classify(str(path))
    assert from_pil.get_label() == from_path.get_label() == "glass"
    assert from_pil.get_confidence() > 0.9


@unit
def test_unit_26_waste_classifier_rejects_wrong_type_and_resets_on_rename(oop):
    clf = oop.WasteClassifier("some/model")
    with pytest.raises(TypeError):
        clf.classify(12345)
    clf.initialize_model()
    assert clf._model is not None
    clf.set_model_name("other/model")
    assert clf.get_model_name() == "other/model" and clf._model is None
    with pytest.raises(ValueError):
        clf.set_model_name(" ")


@unit
def test_unit_27_model_evaluator_collects_and_validates(oop):
    ev = oop.ModelEvaluator()
    with pytest.raises(ValueError):
        ev.evaluate()
    ev.add_prediction("glass", "glass")
    assert ev.get_actual_labels() == ["glass"] and ev.get_predicted_labels() == ["glass"]
    ev.set_predicted_labels([])
    with pytest.raises(ValueError):
        ev.evaluate()
    ev.reset()
    assert ev.get_actual_labels() == []


@unit
def test_unit_28_model_evaluator_computes_accuracy(oop):
    pytest.importorskip("sklearn")
    ev = oop.ModelEvaluator(["glass", "metal", "paper"], ["glass", "metal", "metal"])
    report = ev.evaluate()
    assert round(report["accuracy"], 3) == 0.667
    assert report["labels"] == ["glass", "metal", "paper"]


@unit
def test_unit_29_confidence_filter_drops_low_and_keeps_boundary():
    out = list(ConfidenceFilter(0.6)(ResultStream(events())))
    assert [e.label for e in out] == ["plastic bottle", "tin can"]


@unit
def test_unit_30_top_k_limiter_stops_early():
    assert [e.label for e in TopKLimiter(2)(ResultStream(events()))] == ["plastic bottle", "paper"]


@unit
@pytest.mark.parametrize("label,material", [
    ("PET bottle", "plastic"), ("tin can", "metal"), ("newspaper", "paper"),
    ("cardboard box", "cardboard"), ("glass jar", "glass"), ("fruit peel", "organic"),
    ("old shoes", "textile"), ("phone battery", "e-waste"), ("mystery object", "trash")])
def test_unit_31_label_normalizer_maps_labels(label, material):
    assert LabelNormalizer().normalize(label) == material


@unit
def test_unit_32_pipeline_composes_with_or_and_add():
    a, b, c = ConfidenceFilter(0.5), LabelNormalizer(), TopKLimiter(1)
    piped, added = a | b | c, a + b + c
    assert isinstance(piped, Pipeline) and len(piped) == len(added) == 3
    assert [e.material for e in piped(ResultStream(events()))] == ["plastic"]
    assert repr(a | b) == "ConfidenceFilter | LabelNormalizer"


@unit
def test_unit_33_processor_is_abstract_and_stream_is_an_iterator():
    with pytest.raises(TypeError):
        Processor()
    stream = ResultStream([1, 2])
    assert iter(stream) is stream and next(stream) == 1 and next(stream) == 2
    with pytest.raises(StopIteration):
        next(stream)


@unit
def test_unit_34_service_filters_sorts_and_normalises():
    svc = ClassifierService(StubClassifier([["paper", 0.4], ["tin can", 0.9], ["glass", 0.1]]),
                            ImagePreprocessor(), 0.35)
    out = svc.classify(make_image_bytes())
    assert [(r.label, r.material) for r in out] == [("tin can", "metal"), ("paper", "paper")]


@unit
def test_unit_35_service_returns_empty_when_nothing_is_confident():
    svc = ClassifierService(StubClassifier([["paper", 0.1]]), ImagePreprocessor(), 0.35)
    assert svc.classify(make_image_bytes()) == []


@unit
def test_unit_36_service_rejects_invalid_images_before_the_model():
    stub = StubClassifier()
    svc = ClassifierService(stub, ImagePreprocessor(), 0.35)
    with pytest.raises(InvalidImageError):
        svc.classify(b"nope")
    assert stub.init_calls == 0


@unit
def test_unit_37_service_setters_validate_and_swap_backend():
    svc = ClassifierService(StubClassifier(), ImagePreprocessor())
    svc.min_confidence = 0.8
    other = StubClassifier([["glass", 0.95]])
    svc.backend = other
    assert svc.min_confidence == 0.8 and svc.backend is other
    with pytest.raises(ValueError):
        svc.min_confidence = 1.5


@unit
def test_unit_38_classifier_error_handler_returns_json():
    client = error_client(ClassifierErrorHandler, InvalidImageError("bad file"))
    res = client.get("/boom")
    assert res.status_code == 400
    assert res.get_json()["error"] == {"code": "invalid_image", "subsystem": "classifier",
                                       "message": "bad file", "details": {}}
    client = error_client(ClassifierErrorHandler, ModelLoadError("no model"))
    assert client.get("/boom").status_code == 503


# integration tests
@integration
def test_integration_01_classifier_feeds_the_rules_engine(engine):
    svc = ClassifierService(StubClassifier([["a metal can or tin", 0.8]]), ImagePreprocessor(), 0.35)
    decision = engine.decide(svc.classify(make_image_bytes())[0])
    assert decision.material == "metal" and "Yellow" in decision.bin_name


@integration
def test_integration_03_app_uses_the_siglip2_backend(monkeypatch):
    install_fake_oop(monkeypatch)
    app = create_app({"DATABASE_URL": "sqlite://", "KICONNECT_API_KEY": ""})
    assert type(app.extensions["services"].classifier.backend) is SigLIP2Classifier


@integration
def test_integration_04_a_failing_model_gives_a_json_error_and_stores_nothing(make_app, upload):
    app = make_app()
    app.extensions["services"].classifier.backend = FailingClassifier()
    client = app.test_client()
    res = upload(client)
    assert res.status_code == 500 and res.get_json()["error"]["subsystem"] == "classifier"
    assert client.get("/api/dashboard").get_json()["summary"]["total"] == 0


# functional tests
@functional
def test_functional_01_scanning_a_photo_returns_decision_advice_and_dashboard(client, upload):
    res = upload(client)
    body = res.get_json()
    assert res.status_code == 200 and body["status"] == "ok"
    assert body["decision"]["material"] == "plastic"
    assert body["decision"]["bin"] and body["decision"]["recyclable"] is True
    assert body["advice"]["headline"] and body["advice"]["tips"]
    assert body["alternatives"][0]["material"] == "glass"
    assert body["dashboard"]["summary"]["total"] == 1


@functional
@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "BMP"])
def test_functional_02_common_photo_formats_are_accepted(client, upload, fmt):
    assert upload(client, make_image_bytes(fmt=fmt), f"p.{fmt.lower()}").status_code == 200


@functional
def test_functional_03_unsure_photos_ask_for_a_better_picture_and_are_not_saved(make_app, upload):
    client = make_app(results=[["paper", 0.1]]).test_client()
    body = upload(client).get_json()
    assert body["status"] == "uncertain" and "not sure" in body["message"]
    assert client.get("/api/dashboard").get_json()["summary"]["total"] == 0


@functional
def test_functional_04_a_non_image_file_is_rejected_with_a_clear_error(client, upload):
    res = upload(client, b"this is not a picture", "notes.txt")
    assert res.status_code == 400 and res.get_json()["error"]["code"] == "invalid_image"


@functional
def test_functional_05_a_request_without_a_file_is_rejected(client):
    res = client.post("/api/scan", data={}, content_type="multipart/form-data")
    assert res.status_code == 400 and "No image" in res.get_json()["error"]["message"]


@functional
def test_functional_06_files_over_the_size_limit_are_rejected(make_app):
    client = make_app(MAX_UPLOAD_MB=1).test_client()
    big = io.BytesIO(b"0" * (1024 * 1024 + 100))
    res = client.post("/api/scan", data={"image": (big, "big.png")},
                      content_type="multipart/form-data")
    assert res.status_code == 413 and res.get_json()["error"]["code"] == "invalid_image"


# regression tests
@regression
def test_regression_01_a_prediction_exactly_at_the_threshold_is_kept():
    kept = list(ConfidenceFilter(0.35)(ResultStream([ClassificationResult("paper", 0.35)])))
    assert len(kept) == 1


@regression
def test_regression_02_whole_words_only_so_scanner_is_not_a_metal_can():
    assert LabelNormalizer().normalize("scanner") == "trash"
    assert LabelNormalizer().normalize("tin can") == "metal"


@regression
def test_regression_03_descriptive_labels_map_to_the_intended_material():
    labels = ["a plastic bottle or plastic packaging", "a metal can or tin",
              "a glass bottle or jar", "a sheet of paper or newspaper",
              "a cardboard box", "food waste or fruit peel",
              "clothing or fabric", "an electronic device or battery",
              "general trash"]
    expected = ["plastic", "metal", "glass", "paper", "cardboard", "organic", "textile",
                "e-waste", "trash"]
    assert [LabelNormalizer().normalize(label) for label in labels] == expected


@regression
def test_regression_04_error_responses_keep_the_same_json_shape(client, upload):
    error = upload(client, b"bad", "x.png").get_json()["error"]
    assert set(error) == {"code", "subsystem", "message", "details"}


@regression
def test_regression_05_environment_values_are_converted_to_the_right_types(monkeypatch):
    monkeypatch.setenv("MIN_CONFIDENCE", "0.5")
    monkeypatch.setenv("MAX_UPLOAD_MB", "2")
    config = load_config()
    assert config["MIN_CONFIDENCE"] == 0.5 and config["MAX_UPLOAD_MB"] == 2
    assert config["MAX_CONTENT_LENGTH"] == 2 * 1024 * 1024


@regression
def test_regression_06_explicit_settings_override_the_environment(monkeypatch):
    monkeypatch.setenv("REGION", "Berlin")
    assert load_config({"REGION": "Essen"})["REGION"] == "Essen"


@regression
def test_regression_07_transparent_png_uploads_are_accepted(client, upload):
    data = make_image_bytes((10, 20, 30, 0), mode="RGBA")
    assert upload(client, data).status_code == 200


@regression
def test_regression_08_importing_the_backends_does_not_load_torch():
    code = "import sys, app.classifier.backends; print('torch' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert out.stdout.strip() == "False", out.stderr


@regression
def test_regression_09_images_are_still_rejected_when_the_file_is_not_an_image():
    from app.classifier.preprocessor import ImagePreprocessor
    with pytest.raises(InvalidImageError):
        ImagePreprocessor().prepare(Image.new("RGB", (2, 2)).tobytes())
