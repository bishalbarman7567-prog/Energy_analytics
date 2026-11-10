from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.database import get_db
from backend.models import Plant, Meter, Machine, Shift, Tariff, WeatherObservation, ProductionBatch, MaintenanceEvent, EnergyReading
from backend.schemas import (
    PlantSchema, MeterSchema, MachineSchema, ShiftSchema, TariffSchema, WeatherObservationSchema
)

router = APIRouter(tags=["Master Data"])


@router.get("/plants", response_model=List[PlantSchema])
def get_plants(db: Session = Depends(get_db)):
    return db.query(Plant).all()


@router.get("/meters", response_model=List[MeterSchema])
def get_meters(
    plant_id: str = Query("PLANT-001"),
    meter_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Meter).filter(Meter.plant_id == plant_id)
    if meter_type:
        query = query.filter(Meter.meter_type == meter_type)
    return query.all()


@router.get("/machines", response_model=List[MachineSchema])
def get_machines(
    plant_id: str = Query("PLANT-001"),
    meter_id: Optional[str] = None,
    machine_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Machine).filter(Machine.plant_id == plant_id)
    if meter_id:
        query = query.filter(Machine.meter_id == meter_id)
    if machine_type:
        query = query.filter(Machine.machine_type == machine_type)
    return query.all()


@router.get("/machines/{machine_id}/diagnostics")
def get_machine_diagnostics(
    machine_id: str,
    db: Session = Depends(get_db)
):
    """Deep-dive diagnostic telemetry and condition-based health report for a specific machine asset."""
    mach = db.query(Machine).filter(Machine.machine_id == machine_id).first()
    if not mach:
        raise HTTPException(status_code=404, detail="Machine ID not found")

    # Aggregate telemetry for this specific machine
    telemetry_row = db.execute(text("""
        SELECT 
            SUM(kwh) as tot_kwh,
            SUM(CASE WHEN is_idle = 'true' THEN kwh ELSE 0 END) as idle_kwh,
            MAX(kw_avg) as peak_kw,
            AVG(kw_avg) as mean_kw,
            COUNT(*) as reading_count
        FROM EnergyReading
        WHERE machine_id = :mid AND quality_flag = 'ok'
    """), {"mid": machine_id}).fetchone()

    tot_kwh = float(telemetry_row[0] or 0.0)
    idle_kwh = float(telemetry_row[1] or 0.0)
    peak_kw = float(telemetry_row[2] or 0.0)
    mean_kw = float(telemetry_row[3] or 0.0)
    idle_pct = round((idle_kwh / tot_kwh * 100) if tot_kwh > 0 else 0.0, 1)

    # Health & wear scoring (100 is pristine; penalize high idle excess above baseline)
    actual_idle_avg = idle_kwh / (float(telemetry_row[4] or 1) * 0.25) if float(telemetry_row[4] or 0) > 0 else mach.idle_kw_baseline
    idle_overage_pct = max(0.0, ((actual_idle_avg - mach.idle_kw_baseline) / mach.idle_kw_baseline * 100)) if mach.idle_kw_baseline > 0 else 0.0
    health_score = max(45, min(98, round(100.0 - (idle_overage_pct * 0.8))))

    # Recent batches executed on this machine
    batches = db.query(ProductionBatch).filter(ProductionBatch.machine_id == machine_id).order_by(ProductionBatch.actual_start_ts.desc()).limit(10).all()

    # Maintenance history
    maint_events = db.query(MaintenanceEvent).filter(MaintenanceEvent.machine_id == machine_id).order_by(MaintenanceEvent.start_ts.desc()).limit(10).all()

    # Diurnal hourly profile for this machine
    hourly_rows = db.execute(text("""
        SELECT 
            CAST(substr(interval_start_ts, 12, 2) AS INTEGER) as hr,
            AVG(kw_avg) as avg_power
        FROM EnergyReading
        WHERE machine_id = :mid AND quality_flag = 'ok'
        GROUP BY hr
        ORDER BY hr ASC
    """), {"mid": machine_id}).fetchall()
    hourly_profile = [{"hour": f"{int(r[0]):02d}:00", "kw": round(float(r[1]), 2)} for r in hourly_rows]

    return {
        "machine_id": mach.machine_id,
        "machine_name": mach.machine_name,
        "machine_type": mach.machine_type,
        "rated_kw": mach.rated_kw,
        "idle_kw_baseline": mach.idle_kw_baseline,
        "meter_id": mach.meter_id,
        "commission_date": mach.commission_date,
        "status": mach.status,
        "health_score_pct": health_score,
        "health_status": "EXCELLENT" if health_score > 85 else ("FAIR" if health_score > 70 else "NEEDS_SERVICE"),
        "total_energy_kwh": round(tot_kwh, 2),
        "idle_energy_kwh": round(idle_kwh, 2),
        "idle_percentage": idle_pct,
        "peak_power_kw": round(peak_kw, 2),
        "average_power_kw": round(mean_kw, 2),
        "wear_drift_pct": round(idle_overage_pct, 1),
        "hourly_profile": hourly_profile,
        "recent_batches": [
            {
                "batch_id": b.batch_id,
                "output_qty": b.output_qty,
                "scrap_qty": b.scrap_qty,
                "status": b.status,
                "actual_start_ts": b.actual_start_ts
            }
            for b in batches
        ],
        "maintenance_history": [
            {
                "maintenance_id": m.maintenance_id,
                "event_type": m.event_type,
                "start_ts": m.start_ts,
                "description": m.description,
                "impact": m.impact
            }
            for m in maint_events
        ]
    }


@router.get("/shifts", response_model=List[ShiftSchema])
def get_shifts(plant_id: str = Query("PLANT-001"), db: Session = Depends(get_db)):
    return db.query(Shift).filter(Shift.plant_id == plant_id).all()


@router.get("/tariffs", response_model=List[TariffSchema])
def get_tariffs(plant_id: str = Query("PLANT-001"), db: Session = Depends(get_db)):
    return db.query(Tariff).filter(Tariff.plant_id == plant_id).all()


@router.get("/weather", response_model=List[WeatherObservationSchema])
def get_weather(
    plant_id: str = Query("PLANT-001"),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    return db.query(WeatherObservation).filter(WeatherObservation.plant_id == plant_id).order_by(WeatherObservation.timestamp_local.desc()).limit(limit).all()

