# EnergyIQ – AI-Powered Industrial Energy Intelligence Platform

**EnergyIQ** is an end-to-end industrial energy intelligence and decision-support platform designed for manufacturing plants, smart factories, and industrial IoT environments.

For complete documentation, see [energy_analytics/README.md](energy_analytics/README.md).

## Quickstart

```bash
# 1. Install dependencies
pip install -r energy_analytics/requirements.txt

# 2. Run the EnergyIQ platform
python run_server.py
```

Then open your browser to:
- **Interactive Industrial Dashboard:** [http://localhost:8000/](http://localhost:8000/)
- **Interactive REST API (Swagger UI):** [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Healthcheck:** [http://localhost:8000/api/health](http://localhost:8000/api/health)

## Automated Tests & Evaluation Suite

```bash
# Run acceptance benchmark evaluation suite
python energy_analytics/tests/test_evaluation_benchmark.py

# Run API & data quality test suite
python energy_analytics/tests/test_api.py
python energy_analytics/tests/test_data_quality.py
python energy_analytics/tests/test_energy_engine.py

# Verify deterministic reproducibility (Seed: 20261022)
python energy_analytics/repro_check.py
```

