from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Recommendation
from backend.schemas import RecommendationSchema, RecommendationActionRequest
from backend.analytics.recommendation_engine import (
    generate_and_sync_recommendations, update_recommendation_status
)

router = APIRouter(prefix="/recommendations", tags=["AI Recommendations"])


@router.get("", response_model=List[RecommendationSchema])
def list_recommendations(
    plant_id: str = Query("PLANT-001"),
    category: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Recommendation).filter(Recommendation.plant_id == plant_id)
    if category:
        query = query.filter(Recommendation.category == category)
    if status:
        query = query.filter(Recommendation.status == status)

    recs = query.order_by(Recommendation.expected_savings_usd.desc()).all()
    if not recs:
        recs = generate_and_sync_recommendations(db, plant_id=plant_id)

    return recs


@router.post("/{recommendation_id}/approve", response_model=RecommendationSchema)
def approve_recommendation(
    recommendation_id: str,
    req: RecommendationActionRequest,
    db: Session = Depends(get_db)
):
    rec = update_recommendation_status(
        db,
        rec_id=recommendation_id,
        new_status="approved",
        user_role=req.user_role,
        reason=req.reason or "Approved by plant operator in EnergyIQ"
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation ID not found")
    return rec


@router.post("/{recommendation_id}/reject", response_model=RecommendationSchema)
def reject_recommendation(
    recommendation_id: str,
    req: RecommendationActionRequest,
    db: Session = Depends(get_db)
):
    rec = update_recommendation_status(
        db,
        rec_id=recommendation_id,
        new_status="rejected",
        user_role=req.user_role,
        reason=req.reason or "Rejected by engineering"
    )
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation ID not found")
    return rec

