import json
import logging
from dotenv import load_dotenv

load_dotenv()
from abc import ABC, abstractmethod

from app.errors import CoachError, CoachUnavailableError

log = logging.getLogger("waste_sorting")


class CoachAdvice:
    def __init__(self, headline, tips, fun_fact="", source="offline"):
        self.headline = headline
        self.tips = list(tips)
        self.fun_fact = fun_fact
        self.source = source

    def to_dict(self):
        return {"headline": self.headline, "tips": self.tips,
                "fun_fact": self.fun_fact, "source": self.source}


class PromptBuilder:
    def __init__(self, region="Dortmund", language="English"):
        self._region = region
        self._language = language

    @property
    def region(self):
        return self._region

    @region.setter
    def region(self, value):
        self._region = value

    @property
    def language(self):
        return self._language

    @language.setter
    def language(self, value):
        self._language = value

    def build(self, decision):
        return (f"A resident of {self._region} scanned an item recognised as "
                f"'{decision.label}' (material: {decision.material}). Local rule: put it in "
                f"'{decision.bin_name}'. Reply in {self._language} with ONLY JSON: "
                '{"headline": str, "tips": [2-3 short practical tips], "fun_fact": str}.')


class BaseCoach(ABC):
    def __init__(self, prompt_builder):
        self._prompts = prompt_builder

    @property
    def prompts(self):
        return self._prompts

    @prompts.setter
    def prompts(self, value):
        self._prompts = value

    @abstractmethod
    def advise(self, decision):
     pass


class OfflineCoach(BaseCoach):
  #offline coach with no internet

    FACTS = {
        "plastic": "Recycling one plastic bottle saves enough energy to power a lamp for hours.",
        "metal": "Aluminium can be recycled endlessly and saves about 95% of the energy of new metal.",
        "paper": "Paper fibres can be recycled around five to seven times.",
        "cardboard": "Flattened cardboard takes far less space in the collection bin.",
        "glass": "Glass can be recycled forever without losing quality.",
        "organic": "Composting turns food scraps into soil instead of methane in landfill.",
        "textile": "Reusing clothes is better than recycling them, so donate wearable items.",
        "e-waste": "Old electronics contain valuable metals that can be recovered.",
        "trash": "Reducing packaging at the shop is the best way to shrink residual waste.",
    }

    def advise(self, decision):
        tips = [f"Put it in: {decision.bin_name}.", decision.instructions]
        if not decision.recyclable:
            tips.append("Check whether a reusable alternative exists next time.")
        return CoachAdvice(f"This looks like {decision.material}.", tips,
                           self.FACTS.get(decision.material, ""), source="offline")


class OpenAICoach(BaseCoach):
    def __init__(self, prompt_builder, api_key, model="GPT-OSS-120B"):
        super().__init__(prompt_builder)
        self._api_key = api_key
        self._model = model

    @property
    def model(self):
        return self._model

    @model.setter
    def model(self, value):
        self._model = value

    def advise(self, decision):
        if not self._api_key:
            raise CoachUnavailableError("No KI:connect API key configured.")
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self._api_key,
                            base_url="https://chat.kiconnect.nrw/api/v1",
                            timeout=15)
            reply = client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": self._prompts.build(decision)}])
            data = json.loads(reply.choices[0].message.content)
            return CoachAdvice(data["headline"], data["tips"], data.get("fun_fact", ""), "kiconnect")
        except CoachError:
            raise
        except Exception as exc:
            raise CoachUnavailableError("The AI coach could not be reached.",
                                        details={"reason": str(exc)[:200]}) from exc


class CoachService:
 #uses offline coach when error

    def __init__(self, primary, fallback):
        self._primary = primary
        self._fallback = fallback

    @property
    def primary(self):
        return self._primary

    @primary.setter
    def primary(self, value):
        self._primary = value

    def advise(self, decision):
        try:
            return self._primary.advise(decision)
        except CoachError as exc:
            log.warning("Coach fallback: %s", exc.message)
            return self._fallback.advise(decision)
if __name__ == "__main__":
    import os
    import sys

    from app.classifier.models import ClassificationResult
    from app.rules.engine import RulesEngine
    from app.rules.models import RuleSet

    if len(sys.argv) < 3:
        print('Usage: python -m app.coach.coach "item label" material [region]')
        print('Example: python -m app.coach.coach "glass bottle" glass Dortmund')
    else:
        label, material = sys.argv[1], sys.argv[2]
        region = sys.argv[3] if len(sys.argv) > 3 else "Dortmund"

        decision = RulesEngine(RuleSet(region)).decide(ClassificationResult(label, 0.9, material))

        prompts = PromptBuilder(region)
        service = CoachService(
            OpenAICoach(prompts, os.getenv("KICONNECT_API_KEY", "")),
            OfflineCoach(prompts),
        )
        advice = service.advise(decision)

        print("Source:", advice.source)
        print("Headline:", advice.headline)
        print("Tips:")
        for tip in advice.tips:
            print(f"  - {tip}")
        print("Fun fact:", advice.fun_fact)