from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import AnomalyRecord, AuditLog
from backend.schemas import AnomalySchema, AnomalyAcknowledgeRequest
from backend.analytics.anomaly_detector import get_stored_anomalies, run_hybrid_anomaly_detection

router = APIRouter(prefix="/anomalies", tags=["Anomaly Detection"])


@router.get("", response_model=List[AnomalySchema])
def list_anomalies(
    plant_id: str = Query("PLANT-001"),
    severity: Optional[str] = None,
    anomaly_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    query = db.query(AnomalyRecord).filter(AnomalyRecord.plant_id == plant_id)
    if severity:
        query = query.filter(AnomalyRecord.severity == severity.upper())
    if anomaly_type:
        query = query.filter(AnomalyRecord.anomaly_type == anomaly_type)
    if status:
        query = query.filter(AnomalyRecord.status == status.upper())

    results = query.order_by(AnomalyRecord.timestamp.desc()).limit(limit).all()
    if not results and not severity and not anomaly_type:
        # Auto-run if empty
        run_hybrid_anomaly_detection(db, plant_id=plant_id)
        results = query.order_by(AnomalyRecord.timestamp.desc()).limit(limit).all()

    return results


@router.post("/{anomaly_id}/acknowledge", response_model=AnomalySchema)
def acknowledge_anomaly(
    anomaly_id: str,
    req: AnomalyAcknowledgeRequest,
    db: Session = Depends(get_db)
):
    anom = db.query(AnomalyRecord).filter(AnomalyRecord.anomaly_id == anomaly_id).first()
    if not anom:
        raise HTTPException(status_code=404, detail="Anomaly record not found")

    prev = anom.status
    anom.status = "ACKNOWLEDGED"
    anom.acknowledged_by = req.user_role
    anom.acknowledged_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S-06:00")

    audit = AuditLog(
        timestamp=anom.acknowledged_at,
        event_type="ANOMALY_ACKNOWLEDGED",
        user_role=req.user_role,
        entity_type="AnomalyRecord",
        entity_id=anomaly_id,
        details=f"Anomaly acknowledged by {req.user_role}. Notes: {req.notes}",
        previous_state=prev,
        new_state="ACKNOWLEDGED"
    )
    db.add(audit)
    db.commit()
    db.refresh(anom)
    return anom


@router.post("/{anomaly_id}/resolve", response_model=AnomalySchema)
def resolve_anomaly(
    anomaly_id: str,
    req: AnomalyAcknowledgeRequest,
    db: Session = Depends(get_db)
):
    anom = db.query(AnomalyRecord).filter(AnomalyRecord.anomaly_id == anomaly_id).first()
    if not anom:
        raise HTTPException(status_code=404, detail="Anomaly record not found")

    prev = anom.status
    anom.status = "RESOLVED"

    audit = AuditLog(
        timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%S-06:00"),
        event_type="ANOMALY_RESOLVED",
        user_role=req.user_role,
        entity_type="AnomalyRecord",
        entity_id=anomaly_id,
        details=f"Anomaly marked resolved by {req.user_role}. Action taken: {req.notes}",
        previous_state=prev,
        new_state="RESOLVED"
    )
    db.add(audit)
    db.commit()
    db.refresh(anom)
    return anom

