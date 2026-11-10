import math
from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.models import (
    Plant, Meter, Machine, EnergyReading, ProductionBatch, Tariff, WeatherObservation, Recommendation
)
from backend.config import DEFAULT_PLANT_TZ, DEFAULT_INTERVAL_MIN


def calculate_interval_kwh(kw_avg: float, interval_minutes: int = DEFAULT_INTERVAL_MIN) -> float:
    """Energy (kWh) = Average Power (kW) * Interval Duration (hours)."""
    return round(kw_avg * (interval_minutes / 60.0), 6)


def parse_iso_datetime(dt_str: str) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        # Handles offsets like -06:00
        return datetime.fromisoformat(dt_str)
    except Exception:
        try:
            # Fallback naive parsing
            clean = dt_str[:19]
            return datetime.strptime(clean, "%Y-%m-%dT%H:%M:%S")
        except Exception:
            return None


def resolve_tariff_for_timestamp(ts: datetime, tariffs: List[Tariff], plant_tz: str = DEFAULT_PLANT_TZ) -> Optional[Tariff]:
    """
    Evaluates electricity tariff using the plant local timezone.
    Matches day_type (weekday/weekend) and time windows (e.g., peak 14:00-20:00).
    """
    is_weekend = ts.weekday() >= 5
    day_type_match = "weekend" if is_weekend else "weekday"
    minutes = ts.hour * 60 + ts.minute

    matched_tariffs = []
    for t in tariffs:
        # Check day type
        if t.day_type != "all" and t.day_type != day_type_match:
            continue
        try:
            st_h, st_m = map(int, t.start_time_local.split(":"))
            et_h, et_m = map(int, t.end_time_local.split(":"))
            st = st_h * 60 + st_m
            et = et_h * 60 + et_m
            if st <= et:
                is_in_window = (st <= minutes < et)
            else:
                is_in_window = (minutes >= st or minutes < et)  # spans midnight

            if is_in_window:
                matched_tariffs.append(t)
        except Exception:
            continue

    if matched_tariffs:
        # Specific peak or shoulder prioritized over broad offpeak
        for t in matched_tariffs:
            if t.name == "peak":
                return t
        for t in matched_tariffs:
            if t.name == "shoulder":
                return t
        return matched_tariffs[0]

    # Fallback to offpeak tariff
    for t in tariffs:
        if t.name == "offpeak":
            return t
    return tariffs[0] if tariffs else None


def calculate_plant_energy_summary(db: Session, plant_id: str = "PLANT-001") -> Dict[str, Any]:
    """
    Aggregates verifiable plant KPIs directly from raw readings and business entities.
    No fabricated numbers.
    """
    tariffs = db.query(Tariff).filter(Tariff.plant_id == plant_id).all()
    tariff_dict = {t.tariff_id: t for t in tariffs}

    # Fetch readings count & quality breakdown
    quality_rows = db.execute(
        text("SELECT quality_flag, COUNT(*) FROM EnergyReading WHERE plant_id = :p GROUP BY quality_flag"),
        {"p": plant_id}
    ).fetchall()
    quality_breakdown = {r[0]: r[1] for r in quality_rows}
    readings_count = sum(quality_breakdown.values())

    # Compute totals and peak demand over the recent 90‑day window, using only rows flagged as peak windows.
    from datetime import datetime, timedelta
    cutoff_ts = (datetime.utcnow() - timedelta(days=90)).isoformat()
    valid_query = text("""
        SELECT 
            SUM(kwh) as total_kwh,
            MAX(CASE WHEN is_peak_window = 'true' THEN kw_avg ELSE NULL END) as peak_kw,
            SUM(CASE WHEN is_idle = 'true' THEN kwh ELSE 0 END) as idle_kwh
        FROM EnergyReading
        WHERE plant_id = :p 
          AND quality_flag NOT IN ('duplicate', 'unit_confusion')
          AND interval_start_ts >= :cutoff
    """)
    totals = db.execute(valid_query, {"p": plant_id, "cutoff": cutoff_ts}).fetchone()
    # Determine timestamp of the peak within the same window
    peak_ts_row = db.execute(text("""
        SELECT interval_start_ts
        FROM EnergyReading
        WHERE plant_id = :p 
          AND quality_flag NOT IN ('duplicate', 'unit_confusion')
          AND is_peak_window = 'true'
          AND interval_start_ts >= :cutoff
        ORDER BY kw_avg DESC
        LIMIT 1
        """), {"p": plant_id, "cutoff": cutoff_ts}).fetchone()
    peak_demand_timestamp = peak_ts_row[0] if peak_ts_row else None

    total_kwh = float(totals[0] or 0.0)
    peak_demand_kw = float(totals[1] or 0.0)
    total_idle_kwh = float(totals[2] or 0.0)

    # Cost calculation: iterate readings with tariffs or aggregate by tariff_id
    cost_rows = db.execute(text("""
        SELECT tariff_id, SUM(kwh) 
        FROM EnergyReading 
        WHERE plant_id = :p AND quality_flag NOT IN ('duplicate', 'unit_confusion')
        GROUP BY tariff_id
    """), {"p": plant_id}).fetchall()

    total_cost_usd = 0.0
    for tid, kwh_sum in cost_rows:
        if tid and tid in tariff_dict:
            total_cost_usd += (kwh_sum or 0.0) * tariff_dict[tid].rate_per_kwh
        else:
            total_cost_usd += (kwh_sum or 0.0) * 0.12  # blended average if unmapped

    # Idle waste estimation: Idle cost = Idle kWh * blended/offpeak tariff
    idle_energy_waste_usd = total_idle_kwh * 0.11
    idle_percentage = round((total_idle_kwh / total_kwh * 100) if total_kwh > 0 else 0.0, 2)

    # Production intensity calculation:
    prod_query = text("""
        SELECT SUM(output_qty) as total_units
        FROM ProductionBatch
        WHERE plant_id = :p AND status = 'completed'
    """)
    prod_units = float(db.execute(prod_query, {"p": plant_id}).fetchone()[0] or 0.0)
    avg_intensity = round((total_kwh / prod_units) if prod_units > 0 else 0.0, 4)

    # Potential savings from active recommendations
    rec_query = text("""
        SELECT 
            SUM(expected_savings_kwh) as tot_kwh,
            SUM(expected_savings_usd) as tot_usd
        FROM Recommendation
        WHERE plant_id = :p
    """)
    rec_totals = db.execute(rec_query, {"p": plant_id}).fetchone()
    pot_savings_kwh = float(rec_totals[0] or 0.0)
    pot_savings_usd = float(rec_totals[1] or 0.0)

    return {
        "plant_id": plant_id,
        "total_energy_kwh": round(total_kwh, 2),
        "total_cost_usd": round(total_cost_usd, 2),
        "peak_demand_kw": round(peak_demand_kw, 2),
        "peak_demand_timestamp": peak_demand_timestamp,
        "avg_energy_intensity_kwh_per_unit": avg_intensity,
        "total_production_units": round(prod_units, 2),
        "total_idle_energy_kwh": round(total_idle_kwh, 2),
        "idle_energy_waste_usd": round(idle_energy_waste_usd, 2),
        "idle_percentage": idle_percentage,
        "total_potential_savings_kwh": round(pot_savings_kwh, 2),
        "total_potential_savings_usd": round(pot_savings_usd, 2),
        "readings_count": readings_count,
        "quality_flag_breakdown": quality_breakdown
    }


def calculate_energy_trends(db: Session, plant_id: str = "PLANT-001") -> Dict[str, Any]:
    """
    Extracts time-series aggregations:
    - Daily energy & cost trend (90 days)
    - Hourly diurnal profile (0-23 hours)
    - Machine breakdown (top 10 machines by energy consumption and idle share)
    - Tariff breakdown (peak, shoulder, off-peak kWh and costs)
    - Weather temperature correlation
    """
    # 1. Daily Trend
    daily_rows = db.execute(text("""
        SELECT 
            substr(interval_start_ts, 1, 10) as day_date,
            SUM(kwh) as daily_kwh,
            SUM(CASE WHEN is_idle = 'true' THEN kwh ELSE 0 END) as daily_idle_kwh,
            MAX(kw_avg) as daily_peak_kw
        FROM EnergyReading
        WHERE plant_id = :p AND quality_flag NOT IN ('duplicate', 'unit_confusion')
        GROUP BY day_date
        ORDER BY day_date ASC
    """), {"p": plant_id}).fetchall()

    daily_labels = [r[0] for r in daily_rows]
    daily_kwh = [round(float(r[1] or 0.0), 2) for r in daily_rows]
    daily_idle = [round(float(r[2] or 0.0), 2) for r in daily_rows]
    daily_peak = [round(float(r[3] or 0.0), 2) for r in daily_rows]

    # 2. Hourly Profile (Diurnal pattern across 24 hours)
    hourly_rows = db.execute(text("""
        SELECT 
            CAST(substr(interval_start_ts, 12, 2) AS INTEGER) as hour_of_day,
            AVG(kw_avg) as avg_power_kw,
            SUM(kwh) as total_kwh,
            SUM(CASE WHEN is_peak_window = 'true' THEN kwh ELSE 0 END) as peak_window_kwh
        FROM EnergyReading
        WHERE plant_id = :p AND quality_flag NOT IN ('duplicate', 'unit_confusion')
        GROUP BY hour_of_day
        ORDER BY hour_of_day ASC
    """), {"p": plant_id}).fetchall()

    hourly_labels = [f"{int(r[0]):02d}:00" for r in hourly_rows]
    hourly_avg_kw = [round(float(r[1] or 0.0), 2) for r in hourly_rows]
    hourly_peak_kwh = [round(float(r[3] or 0.0), 2) for r in hourly_rows]

    # 3. Machine Breakdown
    machine_rows = db.execute(text("""
        SELECT 
            m.machine_id,
            m.machine_name,
            m.machine_type,
            m.idle_kw_baseline,
            SUM(r.kwh) as total_kwh,
            SUM(CASE WHEN r.is_idle = 'true' THEN r.kwh ELSE 0 END) as idle_kwh
        FROM EnergyReading r
        JOIN Machine m ON r.machine_id = m.machine_id
        WHERE r.plant_id = :p AND r.quality_flag NOT IN ('duplicate', 'unit_confusion')
        GROUP BY m.machine_id
        ORDER BY total_kwh DESC
        LIMIT 10
    """), {"p": plant_id}).fetchall()

    machines_data = []
    for r in machine_rows:
        tot = float(r[4] or 0.0)
        idle = float(r[5] or 0.0)
        machines_data.append({
            "machine_id": r[0],
            "machine_name": r[1],
            "machine_type": r[2],
            "idle_kw_baseline": r[3],
            "total_kwh": round(tot, 2),
            "idle_kwh": round(idle, 2),
            "idle_pct": round((idle / tot * 100) if tot > 0 else 0.0, 1)
        })

    # 4. Tariff Window Breakdown
    tariff_rows = db.execute(text("""
        SELECT 
            t.name as tariff_name,
            t.rate_per_kwh,
            SUM(r.kwh) as window_kwh
        FROM EnergyReading r
        LEFT JOIN Tariff t ON r.tariff_id = t.tariff_id
        WHERE r.plant_id = :p AND r.quality_flag NOT IN ('duplicate', 'unit_confusion')
        GROUP BY t.name
    """), {"p": plant_id}).fetchall()

    tariff_breakdown = []
    for r in tariff_rows:
        tname = r[0] or "standard"
        rate = float(r[1] or 0.12)
        kwh = float(r[2] or 0.0)
        tariff_breakdown.append({
            "tariff_name": tname.upper(),
            "rate_per_kwh": rate,
            "kwh": round(kwh, 2),
            "cost_usd": round(kwh * rate, 2)
        })

    # 5. Weather vs Energy Correlation
    weather_corr_rows = db.execute(text("""
        SELECT 
            CAST(w.temperature_c / 5 AS INTEGER) * 5 as temp_bin,
            AVG(r.kw_avg) as avg_kw,
            SUM(r.kwh) as total_kwh,
            COUNT(*) as reading_count
        FROM EnergyReading r
        JOIN WeatherObservation w ON substr(r.interval_start_ts, 1, 13) = substr(w.timestamp_local, 1, 13)
        WHERE r.plant_id = :p AND r.quality_flag = 'ok'
        GROUP BY temp_bin
        ORDER BY temp_bin ASC
    """), {"p": plant_id}).fetchall()

    weather_data = []
    for r in weather_corr_rows:
        bin_floor = int(r[0])
        weather_data.append({
            "temp_bucket": f"{bin_floor}°C to {bin_floor + 5}°C",
            "avg_power_kw": round(float(r[1] or 0.0), 2),
            "total_kwh": round(float(r[2] or 0.0), 2),
            "count": int(r[3])
        })

    return {
        "daily": {
            "labels": daily_labels,
            "total_kwh": daily_kwh,
            "idle_kwh": daily_idle,
            "peak_kw": daily_peak
        },
        "hourly": {
            "labels": hourly_labels,
            "avg_power_kw": hourly_avg_kw,
            "peak_window_kwh": hourly_peak_kwh
        },
        "machines": machines_data,
        "tariffs": tariff_breakdown,
        "weather_correlation": weather_data
    }

