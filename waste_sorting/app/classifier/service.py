from app.streaming.processors import (ConfidenceFilter, LabelNormalizer, ResultStream,
                                      TopKLimiter)


class ClassifierService:


    def __init__(self, backend, preprocessor, min_confidence=0.35):
        self._backend = backend
        self._preprocessor = preprocessor
        self._min_confidence = min_confidence

    @property
    def backend(self):
        return self._backend

    @backend.setter
    def backend(self, value):
        self._backend = value

    @property
    def min_confidence(self):
        return self._min_confidence

    @min_confidence.setter
    def min_confidence(self, value):
        if not 0 <= value <= 1:
            raise ValueError("min_confidence must be between 0 and 1")
        self._min_confidence = value

    def build_pipeline(self):
        return ConfidenceFilter(self._min_confidence) | LabelNormalizer() | TopKLimiter(3)

    def classify(self, data):
        image = self._preprocessor.prepare(data)
        self._backend.ensure_ready()
        raw = sorted(self._backend.predict(image), key=lambda r: r.confidence, reverse=True)
        return list(self.build_pipeline()(ResultStream(raw)))
