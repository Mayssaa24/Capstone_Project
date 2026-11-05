from abc import ABC, abstractmethod
from collections.abc import Iterator

from app.coach.coach import CoachAdvice
from app.errors import CoachError


class CoachEvent:


    def __init__(self, decision, prompt=None, advice=None):
        self._decision = decision
        self._prompt = prompt
        self._advice = advice

    @property
    def decision(self):
        return self._decision

    @property
    def prompt(self):
        return self._prompt

    @property
    def advice(self):
        return self._advice

    def with_prompt(self, prompt):
        return CoachEvent(self._decision, prompt, self._advice)

    def with_advice(self, advice):
        return CoachEvent(self._decision, self._prompt, advice)


class DecisionStream(Iterator):

    def __init__(self, decisions=()):
        self._decisions = list(decisions)
        self._index = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self._index >= len(self._decisions):
            raise StopIteration
        decision = self._decisions[self._index]
        self._index += 1
        return CoachEvent(decision)


class CoachStage(ABC):
    @abstractmethod
    def process(self, stream):
      pass

    def __call__(self, stream):
        return self.process(stream)

    def __or__(self, other):
        return CoachPipeline([self]) | other

    def __add__(self, other):
        return self | other


class CoachPipeline(CoachStage):
    def __init__(self, stages=()):
        self._stages = list(stages)

    @property
    def stages(self):
        return tuple(self._stages)

    def __or__(self, other):
        extra = other.stages if isinstance(other, CoachPipeline) else (other,)
        return CoachPipeline(self._stages + list(extra))

    def __len__(self):
        return len(self._stages)

    def __repr__(self):
        return " | ".join(type(s).__name__ for s in self._stages) or "CoachPipeline()"

    def process(self, stream):
        stream = iter(stream)
        for stage in self._stages:
            stream = stage.process(stream)
        return stream


class PromptStage(CoachStage):
#adds the prompt

    def __init__(self, prompt_builder):
        self._builder = None
        self.prompt_builder = prompt_builder

    @property
    def prompt_builder(self):
        return self._builder

    @prompt_builder.setter
    def prompt_builder(self, value):
        if not hasattr(value, "build"):
            raise CoachError("PromptStage needs a prompt builder with build().")
        self._builder = value

    def process(self, stream):
        for event in stream:
            yield event.with_prompt(self._builder.build(event.decision))


class AdviceStage(CoachStage):
    """Asks a coach (AI, offline or CoachService) for advice on each decision."""

    def __init__(self, coach):
        self._coach = None
        self.coach = coach

    @property
    def coach(self):
        return self._coach

    @coach.setter
    def coach(self, value):
        if not hasattr(value, "advise"):
            raise CoachError("AdviceStage needs a coach with advise().")
        self._coach = value

    def process(self, stream):
        for event in stream:
            yield event.with_advice(self._coach.advise(event.decision))


def _require_advice(event, stage):
    if event.advice is None:
        raise CoachError(f"{stage} needs AdviceStage to run before it.")
    return event.advice


class TipCleaner(CoachStage):

    def process(self, stream):
        for event in stream:
            advice = _require_advice(event, "TipCleaner")
            seen, tips = set(), []
            for tip in advice.tips:
                tip = tip.strip()
                if tip and tip.lower() not in seen:
                    seen.add(tip.lower())
                    tips.append(tip)
            yield event.with_advice(CoachAdvice(advice.headline, tips, advice.fun_fact,
                                                advice.source))


class TipLimiter(CoachStage):

    def __init__(self, max_tips=3):
        self._max_tips = 3
        self.max_tips = max_tips

    @property
    def max_tips(self):
        return self._max_tips

    @max_tips.setter
    def max_tips(self, value):
        if value < 1:
            raise CoachError("max_tips must be at least 1.")
        self._max_tips = value

    def process(self, stream):
        for event in stream:
            advice = _require_advice(event, "TipLimiter")
            yield event.with_advice(CoachAdvice(advice.headline, advice.tips[:self._max_tips],
                                                advice.fun_fact, advice.source))
