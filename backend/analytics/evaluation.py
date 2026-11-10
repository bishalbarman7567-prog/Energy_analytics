import json
from pathlib import Path
from typing import Dict, Any, List
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import text
from backend.models import (
    Plant, Meter, Machine, Shift, Tariff, WeatherObservation, ProductionBatch, EnergyReading, MaintenanceEvent, Recommendation, MeterDailyTotal
)
from backend.analytics.data_quality import detect_all_data_quality_issues
from backend.config import OUTPUT_DIR


def run_full_system_evaluation(db: Session, plant_id: str = "PLANT-001") -> Dict[str, Any]:
    """
    Automated Industrial AI Hackathon Acceptance & Benchmark Suite:
    - Verifies Primary Key Uniqueness
    - Verifies Foreign Key Integrity across all entity relationships
    - Evaluates Detection Precision, Recall, and F1 against separate ground-truth dataset
    - Evaluates Energy and Savings calculation accuracy
    """
    checks = {}
    errors = []
    metrics = {}

    # 1. Primary Key Uniqueness Check
    pk_targets = [
        ("Plant", Plant, "plant_id"),
        ("Meter", Meter, "meter_id"),
        ("Machine", Machine, "machine_id"),
        ("Shift", Shift, "shift_id"),
        ("Tariff", Tariff, "tariff_id"),
        ("WeatherObservation", WeatherObservation, "weather_id"),
        ("ProductionBatch", ProductionBatch, "batch_id"),
        ("MaintenanceEvent", MaintenanceEvent, "maintenance_id"),
        ("Recommendation", Recommendation, "recommendation_id"),
    ]

    pk_all_unique = True
    for tbl_name, model_cls, pk_field in pk_targets:
        total_count = db.query(model_cls).count()
        distinct_count = db.execute(text(f"SELECT COUNT(DISTINCT {pk_field}) FROM {tbl_name}")).scalar()
        is_unique = (total_count == distinct_count)
        checks[f"{tbl_name}_pk_uniqueness"] = {
            "passed": is_unique,
            "total_records": total_count,
            "distinct_keys": distinct_count
        }
        if not is_unique:
            pk_all_unique = False
            errors.append(f"{tbl_name} contains duplicate primary keys")

    # Energy reading PK check
    er_count = db.query(EnergyReading).count()
    er_distinct = db.execute(text("SELECT COUNT(DISTINCT reading_id) FROM EnergyReading")).scalar()
    checks["EnergyReading_pk_uniqueness"] = {
        "passed": (er_count == er_distinct),
        "total_records": er_count,
        "distinct_keys": er_distinct
    }

    # 2. Foreign Key Integrity Check
    meter_pks = set(r[0] for r in db.execute(text("SELECT meter_id FROM Meter")).fetchall())
    plant_pks = set(r[0] for r in db.execute(text("SELECT plant_id FROM Plant")).fetchall())
    mach_pks = set(r[0] for r in db.execute(text("SELECT machine_id FROM Machine")).fetchall())

    invalid_meter_fk = db.execute(text("SELECT COUNT(*) FROM Machine WHERE meter_id NOT IN (SELECT meter_id FROM Meter)")).scalar()
    invalid_batch_mach_fk = db.execute(text("SELECT COUNT(*) FROM ProductionBatch WHERE machine_id NOT IN (SELECT machine_id FROM Machine)")).scalar()
    invalid_reading_meter_fk = db.execute(text("SELECT COUNT(*) FROM EnergyReading WHERE meter_id NOT IN (SELECT meter_id FROM Meter)")).scalar()

    fk_passed = (invalid_meter_fk == 0 and invalid_batch_mach_fk == 0 and invalid_reading_meter_fk == 0)
    checks["foreign_key_integrity"] = {
        "passed": fk_passed,
        "invalid_machine_meter_fk": invalid_meter_fk,
        "invalid_batch_machine_fk": invalid_batch_mach_fk,
        "invalid_reading_meter_fk": invalid_reading_meter_fk
    }

    # 3. Ground Truth Benchmark Evaluation (Precision, Recall, F1)
    gt_path = OUTPUT_DIR / "ground_truth.json"
    if not gt_path.exists():
        gt_path = Path("energy_analytics/output/ground_truth.json")

    ground_truth = []
    if gt_path.exists():
        try:
            with open(gt_path, "r", encoding="utf-8") as f:
                ground_truth = json.load(f)
        except Exception as e:
            errors.append(f"Could not load ground truth file: {e}")

    # Run detection on raw tables without giving detector access to ground truth labels
    detected_data_quality = detect_all_data_quality_issues(db, plant_id)

    # Map detected issue IDs to compare against ground truth records
    detected_keys_by_scenario = {
        "meter_total_disagrees_with_interval_sums": set(item["record_id"] for item in detected_data_quality["reconciliation_items"]),
        "kw_confused_with_kwh": set(item["record_id"] for item in detected_data_quality["unit_confusion_items"]),
        "tariff_timezone_mismatch": set(item["record_id"] for item in detected_data_quality["timezone_items"]),
        "reading_duplicate": set(item["record_id"] for item in detected_data_quality["duplicate_items"]),
        "machine_outside_meter_hierarchy": set(item["record_id"] for item in detected_data_quality["hierarchy_items"]),
    }

    # Ground truth grouping
    gt_by_issue = defaultdict(set)
    for gt in ground_truth:
        itype = gt.get("issue_type")
        rid = gt.get("record_id")
        if itype and rid:
            gt_by_issue[itype].add(rid)

    scenario_metrics = {}
    total_tp = 0
    total_fp = 0
    total_fn = 0

    evaluated_scenarios = [
        ("Meter Reconciliation Discrepancy", "meter_total_disagrees_with_interval_sums"),
        ("kW vs kWh Unit Inconsistency", "kw_confused_with_kwh"),
        ("Tariff Timezone Misalignment", "tariff_timezone_mismatch"),
        ("Duplicate Reading Ingestion", "reading_duplicate"),
        ("Invalid Machine-Meter Hierarchy", "machine_outside_meter_hierarchy"),
    ]

    for label, itype in evaluated_scenarios:
        gt_set = gt_by_issue.get(itype, set())
        pred_set = detected_keys_by_scenario.get(itype, set())

        tp = len(gt_set.intersection(pred_set))
        fp = len(pred_set - gt_set)
        fn = len(gt_set - pred_set)

        precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 1.0
        recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 1.0
        f1 = round(2 * (precision * recall) / (precision + recall), 4) if (precision + recall) > 0 else 0.0

        total_tp += tp
        total_fp += fp
        total_fn += fn

        scenario_metrics[label] = {
            "ground_truth_count": len(gt_set),
            "detected_count": len(pred_set),
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "passed": (f1 >= 0.90)
        }

    overall_precision = round(total_tp / (total_tp + total_fp), 4) if (total_tp + total_fp) > 0 else 1.0
    overall_recall = round(total_tp / (total_tp + total_fn), 4) if (total_tp + total_fn) > 0 else 1.0
    overall_f1 = round(2 * (overall_precision * overall_recall) / (overall_precision + overall_recall), 4) if (overall_precision + overall_recall) > 0 else 0.0

    # 4. Energy and Savings Math Verification
    savings_verified = True
    recs = db.query(Recommendation).filter(Recommendation.plant_id == plant_id).all()
    for rec in recs:
        # Expected cost savings should be approximately kWh savings * tariff
        if rec.expected_savings_kwh > 0:
            implied_rate = rec.expected_savings_usd / rec.expected_savings_kwh
            if implied_rate < 0.05 or implied_rate > 0.35:
                savings_verified = False

    checks["savings_calculation_accuracy"] = {
        "passed": savings_verified,
        "recommendations_audited": len(recs),
        "rule": "0.05 <= (expected_savings_usd / expected_savings_kwh) <= 0.35"
    }

    # Final verdict
    overall_passed = (
        pk_all_unique and 
        fk_passed and 
        overall_f1 >= 0.90 and 
        savings_verified
    )

    return {
        "overall_status": "PASS" if overall_passed else "FAIL",
        "benchmark_summary": {
            "overall_precision": overall_precision,
            "overall_recall": overall_recall,
            "overall_f1_score": overall_f1,
            "total_ground_truth_cases": len(ground_truth),
            "true_positives": total_tp,
            "false_positives": total_fp,
            "false_negatives": total_fn
        },
        "scenario_evaluations": scenario_metrics,
        "structural_integrity_checks": checks,
        "errors": errors
    }

