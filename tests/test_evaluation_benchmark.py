import json
from pathlib import Path
from backend.database import SessionLocal
from backend.analytics.evaluation import run_full_system_evaluation


def run_acceptance_benchmark():
    db = SessionLocal()
    try:
        report = run_full_system_evaluation(db, "PLANT-001")
        print("=" * 70)
        print("   EnergyIQ Acceptance & Benchmark Evaluation Report")
        print("=" * 70)
        print(f"Overall Status: {report['overall_status']}")
        print(f"Overall Precision: {report['benchmark_summary']['overall_precision'] * 100:.2f}%")
        print(f"Overall Recall:    {report['benchmark_summary']['overall_recall'] * 100:.2f}%")
        print(f"Overall F1-Score:  {report['benchmark_summary']['overall_f1_score'] * 100:.2f}%")
        print("-" * 70)
        print("Scenario Detection Performance:")
        for name, sc in report["scenario_evaluations"].items():
            print(f" - {name:38s}: F1={sc['f1_score']*100:5.1f}% (TP={sc['true_positives']}, FP={sc['false_positives']}, FN={sc['false_negatives']})")
        print("-" * 70)
        print("Structural Integrity & Calculations:")
        for chk, val in report["structural_integrity_checks"].items():
            print(f" - {chk:38s}: {'PASSED' if val['passed'] else 'FAILED'}")
        print("=" * 70)

        # Save to output
        out_path = Path("energy_analytics/output/evaluation_benchmark_report.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        print(f"Saved evaluation report to: {out_path.resolve()}")

        assert report["overall_status"] == "PASS", "Benchmark evaluation must pass all criteria"
        assert report["benchmark_summary"]["overall_f1_score"] >= 0.90, "F1-score must be >= 0.90"
        return report
    finally:
        db.close()


if __name__ == "__main__":
    run_acceptance_benchmark()

