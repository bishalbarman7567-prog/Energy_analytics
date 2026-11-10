from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_healthcheck():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "HEALTHY"


def test_energy_summary_endpoint():
    resp = client.get("/api/energy/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_energy_kwh" in data
    assert data["total_energy_kwh"] > 0
    assert "total_cost_usd" in data
    assert "peak_demand_kw" in data


def test_anomalies_and_acknowledgement():
    resp = client.get("/api/anomalies?limit=10")
    assert resp.status_code == 200
    anomalies = resp.json()
    assert len(anomalies) > 0

    first_id = anomalies[0]["anomaly_id"]
    ack_resp = client.post(
        f"/api/anomalies/{first_id}/acknowledge",
        json={"user_role": "Plant Operator", "notes": "Automated test acknowledgement"}
    )
    assert ack_resp.status_code == 200
    assert ack_resp.json()["status"] == "ACKNOWLEDGED"


def test_recommendations_and_approval():
    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    recs = resp.json()
    assert len(recs) > 0

    first_id = recs[0]["recommendation_id"]
    approve_resp = client.post(
        f"/api/recommendations/{first_id}/approve",
        json={"user_role": "Plant Operator", "reason": "Automated test approval"}
    )
    assert approve_resp.status_code == 200
    assert approve_resp.json()["status"] == "approved"


def test_maintenance_event_creation():
    payload = {
        "plant_id": "PLANT-001",
        "machine_id": "MCH-PLANT-001-001",
        "event_type": "preventive",
        "start_ts": "2026-03-31T08:00:00-06:00",
        "end_ts": "2026-03-31T12:00:00-06:00",
        "description": "Routine motor bearing lubrication test",
        "impact": "none"
    }
    resp = client.post("/api/maintenance/events", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["machine_id"] == "MCH-PLANT-001-001"
    assert "maintenance_id" in data


def test_evaluation_benchmark_endpoint():
    resp = client.get("/api/analytics/evaluation")
    assert resp.status_code == 200
    data = resp.json()
    assert data["overall_status"] == "PASS"
    assert data["benchmark_summary"]["overall_f1_score"] >= 0.90


if __name__ == "__main__":
    test_healthcheck()
    test_energy_summary_endpoint()
    test_anomalies_and_acknowledgement()
    test_recommendations_and_approval()
    test_maintenance_event_creation()
    test_evaluation_benchmark_endpoint()
    print("All API endpoint tests passed successfully.")

