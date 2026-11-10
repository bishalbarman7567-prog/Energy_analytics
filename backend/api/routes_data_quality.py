from fastapi import APIRouter, Depends, Query, Body
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.schemas import DataQualitySummaryResponse
from backend.analytics.data_quality import detect_all_data_quality_issues, remediate_data_quality_issues

router = APIRouter(prefix="/data-quality", tags=["Data Quality & Integrity"])


@router.get("", response_model=DataQualitySummaryResponse)
def get_data_quality_report(
    plant_id: str = Query("PLANT-001"),
    db: Session = Depends(get_db)
):
    """
    Executes automated rule-based checks for the 5 industrial anomaly/exception scenarios:
    A. Meter reconciliation mismatch
    B. kW and kWh unit confusion
    C. Tariff timezone mismatch
    D. Duplicate energy readings
    E. Invalid meter-machine assignment
    """
    return detect_all_data_quality_issues(db, plant_id=plant_id)


@router.post("/remediate")
def execute_remediation(
    plant_id: str = Query("PLANT-001"),
    user_role: str = Query("OT/IT Administrator"),
    db: Session = Depends(get_db)
):
    """
    Executes automated industrial self-healing remediation:
    - Normalizes kW to kWh unit confusion (-300% billing error eliminated)
    - Isolates duplicate readings into quarantine ledger
    - Re-aligns machine electrical submeter hierarchy
    - Aligns reconciliation daily totals
    """
    return remediate_data_quality_issues(db, plant_id=plant_id, user_role=user_role)


