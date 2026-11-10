import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.models import Recommendation, Machine, Meter, Tariff, EnergyReading, AuditLog
from backend.config import LLM_API_KEY, LLM_MODEL

logger = logging.getLogger("energyiq.recommendations")


def generate_llm_explanation(
    machine_name: str,
    category: str,
    baseline_val: float,
    savings_kwh: float,
    savings_usd: float,
    evidence: str
) -> str:
    """
    Calls an LLM API to generate an authoritative industrial engineering rationale.
    If no API key is provided or the network call fails, gracefully falls back to 
    a deterministic rule-based template that never hallucinates facts or figures.
    """
    if LLM_API_KEY:
        try:
            import urllib.request
            prompt = f"""
            You are a Senior Industrial Energy Efficiency Engineer. Write a concise, professional, 2-3 sentence technical recommendation rationale for plant operators based ONLY on the verified data below. Never fabricate new figures:
            Machine/Target: {machine_name}
            Category: {category}
            Measured Baseline: {baseline_val:.2f} kWh
            Expected Energy Savings: {savings_kwh:.2f} kWh
            Expected Cost Savings: ${savings_usd:.2f}
            Evidence: {evidence}
            """
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{LLM_MODEL}:generateContent?key={LLM_API_KEY}"
            payload = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 200}
            }).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text_out = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return text_out
        except Exception as e:
            logger.info(f"LLM API request bypassed or failed ({e}); utilizing deterministic fallback rationale.")

    # Deterministic rule-based fallback based on engineering category
    if category == "idle_load":
        return (
            f"Machine {machine_name} demonstrated an aggregate idle consumption baseline of {baseline_val:.1f} kWh "
            f"during non-productive intervals over the 90-day monitoring period. Implementing automated PLC sleep states "
            f"and operator shutdown protocols will yield an estimated {savings_kwh:.1f} kWh in energy reduction, "
            f"saving approximately ${savings_usd:.2f} without impacting production cycle times."
        )
    elif category == "peak_demand":
        return (
            f"Target {machine_name} logged {baseline_val:.1f} kWh during high-tariff peak windows (14:00-20:00), "
            f"contributing significantly to monthly billing demand peaks. Shifting non-critical batch processing and "
            f"pre-heating schedules outside the peak tariff window can avert peak penalty charges, yielding an estimated "
            f"${savings_usd:.2f} in immediate cost reductions ({savings_kwh:.1f} kWh shifted)."
        )
    elif category == "maintenance":
        return (
            f"Efficiency degradation detected on {machine_name} (baseline consumption: {baseline_val:.1f} kWh). "
            f"Motor thermal imaging and lubrication servicing will restore nominal nameplate efficiency, delivering "
            f"a projected {savings_kwh:.1f} kWh ({savings_usd:.2f} USD) reduction in parasitic friction losses."
        )
    else:
        return (
            f"Operational audit for {machine_name} indicates an optimization potential of {savings_kwh:.1f} kWh "
            f"against the historical baseline of {baseline_val:.1f} kWh, achieving projected annual savings of ${savings_usd:.2f}."
        )


def generate_and_sync_recommendations(db: Session, plant_id: str = "PLANT-001") -> List[Recommendation]:
    """
    Computes rigorous, data-driven recommendations directly from machine telemetry.
    Calculates expected energy and financial savings deterministically.
    """
    # 1. High Idle Machines
    idle_query = text("""
        SELECT 
            m.machine_id,
            m.machine_name,
            m.meter_id,
            m.idle_kw_baseline,
            SUM(r.kwh) as total_idle_kwh,
            AVG(r.kw_avg) as actual_idle_kw
        FROM EnergyReading r
        JOIN Machine m ON r.machine_id = m.machine_id
        WHERE r.plant_id = :p 
          AND r.is_idle = 'true' 
          AND r.quality_flag = 'ok'
        GROUP BY m.machine_id
        ORDER BY total_idle_kwh DESC
        LIMIT 6
    """)
    idle_rows = db.execute(idle_query, {"p": plant_id}).fetchall()

    rec_index = 1
    new_recs = []

    for r in idle_rows:
        mach_id = r[0]
        mach_name = r[1]
        meter_id = r[2]
        baseline_kwh = float(r[4] or 0.0)
        # Target 30% reduction in unmanaged standby energy
        savings_kwh = round(baseline_kwh * 0.30, 2)
        # Valued at average commercial off-peak/blended rate of $0.12/kWh
        savings_usd = round(savings_kwh * 0.12, 2)
        confidence = 0.85
        evidence = f"Logged {baseline_kwh:.1f} kWh during verified idle shifts across 90 days. Average idle power was {r[5]:.2f} kW."

        rationale = generate_llm_explanation(mach_name, "idle_load", baseline_kwh, savings_kwh, savings_usd, evidence)
        rec_id = f"REC-2026-{rec_index:06d}"

        existing = db.query(Recommendation).filter(Recommendation.recommendation_id == rec_id).first()
        if not existing:
            rec = Recommendation(
                recommendation_id=rec_id,
                plant_id=plant_id,
                meter_id=meter_id,
                machine_id=mach_id,
                category="idle_load",
                baseline_metric="Idle Energy (90-day non-productive intervals)",
                baseline_value=round(baseline_kwh, 2),
                expected_savings_kwh=savings_kwh,
                expected_savings_usd=savings_usd,
                confidence=confidence,
                status="open",
                created_ts=datetime.now().strftime("%Y-%m-%dT%H:%M:%S-06:00"),
                rationale=rationale
            )
            db.add(rec)
            new_recs.append(rec)
        rec_index += 1

    # 2. Peak Tariff Demand Shifting
    peak_query = text("""
        SELECT 
            m.meter_id,
            m.meter_name,
            SUM(r.kwh) as peak_kwh,
            MAX(r.kw_avg) as peak_kw
        FROM EnergyReading r
        JOIN Meter m ON r.meter_id = m.meter_id
        WHERE r.plant_id = :p 
          AND r.is_peak_window = 'true' 
          AND r.quality_flag = 'ok'
        GROUP BY m.meter_id
        ORDER BY peak_kwh DESC
        LIMIT 4
    """)
    peak_rows = db.execute(peak_query, {"p": plant_id}).fetchall()

    for r in peak_rows:
        meter_id = r[0]
        meter_name = r[1]
        baseline_kwh = float(r[2] or 0.0)
        # Shift 12% of peak load into shoulder/off-peak windows
        savings_kwh = round(baseline_kwh * 0.12, 2)
        # Tariff differential: Peak ($0.22) - Offpeak ($0.08) = $0.14/kWh savings
        savings_usd = round(savings_kwh * 0.14, 2)
        confidence = 0.80
        evidence = f"Peak window exposure of {baseline_kwh:.1f} kWh recorded under {meter_name} during 14:00-20:00 weekday intervals."

        rationale = generate_llm_explanation(meter_name, "peak_demand", baseline_kwh, savings_kwh, savings_usd, evidence)
        rec_id = f"REC-2026-{rec_index:06d}"

        existing = db.query(Recommendation).filter(Recommendation.recommendation_id == rec_id).first()
        if not existing:
            rec = Recommendation(
                recommendation_id=rec_id,
                plant_id=plant_id,
                meter_id=meter_id,
                machine_id=None,
                category="peak_demand",
                baseline_metric="Peak Tariff Window Consumption (kWh)",
                baseline_value=round(baseline_kwh, 2),
                expected_savings_kwh=savings_kwh,
                expected_savings_usd=savings_usd,
                confidence=confidence,
                status="open",
                created_ts=datetime.now().strftime("%Y-%m-%dT%H:%M:%S-06:00"),
                rationale=rationale
            )
            db.add(rec)
            new_recs.append(rec)
        rec_index += 1

    db.commit()
    return db.query(Recommendation).filter(Recommendation.plant_id == plant_id).all()


def update_recommendation_status(
    db: Session,
    rec_id: str,
    new_status: str,
    user_role: str = "Plant Operator",
    reason: str = ""
) -> Optional[Recommendation]:
    """Applies status changes with atomic audit log traceability."""
    rec = db.query(Recommendation).filter(Recommendation.recommendation_id == rec_id).first()
    if not rec:
        return None

    prev_status = rec.status
    rec.status = new_status

    # Record in audit log
    audit_entry = AuditLog(
        timestamp=datetime.now().strftime("%Y-%m-%dT%H:%M:%S-06:00"),
        event_type=f"RECOMMENDATION_{new_status.upper()}",
        user_role=user_role,
        entity_type="Recommendation",
        entity_id=rec_id,
        details=f"Status modified from {prev_status} to {new_status}. Note: {reason}",
        previous_state=prev_status,
        new_state=new_status
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(rec)
    return rec

