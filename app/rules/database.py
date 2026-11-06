from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool

from app.errors import StorageError


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)
    label: Mapped[str] = mapped_column(String(100))
    material: Mapped[str] = mapped_column(String(50), index=True)
    bin_name: Mapped[str] = mapped_column(String(100))
    recyclable: Mapped[bool] = mapped_column(Boolean)
    confidence: Mapped[float] = mapped_column(Float)
    region: Mapped[str] = mapped_column(String(50))

    def to_dict(self):
        return {"id": self.id, "created_at": self.created_at.isoformat(),
                "label": self.label, "material": self.material, "bin": self.bin_name,
                "recyclable": self.recyclable, "confidence": round(self.confidence, 4),
                "region": self.region}


class Database:

    def __init__(self, url):
        self._url = url
        self._engine = None
        self._sessions = None
        self.initialize()

    @property
    def url(self):
        return self._url

    @url.setter
    def url(self, value):
        self._url = value
        self.initialize()

    def initialize(self):
        kwargs = {}
        if self._url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            if self._url in ("sqlite://", "sqlite:///:memory:"):
                kwargs["poolclass"] = StaticPool
        else:
            kwargs["pool_pre_ping"] = True
        try:
            self._engine = create_engine(self._url, **kwargs)
            self._sessions = sessionmaker(self._engine, expire_on_commit=False)
        except Exception as exc:
            raise StorageError("Invalid database configuration.") from exc

    def create_tables(self):
        try:
            Base.metadata.create_all(self._engine)
        except SQLAlchemyError as exc:
            raise StorageError("Could not create database tables.",
                               details={"reason": str(exc.__cause__ or exc)[:200]}) from exc

    def session(self):
        return self._sessions()


class ScanRepository:
    def __init__(self, database):
        self._db = database

    @property
    def database(self):
        return self._db

    @database.setter
    def database(self, value):
        self._db = value

    def add(self, decision):
        scan = Scan(label=decision.label, material=decision.material,
                    bin_name=decision.bin_name, recyclable=decision.recyclable,
                    confidence=decision.confidence, region=decision.region)
        try:
            with self._db.session() as session:
                session.add(scan)
                session.commit()
            return scan
        except SQLAlchemyError as exc:
            raise StorageError("Could not save the scan.") from exc

    def list_scans(self, region=None):
        try:
            query = select(Scan).order_by(Scan.created_at, Scan.id)
            if region:
                query = query.where(Scan.region == region)
            with self._db.session() as session:
                return list(session.scalars(query))
        except SQLAlchemyError as exc:
            raise StorageError("Could not read scans.") from exc

    def count(self):
        return len(self.list_scans())
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print('Usage: python -m app.rules.database "sqlite:///waste_sorting.db" [region] [--add]')
    else:
        args = [a for a in sys.argv[1:] if a != "--add"]
        add_sample = "--add" in sys.argv
        region = args[1] if len(args) > 1 else None

        database = Database(args[0])
        database.create_tables()
        repository = ScanRepository(database)

        if add_sample:
            from app.classifier.models import ClassificationResult
            from app.rules.engine import RulesEngine
            from app.rules.models import RuleSet

            engine = RulesEngine(RuleSet(region or "Dortmund"))
            saved = repository.add(engine.decide(ClassificationResult("glass bottle", 0.9, "glass")))
            print("Added sample scan with id", saved.id)

        scans = repository.list_scans(region)
        print("Database:", database.url)
        print("Region filter:", region or "none")
        print("Total scans:", len(scans))

        for scan in scans:
            print(f"  #{scan.id}  {scan.created_at:%Y-%m-%d %H:%M:%S}  {scan.label} "
                  f"[{scan.material}] -> {scan.bin_name}  ({scan.confidence:.2f}, {scan.region})")