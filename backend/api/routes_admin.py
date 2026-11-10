import csv
import json
import io
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.database import get_db
from backend.models import AuditLog
from backend.schemas import AuditLogSchema
from backend.analytics.evaluation import run_full_system_evaluation
from backend.analytics.anomaly_detector import run_hybrid_anomaly_detection
from backend.analytics.recommendation_engine import generate_and_sync_recommendations
from backend.analytics.copilot import ask_energy_copilot
from backend.config import RAW_DATA_DIR, OUTPUT_DIR

router = APIRouter(tags=["Admin, Traceability & Evaluation"])


@router.post("/copilot/query")
def query_copilot(
    query: str = Query(..., description="Operator question in natural language"),
    plant_id: str = Query("PLANT-001"),
    db: Session = Depends(get_db)
):
    """Interactive Plant Energy AI Copilot natural language assistant."""
    return ask_energy_copilot(query, db, plant_id=plant_id)


@router.post("/analytics/run")
def trigger_analytics_engine(
    plant_id: str = Query("PLANT-001"),
    db: Session = Depends(get_db)
):
    """Executes full analytics pipeline: hybrid anomaly detection and recommendation optimization."""
    anomalies = run_hybrid_anomaly_detection(db, plant_id=plant_id)
    recs = generate_and_sync_recommendations(db, plant_id=plant_id)

    # Log execution in AuditLog
    audit = AuditLog(
        event_type="ANALYTICS_PIPELINE_RUN",
        user_role="OT/IT Administrator",
        entity_type="System",
        entity_id=plant_id,
        details=f"Analytics cycle executed: {len(anomalies)} anomalies identified, {len(recs)} recommendations generated."
    )
    db.add(audit)
    db.commit()

    return {
        "status": "SUCCESS",
        "message": "Analytics engine executed successfully.",
        "anomalies_detected": len(anomalies),
        "recommendations_synchronized": len(recs)
    }


@router.get("/analytics/evaluation")
def get_system_evaluation(
    plant_id: str = Query("PLANT-001"),
    db: Session = Depends(get_db)
):
    """
    Automated benchmark evaluation suite:
    Evaluates PK uniqueness, FK integrity, ground-truth anomaly detection precision/recall/F1, and savings accuracy.
    """
    report = run_full_system_evaluation(db, plant_id=plant_id)
    return report


@router.get("/audit-logs", response_model=List[AuditLogSchema])
def get_audit_logs(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Preserves full historical event traceability and decision history."""
    return db.query(AuditLog).order_by(AuditLog.log_id.desc()).limit(limit).all()


@router.post("/data/generate")
def regenerate_synthetic_data(
    seed: int = Query(20261022),
    meters: int = Query(20),
    days: int = Query(90),
    batches: int = Query(2000),
    db: Session = Depends(get_db)
):
    """
    Triggers the reproducible deterministic synthetic data generator.
    """
    try:
        from generator import Generator
        gen = Generator(out_dir=RAW_DATA_DIR, seed=seed, meters=meters, days=days, batches=batches)
        gen.run()

        audit = AuditLog(
            event_type="DATA_GENERATOR_RUN",
            user_role="OT/IT Administrator",
            entity_type="Plant",
            entity_id="PLANT-001",
            details=f"Synthetic data generation triggered (seed={seed}, meters={meters}, days={days}, batches={batches})."
        )
        db.add(audit)
        db.commit()

        return {
            "status": "SUCCESS",
            "message": "Synthetic dataset successfully regenerated and database updated.",
            "seed": seed,
            "meters": meters,
            "days": days
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Data generation failed: {str(e)}")


@router.get("/export/{entity}/csv")
def export_entity_csv(entity: str, db: Session = Depends(get_db)):
    """Exports any core table as a streaming CSV download."""
    allowed_entities = [
        "Plant", "Meter", "Machine", "Shift", "Tariff",
        "WeatherObservation", "ProductionBatch", "EnergyReading",
        "MaintenanceEvent", "Recommendation", "MeterDailyTotal", "AuditLog"
    ]
    if entity not in allowed_entities:
        raise HTTPException(status_code=400, detail=f"Entity '{entity}' not allowed. Must be one of: {', '.join(allowed_entities)}")

    query = f"SELECT * FROM {entity}"
    if entity == "EnergyReading":
        query += " LIMIT 50000"  # Protect against memory overflow on single CSV export

    rows = db.execute(text(query)).fetchall()
    if not rows:
        return Response(content="", media_type="text/csv")

    output = io.StringIO()
    writer = csv.writer(output)
    # Get column names
    col_names = db.execute(text(f"PRAGMA table_info({entity})")).fetchall()
    writer.writerow([c[1] for c in col_names])
    for r in rows:
        writer.writerow(list(r))

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=EnergyIQ_{entity}.csv"}
    )


@router.get("/export/{entity}/json")
def export_entity_json(entity: str, db: Session = Depends(get_db)):
    """Exports any core table as JSON."""
    allowed_entities = [
        "Plant", "Meter", "Machine", "Shift", "Tariff",
        "WeatherObservation", "ProductionBatch", "EnergyReading",
        "MaintenanceEvent", "Recommendation", "MeterDailyTotal"
    ]
    if entity not in allowed_entities:
        raise HTTPException(status_code=400, detail=f"Entity '{entity}' not allowed.")

    col_names = [c[1] for c in db.execute(text(f"PRAGMA table_info({entity})")).fetchall()]
    query = f"SELECT * FROM {entity}"
    if entity == "EnergyReading":
        query += " LIMIT 10000"

    rows = db.execute(text(query)).fetchall()
    data = [dict(zip(col_names, list(r))) for r in rows]

    return Response(
        content=json.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=EnergyIQ_{entity}.json"}
    )

