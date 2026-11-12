import pytest

from app import create_app
from app.classifier.models import ClassificationResult
from app.rules.engine import RulesEngine
from app.rules.models import RuleSet
from tests.helpers import FakeScan, StubClassifier, make_image_bytes


# data fixtures
@pytest.fixture(scope="session")
def image_bytes():

    return make_image_bytes()


@pytest.fixture
def ruleset():
    return RuleSet("Dortmund")


@pytest.fixture
def engine(ruleset):
    return RulesEngine(ruleset)


@pytest.fixture
def decision(engine):
    return engine.decide(ClassificationResult("tin can", 0.8, "metal"))


@pytest.fixture
def scans():
    return [FakeScan(1), FakeScan(3), FakeScan(3, "trash", False, 0.6),
            FakeScan(2, region="Berlin")]


# database fixtures
@pytest.fixture
def database():
    from app.rules.database import Database
    db = Database("sqlite://")
    db.create_tables()
    return db


@pytest.fixture
def repository(database):
    from app.rules.database import ScanRepository
    return ScanRepository(database)


# application fixtures
@pytest.fixture
def make_app():

    def _make(results=None, **overrides):
        cfg = {"DATABASE_URL": "sqlite://", "KICONNECT_API_KEY": ""}
        cfg.update(overrides)
        app = create_app(cfg)
        app.extensions["services"].classifier.backend = StubClassifier(results)
        return app
    return _make


@pytest.fixture
def app(make_app):
    return make_app(results=[["plastic bottle", 0.9], ["glass jar", 0.5]])


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def upload(image_bytes):
    import io

    def _upload(client, data=None, name="photo.png"):
        return client.post("/api/scan", content_type="multipart/form-data",
                           data={"image": (io.BytesIO(data or image_bytes), name)})
    return _upload