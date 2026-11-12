from app.classifier.backends import SigLIP2Classifier
from app.classifier.preprocessor import ImagePreprocessor
from app.classifier.service import ClassifierService
from app.coach.coach import CoachService, OfflineCoach, OpenAICoach, PromptBuilder
from app.dashboard.analytics import DashboardService
from app.rules.database import Database, ScanRepository
from app.rules.engine import RulesEngine
from app.rules.models import RuleSet


class ServiceContainer:

    def __init__(self, config):
        self.config = config
        region = config["REGION"]

        database = Database(config["DATABASE_URL"])
        database.create_tables()
        self.repository = ScanRepository(database)
        self.rules = RulesEngine(RuleSet(region))

        backend = SigLIP2Classifier()
        self.classifier = ClassifierService(
            backend, ImagePreprocessor(config["MAX_CONTENT_LENGTH"]), config["MIN_CONFIDENCE"])

        prompts = PromptBuilder(region)
        self.coach = CoachService(
            OpenAICoach(prompts, config["KICONNECT_API_KEY"], config["KICONNECT_MODEL"]),
            OfflineCoach(prompts))
        self.dashboard = DashboardService(self.repository, region)
