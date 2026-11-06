import re
from abc import ABC, abstractmethod
from collections.abc import Iterator

from app.classifier.models import ClassificationResult


class ResultStream(Iterator):

    def __init__(self, items=()):
        self._items = list(items)
        self._index = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self._index >= len(self._items):
            raise StopIteration
        item = self._items[self._index]
        self._index += 1
        return item


class Processor(ABC):
    """Interface contract: every stage turns a stream into a stream."""

    @abstractmethod
    def process(self, stream):
        """Yield processed events lazily."""

    def __call__(self, stream):
        return self.process(stream)

    def __or__(self, other):
        return Pipeline([self]) | other

    def __add__(self, other):
        return self | other


class Pipeline(Processor):
    def __init__(self, stages=()):
        self._stages = list(stages)

    @property
    def stages(self):
        return tuple(self._stages)

    def __or__(self, other):
        extra = other.stages if isinstance(other, Pipeline) else (other,)
        return Pipeline(self._stages + list(extra))

    def __len__(self):
        return len(self._stages)

    def __repr__(self):
        return " | ".join(type(s).__name__ for s in self._stages) or "Pipeline()"

    def process(self, stream):
        stream = iter(stream)
        for stage in self._stages:
            stream = stage.process(stream)
        return stream


class ConfidenceFilter(Processor):
    def __init__(self, min_confidence=0.35):
        self.min_confidence = min_confidence

    def process(self, stream):
        for event in stream:
            if event.confidence >= self.min_confidence:
                yield event


class TopKLimiter(Processor):
    def __init__(self, k=3):
        self.k = k

    def process(self, stream):
        for count, event in enumerate(stream):
            if count >= self.k:
                return
            yield event


class LabelNormalizer(Processor):

    KEYWORDS = (
        ("cardboard", {"cardboard", "carton", "box"}),
        ("paper", {"paper", "newspaper", "magazine", "envelope"}),
        ("plastic", {"plastic", "pet", "hdpe", "polythene", "foil"}),
        ("glass", {"glass", "jar"}),
        ("metal", {"metal", "can", "aluminum", "aluminium", "steel", "tin"}),
        ("organic", {"organic", "biological", "food", "compost", "fruit", "vegetable"}),
        ("textile", {"clothes", "clothing", "textile", "shoes", "fabric", "cloth"}),
        ("e-waste", {"battery", "electronic", "ewaste", "phone", "cable"}),
    )

    def __init__(self, default="trash"):
        self.default = default

    def normalize(self, label):
        tokens = set(re.split(r"[^a-z0-9]+", label.lower()))
        for material, words in self.KEYWORDS:
            if tokens & words:
                return material
        return self.default

    def process(self, stream):
        for event in stream:
            yield ClassificationResult(event.label, event.confidence, self.normalize(event.label))
