from backend.database import SessionLocal
from backend.analytics.data_quality import detect_all_data_quality_issues


def test_data_quality_five_scenarios():
    db = SessionLocal()
    try:
        dq = detect_all_data_quality_issues(db, "PLANT-001")

        # Scenario A: Meter Reconciliation Mismatch
        assert dq["reconciliation_mismatches_count"] > 0, "Scenario A discrepancies must be detected"

        # Scenario B: kW vs kWh Unit Confusion
        assert dq["unit_confusions_count"] > 0, "Scenario B unit inconsistencies must be detected"

        # Scenario C: Tariff Timezone Mismatch
        assert dq["timezone_mismatches_count"] > 0, "Scenario C timezone mismatches must be detected"

        # Scenario D: Duplicate Readings
        assert dq["duplicates_count"] > 0, "Scenario D duplicate readings must be detected"

        # Scenario E: Machine-Meter Hierarchy Mismatch
        assert dq["hierarchy_mismatches_count"] > 0, "Scenario E hierarchy mismatches must be detected"

        print("Data Quality Verification Passed:")
        print(f" - Reconciliation Discrepancies (A): {dq['reconciliation_mismatches_count']}")
        print(f" - Unit Confusions (B): {dq['unit_confusions_count']}")
        print(f" - Timezone Mismatches (C): {dq['timezone_mismatches_count']}")
        print(f" - Duplicate Ingestions (D): {dq['duplicates_count']}")
        print(f" - Hierarchy Mismatches (E): {dq['hierarchy_mismatches_count']}")
    finally:
        db.close()


if __name__ == "__main__":
    test_data_quality_five_scenarios()

