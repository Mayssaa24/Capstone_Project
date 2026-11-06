from abc import ABC, abstractmethod

from app.classifier.models import ClassificationResult
from app.errors import InferenceError, ModelLoadError


class BaseClassifier(ABC):

    def __init__(self, name):
        self._name = name
        self._ready = False

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def is_ready(self):
        return self._ready

    def ensure_ready(self):
        if not self._ready:
            self.initialize()
            self._ready = True

    @abstractmethod
    def initialize(self):
        pass

    @abstractmethod
    def predict(self, image):
        pass
class HuggingFaceClassifier(BaseClassifier):

    def __init__(self, model_name="yangy50/garbage-classification", top_k=5):
        super().__init__(model_name)
        self._top_k = top_k
        self._pipeline = None

    @property
    def top_k(self):
        return self._top_k

    @top_k.setter
    def top_k(self, value):
        if value < 1:
            raise ValueError("top_k must be >= 1")
        self._top_k = value

    def initialize(self):
        try:
            from transformers import pipeline
            self._pipeline = pipeline("image-classification", model=self._name)
        except Exception as exc:  # missing torch, no network, bad model id ...
            raise ModelLoadError(f"Could not load model '{self._name}'.",
                                 details={"reason": str(exc)[:200]}) from exc

    def predict(self, image):
        try:
            raw = self._pipeline(image, top_k=self._top_k)
            return [ClassificationResult(r["label"], r["score"]) for r in raw]
        except Exception as exc:
            raise InferenceError("The model failed to classify the image.",
                                 details={"reason": str(exc)[:200]}) from exc


class ClipZeroShotClassifier(BaseClassifier):

    LABELS = ["a plastic bottle or plastic packaging", "a metal can or tin",
              "a glass bottle or jar", "a sheet of paper or newspaper",
              "a cardboard box", "food waste or fruit peel",
              "clothing or fabric", "an electronic device or battery",
              "general trash"]

    def __init__(self, model_name="openai/clip-vit-base-patch32"):
        super().__init__(model_name)
        self._pipeline = None

    def initialize(self):
        try:
            from transformers import pipeline
            self._pipeline = pipeline("zero-shot-image-classification", model=self._name)
        except Exception as exc:
            raise ModelLoadError(f"Could not load model '{self._name}'.",
                                 details={"reason": str(exc)[:200]}) from exc

    def predict(self, image):
        try:
            raw = self._pipeline(image, candidate_labels=self.LABELS)
            return [ClassificationResult(r["label"], r["score"]) for r in raw]
        except Exception as exc:
            raise InferenceError("The model failed to classify the image.",
                                 details={"reason": str(exc)[:200]}) from exc


class SigLIP2Classifier(BaseClassifier):


    def __init__(self):
        from app.classifier.classifier_oop import WasteClassifier  # heavy: torch

        model_name = "prithivMLmods/Augmented-Waste-Classifier-SigLIP2"
        super().__init__(model_name)
        self._classifier = WasteClassifier(model_name)

    def initialize(self):
        try:
            self._classifier.initialize_model()

        except Exception as exc:
            raise ModelLoadError(
                "Could not load SigLIP2 model.",
                details={"reason": str(exc)[:200]}
            ) from exc

    def predict(self, image):
        try:
            result = self._classifier.classify(image)

            return [
                ClassificationResult(
                    result.get_label(),
                    result.get_confidence()
                )
            ]

        except Exception as exc:
            raise InferenceError(
                "SigLIP2 classification failed.",
                details={"reason": str(exc)[:200]}
            ) from exc
