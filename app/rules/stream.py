from app.errors import InvalidRuleError
from app.streaming.processors import Processor


class RoutedDecision:
    def __init__(self, decision, lane_code):
        self._decision = decision
        self._lane_code = ""
        self.lane_code = lane_code

    @property
    def decision(self):
        return self._decision

    @property
    def lane_code(self):
        return self._lane_code

    @lane_code.setter
    def lane_code(self, value):
        if not isinstance(value, str) or not value.strip():
            raise InvalidRuleError("A lane code must be a non-empty string.")
        self._lane_code = value.strip().upper()

    def to_dict(self):
        data = self._decision.to_dict()
        data["lane_code"] = self._lane_code
        return data


class DecisionMapper(Processor):

    def __init__(self, engine):
        self._engine = None
        self.engine = engine

    @property
    def engine(self):
        return self._engine

    @engine.setter
    def engine(self, value):
        if not hasattr(value, "decide"):
            raise InvalidRuleError("DecisionMapper needs a rules engine with decide().")
        self._engine = value

    def process(self, stream):
        for result in stream:
            yield self._engine.decide(result)


class RoutingCodeAssigner(Processor):
    DEFAULT_CODES = {"plastic": "YEL-1", "metal": "YEL-2", "paper": "BLU-1",
                     "cardboard": "BLU-2", "glass": "GLS-1", "organic": "BIO-1",
                     "textile": "TEX-1", "e-waste": "ELE-1", "trash": "RES-1"}

    def __init__(self, codes=None, fallback="RES-1"):
        self._codes = {}
        self._fallback = ""
        self.initialize(codes, fallback)

    def initialize(self, codes, fallback):
        self.codes = codes if codes is not None else self.DEFAULT_CODES
        self.fallback = fallback

    @property
    def codes(self):
        return dict(self._codes)

    @codes.setter
    def codes(self, value):
        if not value:
            raise InvalidRuleError("The routing table cannot be empty.")
        self._codes = {str(k).strip().lower(): str(v).strip().upper() for k, v in value.items()}

    @property
    def fallback(self):
        return self._fallback

    @fallback.setter
    def fallback(self, value):
        if not isinstance(value, str) or not value.strip():
            raise InvalidRuleError("The fallback lane code cannot be empty.")
        self._fallback = value.strip().upper()

    def code_for(self, material):
        return self._codes.get((material or "").strip().lower(), self._fallback)

    def process(self, stream):
        for decision in stream:
            yield RoutedDecision(decision, self.code_for(decision.material))


class ScanRecorder(Processor):

    def __init__(self, repository):
        self._repository = None
        self.repository = repository

    @property
    def repository(self):
        return self._repository

    @repository.setter
    def repository(self, value):
        if not hasattr(value, "add"):
            raise InvalidRuleError("ScanRecorder needs a repository with add().")
        self._repository = value

    def process(self, stream):
        for routed in stream:
            self._repository.add(routed.decision)
            yield routed
