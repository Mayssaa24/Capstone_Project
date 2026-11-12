from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Iterator
from datetime import timedelta

from app.errors import DashboardError


class ScanEventStream(Iterator):

    def __init__(self, scans=()):
        self._scans = list(scans)
        self._index = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self._index >= len(self._scans):
            raise StopIteration
        scan = self._scans[self._index]
        self._index += 1
        return scan


class StreamStage(ABC):

    @abstractmethod
    def process(self, stream):
        pass
    def __call__(self, stream):
        return self.process(stream)

    def __or__(self, other):
        return StagePipeline([self]) | other

    def __add__(self, other):
        return self | other


class StagePipeline(StreamStage):
    def __init__(self, stages=()):
        self._stages = list(stages)

    @property
    def stages(self):
        return tuple(self._stages)

    def __or__(self, other):
        extra = other.stages if isinstance(other, StagePipeline) else (other,)
        return StagePipeline(self._stages + list(extra))

    def __len__(self):
        return len(self._stages)

    def __repr__(self):
        return " | ".join(type(s).__name__ for s in self._stages) or "StagePipeline()"

    def process(self, stream):
        stream = iter(stream)
        for stage in self._stages:
            stream = stage.process(stream)
        return stream


class RegionFilter(StreamStage):
    def __init__(self, region=None):
        self._region = None
        self.region = region

    @property
    def region(self):
        return self._region

    @region.setter
    def region(self, value):
        self._region = value or None      # None = let every region through

    def process(self, stream):
        for scan in stream:
            if self._region is None or scan.region == self._region:
                yield scan


class DateRangeFilter(StreamStage):

    def __init__(self, start, end):
        self._start = start
        self._end = end
        self.initialize()

    @staticmethod
    def _check(start, end):
        if start > end:
            raise DashboardError("Date range start must not be after its end.")

    def initialize(self):
        self._check(self._start, self._end)

    @property
    def start(self):
        return self._start

    @start.setter
    def start(self, value):
        self._check(value, self._end)
        self._start = value

    @property
    def end(self):
        return self._end

    @end.setter
    def end(self, value):
        self._check(self._start, value)
        self._end = value

    def process(self, stream):
        for scan in stream:
            if self._start <= scan.created_at.date() <= self._end:
                yield scan


class DailyAggregator(StreamStage):
    """Consumes scans and yields (date, count) for EVERY day in the range."""

    def __init__(self, start, end):
        self._start = start
        self._end = end

    def process(self, stream):
        counts = Counter(scan.created_at.date() for scan in stream)
        day = self._start
        while day <= self._end:
            yield day, counts.get(day, 0)
            day += timedelta(days=1)
