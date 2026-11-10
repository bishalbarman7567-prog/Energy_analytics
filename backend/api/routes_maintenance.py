from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import MaintenanceEvent, AuditLog
from backend.schemas import MaintenanceEventSchema, MaintenanceEventCreate

router = APIRouter(prefix="/maintenance", tags=["Maintenance Events"])


@router.get("/events", response_model=List[MaintenanceEventSchema])
def list_maintenance_events(
    plant_id: str = Query("PLANT-001"),
    machine_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    query = db.query(MaintenanceEvent).filter(MaintenanceEvent.plant_id == plant_id)
    if machine_id:
        query = query.filter(MaintenanceEvent.machine_id == machine_id)
    if event_type:
        query = query.filter(MaintenanceEvent.event_type == event_type)
    return query.order_by(MaintenanceEvent.start_ts.desc()).limit(limit).all()


@router.post("/events", response_model=MaintenanceEventSchema)
def create_maintenance_event(
    ev: MaintenanceEventCreate,
    user_role: str = Query("Maintenance/Quality Engineer"),
    db: Session = Depends(get_db)
):
    count = db.query(MaintenanceEvent).filter(MaintenanceEvent.machine_id == ev.machine_id).count()
    maint_id = f"MNT-{ev.machine_id}-{count + 1:03d}"

    record = MaintenanceEvent(
        maintenance_id=maint_id,
        plant_id=ev.plant_id,
        machine_id=ev.machine_id,
        event_type=ev.event_type,
        start_ts=ev.start_ts,
        end_ts=ev.end_ts,
        description=ev.description,
        impact=ev.impact
    )
    db.add(record)

    # Traceability Audit Log
    audit = AuditLog(
        timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%S-06:00"),
        event_type="MAINTENANCE_EVENT_LOGGED",
        user_role=user_role,
        entity_type="MaintenanceEvent",
        entity_id=maint_id,
        details=f"Maintenance logged for {ev.machine_id}: {ev.event_type} - {ev.description}",
        previous_state=None,
        new_state="RECORDED"
    )
    db.add(audit)
    db.commit()
    db.refresh(record)
    return record

