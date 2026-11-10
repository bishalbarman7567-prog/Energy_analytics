from datetime import datetime
from backend.analytics.energy_engine import calculate_interval_kwh, resolve_tariff_for_timestamp
from backend.models import Tariff


def test_calculate_interval_kwh():
    # 100 kW for 15 minutes (0.25 hours) must equal exactly 25.0 kWh
    kwh = calculate_interval_kwh(100.0, 15)
    assert kwh == 25.0

    # 40 kW for 15 minutes must equal 10.0 kWh
    assert calculate_interval_kwh(40.0, 15) == 10.0

    # 0 kW must equal 0 kWh
    assert calculate_interval_kwh(0.0, 15) == 0.0


def test_resolve_tariff_peak_and_offpeak():
    mock_tariffs = [
        Tariff(
            tariff_id="TAR-PEAK",
            plant_id="PLANT-001",
            name="peak",
            rate_per_kwh=0.22,
            demand_charge_per_kw=12.0,
            day_type="weekday",
            start_time_local="14:00",
            end_time_local="20:00",
            timezone="America/Chicago",
            effective_start="2026-01-01",
            effective_end="2026-12-31"
        ),
        Tariff(
            tariff_id="TAR-OFFPEAK",
            plant_id="PLANT-001",
            name="offpeak",
            rate_per_kwh=0.08,
            demand_charge_per_kw=4.0,
            day_type="weekday",
            start_time_local="20:00",
            end_time_local="06:00",
            timezone="America/Chicago",
            effective_start="2026-01-01",
            effective_end="2026-12-31"
        ),
    ]

    # Wednesday (weekday) at 15:30 -> Peak
    dt_peak = datetime(2026, 3, 4, 15, 30)
    matched = resolve_tariff_for_timestamp(dt_peak, mock_tariffs)
    assert matched is not None
    assert matched.name == "peak"
    assert matched.rate_per_kwh == 0.22

    # Wednesday at 22:00 -> Off-peak
    dt_offpeak = datetime(2026, 3, 4, 22, 0)
    matched_off = resolve_tariff_for_timestamp(dt_offpeak, mock_tariffs)
    assert matched_off is not None
    assert matched_off.name == "offpeak"
    assert matched_off.rate_per_kwh == 0.08


if __name__ == "__main__":
    test_calculate_interval_kwh()
    test_resolve_tariff_peak_and_offpeak()
    print("All energy engine tests passed.")
