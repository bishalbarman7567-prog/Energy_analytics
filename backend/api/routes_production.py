from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.database import get_db
from backend.models import ProductionBatch, Machine
from backend.schemas import ProductionBatchSchema

router = APIRouter(prefix="/production", tags=["Production & Intensity"])


@router.get("/batches")
def get_production_batches(
    plant_id: str = Query("PLANT-001"),
    machine_id: Optional[str] = None,
    shift_id: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    query = db.query(ProductionBatch).filter(ProductionBatch.plant_id == plant_id)
    if machine_id:
        query = query.filter(ProductionBatch.machine_id == machine_id)
    if shift_id:
        query = query.filter(ProductionBatch.shift_id == shift_id)
    if status:
        query = query.filter(ProductionBatch.status == status)

    total_count = query.count()
    offset = (page - 1) * page_size
    batches = query.order_by(ProductionBatch.actual_start_ts.desc()).offset(offset).limit(page_size).all()

    return {
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "batch_id": b.batch_id,
                "plant_id": b.plant_id,
                "machine_id": b.machine_id,
                "shift_id": b.shift_id,
                "actual_start_ts": b.actual_start_ts,
                "actual_end_ts": b.actual_end_ts,
                "output_qty": round(b.output_qty, 2),
                "scrap_qty": round(b.scrap_qty, 2),
                "scrap_rate_pct": round((b.scrap_qty / b.output_qty * 100) if b.output_qty > 0 else 0.0, 2),
                "status": b.status
            }
            for b in batches
        ]
    }


@router.get("/intensity")
def get_energy_intensity_by_machine(
    plant_id: str = Query("PLANT-001"),
    db: Session = Depends(get_db)
):
    """
    Computes rigorous energy intensity per production unit (kWh/unit)
    correlated between ProductionBatch output and attributed EnergyReading intervals.
    """
    intensity_query = text("""
        SELECT 
            m.machine_id,
            m.machine_name,
            m.machine_type,
            m.rated_kw,
            COUNT(DISTINCT b.batch_id) as batch_count,
            SUM(b.output_qty) as total_output_units,
            SUM(b.scrap_qty) as total_scrap_units,
            (SELECT SUM(r.kwh) 
             FROM EnergyReading r 
             WHERE r.machine_id = m.machine_id 
               AND r.quality_flag = 'ok'
               AND r.batch_id IS NOT NULL AND r.batch_id != '') as productive_kwh
        FROM Machine m
        JOIN ProductionBatch b ON m.machine_id = b.machine_id
        WHERE m.plant_id = :p AND b.status = 'completed'
        GROUP BY m.machine_id
        ORDER BY productive_kwh DESC
    """)
    rows = db.execute(intensity_query, {"p": plant_id}).fetchall()

    results = []
    for r in rows:
        output_units = float(r[5] or 0.0)
        prod_kwh = float(r[7] or 0.0)
        scrap_units = float(r[6] or 0.0)

        kwh_per_unit = round(prod_kwh / output_units, 4) if output_units > 0 else 0.0
        scrap_pct = round((scrap_units / output_units * 100) if output_units > 0 else 0.0, 2)

        results.append({
            "machine_id": r[0],
            "machine_name": r[1],
            "machine_type": r[2],
            "rated_kw": r[3],
            "completed_batches": r[4],
            "total_output_units": round(output_units, 1),
            "productive_kwh": round(prod_kwh, 2),
            "energy_intensity_kwh_per_unit": kwh_per_unit,
            "scrap_percentage": scrap_pct
        })

    # Sort from highest intensity (most energy intensive per unit) to lowest
    results.sort(key=lambda x: x["energy_intensity_kwh_per_unit"], reverse=True)
    return results

