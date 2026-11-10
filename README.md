# EnergyIQ – AI-Powered Industrial Energy Intelligence Platform

**EnergyIQ** is an end-to-end industrial energy intelligence and decision-support platform designed for manufacturing plants, smart factories, and industrial IoT environments. It ingests machine-level telemetry, correlates power demand with production schedules and time-of-use tariffs, detects complex energy anomalies, resolves meter data quality exceptions, and provides actionable, verified energy-saving recommendations.

---

## 1. System Architecture

```
                                  +---------------------------------------+
                                  |   Web Dashboard (HTML5/CSS3/Chart.js) |
                                  |   - Executive Overview & KPIs         |
                                  |   - 90-Day Diurnal & Trend Analytics  |
                                  |   - Anomaly Alert Management & ACK    |
                                  |   - Machine Energy Intensity (kWh/u)  |
                                  |   - Actionable AI Recommendations     |
                                  |   - Data Quality Exception Hub        |
                                  |   - Automated Acceptance Suite        |
                                  +---------------------------------------+
                                                     |
                                                     v (REST APIs / JSON)
+----------------------------------------------------------------------------------------------------+
|                                    FastAPI Backend Architecture                                    |
|                                                                                                    |
|  [REST API Layer]                                                                                  |
|  - /api/plants, /api/meters, /api/machines, /api/shifts, /api/tariffs, /api/weather                |
|  - /api/energy/summary, /api/energy/trends, /api/energy/readings                                   |
|  - /api/production/batches, /api/production/intensity                                             |
|  - /api/anomalies (ACK / Resolve), /api/recommendations (Approve / Reject)                        |
|  - /api/data-quality (5 Exception Scenarios), /api/analytics/evaluation, /api/audit-logs            |
|                                                                                                    |
|  [Analytics & AI Engine]                                                                           |
|  - Energy & Cost Engine: kWh = kW * h, TOU Tariffs, Peak Demand kW, Idle Waste                    |
|  - Anomaly Detector: Hybrid Deterministic Industrial Bounds + Isolation Forest ML                  |
|  - Recommendation Engine: Verified Baselines, Measurable $ Savings, LLM Explainer + Fallback      |
|  - Data Quality Detector: Automated inspection of Scenarios A, B, C, D, E                          |
|  - Benchmark Suite: Evaluation against isolated ground-truth dataset (Precision, Recall, F1)       |
|                                                                                                    |
|  [Storage Layer - SQLAlchemy ORM]                                                                 |
|  - SQLite (PostgreSQL compatible DDL) with indexed queries                                        |
+----------------------------------------------------------------------------------------------------+
                                                     |
                                                     v
+----------------------------------------------------------------------------------------------------+
|                         Industrial Relational Schema & Synthetic Data                              |
|  Plant (1) ---> Meter (20) ---> Machine (28) ---> ProductionBatch (2,000)                          |
|  Shift (3) ---> ProductionBatch | Tariff (4) ---> EnergyReading (172,800 @ 15-min)                 |
|  WeatherObservation (2,160) | MaintenanceEvent (14) | Recommendation (13) | AuditLog (Dynamic)     |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Core Entities & Relational Schema

| Entity | PK | Relationships | Description |
|---|---|---|---|
| **Plant** | `plant_id` | 1:N Meter, Machine, Shift, Tariff | Manufacturing facility master data with local timezone (`America/Chicago`). |
| **Meter** | `meter_id` | 1:N Machine, 1:N EnergyReading | Main, feeder, and sub-meters monitoring 15-minute power demand. |
| **Machine** | `machine_id` | N:1 Meter, 1:N Batch, 1:N Maint | Industrial assets (Press, CNC, Oven, Conveyor, Compressor, Mixer) with nameplate kW and idle baseline. |
| **Shift** | `shift_id` | 1:N ProductionBatch | Daily work shifts (Day: 06:00-14:00, Evening: 14:00-22:00, Night: 22:00-06:00). |
| **Tariff** | `tariff_id` | Effective time match | Time-of-use rate windows (Peak: \$0.22/kWh, Shoulder: \$0.14/kWh, Off-Peak: \$0.08/kWh). |
| **WeatherObservation** | `weather_id` | Hourly observation | Ambient temperature (°C), humidity (%), and weather conditions. |
| **ProductionBatch** | `batch_id` | N:1 Machine, N:1 Shift | Production runs with planned/actual timestamps, output units, and scrap units. |
| **EnergyReading** | `reading_id` | N:1 Meter, N:1 Machine | 15-minute interval energy readings (172,800 intervals) with `kw_avg`, `kwh`, and quality flags. |
| **MaintenanceEvent** | `maintenance_id` | N:1 Machine | Preventive, corrective, and inspection work orders with downtime impacts. |
| **Recommendation** | `recommendation_id` | N:1 Machine/Meter | Energy-saving actions citing baseline kWh, expected savings ($ and kWh), confidence, and approval status. |
| **MeterDailyTotal** | Composite (`meter_id`, `day`) | N:1 Meter | Reconciliation table tracking reported daily total vs sum of 15-min intervals. |
| **AnomalyRecord** | `anomaly_id` | N:1 Machine/Meter | Persisted anomalies with severity, score, evidence, and operator status. |
| **AuditLog** | `log_id` | Immutable ledger | Traceability event history capturing all approvals, acknowledgements, and system runs. |

---

## 3. The 5 Core Industrial Exception Scenarios

EnergyIQ automatically detects, isolates, and recommends corrective actions for 5 critical industrial data exceptions without corrupting historical records:

1. **Scenario A: Meter Reconciliation Discrepancy**
   - *Problem:* Submeter daily reported telemetry deviates from the integral sum of its 15-minute interval readings (up to 25% inflation).
   - *Detection:* Automated cross-tabulation comparing `reported_total_kwh` against $\sum \text{kWh}_{\text{interval}}$.
   - *Decision:* Automatically bills against validated interval sums and flags the physical meter buffer for calibration.

2. **Scenario B: kW and kWh Physical Unit Inconsistency**
   - *Problem:* SCADA registers mistakenly output average power ($\text{kW}$) directly into energy ($\text{kWh}$) columns without multiplying by time interval duration ($\Delta t = 0.25\text{h}$), resulting in a 400% error.
   - *Detection:* Validation check identifying records where $\text{kWh} \approx \text{kW}_{\text{avg}}$ rather than $\text{kW}_{\text{avg}} \times 0.25$.
   - *Decision:* Quarantine raw value and recompute valid energy to prevent financial overbilling.

3. **Scenario C: Tariff Timezone Misalignment**
   - *Problem:* SCADA or utility rate schedules ingested in UTC rather than plant local operational time (`America/Chicago`), shifting peak window pricing by 6 hours.
   - *Detection:* Timestamp offset comparison between Plant master timezone and Tariff effective timezone.
   - *Decision:* Normalize timestamps to plant local standard time prior to billing calculation.

4. **Scenario D: Duplicate Reading Ingestion**
   - *Problem:* Retransmission in telemetry buffers generating duplicate `(meter_id, interval_start_ts)` records.
   - *Detection:* Unique composite key indexing and duplicate flag evaluation.
   - *Decision:* Isolate duplicate copies in historical audit log while excluding them from billing aggregation.

5. **Scenario E: Machine-Meter Hierarchy Mismatch**
   - *Problem:* SCADA readings attributing power draw to a machine that is not physically wired under the assigned sub-meter.
   - *Detection:* Cross-reference between `EnergyReading.meter_id` and master `Machine.meter_id`.
   - *Decision:* Quarantine attribution to prevent distortion of machine energy intensity (kWh/unit).

---

## 4. Rigorous Energy Calculation Engine

All displayed KPIs are computed directly from the underlying relational database:

1. **Interval Energy:**
   $$\text{Energy (kWh)} = \text{Average Power (kW)} \times \left(\frac{\text{Interval Minutes}}{60}\right)$$

2. **Machine Energy Intensity:**
   $$\text{Energy Intensity} = \frac{\sum \text{kWh}_{\text{productive}}}{\text{Total Finished Units}}$$

3. **Time-of-Use Electricity Cost:**
   $$\text{Cost (\$) } = \sum \left( \text{kWh}_i \times \text{Tariff Rate}_i \right)$$

4. **Idle Energy Waste:**
   $$\text{Idle Waste (kWh)} = \sum_{i \in \text{Idle}} \max(0, \text{kW}_{i} - \text{Baseline kW}_{\text{machine}}) \times 0.25\text{h}$$

5. **Expected Financial Savings:**
   $$\text{Expected Savings (\$) } = \text{Expected kWh Reduction} \times \text{Applicable Tariff Rate}$$

---

## 5. Automated Benchmark & Evaluation Results

The automated acceptance test suite benchmarks EnergyIQ against an isolated ground-truth dataset (`output/ground_truth.json`) with zero leakage into model feature inputs:

```
======================================================================
   EnergyIQ Acceptance & Benchmark Evaluation Report
======================================================================
Overall Status:    PASS
Overall Precision: 100.00%
Overall Recall:    94.51%
Overall F1-Score:  97.18%  (Acceptance Criterion >= 90.0%)
----------------------------------------------------------------------
Scenario Performance:
 - Meter Reconciliation Discrepancy (A) : F1 = 100.0% (TP=15, FP=0, FN=0)
 - kW vs kWh Unit Inconsistency     (B) : F1 =  90.9% (TP=25, FP=0, FN=5)
 - Tariff Timezone Misalignment     (C) : F1 = 100.0% (TP=1,  FP=0, FN=0)
 - Duplicate Reading Ingestion      (D) : F1 = 100.0% (TP=20, FP=0, FN=0)
 - Invalid Machine-Meter Hierarchy  (E) : F1 = 100.0% (TP=25, FP=0, FN=0)
----------------------------------------------------------------------
Relational & Mathematical Integrity:
 - All 10 Entities Primary Key Uniqueness : PASSED (100% Unique)
 - Foreign Key Relational Integrity       : PASSED (Zero orphaned records)
 - Savings Calculation Math Bounds        : PASSED (All implied rates valid)
======================================================================
```

---

## 6. User Roles & Persona Workflows

EnergyIQ includes a dynamic persona switcher tailoring telemetry to four industrial roles:

1. **Plant Operator:**
   - Monitors real-time plant KPIs, hourly diurnal load curves, and active alarms.
   - One-click acknowledgement of threshold alerts and peak demand warnings.
2. **Maintenance / Quality Engineer:**
   - Investigates machine baseline deviations and excessive standby power.
   - Logs maintenance work orders (preventive, corrective, inspection) with downtime tracking.
3. **Production Planner:**
   - Analyzes machine energy intensity ($\text{kWh}/\text{unit}$) and scrap rates.
   - Schedules high-power production batches into shoulder and off-peak tariff periods.
4. **OT / IT Administrator:**
   - Inspects meter reconciliation discrepancies and SCADA communication faults.
   - Triggers synthetic data generation cycles, executes model evaluations, and exports tables.

---

## 7. Quickstart Guide

### Prerequisites
- Python 3.10+
- Modern Web Browser (Chrome, Edge, Firefox, Safari)

### Installation
```bash
# Clone repository and enter project directory
cd energy_analytics

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Start the EnergyIQ server
python run_server.py
```

Open your browser to:
- **Interactive Dashboard:** [http://localhost:8000/](http://localhost:8000/)
- **Interactive Swagger REST API:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Health Check:** [http://localhost:8000/api/health](http://localhost:8000/api/health)

### Running Automated Test Suite
```bash
# Run unit & API tests
python tests/test_energy_engine.py
python tests/test_data_quality.py
python tests/test_api.py

# Run benchmark evaluation suite
python tests/test_evaluation_benchmark.py

# Verify seed reproducibility (Seed: 20261022)
python repro_check.py
```

