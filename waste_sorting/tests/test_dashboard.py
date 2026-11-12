from datetime import date

import pytest

from app.coach.coach import OpenAICoach
from app.dashboard.analytics import ChartBuilder, DashboardService, ScanAnalytics, TrendCalculator
from app.dashboard.stream import (
    DailyAggregator,
    DateRangeFilter,
    RegionFilter,
    ScanEventStream,
    StagePipeline,
    StreamStage,
)
from app.errors import DashboardError, DashboardErrorHandler
from tests.helpers import FakeRepository, FakeScan, error_client

unit = pytest.mark.unit
integration = pytest.mark.integration
functional = pytest.mark.functional
regression = pytest.mark.regression


@unit
def test_unit_01_event_stream_is_an_iterator(scans):
    stream = ScanEventStream(scans)
    assert iter(stream) is stream
    assert len(list(stream)) == 4
    with pytest.raises(StopIteration):
        next(stream)


@unit
def test_unit_02_region_filter_keeps_only_matching_region(scans):
    out = list(RegionFilter("Dortmund")(ScanEventStream(scans)))
    assert len(out) == 3 and all(s.region == "Dortmund" for s in out)


@unit
def test_unit_03_region_filter_setter_changes_behaviour(scans):
    stage = RegionFilter("Dortmund")
    stage.region = None
    assert len(list(stage(ScanEventStream(scans)))) == 4


@unit
def test_unit_04_date_range_filter_is_inclusive(scans):
    out = list(DateRangeFilter(date(2026, 11, 1), date(2026, 11, 2))(ScanEventStream(scans)))
    assert [s.created_at.day for s in out] == [1, 2]


@unit
def test_unit_05_date_range_filter_validates_and_setters_revalidate():
    stage = DateRangeFilter(date(2026, 11, 1), date(2026, 11, 5))
    with pytest.raises(DashboardError):
        DateRangeFilter(date(2026, 11, 5), date(2026, 11, 1))
    with pytest.raises(DashboardError):
        stage.start = date(2026, 12, 1)
    assert stage.start == date(2026, 11, 1)
    stage.end = date(2026, 11, 9)
    assert stage.end == date(2026, 11, 9)


@unit
def test_unit_06_daily_aggregator_zero_fills_days(scans):
    agg = DailyAggregator(date(2026, 11, 1), date(2026, 11, 4))
    assert [n for _, n in agg(ScanEventStream(scans))] == [1, 1, 2, 0]


@unit
def test_unit_07_stages_compose_with_or_and_add(scans):
    a = RegionFilter("Dortmund")
    b = DateRangeFilter(date(2026, 11, 1), date(2026, 11, 3))
    c = DailyAggregator(date(2026, 11, 1), date(2026, 11, 3))
    piped, added = a | b | c, a + b + c
    assert isinstance(piped, StagePipeline) and len(piped) == len(added) == 3
    assert repr(piped) == "RegionFilter | DateRangeFilter | DailyAggregator"
    assert [n for _, n in piped(ScanEventStream(scans))] == [1, 0, 2]


@unit
def test_unit_08_stream_stage_is_abstract():
    with pytest.raises(TypeError):
        StreamStage()


@unit
def test_unit_09_totals_rate_and_confidence(scans):
    stats = ScanAnalytics([s for s in scans if s.region == "Dortmund"])
    assert stats.total() == 3 and stats.recycling_rate() == 66.7
    assert stats.average_confidence() == 0.733


@unit
def test_unit_10_empty_data_gives_zeroes():
    stats = ScanAnalytics()
    assert (stats.total(), stats.recycling_rate(), stats.average_confidence()) == (0, 0.0, 0.0)


@unit
def test_unit_11_count_by_groups_values(scans):
    assert ScanAnalytics(scans).count_by("material") == {"plastic": 3, "trash": 1}


@unit
def test_unit_12_daily_counts_and_invalid_days(scans):
    stats = ScanAnalytics(scans)
    assert [n for _, n in stats.daily_counts(3, date(2026, 11, 3))] == [1, 1, 2]
    with pytest.raises(DashboardError):
        stats.daily_counts(0)


@unit
def test_unit_13_scans_setter_replaces_data_and_validates():
    stats = ScanAnalytics([FakeScan(1), FakeScan(2)])
    stats.scans = [FakeScan(1)]
    assert stats.total() == 1
    with pytest.raises(DashboardError):
        stats.scans = [object()]


@unit
def test_unit_14_scans_property_returns_a_copy():
    stats = ScanAnalytics([FakeScan(1)])
    stats.scans.append(FakeScan(2))
    assert stats.total() == 1


@unit
def test_unit_15_trend_direction():
    calc = TrendCalculator()
    assert (calc.direction([0, 0, 3, 4]), calc.direction([4, 3, 0, 0]), calc.direction([])) == \
        ("up", "down", "flat")
    assert calc.direction([2, 2, 2, 2]) == "flat"


@unit
def test_unit_16_trend_tolerance_setter_validates():
    calc = TrendCalculator()
    calc.tolerance = 10
    assert calc.direction([0, 0, 3, 4]) == "flat"
    with pytest.raises(DashboardError):
        calc.tolerance = -1
    assert calc.tolerance == 10
    with pytest.raises(DashboardError):
        TrendCalculator(tolerance=-5)


@unit
def test_unit_17_material_chart_colours_and_unknown_material():
    chart = ChartBuilder().material_chart({"plastic": 2, "mystery": 1})
    assert chart["type"] == "doughnut" and chart["values"] == [2, 1]
    assert chart["colors"] == ["#f5b700", "#adb5bd"]


@unit
def test_unit_18_bin_chart_and_trend_chart_shapes():
    builder = ChartBuilder()
    assert builder.bin_chart({"Yellow": 3}) == {"type": "bar", "labels": ["Yellow"], "values": [3]}
    trend = builder.trend_chart([(date(2026, 11, 3), 2)])
    assert trend == {"type": "line", "labels": ["03 Nov"], "values": [2]}


@unit
def test_unit_19_palette_and_default_colour_setters():
    builder = ChartBuilder()
    builder.palette = {"plastic": "#000000"}
    builder.default_color = "#ffffff"
    chart = builder.material_chart({"plastic": 1, "glass": 1})
    assert chart["colors"] == ["#000000", "#ffffff"] and builder.palette == {"plastic": "#000000"}


@unit
def test_unit_20_service_builds_the_full_payload(scans):
    data = DashboardService(FakeRepository(scans), "Dortmund", days=3).build(date(2026, 11, 3))
    assert data["summary"]["total"] == 3 and data["summary"]["trend"] == "up"
    assert set(data["charts"]) == {"materials", "bins", "trend"}
    assert data["charts"]["trend"]["values"] == [1, 0, 2]
    assert len(data["recent"]) == 3 and data["region"] == "Dortmund"


@unit
def test_unit_21_service_with_no_scans_is_empty_not_an_error():
    data = DashboardService(FakeRepository([]), "Dortmund").build()
    assert data["summary"]["total"] == 0 and data["summary"]["trend"] == "flat"
    assert data["recent"] == []


@unit
def test_unit_22_service_setters_validate(scans):
    service = DashboardService(FakeRepository([]), "Dortmund")
    with pytest.raises(DashboardError):
        service.days = 0
    with pytest.raises(DashboardError):
        service.region = ""
    service.repository, service.region, service.days = FakeRepository(scans), "Berlin", 5
    assert (service.region, service.days) == ("Berlin", 5)
    assert service.build(date(2026, 11, 3))["summary"]["total"] == 1


@unit
def test_unit_23_dashboard_error_handler_returns_json():
    res = error_client(DashboardErrorHandler, DashboardError("chart failed")).get("/boom")
    assert res.status_code == 500
    assert res.get_json()["error"]["subsystem"] == "dashboard"


@integration
def test_integration_01_service_container_wires_every_subsystem(app):
    services = app.extensions["services"]
    assert services.rules.region == "Dortmund"
    assert isinstance(services.coach.primary, OpenAICoach)
    assert services.dashboard.repository is services.repository
    assert services.classifier.min_confidence == 0.35


@integration
def test_integration_02_rows_written_by_the_repository_show_up_on_the_dashboard_api(client, decision):
    client.application.extensions["services"].repository.add(decision)
    body = client.get("/api/dashboard").get_json()
    assert body["summary"]["total"] == 1 and body["charts"]["materials"]["labels"] == ["metal"]


@functional
def test_functional_01_home_page_offers_camera_upload_and_charts(client):
    html = client.get("/").get_data(as_text=True)
    for part in ("Take photo", "Upload photo", 'capture="environment"', "chart-materials",
                 "chart-bins", "chart-trend", "Dortmund", "chart.umd.min.js"):
        assert part in html


@functional
def test_functional_02_static_assets_are_served(client):
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200


@functional
def test_functional_03_health_endpoint(client):
    assert client.get("/health").get_json() == {"status": "ok"}


@functional
def test_functional_04_unknown_url_returns_json_404(client):
    res = client.get("/nope")
    assert res.status_code == 404 and res.get_json()["error"]["code"] == "not_found"


@functional
def test_functional_05_dashboard_starts_empty(client):
    body = client.get("/api/dashboard").get_json()
    assert body["summary"] == {"total": 0, "recycling_rate": 0.0, "average_confidence": 0.0,
                               "trend": "flat"}
    assert body["charts"]["materials"]["values"] == []
    assert len(body["charts"]["trend"]["values"]) == 14


@functional
def test_functional_06_charts_update_after_each_scan(client, upload):
    upload(client)
    upload(client)
    body = client.get("/api/dashboard").get_json()
    assert body["summary"]["total"] == 2
    assert body["charts"]["materials"] == {"type": "doughnut", "labels": ["plastic"],
                                           "values": [2], "colors": ["#f5b700"]}
    assert body["charts"]["trend"]["values"][-1] == 2
    assert len(body["recent"]) == 2


@functional
def test_functional_07_different_items_appear_in_the_materials_chart(make_app, upload):
    app = make_app(results=[["tin can", 0.9]])
    client = app.test_client()
    upload(client)
    app.extensions["services"].classifier.backend._results = [["cardboard", 0.9]]
    upload(client)
    labels = client.get("/api/dashboard").get_json()["charts"]["materials"]["labels"]
    assert sorted(labels) == ["cardboard", "metal"]


@regression
def test_regression_01_days_without_scans_still_appear_in_the_trend_chart():
    repo = FakeRepository([FakeScan(1), FakeScan(5)])
    values = DashboardService(repo, "Dortmund", days=5).build(date(2026, 11, 5))["charts"]["trend"]["values"]
    assert values == [1, 0, 0, 0, 1]


@regression
def test_regression_02_an_empty_database_gives_a_flat_dashboard():
    data = DashboardService(FakeRepository([]), "Dortmund").build()
    assert data["summary"]["trend"] == "flat" and data["summary"]["total"] == 0


@regression
def test_regression_03_the_removed_trend_tile_is_not_referenced_by_page_or_script(client):
    html = client.get("/").get_data(as_text=True)
    script = client.get("/static/app.js").get_data(as_text=True)
    assert "kpi-trend" not in html and "kpi-trend" not in script