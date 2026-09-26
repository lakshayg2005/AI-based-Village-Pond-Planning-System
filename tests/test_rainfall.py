import pytest

from app.services import rainfall_service as rain


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(rain, "_CACHE_FILE", tmp_path / "rain.json")


def _ok(source):
    def provider(lat, lon):
        return rain.RainfallResult(1200.0, [100.0] * 12, source, True, "test")
    return provider


def _down(lat, lon):
    raise ConnectionError("blocked")


def test_falls_through_to_next_provider(monkeypatch):
    monkeypatch.setattr(rain, "PROVIDERS", (_down, _ok("second")))
    assert rain.get_annual_rainfall(21.26, 81.28).source == "second"


def test_all_providers_failing_raises(monkeypatch):
    monkeypatch.setattr(rain, "PROVIDERS", (_down, _down))
    with pytest.raises(rain.RainfallError):
        rain.get_annual_rainfall(21.26, 81.28)


def test_result_is_cached_and_shared_by_nearby_points(monkeypatch):
    calls = []

    def counting(lat, lon):
        calls.append((lat, lon))
        return _ok("first")(lat, lon)

    monkeypatch.setattr(rain, "PROVIDERS", (counting,))
    rain.get_annual_rainfall(21.26, 81.28)
    rain.get_annual_rainfall(21.27, 81.29)  # same 0.25 degree cell

    assert len(calls) == 1


def test_fallback_is_flagged_not_measured():
    result = rain.fallback_rainfall()
    assert result.measured is False
    assert "default" in result.source
