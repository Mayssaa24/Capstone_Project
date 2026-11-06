from app.errors import InferenceError


class ClassificationResult:

    def __init__(self, label, confidence, material=None):
        self._label = ""
        self._confidence = 0.0
        self._material = material
        self.label = label
        self.confidence = confidence

    @property
    def label(self):
        return self._label

    @label.setter
    def label(self, value):
        if not isinstance(value, str) or not value.strip():
            raise InferenceError("Prediction label must be a non-empty string.")
        self._label = value.strip()

    @property
    def confidence(self):
        return self._confidence

    @confidence.setter
    def confidence(self, value):
        if not 0.0 <= float(value) <= 1.0:
            raise InferenceError("Confidence must be between 0 and 1.", details={"value": value})
        self._confidence = float(value)

    @property
    def material(self):
        return self._material

    @material.setter
    def material(self, value):
        self._material = value

    def to_dict(self):
        return {"label": self.label, "confidence": round(self.confidence, 4),
                "material": self.material}

    def __repr__(self):
        return f"ClassificationResult({self.label!r}, {self.confidence:.2f}, {self.material!r})"
