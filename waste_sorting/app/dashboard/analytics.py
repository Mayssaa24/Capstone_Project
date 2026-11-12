from collections import Counter
from datetime import datetime, timedelta, timezone

from app.dashboard.stream import DailyAggregator, DateRangeFilter, ScanEventStream
from app.errors import DashboardError


class ScanAnalytics:

    def __init__(self, scans=()):
        self._scans = []
        self.scans = scans

    def initialize(self):
        for scan in self._scans:
            if not hasattr(scan, "created_at"):
                raise DashboardError("Every scan needs a created_at value.")

    @property
    def scans(self):
        return list(self._scans)

    @scans.setter
    def scans(self, value):
        self._scans = list(value)
        self.initialize()

    def total(self):
        return len(self._scans)

    def recycling_rate(self):
        if not self._scans:
            return 0.0
        return round(100 * sum(s.recyclable for s in self._scans) / len(self._scans), 1)

    def average_confidence(self):
        if not self._scans:
            return 0.0
        return round(sum(s.confidence for s in self._scans) / len(self._scans), 3)

    def count_by(self, attribute):
        return dict(Counter(getattr(s, attribute) for s in self._scans))

    def daily_counts(self, days=14, today=None):
        if days < 1:
            raise DashboardError("days must be at least 1")
        today = today or datetime.now(timezone.utc).date()
        start = today - timedelta(days=days - 1)
        pipeline = DateRangeFilter(start, today) | DailyAggregator(start, today)
        return list(pipeline(ScanEventStream(self._scans)))


class TrendCalculator:
    def __init__(self, tolerance=0):
        self._tolerance = tolerance
        self.initialize()

    @staticmethod
    def _check(tolerance):
        if tolerance < 0:
            raise DashboardError("tolerance cannot be negative")

    def initialize(self):
        self._check(self._tolerance)

    @property
    def tolerance(self):
        return self._tolerance

    @tolerance.setter
    def tolerance(self, value):
        self._check(value)
        self._tolerance = value

    def direction(self, series):
        half = len(series) // 2
        if half == 0:
            return "flat"
        diff = sum(series[half:]) - sum(series[:half])
        if diff > self._tolerance:
            return "up"
        if diff < -self._tolerance:
            return "down"
        return "flat"


class ChartBuilder:
    DEFAULT_PALETTE = {"plastic": "#f5b700", "metal": "#8d99ae", "paper": "#4cc9f0",
                       "cardboard": "#b08968", "glass": "#2ec4b6", "organic": "#70a37f",
                       "textile": "#c77dff", "e-waste": "#ef476f", "trash": "#6c757d"}

    def __init__(self, default_color="#adb5bd"):
        self._default_color = default_color
        self._palette = {}
        self.initialize()

    def initialize(self):
        self._palette = dict(self.DEFAULT_PALETTE)

    @property
    def default_color(self):
        return self._default_color

    @default_color.setter
    def default_color(self, value):
        self._default_color = value

    @property
    def palette(self):
        return dict(self._palette)

    @palette.setter
    def palette(self, value):
        self._palette = dict(value)

    def material_chart(self, counts):
        labels = list(counts)
        return {"type": "doughnut", "labels": labels, "values": [counts[k] for k in labels],
                "colors": [self._palette.get(k, self._default_color) for k in labels]}

    def bin_chart(self, counts):
        labels = list(counts)
        return {"type": "bar", "labels": labels, "values": [counts[k] for k in labels]}

    def trend_chart(self, daily):
        return {"type": "line", "labels": [d.strftime("%d %b") for d, _ in daily],
                "values": [n for _, n in daily]}


class DashboardService:
    def __init__(self, repository, region, days=14):
        self._repository = repository
        self._region = region
        self._days = days
        self.initialize()

    def initialize(self):
        self._charts = ChartBuilder()
        self._trends = TrendCalculator()

    @property
    def repository(self):
        return self._repository

    @repository.setter
    def repository(self, value):
        self._repository = value

    @property
    def region(self):
        return self._region

    @region.setter
    def region(self, value):
        if not value:
            raise DashboardError("Region cannot be empty.")
        self._region = value

    @property
    def days(self):
        return self._days

    @days.setter
    def days(self, value):
        if value < 1:
            raise DashboardError("days must be at least 1")
        self._days = value

    def build(self, today=None):
        scans = self._repository.list_scans(self._region)
        stats = ScanAnalytics(scans)
        daily = stats.daily_counts(self._days, today)
        series = [n for _, n in daily]
        return {
            "region": self._region,
            "summary": {"total": stats.total(), "recycling_rate": stats.recycling_rate(),
                        "average_confidence": stats.average_confidence(),
                        "trend": self._trends.direction(series)},
            "charts": {"materials": self._charts.material_chart(stats.count_by("material")),
                       "bins": self._charts.bin_chart(stats.count_by("bin_name")),
                       "trend": self._charts.trend_chart(daily)},
            "recent": [s.to_dict() for s in reversed(scans[-5:])],
        }
if __name__ == "__main__":
    import sys

    from app.rules.database import Database, ScanRepository

    if len(sys.argv) < 2:
        print('Usage: python -m app.dashboard.analytics "sqlite:///path/to/scans.db" [region]')
    else:
        database = Database(sys.argv[1])
        database.create_tables()
        region = sys.argv[2] if len(sys.argv) > 2 else "Dortmund"

        data = DashboardService(ScanRepository(database), region).build()

        print("Region:", data["region"])
        print("Total scans:", data["summary"]["total"])
        print("Recycling rate:", data["summary"]["recycling_rate"], "%")
        print("Average confidence:", data["summary"]["average_confidence"])
        print("Trend:", data["summary"]["trend"])

        print("\nMaterials:")
        materials = data["charts"]["materials"]
        for label, value in zip(materials["labels"], materials["values"]):
            print(f"  {label}: {value}")

        print("\nBins:")
        bins = data["charts"]["bins"]
        for label, value in zip(bins["labels"], bins["values"]):
            print(f"  {label}: {value}")

        print("\nRecent scans:")
        for scan in data["recent"]:
            print(f"  {scan['created_at']}  {scan['label']} -> {scan['bin']}")