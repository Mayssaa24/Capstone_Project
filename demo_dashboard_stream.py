"""Demo for the video: scan events flowing through the dashboard stream pipeline."""
from datetime import date, datetime

from app.dashboard.stream import (DailyAggregator, DateRangeFilter, RegionFilter,
                                  ScanEventStream)


class Scan:
    def __init__(self, day, region="Dortmund"):
        self.created_at = datetime(2026, 11, day, 10)
        self.region = region


scans = [Scan(1), Scan(1), Scan(3), Scan(2, "Berlin"), Scan(4)]
start, end = date(2026, 11, 1), date(2026, 11, 5)

pipeline = RegionFilter("Dortmund") | DateRangeFilter(start, end) | DailyAggregator(start, end)
print("Pipeline:", pipeline)
for day, count in pipeline(ScanEventStream(scans)):
    print(day, "#" * count, count)
