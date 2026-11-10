from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.database import get_db
from backend.models import EnergyReading
from backend.schemas import EnergyReadingSchema, EnergySummaryResponse
from backend.analytics.energy_engine import calculate_plant_energy_summary, calculate_energy_trends
from backend.analytics.forecasting import forecast_next_24h_demand

router = APIRouter(prefix="/energy", tags=["Energy Analytics"])


@router.get("/forecast")
def get_energy_demand_forecast(
    plant_id: str = Query("PLANT-001"),
    db: Session = Depends(get_db)
):
    """Generates 24-hour predictive power demand forecast with proactive peak shaving alerts."""
    try:
        return forecast_next_24h_demand(db, plant_id=plant_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error computing forecast: {str(e)}")


@router.get("/summary", response_model=EnergySummaryResponse)
def get_energy_summary(
    plant_id: str = Query("PLANT-001"),
    db: Session = Depends(get_db)
):
    try:
        summary = calculate_plant_energy_summary(db, plant_id=plant_id)
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating energy summary: {str(e)}")


@router.get("/trends")
def get_energy_trends(
    plant_id: str = Query("PLANT-001"),
    db: Session = Depends(get_db)
):
    try:
        trends = calculate_energy_trends(db, plant_id=plant_id)
        return trends
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting energy trends: {str(e)}")


@router.get("/readings")
def get_energy_readings(
    plant_id: str = Query("PLANT-001"),
    meter_id: Optional[str] = None,
    machine_id: Optional[str] = None,
    quality_flag: Optional[str] = None,
    is_idle: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    query = db.query(EnergyReading).filter(EnergyReading.plant_id == plant_id)

    if meter_id:
        query = query.filter(EnergyReading.meter_id == meter_id)
    if machine_id:
        query = query.filter(EnergyReading.machine_id == machine_id)
    if quality_flag:
        query = query.filter(EnergyReading.quality_flag == quality_flag)
    if is_idle:
        query = query.filter(EnergyReading.is_idle == is_idle.lower())
    if start_date:
        query = query.filter(EnergyReading.interval_start_ts >= start_date)
    if end_date:
        query = query.filter(EnergyReading.interval_start_ts <= end_date + "T23:59:59")

    total_count = query.count()
    offset = (page - 1) * page_size
    readings = query.order_by(EnergyReading.interval_start_ts.desc()).offset(offset).limit(page_size).all()

    return {
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "pages": (total_count + page_size - 1) // page_size,
        "items": [
            {
                "reading_id": r.reading_id,
                "meter_id": r.meter_id,
                "machine_id": r.machine_id,
                "batch_id": r.batch_id,
                "tariff_id": r.tariff_id,
                "interval_start_ts": r.interval_start_ts,
                "interval_end_ts": r.interval_end_ts,
                "kwh": round(r.kwh, 4),
                "kw_avg": round(r.kw_avg, 2),
                "is_idle": r.is_idle,
                "is_peak_window": r.is_peak_window,
                "quality_flag": r.quality_flag,
                "source": r.source
            }
            for r in readings
        ]
    }

