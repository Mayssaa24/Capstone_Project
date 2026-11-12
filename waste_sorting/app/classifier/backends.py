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
