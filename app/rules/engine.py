from app.rules.models import Decision


class RulesEngine:
    def __init__(self, ruleset):
        self._ruleset = ruleset

    @property
    def ruleset(self):
        return self._ruleset

    @ruleset.setter
    def ruleset(self, value):
        self._ruleset = value

    @property
    def region(self):
        return self._ruleset.region

    def decide(self, result):
        rule = self._ruleset.get_rule(result.material)
        return Decision(result.label, result.confidence, rule, self._ruleset.region)
