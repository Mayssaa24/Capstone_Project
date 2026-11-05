import io
import sys
import types
from datetime import datetime

from flask import Flask
from PIL import Image

from app.classifier.backends import BaseClassifier
from app.classifier.models import ClassificationResult
from app.errors import InferenceError


def make_image_bytes(color=(40, 160, 90), size=(64, 64), fmt="PNG", mode="RGB"):
    buf = io.BytesIO()
    Image.new(mode, size, color).save(buf, fmt)
    return buf.getvalue()


class StubClassifier(BaseClassifier):


    def __init__(self, results=None):
        super().__init__("stub")
        self._results = results if results is not None else [["plastic bottle", 0.9]]
        self.init_calls = 0

    def initialize(self):
        self.init_calls += 1

    def predict(self, image):
        return [ClassificationResult(label, conf) for label, conf in self._results]


class FailingClassifier(BaseClassifier):
    def __init__(self):
        super().__init__("failing")

    def initialize(self):
        pass

    def predict(self, image):
        raise InferenceError("model crashed")


class FakeScan:
    def __init__(self, day, material="plastic", recyclable=True, confidence=0.8,
                 region="Dortmund", bin_name="Yellow bin"):
        self.created_at = datetime(2026, 11, day, 12)
        self.material, self.recyclable, self.confidence = material, recyclable, confidence
        self.region, self.bin_name = region, bin_name

    def to_dict(self):
        return {"material": self.material, "created_at": self.created_at.isoformat()}


class FakeRepository:
    def __init__(self, scans=()):
        self.scans = list(scans)

    def list_scans(self, region=None):
        return [s for s in self.scans if region is None or s.region == region]


def install_fake_transformers(monkeypatch, outputs=None, fail_load=False, fail_call=False):
    module = types.ModuleType("transformers")
    calls = {}

    def pipeline(task, model=None):
        if fail_load:
            raise RuntimeError("no network")
        calls.update(task=task, model=model)

        def run(image, **kwargs):
            if fail_call:
                raise RuntimeError("boom")
            calls["kwargs"] = kwargs
            return outputs
        return run

    module.pipeline = pipeline
    monkeypatch.setitem(sys.modules, "transformers", module)
    return calls


def install_fake_openai(monkeypatch, content=None, error=None):
    seen = {}

    class Completions:
        def create(self, model, messages):
            seen["model"], seen["messages"] = model, messages
            if error:
                raise error
            message = types.SimpleNamespace(content=content)
            return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    class OpenAI:
        def __init__(self, **kwargs):
            seen["client_kwargs"] = kwargs
            self.chat = types.SimpleNamespace(completions=Completions())

    module = types.ModuleType("openai")
    module.OpenAI = OpenAI
    monkeypatch.setitem(sys.modules, "openai", module)
    return seen


def error_client(handler_class, exception):
    app = Flask(__name__)
    handler_class().register(app)

    @app.get("/boom")
    def boom():
        raise exception

    return app.test_client()


def install_fake_oop(monkeypatch, label="plastic", confidence=0.9,
                     init_error=None, classify_error=None):
    class FakeResult:
        def get_label(self):
            return label

        def get_confidence(self):
            return confidence

    class WasteClassifier:
        def __init__(self, model_name):
            self.model_name = model_name
            self.classified = []

        def initialize_model(self):
            if init_error:
                raise init_error

        def classify(self, image):
            if classify_error:
                raise classify_error
            self.classified.append(image)
            return FakeResult()

    module = types.ModuleType("app.classifier.classifier_oop")
    module.WasteClassifier = WasteClassifier
    monkeypatch.setitem(sys.modules, "app.classifier.classifier_oop", module)
    return module
