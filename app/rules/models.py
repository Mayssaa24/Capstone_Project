from app.errors import InvalidRuleError


class Rule:
    def __init__(self, material, bin_name, recyclable, instructions):
        self._material = ""
        self._bin_name = ""
        self._recyclable = False
        self._instructions = ""
        self.material = material
        self.bin_name = bin_name
        self.recyclable = recyclable
        self.instructions = instructions

    @property
    def material(self):
        return self._material

    @material.setter
    def material(self, value):
        if not value or not str(value).strip():
            raise InvalidRuleError("A rule needs a material.")
        self._material = str(value).strip().lower()

    @property
    def bin_name(self):
        return self._bin_name

    @bin_name.setter
    def bin_name(self, value):
        if not value or not str(value).strip():
            raise InvalidRuleError("A rule needs a bin.")
        self._bin_name = str(value).strip()

    @property
    def recyclable(self):
        return self._recyclable

    @recyclable.setter
    def recyclable(self, value):
        self._recyclable = bool(value)

    @property
    def instructions(self):
        return self._instructions

    @instructions.setter
    def instructions(self, value):
        self._instructions = str(value or "")


class Decision:

    def __init__(self, label, confidence, rule, region):
        self.label = label
        self.confidence = confidence
        self.rule = rule
        self.region = region

    @property
    def material(self):
        return self.rule.material

    @property
    def bin_name(self):
        return self.rule.bin_name

    @property
    def recyclable(self):
        return self.rule.recyclable

    @property
    def instructions(self):
        return self.rule.instructions

    def to_dict(self):
        return {"label": self.label, "confidence": round(self.confidence, 4),
                "material": self.material, "bin": self.bin_name,
                "recyclable": self.recyclable, "instructions": self.instructions,
                "region": self.region}


class RuleSet:

    DEFAULTS = (
        ("plastic", "Yellow bin (Gelbe Tonne)", True,
         "Empty the packaging; scraping is enough, no need to wash it."),
        ("metal", "Yellow bin (Gelbe Tonne)", True,
         "Empty cans and lids go in the yellow bin; no need to rinse thoroughly."),
        ("paper", "Blue bin (Blaue Tonne)", True,
         "Clean paper only. Greasy or wet paper goes in residual waste."),
        ("cardboard", "Blue bin (Blaue Tonne)", True,
         "Flatten boxes and remove tape and plastic wrapping."),
        ("glass", "Glass container (Altglascontainer)", True,
         "Sort by colour, remove lids. Deposit bottles (Pfand) go back to the shop."),
        ("organic", "Organic waste bin (Biotonne)", True,
         "Food scraps and garden waste only, no plastic bags."),
        ("textile", "Textile collection container", True,
         "Clean, dry clothes and shoes, tied in pairs or bagged."),
        ("e-waste", "Recycling centre / retailer take-back", True,
         "Never put batteries or electronics in household bins."),
        ("trash", "Residual waste bin (Restmülltonne)", False,
         "If nothing else fits, it goes in residual waste."),
    )

    def __init__(self, region="Dortmund"):
        self._region = region
        self._rules = {}
        self.load_defaults()

    @property
    def region(self):
        return self._region

    @region.setter
    def region(self, value):
        if not value:
            raise InvalidRuleError("Region cannot be empty.")
        self._region = value

    def load_defaults(self):
        self._rules.clear()
        for args in self.DEFAULTS:
            self.add_rule(Rule(*args))

    def add_rule(self, rule):
        self._rules[rule.material] = rule

    def get_rule(self, material):
        return self._rules.get((material or "").lower(), self._rules["trash"])

    def materials(self):
        return sorted(self._rules)
